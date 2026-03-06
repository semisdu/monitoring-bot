#!/usr/bin/env python3
"""
Мониторинг логов Docker контейнеров ИЗНУТРИ
Проверяет логи каждого контейнера на наличие ошибок
"""

import logging
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from telegram import Bot

from config.settings import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

# Константы
ALERT_COOLDOWN_MINUTES = 30
DEFAULT_LOG_LINES = 200  # Больше строк, так как ищем глубже

# Кэш для алертов
_alert_cache: Dict[str, datetime] = {}
_alert_cooldown: timedelta = timedelta(minutes=ALERT_COOLDOWN_MINUTES)

# Конфигурация контейнеров и их паттернов ошибок
CONTAINER_PATTERNS = {
    # Django приложения
    "course_app": {
        "name": "Django App (курсы)",
        "patterns": [
            (r'OperationalError', "🚨 Помилка БД: {0}"),
            (r'DatabaseError', "🚨 Помилка БД: {0}"),
            (r'Internal Server Error', "🔥 500 помилка: {0}"),
            (r'does not exist', "❌ Таблиця не існує: {0}"),
            (r'CRITICAL', "🔥 Критична помилка: {0}"),
            (r'ERROR', "⚠ Помилка: {0}"),
            (r'Exception', "⚠ Виняток: {0}"),
            (r'Traceback', "📋 Traceback знайдено"),
            (r'No module named', "📦 Модуль не знайдено: {0}"),
            (r'Connection refused', "🔌 Підключення відхилено"),
            (r'Timeout', "⏰ Таймаут: {0}"),
        ],
        "critical": True
    },
    "competitions": {
        "name": "Competitions App (конкурси)",
        "patterns": [
            (r'OperationalError', "🚨 Помилка БД: {0}"),
            (r'DatabaseError', "🚨 Помилка БД: {0}"),
            (r'Internal Server Error', "🔥 500 помилка: {0}"),
            (r'ERROR', "⚠ Помилка: {0}"),
            (r'Exception', "⚠ Виняток: {0}"),
            (r'CRITICAL', "🔥 Критична помилка: {0}"),
            (r'Traceback', "📋 Traceback знайдено"),
        ],
        "critical": True
    },
    
    # Базы данных
    "course_postgres": {
        "name": "PostgreSQL (курси)",
        "patterns": [
            (r'FATAL', "🔥 Фатальна помилка: {0}"),
            (r'PANIC', "💥 Паніка БД: {0}"),
            (r'ERROR', "⚠ Помилка БД: {0}"),
            (r'could not connect', "🔌 Не вдається підключитись: {0}"),
            (r'connection refused', "🔌 Підключення відхилено"),
            (r'no pg_hba.conf entry', "🔒 Помилка автентифікації"),
            (r'database .* does not exist', "❌ БД не існує"),
        ],
        "critical": True
    },
    
    # Nginx
    "profcompetitions-nginx": {
        "name": "Nginx (конкурси)",
        "patterns": [
            (r'\[emerg\]', "🔥 Критична помилка: {0}"),
            (r'\[alert\]', "⚠ Тривога: {0}"),
            (r'\[crit\]', "⚠ Критично: {0}"),
            (r'\[error\]', "⚠ Помилка: {0}"),
            (r'connect\(\) failed', "🔌 Помилка підключення до бекенду"),
            (r'open\(\) .* failed', "📁 Помилка відкриття файлу: {0}"),
            (r'no live upstreams', "🌐 Немає живих upstream серверів"),
        ],
        "critical": True
    }
}

# Мапінг серверів до контейнерів
SERVER_CONTAINERS = {
    "vm301-courses": ["course_app", "course_postgres"],
    "vm300-competitions": ["profcompetitions-nginx", "competitions"]
}


