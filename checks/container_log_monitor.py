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

from config.loader import (
    get_telegram_token,
    get_admin_chat_id,
    get_container_log_monitoring_config,
    get_container_patterns,
    get_all_containers_with_servers,
    get_server_config,
    load_config
)
from utils.ssh import SSHClient
from bot.language import get_text

logger = logging.getLogger(__name__)

# Константы из конфига
config = get_container_log_monitoring_config()
ALERT_COOLDOWN_MINUTES = config.get('alert_cooldown', 1800) / 60
DEFAULT_LOG_LINES = config.get('default_log_lines', 200)

# ID админа для языка
ADMIN_USER_ID = get_admin_chat_id()

# Кэш для алертов
_alert_cache: Dict[str, datetime] = {}
_alert_cooldown: timedelta = timedelta(minutes=ALERT_COOLDOWN_MINUTES)


class ContainerLogMonitor:
    """Мониторинг логов Docker контейнеров"""

    def __init__(self) -> None:
        self.bot = Bot(token=get_telegram_token())
        self.patterns = get_container_patterns()
        self.full_config = load_config()
        self.instant_alerts_enabled = self.full_config.get('instant_alerts', {}).get('enabled', True)

    async def check_all_containers_logs(self) -> None:
        """Проверить логи всех контейнеров"""
        logger.info("🔍 Запуск проверки логов контейнеров...")

        containers = get_all_containers_with_servers()
        
        for container in containers:
            try:
                await self._check_container_logs(
                    container['server_id'],
                    container['container_name'],
                    container.get('log_type')
                )
            except Exception as e:
                logger.error(f"Ошибка проверки {container['container_name']} на {container['server_id']}: {e}")

    async def _check_container_logs(self, server_id: str, container_name: str, log_type: Optional[str]) -> None:
        """
        Проверить логи конкретного контейнера

        Args:
            server_id: ID сервера
            container_name: Имя контейнера
            log_type: Тип контейнера (django_app, postgres, etc)
        """
        if not log_type:
            logger.warning(f"Нет log_type для контейнера {container_name} на {server_id}")
            return

        # Получаем конфиг для контейнера
        container_config = self.patterns.get(log_type)
        if not container_config:
            logger.warning(f"Нет конфигурации для типа {log_type} (контейнер {container_name})")
            return

        ssh = SSHClient(server_id)

        # Команда для получения логов контейнера
        cmd = f"docker logs --tail {DEFAULT_LOG_LINES} {container_name} 2>&1"

        try:
            # Асинхронный вызов SSH команды
            result = await asyncio.to_thread(ssh.execute_command, cmd)

            if not result or "Error: No such container" in result:
                logger.error(f"Контейнер {container_name} не найден на {server_id}")
                return

            log_lines = result.strip().split('\n')
            now = datetime.now()

            for line in log_lines:
                await self._check_line(
                    server_id,
                    container_name,
                    container_config,
                    line,
                    now
                )

        except Exception as e:
            logger.error(f"SSH ошибка при получении логов {container_name}: {e}")

    async def _check_line(
        self,
        server_id: str,
        container_name: str,
        container_config: Dict,
        line: str,
        now: datetime
    ) -> None:
        """Проверить строку лога на наличие ошибок"""

        patterns = container_config.get('patterns', [])
        
        for pattern, template in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if not match:
                continue

            # Уникальный ключ для кэша
            error_key = f"{server_id}:{container_name}:{pattern}"

            # Проверяем, не было ли такого алерта недавно
            if error_key in _alert_cache:
                last_alert = _alert_cache[error_key]
                if now - last_alert < _alert_cooldown:
                    continue

            # Получаем словарь иконок
            icons_dict = get_text(ADMIN_USER_ID, 'container_logs', 'icons')
            icon_key = self._get_icon_key(pattern)
            icon = icons_dict.get(icon_key, '⚠')

            # Формируем сообщение
            error_text = match.group(0) if match.groups() else pattern
            message = template.format(error_text)

            # Обрезаем длинные строки
            short_line = line[:200] + "..." if len(line) > 200 else line

            # Получаем название сервера для красоты
            server_config = get_server_config(server_id)
            server_name = server_config.get('name', server_id) if server_config else server_id
            container_type_name = container_config.get('name', 'Unknown')

            # Получаем словарь сообщений
            messages_dict = get_text(ADMIN_USER_ID, 'container_logs', 'messages')

            alert_text = (
                f"{messages_dict['error_found']}\n"
                f"{messages_dict['container']}: `{container_name}`\n"
                f"{messages_dict['server']}: {server_name}\n"
                f"{messages_dict['type']}: {container_type_name}\n"
                f"{messages_dict['error']}: {icon} {message}\n"
                f"```\n{short_line}\n```"
            )

            # Отправляем алерт только если мгновенные алерты включены
            if self.instant_alerts_enabled:
                await self._send_alert(alert_text)
            else:
                logger.info(f"⚠ Найдена ошибка в {container_name}: {message} (мгновенные алерты отключены)")

            _alert_cache[error_key] = now
            break

    def _get_icon_key(self, pattern: str) -> str:
        """
        Определяет ключ для иконки на основе паттерна

        Args:
            pattern: Regex паттерн

        Returns:
            Ключ для получения иконки из language файла
        """
        pattern_map = {
            r'OperationalError': 'OperationalError',
            r'DatabaseError': 'DatabaseError',
            r'Internal Server Error': 'InternalServerError',
            r'does not exist': 'does_not_exist',
            r'CRITICAL': 'CRITICAL',
            r'ERROR': 'ERROR',
            r'Exception': 'Exception',
            r'Traceback': 'Traceback',
            r'No module named': 'NoModule',
            r'Connection refused': 'ConnectionRefused',
            r'Timeout': 'Timeout',
            r'FATAL': 'FATAL',
            r'PANIC': 'PANIC',
            r'could not connect': 'could_not_connect',
            r'connection refused': 'connection_refused',
            r'no pg_hba.conf entry': 'no_pg_hba',
            r'database .* does not exist': 'database_not_exists',
            r'\[emerg\]': 'emerg',
            r'\[alert\]': 'alert',
            r'\[crit\]': 'crit',
            r'\[error\]': 'error',
            r'connect\(\) failed': 'connect_failed',
            r'open\(\) .* failed': 'open_failed',
            r'no live upstreams': 'no_live_upstreams',
            r'Lost connection': 'LostConnection',
        }
        
        for p, key in pattern_map.items():
            if re.search(p, pattern, re.IGNORECASE):
                return key
        
        return 'ERROR'

    async def _send_alert(self, message: str) -> None:
        """Отправить алерт"""
        try:
            await self.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info("✅ Алерт об ошибке в контейнере отправлен")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки алерта: {e}")


async def check_container_logs():
    """Запустить проверку логов контейнеров"""
    monitor = ContainerLogMonitor()
    await monitor.check_all_containers_logs()


def run_container_logs_check():
    """Синхронный запуск для тестирования"""
    asyncio.run(check_container_logs())


if __name__ == "__main__":
    asyncio.run(check_container_logs())
