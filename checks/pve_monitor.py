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

from config.loader import (
    get_telegram_token,
    get_admin_chat_id,
    get_virtual_machines,
    get_server_config,
    get_alert_config,
    get_pve_server_ids,
    get_full_ssh_key_path
)
from utils.ssh import get_ssh_client  # Используем новый адаптер

logger = logging.getLogger(__name__)

# Кэш для алертов с учётом статуса VM
_alert_cache: Dict[str, Dict[str, Any]] = {}


class PVEMonitor:
    """Мониторинг Proxmox VE"""

    def __init__(self) -> None:
        """Инициализация монитора PVE"""
        self.bot: Bot = Bot(token=get_telegram_token())
        self.admin_chat_id: int = get_admin_chat_id()
        
        self.vms: List[Dict[str, Any]] = get_virtual_machines()
        
        alert_config = get_alert_config()
        self.cpu_warning_threshold: int = alert_config.get('cpu_warning_percent', 80)
        self.cpu_critical_threshold: int = alert_config.get('cpu_critical_percent', 90)
        self.ram_warning_threshold: int = alert_config.get('memory_warning_percent', 85)
        self.ram_critical_threshold: int = alert_config.get('memory_critical_percent', 95)
        
        self.pve_servers: List[str] = get_pve_server_ids()
        self.pve_host: Optional[str] = self.pve_servers[0] if self.pve_servers else None
        
        self.alert_cooldown_minutes: int = 1440  # 24 часа - не спамить повторно
        self.ssh_clients: Dict[str, Any] = {}  # Кэш SSH клиентов по серверам

    def _get_ssh_client(self, server_id: str):
        """Получить SSH клиент из кэша (использует пул через адаптер)"""
        if server_id not in self.ssh_clients:
            self.ssh_clients[server_id] = get_ssh_client(server_id)
            logger.debug(f"Получен SSH клиент для {server_id}")
        return self.ssh_clients[server_id]

    async def check_all_vms(self) -> None:
        """
        Проверить все виртуальные машины.
        """
        if not self.vms:
            logger.info("📭 Немає налаштованих VM для моніторингу")
            return

        if not self.pve_host:
            logger.error("❌ Немає налаштованих PVE серверів")
            return

        logger.info(f"🔍 Перевірка статусу {len(self.vms)} VM...")

        for vm in self.vms:
            try:
                if vm.get('server_id') != self.pve_host:
                    continue
                    
                await self._check_vm_status(vm)
                await self._check_vm_resources(vm)
            except Exception as error:
                logger.error(f"Помилка перевірки VM {vm.get('name', 'unknown')}: {error}")

    async def _check_vm_status(self, vm: Dict[str, Any]) -> None:
        """
        Проверить статус VM (включена/выключена).
        """
        vmid: int = vm["vmid"]
        name: str = vm.get("name", f"VM-{vmid}")
        vm_id: str = vm.get("id", f"vm{vmid}")

        ssh = self._get_ssh_client(self.pve_host)
        # Исправлена команда: теперь точно получаем статус
        command: str = f"sudo qm status {vmid} 2>/dev/null | awk '{{print $2}}'"

        try:
            result: str = ssh.execute_command(command).strip()
            
            # Если результат пустой - VM не существует или команда не сработала
            if not result:
                logger.warning(f"Не удалось получить статус VM {vmid}, результат пустой")
                result = "unknown"
            
            logger.debug(f"VM {vmid} статус: '{result}'")
            
            if result != "running":
                await self._handle_vm_stopped(vmid, name, result, vm_id)
            else:
                # VM работает - проверяем, был ли ранее алерт о её остановке
                await self._handle_vm_resolved(vmid, name, vm_id)

        except Exception as error:
            logger.error(f"Помилка перевірки статусу VM {vmid}: {error}")

    async def _handle_vm_resolved(self, vmid: int, name: str, vm_id: str) -> None:
        """
        Обработать восстановление VM (отправить уведомление о решении проблемы).
        """
        cache_key: str = f"vm_status_{vm_id}"
        
        if cache_key in _alert_cache and _alert_cache[cache_key].get('status') != 'running':
            # Был ранее алерт об остановке - отправляем уведомление о восстановлении
            await self._send_alert(
                f"✅ *VM відновлено!*\n"
                f"Назва: {name}\n"
                f"VM ID: {vmid}\n"
                f"Статус: `running`\n"
                f"Сервер: {self.pve_host}"
            )
            _alert_cache[cache_key] = {
                'last_sent': datetime.now(),
                'status': 'running',
                'resolved': True
            }
            logger.info(f"VM {name} восстановлена, уведомление отправлено")

    async def _handle_vm_stopped(self, vmid: int, name: str, status: str, vm_id: str) -> None:
        """
        Обработать остановленную VM с дедупликацией.
        """
        cache_key: str = f"vm_status_{vm_id}"
        now: datetime = datetime.now()
        
        # Проверяем, нужно ли отправить алерт
        should_alert = False
        
        if cache_key not in _alert_cache:
            # Первый раз - отправляем
            should_alert = True
        else:
            cached = _alert_cache[cache_key]
            last_status = cached.get('status')
            last_sent = cached.get('last_sent')
            
            # Отправляем если: статус изменился ИЛИ прошло больше cooldown
            if last_status != status:
                should_alert = True
            elif last_sent and (now - last_sent).total_seconds() > self.alert_cooldown_minutes * 60:
                should_alert = True
        
        if should_alert:
            await self._send_alert(
                f"🚨 *Помилка: VM зупинено!*\n"
                f"Назва: {name}\n"
                f"VM ID: {vmid}\n"
                f"Статус: `{status}`\n"
                f"Сервер: {self.pve_host}"
            )
            _alert_cache[cache_key] = {
                'last_sent': now,
                'status': status,
                'resolved': False
            }
            logger.info(f"Алерт о остановке VM {name} отправлен (статус: {status})")
        else:
            logger.debug(f"Пропускаем дублирующий алерт для VM {name} (статус: {status})")

    async def _check_vm_resources(self, vm: Dict[str, Any]) -> None:
        """
        Проверить ресурсы VM (CPU, RAM).
        """
        vmid: int = vm["vmid"]
        name: str = vm.get("name", f"VM-{vmid}")
        vm_id: str = vm.get("id", f"vm{vmid}")

        ssh = self._get_ssh_client(self.pve_host)
        command: str = f"pvesh get /nodes/localhost/qemu/{vmid}/status/current --output-format json"

        try:
            result: str = ssh.execute_command(command)
            if not result:
                logger.warning(f"Порожня відповідь від PVE для VM {vmid}")
                return
                
            data: Dict[str, Any] = json.loads(result)

            cpu_usage: float = data.get('cpu', 0) * 100

            mem_usage: float = data.get('mem', 0) / (1024 * 1024)
            max_mem: float = data.get('maxmem', 0) / (1024 * 1024)
            mem_percent: float = (mem_usage / max_mem * 100) if max_mem > 0 else 0

            await self._check_cpu_usage(vmid, name, cpu_usage, vm_id)
            await self._check_ram_usage(vmid, name, mem_percent, vm_id)

        except json.JSONDecodeError as error:
            logger.error(f"Помилка парсингу JSON для VM {vmid}: {error}")
        except Exception as error:
            logger.error(f"Помилка перевірки ресурсів VM {vmid}: {error}")

    async def _check_cpu_usage(self, vmid: int, name: str, cpu_usage: float, vm_id: str) -> None:
        """
        Проверить использование CPU.
        """
        now: datetime = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if cpu_usage > self.cpu_critical_threshold:
            cache_key: str = f"cpu_crit_{vm_id}"
            if cache_key not in _alert_cache or now - _alert_cache.get(cache_key, {}).get('last_sent', datetime.min) > cooldown:
                await self._send_alert(
                    f"🚨 *Критична нагрузка CPU!*\n"
                    f"VM: {name} (ID: {vmid})\n"
                    f"CPU: {cpu_usage:.1f}%"
                )
                _alert_cache[cache_key] = {'last_sent': now, 'value': cpu_usage}
        elif cpu_usage > self.cpu_warning_threshold:
            cache_key: str = f"cpu_warn_{vm_id}"
            if cache_key not in _alert_cache or now - _alert_cache.get(cache_key, {}).get('last_sent', datetime.min) > cooldown:
                await self._send_alert(
                    f"⚠ *Висока нагрузка CPU*\n"
                    f"VM: {name} (ID: {vmid})\n"
                    f"CPU: {cpu_usage:.1f}%"
                )
                _alert_cache[cache_key] = {'last_sent': now, 'value': cpu_usage}

    async def _check_ram_usage(self, vmid: int, name: str, mem_percent: float, vm_id: str) -> None:
        """
        Проверить использование RAM.
        """
        now: datetime = datetime.now()
        cooldown = timedelta(minutes=self.alert_cooldown_minutes)

        if mem_percent > self.ram_critical_threshold:
            cache_key: str = f"ram_crit_{vm_id}"
            if cache_key not in _alert_cache or now - _alert_cache.get(cache_key, {}).get('last_sent', datetime.min) > cooldown:
                await self._send_alert(
                    f"🚨 *Критично мало RAM!*\n"
                    f"VM: {name} (ID: {vmid})\n"
                    f"RAM: {mem_percent:.1f}% використано"
                )
                _alert_cache[cache_key] = {'last_sent': now, 'value': mem_percent}
        elif mem_percent > self.ram_warning_threshold:
            cache_key: str = f"ram_warn_{vm_id}"
            if cache_key not in _alert_cache or now - _alert_cache.get(cache_key, {}).get('last_sent', datetime.min) > cooldown:
                await self._send_alert(
                    f"⚠ *Мало RAM*\n"
                    f"VM: {name} (ID: {vmid})\n"
                    f"RAM: {mem_percent:.1f}% використано"
                )
                _alert_cache[cache_key] = {'last_sent': now, 'value': mem_percent}

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
            logger.info(f"Алерт PVE відправлено: {message[:50]}...")
        except Exception as error:
            logger.error(f"Помилка відправки алерту PVE: {error}")


async def check_pve() -> None:
    """Запустить проверку PVE"""
    monitor = PVEMonitor()
    await monitor.check_all_vms()


def run_pve_check() -> None:
    """Синхронная обёртка для запуска проверки"""
    asyncio.run(check_pve())


if __name__ == "__main__":
    asyncio.run(check_pve())