class ContainerLogMonitor:
    """Моніторинг логів Docker контейнерів"""
    
    def __init__(self) -> None:
        self.bot = Bot(token=TELEGRAM_TOKEN)
    
    async def check_all_containers_logs(self) -> None:
        """Перевірити логи всіх контейнерів"""
        logger.info("🔍 Запуск перевірки логів контейнерів...")
        
        for server_id, containers in SERVER_CONTAINERS.items():
            for container_name in containers:
                try:
                    await self._check_container_logs(server_id, container_name)
                except Exception as e:
                    logger.error(f"Помилка перевірки {container_name} на {server_id}: {e}")
    
    async def _check_container_logs(self, server_id: str, container_name: str) -> None:
        """
        Перевірити логи конкретного контейнера
        
        Args:
            server_id: ID сервера (vm301-courses, vm300-competitions)
            container_name: Ім'я контейнера
        """
        # Отримуємо конфіг для контейнера
        container_config = CONTAINER_PATTERNS.get(container_name)
        if not container_config:
            logger.warning(f"Немає конфігурації для контейнера {container_name}")
            return
        
        ssh = SSHClient(server_id)
        
        # Команда для отримання логів контейнера
        # 2>&1 перенаправляє stderr в stdout, щоб бачити всі помилки
        cmd = f"docker logs --tail {DEFAULT_LOG_LINES} {container_name} 2>&1"
        
        try:
            result = ssh.execute_command(cmd)
            
            if not result or "Error: No such container" in result:
                logger.error(f"Контейнер {container_name} не знайдено на {server_id}")
                return
            
            log_lines = result.strip().split('\n')
            now = datetime.now()
            
            for line in log_lines:
                await self._check_line(server_id, container_name, container_config, line, now)
                
        except Exception as e:
            logger.error(f"SSH помилка при отриманні логів {container_name}: {e}")
    
    async def _check_line(
        self,
        server_id: str,
        container_name: str,
        container_config: Dict,
        line: str,
        now: datetime
    ) -> None:
        """Перевірити рядок логу на наявність помилок"""
        
        for pattern, template in container_config["patterns"]:
            match = re.search(pattern, line, re.IGNORECASE)
            if not match:
                continue
            
            # Унікальний ключ для кешу (сервер+контейнер+помилка)
            error_key = f"{server_id}:{container_name}:{pattern}"
            
            # Перевіряємо чи не було такого алерту нещодавно
            if error_key in _alert_cache:
                last_alert = _alert_cache[error_key]
                if now - last_alert < _alert_cooldown:
                    continue
            
            # Формуємо повідомлення
            error_text = match.group(0) if match.groups() else pattern
            message = template.format(error_text)
            
            # Обрізаємо довгі рядки
            short_line = line[:200] + "..." if len(line) > 200 else line
            
            alert_text = (
                f"🚨 *Помилка в контейнері!*\n"
                f"📦 Контейнер: `{container_name}`\n"
                f"🖥 Сервер: {server_id}\n"
                f"📝 Тип: {container_config['name']}\n"
                f"⚠ Помилка: {message}\n"
                f"```\n{short_line}\n```"
            )
            
            await self._send_alert(alert_text)
            _alert_cache[error_key] = now
            logger.info(f"⚠ Знайдено помилку в {container_name}: {message}")
            break  # Тільки один алерт на рядок
    
    async def _send_alert(self, message: str) -> None:
        """Відправити алерт"""
        try:
            await self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info("✅ Алерт про помилку в контейнері відправлено")
        except Exception as e:
            logger.error(f"❌ Помилка відправки алерту: {e}")


# Функція для запуску
async def check_container_logs():
    """Запустити перевірку логів контейнерів"""
    monitor = ContainerLogMonitor()
    await monitor.check_all_containers_logs()


def run_container_logs_check():
    """Синхронний запуск для тестування"""
    asyncio.run(check_container_logs())


if __name__ == "__main__":
    # Тестовий запуск
    asyncio.run(check_container_logs())
