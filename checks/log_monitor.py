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

from config.loader import (
    get_telegram_token,
    get_admin_chat_id,
    get_log_monitoring_config,
    get_log_paths,
    get_critical_patterns,
    is_log_monitoring_enabled,
    get_log_alert_cooldown,
    get_server_config
)
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

DEFAULT_LOG_LINES = 100
_alert_cache: Dict[str, datetime] = {}


class LogMonitor:
    """Монітор для логів серверів"""

    def __init__(self) -> None:
        """Ініціалізація монітора логів"""
        self.bot: Bot = Bot(token=get_telegram_token())
        self.admin_chat_id: int = get_admin_chat_id()
        
        self.log_monitoring_config = get_log_monitoring_config()
        self.enabled: bool = is_log_monitoring_enabled()
        self.log_paths: Dict[str, List[str]] = get_log_paths()
        self.critical_patterns: List[str] = get_critical_patterns()
        self.alert_cooldown_seconds: int = get_log_alert_cooldown()
        
        self.pattern_templates: List[Tuple[re.Pattern, str]] = []
        for pattern in self.critical_patterns:
            try:
                template = f"Знайдено критичний паттерн: {pattern}"
                self.pattern_templates.append((re.compile(pattern), template))
            except re.error as e:
                logger.error(f"Помилка компіляції regex '{pattern}': {e}")

    async def check_all_logs(self) -> None:
        """
        Перевірити всі логи на критичні помилки.
        """
        if not self.enabled:
            logger.info("📝 Моніторинг логів вимкнено в конфігурації")
            return

        if not self.log_paths:
            logger.info("📭 Немає налаштованих шляхів до логів")
            return

        logger.info(f"📝 Запуск перевірки логів для {len(self.log_paths)} серверів...")

        for server_id, paths in self.log_paths.items():
            for log_path in paths:
                try:
                    await self._check_log_source(server_id, log_path)
                except Exception as error:
                    logger.error(f"Помилка перевірки {server_id}:{log_path}: {error}")

    async def _check_log_source(self, server_id: str, log_path: str) -> None:
        """
        Перевірити конкретне джерело логів.
        """
        server_config = get_server_config(server_id)
        server_name = server_config.get('name', server_id) if server_config else server_id

        ssh = SSHClient(server_id)
        command: str = f"tail -n {DEFAULT_LOG_LINES} {log_path} 2>/dev/null || echo 'LOG_NOT_FOUND'"

        try:
            result: str = ssh.execute_command(command)

            if "LOG_NOT_FOUND" in result:
                logger.warning(f"Лог {log_path} на {server_id} не знайдено")
                return

            log_lines: List[str] = result.strip().split('\n')
            now: datetime = datetime.now()

            for line_num, line in enumerate(log_lines, 1):
                await self._check_line_for_errors(
                    line, server_id, server_name, log_path, line_num, now
                )

        except Exception as error:
            logger.error(f"SSH помилка на {server_id}: {error}")

    async def _check_line_for_errors(
        self,
        line: str,
        server_id: str,
        server_name: str,
        log_path: str,
        line_num: int,
        now: datetime
    ) -> None:
        """
        Перевірити рядок логу на наявність помилок.
        """
        for pattern, template in self.pattern_templates:
            match = pattern.search(line)
            if not match:
                continue

            cache_key: str = f"{server_id}:{log_path}:{pattern.pattern}"

            if cache_key in _alert_cache:
                last_alert: datetime = _alert_cache[cache_key]
                cooldown = timedelta(seconds=self.alert_cooldown_seconds)
                if now - last_alert < cooldown:
                    return

            error_text = match.group(0) if match.groups() else pattern.pattern
            
            line_preview = line.strip()
            if len(line_preview) > 200:
                line_preview = line_preview[:200] + "..."

            await self._send_alert(
                f"🚨 *Критична помилка в логах!*\n"
                f"Сервер: {server_name} (`{server_id}`)\n"
                f"Файл: `{log_path}`\n"
                f"Рядок {line_num}\n"
                f"Паттерн: `{pattern.pattern}`\n"
                f"Знайдено: `{error_text}`\n"
                f"\n```\n{line_preview}\n```"
            )

            _alert_cache[cache_key] = now
            break

    async def _send_alert(self, message: str) -> None:
        """
        Відправити алерт в Telegram.
        """
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Алерт логів відправлено: {message[:50]}...")
        except Exception as error:
            logger.error(f"Помилка відправки алерту логів: {error}")


async def check_logs() -> None:
    """Запустити перевірку логів (асинхронна версія)"""
    monitor = LogMonitor()
    await monitor.check_all_logs()


def run_log_check() -> None:
    """Запустити перевірку логів (синхронна версія для ручного запуску)"""
    asyncio.run(check_logs())


if __name__ == "__main__":
    asyncio.run(check_logs())
