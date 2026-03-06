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

from config.settings import TELEGRAM_TOKEN, ADMIN_CHAT_ID, BACKUP_JOBS
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

# Константы
ALERT_COOLDOWN_MINUTES = 30
DISK_WARNING_THRESHOLD = 80
DISK_CRITICAL_THRESHOLD = 90
DEFAULT_RETENTION_DAYS = 7
PBS_HOST = "pbs-backup"
DATASTORE_PATH = "/mnt/datastore/local"

# Кэш для отслеживания уже отправленных алертов
_alert_cache: Dict[str, datetime] = {}
_alert_cooldown: timedelta = timedelta(minutes=ALERT_COOLDOWN_MINUTES)


class PBSMonitor:
    """Мониторинг Proxmox Backup Server"""
    
    def __init__(self) -> None:
        """Инициализация монитора PBS"""
        self.bot: Bot = Bot(token=TELEGRAM_TOKEN)
        self.pbs_host: str = PBS_HOST
        self.backup_jobs: List[Dict[str, Any]] = BACKUP_JOBS
        
    async def check_all_backups(self) -> None:
        """
        Проверить все бэкапы.
        
        Проходит по всем задачам бэкапа и проверяет их возраст,
        а также свободное место на диске.
        """
        logger.info("💾 Перевірка статусу бэкапів...")
        
        for job in self.backup_jobs:
            try:
                await self._check_backup_age(job)
            except Exception as error:
                logger.error(f"Помилка перевірки бэкапа {job.get('id')}: {error}")
        
        await self._check_disk_space()
    
    async def _check_backup_age(self, job: Dict[str, Any]) -> None:
        """
        Проверить возраст последнего бэкапа.
        
        Args:
            job: Конфигурация задачи бэкапа
        """
        vms: List[int] = job.get("vms", [])
        retention_days: int = job.get("retention_days", DEFAULT_RETENTION_DAYS)
        
        ssh = SSHClient(self.pbs_host)
        
        for vmid in vms:
            await self._check_vm_backup_age(vmid, retention_days, ssh)
    
    async def _check_vm_backup_age(self, vmid: int, retention_days: int, ssh: SSHClient) -> None:
        """
        Проверить возраст бэкапа для конкретной VM.
        
        Args:
            vmid: ID виртуальной машины
            retention_days: Срок хранения бэкапов в днях
            ssh: SSH клиент для подключения к PBS
        """
        # Получаем дату последнего бэкапа
        command: str = (
            f"pvesm list local --vmid {vmid} 2>/dev/null | "
            f"grep 'backup' | tail -1 | awk '{{print $6}}'"
        )
        
        try:
            result: str = ssh.execute_command(command).strip()
            
            if result:
                await self._process_backup_date(vmid, result, retention_days)
            else:
                await self._handle_no_backup(vmid)
                
        except Exception as error:
            logger.error(f"Помилка перевірки бэкапу VM {vmid}: {error}")
    
    async def _process_backup_date(self, vmid: int, date_str: str, retention_days: int) -> None:
        """
        Обработать дату последнего бэкапа.
        
        Args:
            vmid: ID виртуальной машины
            date_str: Строка с датой бэкапа
            retention_days: Срок хранения в днях
        """
        try:
            # Парсим дату (формат: YYYY-MM-DD)
            backup_date: datetime = datetime.strptime(date_str, "%Y-%m-%d")
            now: datetime = datetime.now()
            days_old: int = (now - backup_date).days
            
            cache_key: str = f"backup_age_{vmid}"
            
            if days_old > retention_days:
                # Критично - старше срока хранения
                await self._send_alert(
                    f"🚨 *Бэкап застарів!*\n"
                    f"VM ID: {vmid}\n"
                    f"Останній бэкап: {days_old} днів тому\n"
                    f"Максимум: {retention_days} днів"
                )
            elif days_old > retention_days - 2:
                # Предупреждение - скоро истечёт
                await self._handle_soon_expiring(vmid, days_old, retention_days, cache_key)
                
        except ValueError as error:
            logger.error(f"Помилка парсингу дати {date_str} для VM {vmid}: {error}")
    
    async def _handle_soon_expiring(self, vmid: int, days_old: int, retention_days: int, cache_key: str) -> None:
        """
        Обработать случай, когда бэкап скоро истечёт.
        
        Args:
            vmid: ID виртуальной машины
            days_old: Возраст бэкапа в днях
            retention_days: Срок хранения в днях
            cache_key: Ключ для кэша
        """
        now: datetime = datetime.now()
        
        if cache_key not in _alert_cache or now - _alert_cache[cache_key] > _alert_cooldown:
            await self._send_alert(
                f"⚠ *Бэкап скоро застаріє*\n"
                f"VM ID: {vmid}\n"
                f"Вік бэкапу: {days_old} днів\n"
                f"Залишилось: {retention_days - days_old} днів"
            )
            _alert_cache[cache_key] = now
    
    async def _handle_no_backup(self, vmid: int) -> None:
        """
        Обработать случай отсутствия бэкапов.
        
        Args:
            vmid: ID виртуальной машины
        """
        await self._send_alert(
            f"🚨 *Немає бэкапів!*\n"
            f"VM ID: {vmid}\n"
            f"Бэкапи не знайдено"
        )
    
    async def _check_disk_space(self) -> None:
        """Проверить свободное место на PBS."""
        ssh = SSHClient(self.pbs_host)
        
        # Проверяем место в datastore
        command: str = f"df -h {DATASTORE_PATH} | tail -1 | awk '{{print $5}}' | sed 's/%//'"
        
        try:
            result: str = ssh.execute_command(command).strip()
            usage: int = int(result)
            
            if usage > DISK_CRITICAL_THRESHOLD:
                await self._send_alert(
                    f"🚨 *Критично мало місця на PBS!*\n"
                    f"Використано: {usage}%\n"
                    f"Потрібно очистити старі бэкапи"
                )
            elif usage > DISK_WARNING_THRESHOLD:
                await self._handle_disk_warning(usage)
                    
        except Exception as error:
            logger.error(f"Помилка перевірки диску PBS: {error}")
    
    async def _handle_disk_warning(self, usage: int) -> None:
        """
        Обработать предупреждение о месте на диске.
        
        Args:
            usage: Процент использования диска
        """
        cache_key: str = "pbs_disk_space"
        now: datetime = datetime.now()
        
        if cache_key not in _alert_cache or now - _alert_cache[cache_key] > _alert_cooldown:
            await self._send_alert(
                f"⚠ *Мало місця на PBS*\n"
                f"Використано: {usage}%\n"
                f"Рекомендується перевірити"
            )
            _alert_cache[cache_key] = now
    
    async def _send_alert(self, message: str) -> None:
        """
        Отправить алерт в Telegram.
        
        Args:
            message: Текст сообщения
        """
        try:
            await self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Алерт PBS відправлено: {message[:50]}...")
        except Exception as error:
            logger.error(f"❌ Помилка відправки алерту PBS: {error}")


# Функция для запуска проверки
async def check_pbs() -> None:
    """Запустить проверку PBS"""
    monitor = PBSMonitor()
    await monitor.check_all_backups()


# Функция для ручного запуска
def run_pbs_check() -> None:
    """Синхронная обёртка для запуска проверки"""
    asyncio.run(check_pbs())


if __name__ == "__main__":
    # Для тестирования
    asyncio.run(check_pbs())
