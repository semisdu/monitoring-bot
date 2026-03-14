#!/usr/bin/env python3
"""
Мониторинг Proxmox Backup Server (PBS)
Проверка статуса бэкапов, возраста, места
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from telegram import Bot

from config.loader import (
    get_telegram_token,
    get_admin_chat_id,
    get_backup_jobs,
    get_server_config,
    get_alert_config
)
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 7
DATASTORE_PATH = "/mnt/datastore/local"

_alert_cache: Dict[str, datetime] = {}


class PBSMonitor:
    """Мониторинг Proxmox Backup Server"""

    def __init__(self) -> None:
        """Инициализация монитора PBS"""
        self.bot: Bot = Bot(token=get_telegram_token())
        self.admin_chat_id: int = get_admin_chat_id()
        
        self.backup_jobs: List[Dict[str, Any]] = get_backup_jobs()
        
        alert_config = get_alert_config()
        self.disk_warning_threshold: int = alert_config.get('disk_warning_percent', 80)
        self.disk_critical_threshold: int = alert_config.get('disk_critical_percent', 90)
        self.alert_cooldown_minutes: int = 30
        
        self.pbs_servers = [s for s in get_server_config('pbs-backup')] if get_server_config('pbs-backup') else []
        self.pbs_host: str = "pbs-backup"

    async def check_all_backups(self) -> None:
        """
        Проверить все бэкапы.
        """
        if not self.backup_jobs:
            logger.info("📭 Немає налаштованих завдань бэкапів")
            return

        logger.info(f"💾 Перевірка статусу бэкапів... Знайдено {len(self.backup_jobs)} завдань")

        for job in self.backup_jobs:
            try:
                await self._check_backup_age(job)
            except Exception as error:
                logger.error(f"Помилка перевірки бэкапа {job.get('id')}: {error}")

        await self._check_disk_space()

    async def _check_backup_age(self, job: Dict[str, Any]) -> None:
        """
        Проверить возраст последнего бэкапа.
        """
        vms: List[int] = job.get("vms", [])
        retention_days: int = job.get("retention_days", DEFAULT_RETENTION_DAYS)
        server_id: str = job.get("server_id", self.pbs_host)

        ssh = SSHClient(server_id)

        for vmid in vms:
            await self._check_vm_backup_age(vmid, retention_days, ssh, job.get('id', 'unknown'))

    async def _check_vm_backup_age(self, vmid: int, retention_days: int, ssh: SSHClient, job_id: str) -> None:
        """
        Проверить возраст бэкапа для конкретной VM.
        """
        command: str = (
            f"pvesm list local --vmid {vmid} 2>/dev/null | "
            f"grep 'backup' | tail -1 | awk '{{print $6}}'"
        )

        try:
            result: str = ssh.execute_command(command).strip()

            if result:
                await self._process_backup_date(vmid, result, retention_days, job_id)
            else:
                await self._handle_no_backup(vmid, job_id)

        except Exception as error:
            logger.error(f"Помилка перевірки бэкапу VM {vmid}: {error}")

    async def _process_backup_date(self, vmid: int, date_str: str, retention_days: int, job_id: str) -> None:
        """
        Обработать дату последнего бэкапа.
        """
        try:
            backup_date: datetime = datetime.strptime(date_str, "%Y-%m-%d")
            now: datetime = datetime.now()
            days_old: int = (now - backup_date).days

            cache_key: str = f"backup_age_{job_id}_{vmid}"

            if days_old > retention_days:
                await self._send_alert(
                    f"🚨 *Помилка бэкапу!*\n"
                    f"Завдання: {job_id}\n"
                    f"VM ID: {vmid}\n"
                    f"Останній бэкап: {days_old} днів тому\n"
                    f"Максимум: {retention_days} днів"
                )
            elif days_old > retention_days - 2:
                await self._handle_soon_expiring(vmid, days_old, retention_days, cache_key, job_id)

        except ValueError as error:
            logger.error(f"Помилка парсингу дати {date_str} для VM {vmid}: {error}")

    async def _handle_soon_expiring(self, vmid: int, days_old: int, retention_days: int, cache_key: str, job_id: str) -> None:
        """
        Обработать случай, когда бэкап скоро истечёт.
        """
        now: datetime = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if cache_key not in _alert_cache or now - _alert_cache[cache_key] > cooldown:
            await self._send_alert(
                f"⚠️ *Увага: бэкап скоро застаріє*\n"
                f"Завдання: {job_id}\n"
                f"VM ID: {vmid}\n"
                f"Вік бэкапу: {days_old} днів\n"
                f"Залишилось: {retention_days - days_old} днів"
            )
            _alert_cache[cache_key] = now

    async def _handle_no_backup(self, vmid: int, job_id: str) -> None:
        """
        Обработать случай отсутствия бэкапов.
        """
        cache_key: str = f"no_backup_{job_id}_{vmid}"
        now: datetime = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if cache_key not in _alert_cache or now - _alert_cache[cache_key] > cooldown:
            await self._send_alert(
                f"🚨 *Немає бэкапів!*\n"
                f"Завдання: {job_id}\n"
                f"VM ID: {vmid}\n"
                f"Бэкапи не знайдено"
            )
            _alert_cache[cache_key] = now

    async def _check_disk_space(self) -> None:
        """Проверить свободное место на PBS."""
        ssh = SSHClient(self.pbs_host)

        command: str = f"df -h {DATASTORE_PATH} | tail -1 | awk '{{print $5}}' | sed 's/%//'"

        try:
            result: str = ssh.execute_command(command).strip()
            if not result:
                logger.warning(f"Не вдалося отримати інформацію про диск PBS")
                return
                
            usage: int = int(result)

            if usage > self.disk_critical_threshold:
                await self._send_alert(
                    f"🚨 *Критично мало місця на PBS!*\n"
                    f"Використано: {usage}%\n"
                    f"Потрібно очистити старі бэкапи"
                )
            elif usage > self.disk_warning_threshold:
                await self._handle_disk_warning(usage)

        except Exception as error:
            logger.error(f"Помилка перевірки диску PBS: {error}")

    async def _handle_disk_warning(self, usage: int) -> None:
        """
        Обработать предупреждение о месте на диске.
        """
        cache_key: str = "pbs_disk_space"
        now: datetime = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if cache_key not in _alert_cache or now - _alert_cache[cache_key] > cooldown:
            await self._send_alert(
                f"⚠️ *Мало місця на PBS*\n"
                f"Використано: {usage}%\n"
                f"Рекомендується перевірити"
            )
            _alert_cache[cache_key] = now

    async def _send_alert(self, message: str) -> None:
        """
        Отправить алерт в Telegram.
        """
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Алерт PBS відправлено: {message[:50]}...")
        except Exception as error:
            logger.error(f"Помилка відправки алерту PBS: {error}")


async def check_pbs() -> None:
    """Запустить проверку PBS"""
    monitor = PBSMonitor()
    await monitor.check_all_backups()


def run_pbs_check() -> None:
    """Синхронная обёртка для запуска проверки"""
    asyncio.run(check_pbs())


if __name__ == "__main__":
    asyncio.run(check_pbs())
