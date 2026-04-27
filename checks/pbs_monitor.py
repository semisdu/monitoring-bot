#!/usr/bin/env python3
"""
Мониторинг Proxmox Backup Server (PBS)
Проверка статуса бэкапов через файловую систему
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
    get_alert_config,
    get_pbs_server_ids
)
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 7
DEFAULT_DATASTORE = "backuppbs_37"
DATASTORE_PATH = "/mnt/datastore"

_alert_cache: Dict[str, Dict[str, Any]] = {}


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
        self.alert_cooldown_minutes: int = 1440  # 24 часа
        
        self.pbs_servers: List[str] = get_pbs_server_ids()
        self.pbs_host: Optional[str] = self.pbs_servers[0] if self.pbs_servers else None
        self.ssh_clients: Dict[str, SSHClient] = {}

    def _get_ssh_client(self, server_id: str) -> SSHClient:
        """Получить SSH клиент (с кешированием)"""
        if server_id not in self.ssh_clients:
            self.ssh_clients[server_id] = SSHClient(server_id)
            logger.debug(f"Создан SSH клиент для {server_id}")
        return self.ssh_clients[server_id]

    async def check_all_backups(self) -> None:
        """Проверить все бэкапы."""
        if not self.backup_jobs:
            logger.info("Немає налаштованих завдань бэкапів")
            return

        if not self.pbs_host:
            logger.error("Немає налаштованих PBS серверів")
            return

        logger.info(f"Перевірка статусу бэкапів... Знайдено {len(self.backup_jobs)} завдань")

        for job in self.backup_jobs:
            try:
                await self._check_backup_age(job)
            except Exception as error:
                logger.error(f"Помилка перевірки бэкапа {job.get('id')}: {error}")

        await self._check_disk_space()

    async def _check_backup_age(self, job: Dict[str, Any]) -> None:
        """Проверить возраст последнего бэкапа через stat директории."""
        vms: List[int] = job.get("vms", [])
        retention_days: int = job.get("retention_days", DEFAULT_RETENTION_DAYS)
        server_id: str = job.get("server_id", self.pbs_host)
        datastore: str = job.get("datastore", DEFAULT_DATASTORE)

        ssh = self._get_ssh_client(server_id)

        for vmid in vms:
            await self._check_vm_backup_age(vmid, retention_days, ssh, job.get('id', 'unknown'), datastore)

    async def _check_vm_backup_age(self, vmid: int, retention_days: int, ssh: SSHClient, job_id: str, datastore: str) -> None:
        """
        Проверить возраст бэкапа для конкретной VM через stat директории.
        """
        # Проверяем существование директории и дату последнего изменения
        command = f"stat -c '%Y' {DATASTORE_PATH}/{datastore}/vm/{vmid}/ 2>/dev/null"
        
        try:
            result: str = ssh.execute_command(command).strip()
            
            if result and result.isdigit():
                timestamp = int(result)
                backup_date = datetime.fromtimestamp(timestamp)
                now = datetime.now()
                days_old = (now - backup_date).days
                
                logger.debug(f"VM {vmid}: последний бэкап {backup_date.strftime('%Y-%m-%d')} ({days_old} дней назад)")
                
                if days_old > retention_days:
                    await self._process_expired_backup(vmid, days_old, retention_days, job_id, backup_date)
                elif days_old > retention_days - 2:
                    await self._handle_soon_expiring(vmid, days_old, retention_days, job_id, backup_date)
                # Иначе бэкап свежий — ничего не делаем
            else:
                await self._handle_no_backup(vmid, job_id)

        except Exception as error:
            logger.error(f"Помилка перевірки бэкапу VM {vmid}: {error}")

    async def _process_expired_backup(self, vmid: int, days_old: int, retention_days: int, job_id: str, backup_date: datetime) -> None:
        """Обработать просроченный бэкап."""
        cache_key: str = f"backup_expired_{job_id}_{vmid}"
        now_dt = datetime.now()

        if cache_key not in _alert_cache:
            should_alert = True
        else:
            last_alert = _alert_cache.get(cache_key, {}).get('last_sent')
            if not last_alert or (now_dt - last_alert).total_seconds() > self.alert_cooldown_minutes * 60:
                should_alert = True
            else:
                should_alert = False
        
        if should_alert:
            await self._send_alert(
                f"🚨 *Помилка бэкапу!*\n"
                f"Завдання: {job_id}\n"
                f"VM ID: {vmid}\n"
                f"Останній бэкап: {days_old} днів тому ({backup_date.strftime('%Y-%m-%d')})\n"
                f"Максимум: {retention_days} днів"
            )
            _alert_cache[cache_key] = {'last_sent': now_dt, 'status': 'expired'}

    async def _handle_soon_expiring(self, vmid: int, days_old: int, retention_days: int, job_id: str, backup_date: datetime) -> None:
        """Обработать случай, когда бэкап скоро истечёт."""
        cache_key: str = f"backup_warning_{job_id}_{vmid}"
        now = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if cache_key not in _alert_cache or now - _alert_cache.get(cache_key, {}).get('last_sent', datetime.min) > cooldown:
            await self._send_alert(
                f"⚠ *Увага: бэкап скоро застаріє*\n"
                f"Завдання: {job_id}\n"
                f"VM ID: {vmid}\n"
                f"Вік бэкапу: {days_old} днів ({backup_date.strftime('%Y-%m-%d')})\n"
                f"Залишилось: {retention_days - days_old} днів"
            )
            _alert_cache[cache_key] = {'last_sent': now, 'status': 'warning'}

    async def _handle_no_backup(self, vmid: int, job_id: str) -> None:
        """Обработать случай отсутствия бэкапов."""
        cache_key: str = f"no_backup_{job_id}_{vmid}"
        now = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if cache_key not in _alert_cache or now - _alert_cache.get(cache_key, {}).get('last_sent', datetime.min) > cooldown:
            await self._send_alert(
                f"🚨 *Немає бэкапів!*\n"
                f"Завдання: {job_id}\n"
                f"VM ID: {vmid}\n"
                f"Бэкапи не знайдено"
            )
            _alert_cache[cache_key] = {'last_sent': now, 'status': 'no_backup'}

    async def _check_disk_space(self) -> None:
        """Проверить свободное место на PBS."""
        ssh = self._get_ssh_client(self.pbs_host)

        datastore = DEFAULT_DATASTORE
        if self.backup_jobs and self.backup_jobs[0].get('datastore'):
            datastore = self.backup_jobs[0].get('datastore')
        
        command = f"df -h {DATASTORE_PATH}/{datastore} 2>/dev/null | tail -1 | awk '{{print $5}}' | sed 's/%//'"

        try:
            result: str = ssh.execute_command(command).strip()
            
            if result and result.isdigit():
                usage: int = int(result)
                
                if usage > self.disk_critical_threshold:
                    await self._send_alert(
                        f"🚨 *Критично мало місця на PBS!*\n"
                        f"Використано: {usage}%\n"
                        f"Потрібно очистити старі бэкапи"
                    )
                elif usage > self.disk_warning_threshold:
                    await self._handle_disk_warning(usage)
            else:
                logger.debug(f"Не удалось получить процент использования диска: {result}")

        except Exception as error:
            logger.error(f"Помилка перевірки диску PBS: {error}")

    async def _handle_disk_warning(self, usage: int) -> None:
        """Обработать предупреждение о месте на диске."""
        cache_key: str = "pbs_disk_space"
        now = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if cache_key not in _alert_cache or now - _alert_cache.get(cache_key, {}).get('last_sent', datetime.min) > cooldown:
            await self._send_alert(
                f"⚠ *Мало місця на PBS*\n"
                f"Використано: {usage}%\n"
                f"Рекомендується перевірити"
            )
            _alert_cache[cache_key] = {'last_sent': now, 'status': 'disk_warning'}

    async def _send_alert(self, message: str) -> None:
        """Отправить алерт в Telegram."""
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
