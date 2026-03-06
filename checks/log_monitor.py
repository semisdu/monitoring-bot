#!/usr/bin/env python3
"""
Мониторинг логов серверов
Отправляет алерты при критических ошибках
"""

import logging
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from telegram import Bot

from config.settings import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

# Константы
ALERT_COOLDOWN_MINUTES = 30
DEFAULT_LOG_LINES = 100

# Конфигурация источников логов
LOG_SOURCES_CONFIG: List[Dict[str, Any]] = [
    # Server102 - NGINX
    {
        "server": "server102",
        "path": "/var/log/nginx/access.log",
        "name": "NGINX Access",
        "patterns": [
            (r'" (5\d{2}) ', "HTTP 5xx помилка: {0}"),
        ],
        "lines": DEFAULT_LOG_LINES
    },
    {
        "server": "server102",
        "path": "/var/log/nginx/error.log",
        "name": "NGINX Error",
        "patterns": [
            (r'\[emerg\]', "NGINX критична помилка: {0}"),
            (r'\[alert\]', "NGINX тривога: {0}"),
            (r'\[crit\]', "NGINX критична: {0}"),
        ],
        "lines": DEFAULT_LOG_LINES
    },
    # Serv301 - Django
    {
        "server": "serv301",
        "path": "/home/semis/app/logs/django.log",
        "name": "Django (serv301)",
        "patterns": [
            (r'CRITICAL', "Django CRITICAL: {0}"),
            (r'ERROR', "Django ERROR: {0}"),
            (r'Exception', "Django Exception: {0}"),
            (r'Traceback', "Django Traceback: {0}"),
        ],
        "lines": DEFAULT_LOG_LINES
    },
    {
        "server": "serv301",
        "path": "/home/semis/app/logs/celery.log",
        "name": "Celery (serv301)",
        "patterns": [
            (r'ERROR', "Celery ERROR: {0}"),
            (r'CRITICAL', "Celery CRITICAL: {0}"),
            (r'Exception', "Celery Exception: {0}"),
        ],
        "lines": DEFAULT_LOG_LINES
    },
    # Serv300 - Django
    {
        "server": "serv300",
        "path": "/home/semis/app/logs/django.log",
        "name": "Django (serv300)",
        "patterns": [
            (r'CRITICAL', "Django CRITICAL: {0}"),
            (r'ERROR', "Django ERROR: {0}"),
            (r'Exception', "Django Exception: {0}"),
            (r'Traceback', "Django Traceback: {0}"),
        ],
        "lines": DEFAULT_LOG_LINES
    },
    {
        "server": "serv300",
        "path": "/home/semis/app/logs/celery.log",
        "name": "Celery (serv300)",
        "patterns": [
            (r'ERROR', "Celery ERROR: {0}"),
            (r'CRITICAL', "Celery CRITICAL: {0}"),
            (r'Exception', "Celery Exception: {0}"),
        ],
        "lines": DEFAULT_LOG_LINES
    }
]

# Кэш для отслеживания уже отправленных алертов
_alert_cache: Dict[str, datetime] = {}
_alert_cooldown: timedelta = timedelta(minutes=ALERT_COOLDOWN_MINUTES)


class LogMonitor:
    """Монітор для логів серверів"""
    
    def __init__(self) -> None:
        """Ініціалізація монітора логів"""
        self.bot: Bot = Bot(token=TELEGRAM_TOKEN)
        self.log_sources: List[Dict[str, Any]] = LOG_SOURCES_CONFIG
        
    async def check_all_logs(self) -> None:
        """
        Перевірити всі логи на критичні помилки.
        
        Проходить по всіх джерелах логів,
        перевіряє кожен на наявність помилок.
        """
        logger.info("📝 Запуск перевірки логів...")
        
        for source in self.log_sources:
            try:
                await self._check_log_source(source)
            except Exception as error:
                logger.error(f"Помилка перевірки {source['name']}: {error}")
    
    async def _check_log_source(self, source: Dict[str, Any]) -> None:
        """
        Перевірити конкретне джерело логів.
        
        Args:
            source: Конфігурація джерела логів
        """
        global _alert_cache
        
        server_id: str = source["server"]
        log_path: str = source["path"]
        source_name: str = source["name"]
        patterns: List[Tuple[str, str]] = source["patterns"]
        lines: int = source.get("lines", DEFAULT_LOG_LINES)
        
        # Отримуємо останні рядки логу через SSH
        ssh = SSHClient(server_id)
        command: str = f"tail -n {lines} {log_path} 2>/dev/null || echo 'LOG_NOT_FOUND'"
        
        try:
            result: str = ssh.execute_command(command)
            
            if "LOG_NOT_FOUND" in result:
                logger.warning(f"Лог {log_path} на {server_id} не знайдено")
                return
            
            log_lines: List[str] = result.strip().split('\n')
            now: datetime = datetime.now()
            
            for line in log_lines:
                await self._check_line_for_errors(
                    line, server_id, source_name, log_path, patterns, now
                )
                
        except Exception as error:
            logger.error(f"SSH помилка на {server_id}: {error}")
    
    async def _check_line_for_errors(
        self,
        line: str,
        server_id: str,
        source_name: str,
        log_path: str,
        patterns: List[Tuple[str, str]],
        now: datetime
    ) -> None:
        """
        Перевірити рядок логу на наявність помилок.
        
        Args:
            line: Рядок логу
            server_id: ID сервера
            source_name: Назва джерела
            log_path: Шлях до логу
            patterns: Список патернів для пошуку
            now: Поточний час
        """
        global _alert_cache
        
        for pattern, template in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            
            # Знайшли помилку
            cache_key: str = f"{server_id}:{log_path}:{match.group(0)}"
            
            # Перевіряємо кулдаун
            if cache_key in _alert_cache:
                last_alert: datetime = _alert_cache[cache_key]
                if now - last_alert < _alert_cooldown:
                    return
            
            # Відправляємо алерт
            error_text: str = match.group(0) if match.groups() else pattern
            message: str = template.format(error_text)
            
            await self._send_alert(
                f"🚨 *Помилка в логах!*\n"
                f"Сервер: {server_id.upper()}\n"
                f"Джерело: {source_name}\n"
                f"Файл: `{log_path}`\n"
                f"Помилка: {message}\n"
                f"Рядок: `{line.strip()}`"
            )
            
            _alert_cache[cache_key] = now
            break  # Одна помилка на рядок
    
    async def _send_alert(self, message: str) -> None:
        """
        Відправити алерт в Telegram.
        
        Args:
            message: Текст повідомлення
        """
        try:
            await self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Алерт відправлено: {message[:50]}...")
        except Exception as error:
            logger.error(f"❌ Помилка відправки алерту: {error}")


# Функції для зовнішнього використання
async def check_logs() -> None:
    """Запустити перевірку логів (асинхронна версія)"""
    monitor = LogMonitor()
    await monitor.check_all_logs()


def run_log_check() -> None:
    """Запустити перевірку логів (синхронна версія для ручного запуску)"""
    asyncio.run(check_logs())


if __name__ == "__main__":
    # Для тестування
    asyncio.run(check_logs())
