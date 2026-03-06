#!/usr/bin/env python3
"""
Мониторинг Proxmox VE и виртуальных машин
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from telegram import Bot

from config.settings import TELEGRAM_TOKEN, ADMIN_CHAT_ID, VIRTUAL_MACHINES
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

# Константы
ALERT_COOLDOWN_MINUTES = 30
CPU_WARNING_THRESHOLD = 80
CPU_CRITICAL_THRESHOLD = 90
RAM_WARNING_THRESHOLD = 85
RAM_CRITICAL_THRESHOLD = 95
PVE_HOST = "pve-main"

# Кэш для отслеживания уже отправленных алертов
_alert_cache: Dict[str, datetime] = {}
_alert_cooldown: timedelta = timedelta(minutes=ALERT_COOLDOWN_MINUTES)


class PVEMonitor:
    """Мониторинг Proxmox VE"""
    
    def __init__(self) -> None:
        """Инициализация монитора PVE"""
        self.bot: Bot = Bot(token=TELEGRAM_TOKEN)
        self.pve_host: str = PVE_HOST
        self.vms: List[Dict[str, Any]] = VIRTUAL_MACHINES
        
    async def check_all_vms(self) -> None:
        """
        Проверить все виртуальные машины.
        
        Проходит по всем VM и проверяет их статус и ресурсы.
        """
        logger.info("🔍 Перевірка статусу VM...")
        
        for vm in self.vms:
            try:
                await self._check_vm_status(vm)
                await self._check_vm_resources(vm)
            except Exception as error:
                logger.error(f"Помилка перевірки VM {vm.get('name')}: {error}")
    
    async def _check_vm_status(self, vm: Dict[str, Any]) -> None:
        """
        Проверить статус VM (включена/выключена).
        
        Args:
            vm: Конфигурация виртуальной машины
        """
        vmid: int = vm["vmid"]
        name: str = vm["name"]
        
        ssh = SSHClient(self.pve_host)
        command: str = f"qm status {vmid} 2>/dev/null | grep status | awk '{{print $2}}'"
        
        try:
            result: str = ssh.execute_command(command).strip()
            
            if result != "running":
                await self._handle_vm_stopped(vmid, name, result)
                    
        except Exception as error:
            logger.error(f"Помилка перевірки статусу VM {vmid}: {error}")
    
    async def _handle_vm_stopped(self, vmid: int, name: str, status: str) -> None:
        """
        Обработать остановленную VM.
        
        Args:
            vmid: ID виртуальной машины
            name: Название VM
            status: Текущий статус
        """
        cache_key: str = f"vm_status_{vmid}"
        now: datetime = datetime.now()
        
        if cache_key not in _alert_cache or now - _alert_cache[cache_key] > _alert_cooldown:
            await self._send_alert(
                f"🚨 *VM зупинено!*\n"
                f"Назва: {name}\n"
                f"VM ID: {vmid}\n"
                f"Статус: `{status}`\n"
                f"Сервер: {self.pve_host}"
            )
            _alert_cache[cache_key] = now
    
    async def _check_vm_resources(self, vm: Dict[str, Any]) -> None:
        """
        Проверить ресурсы VM (CPU, RAM).
        
        Args:
            vm: Конфигурация виртуальной машины
        """
        vmid: int = vm["vmid"]
        name: str = vm["name"]
        
        ssh = SSHClient(self.pve_host)
        command: str = f"pvesh get /nodes/localhost/qemu/{vmid}/status/current --output-format json"
        
        try:
            result: str = ssh.execute_command(command)
            data: Dict[str, Any] = json.loads(result)
            
            # CPU
            cpu_usage: float = data.get('cpu', 0) * 100
            
            # RAM
            mem_usage: float = data.get('mem', 0) / (1024 * 1024)  # в MB
            max_mem: float = data.get('maxmem', 0) / (1024 * 1024)  # в MB
            mem_percent: float = (mem_usage / max_mem * 100) if max_mem > 0 else 0
            
            # Проверяем CPU
            await self._check_cpu_usage(vmid, name, cpu_usage)
            
            # Проверяем RAM
            await self._check_ram_usage(vmid, name, mem_percent)
                    
        except Exception as error:
            logger.error(f"Помилка перевірки ресурсів VM {vmid}: {error}")
    
    async def _check_cpu_usage(self, vmid: int, name: str, cpu_usage: float) -> None:
        """
        Проверить использование CPU.
        
        Args:
            vmid: ID виртуальной машины
            name: Название VM
            cpu_usage: Использование CPU в процентах
        """
        now: datetime = datetime.now()
        
        if cpu_usage > CPU_CRITICAL_THRESHOLD:
            await self._send_alert(
                f"🚨 *Висока нагрузка CPU!*\n"
                f"VM: {name}\n"
                f"CPU: {cpu_usage:.1f}% (критично)"
            )
        elif cpu_usage > CPU_WARNING_THRESHOLD:
            cache_key: str = f"cpu_warn_{vmid}"
            if cache_key not in _alert_cache or now - _alert_cache[cache_key] > _alert_cooldown:
                await self._send_alert(
                    f"⚠ *Висока нагрузка CPU*\n"
                    f"VM: {name}\n"
                    f"CPU: {cpu_usage:.1f}%"
                )
                _alert_cache[cache_key] = now
    
    async def _check_ram_usage(self, vmid: int, name: str, mem_percent: float) -> None:
        """
        Проверить использование RAM.
        
        Args:
            vmid: ID виртуальной машины
            name: Название VM
            mem_percent: Использование RAM в процентах
        """
        now: datetime = datetime.now()
        
        if mem_percent > RAM_CRITICAL_THRESHOLD:
            await self._send_alert(
                f"🚨 *Критично мало RAM!*\n"
                f"VM: {name}\n"
                f"RAM: {mem_percent:.1f}% використано"
            )
        elif mem_percent > RAM_WARNING_THRESHOLD:
            cache_key: str = f"ram_warn_{vmid}"
            if cache_key not in _alert_cache or now - _alert_cache[cache_key] > _alert_cooldown:
                await self._send_alert(
                    f"⚠ *Мало RAM*\n"
                    f"VM: {name}\n"
                    f"RAM: {mem_percent:.1f}% використано"
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
            logger.info(f"✅ Алерт відправлено: {message[:50]}...")
        except Exception as error:
            logger.error(f"❌ Помилка відправки алерту: {error}")


# Функция для запуска проверки
async def check_pve() -> None:
    """Запустить проверку PVE"""
    monitor = PVEMonitor()
    await monitor.check_all_vms()


# Функция для ручного запуска
def run_pve_check() -> None:
    """Синхронная обёртка для запуска проверки"""
    asyncio.run(check_pve())


if __name__ == "__main__":
    # Для тестирования
    asyncio.run(check_pve())
