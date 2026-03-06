#!/usr/bin/env python3
"""
Модуль для работы с Proxmox VE и Proxmox Backup Server
Реализация через SSH
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ProxmoxClient:
    """Клиент для работы с Proxmox VE API через SSH"""

    def __init__(self, server_id: str):
        from config.settings import SERVERS
        from checks.servers import ServerChecker

        self.server_id = server_id
        self.server_info = SERVERS.get(server_id, {})
        self.checker = ServerChecker()
        
    def _execute_ssh_command(self, command: str) -> tuple[bool, str, str]:
        """Выполнить команду на сервере через SSH"""
        try:
            client = self.checker._get_ssh_client(self.server_id)
            
            if not client:
                return False, "", f"Не удалось подключиться к серверу {self.server_id}"
            
            # Выполняем команду
            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            return True, output, error
            
        except Exception as e:
            logger.error(f"Ошибка выполнения SSH команды на {self.server_id}: {e}")
            return False, "", str(e)

    def check_connection(self) -> bool:
        """Проверить подключение к Proxmox VE"""
        try:
            success, stdout, stderr = self._execute_ssh_command("pveversion 2>/dev/null || echo 'PVE not found'")
            if success and "pve-manager" in stdout:
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка подключения к PVE {self.server_id}: {e}")
            return False

    def get_vms_status(self) -> Dict[str, Any]:
        """Получить статус виртуальных машин"""
        try:
            # Пробуем разные команды для получения списка VM
            commands = [
                "sudo qm list",
                "sudo qm list 2>/dev/null",
                "qm list 2>/dev/null",
                "pvesh get /nodes/localhost/qemu --output-format json 2>/dev/null"
            ]

            output = ""
            for cmd in commands:
                success, stdout, stderr = self._execute_ssh_command(cmd)
                if success and stdout.strip():
                    output = stdout.strip()
                    break

            if not output:
                return {
                    "status": "error",
                    "message": "Не удалось получить список VM",
                    "vms": []
                }

            # Пробуем парсить как JSON (API формат)
            try:
                data = json.loads(output)
                vms = []
                for vm in data:
                    vms.append({
                        'vmid': str(vm.get('vmid', '')),
                        'name': vm.get('name', 'N/A'),
                        'status': vm.get('status', 'unknown'),
                        'mem': vm.get('mem', 0),
                        'maxmem': vm.get('maxmem', 0),
                        'cpu': vm.get('cpu', 0)
                    })
                return {
                    "status": "success",
                    "message": f"Найдено {len(vms)} VM",
                    "vms": vms
                }
            except json.JSONDecodeError:
                # Парсим текстовый вывод qm list
                vms = []
                lines = output.strip().split('\n')

                for line in lines:
                    line = line.strip()
                    if not line or 'VMID' in line or 'usage:' in line:
                        continue

                    parts = re.split(r'\s+', line)
                    if len(parts) >= 3:
                        vms.append({
                            'vmid': parts[0],
                            'name': parts[1],
                            'status': parts[2].lower(),
                            'mem': parts[3] if len(parts) > 3 else 0,
                            'maxmem': parts[4] if len(parts) > 4 else 0,
                            'cpu': parts[5] if len(parts) > 5 else 0
                        })

                return {
                    "status": "success",
                    "message": f"Найдено {len(vms)} VM",
                    "vms": vms
                }

        except Exception as e:
            logger.error(f"Ошибка получения статуса VM: {e}")
            return {
                "status": "error",
                "message": str(e),
                "vms": []
            }


class ProxmoxBackupClient:
    """Клиент для работы с Proxmox Backup Server через SSH"""

    def __init__(self, server_id: str):
        from config.settings import SERVERS
        from checks.servers import ServerChecker

        self.server_id = server_id
        self.server_info = SERVERS.get(server_id, {})
        self.checker = ServerChecker()
        
    def _execute_ssh_command(self, command: str) -> tuple[bool, str, str]:
        """Выполнить команду на сервере через SSH"""
        try:
            client = self.checker._get_ssh_client(self.server_id)
            
            if not client:
                return False, "", f"Не удалось подключиться к серверу {self.server_id}"
            
            # Выполняем команду
            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            return True, output, error
            
        except Exception as e:
            logger.error(f"Ошибка выполнения SSH команды на {self.server_id}: {e}")
            return False, "", str(e)

    def check_connection(self) -> bool:
        """Проверить подключение к Proxmox Backup Server"""
        try:
            success, stdout, stderr = self._execute_ssh_command("proxmox-backup-manager versions 2>/dev/null || echo 'PBS not found'")
            if success and "proxmox-backup" in stdout:
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка подключения к PBS {self.server_id}: {e}")
            return False

    def get_backups_status(self) -> Dict[str, Any]:
        """Получить статус бэкапов"""
        try:
            # Проверяем версию PBS
            success, stdout, stderr = self._execute_ssh_command("proxmox-backup-manager versions")
            if not success:
                return {
                    "status": "error",
                    "message": "PBS недоступен",
                    "backups": []
                }

            # Проверяем последние задачи бекапа
            success, stdout, stderr = self._execute_ssh_command("proxmox-backup-client task list --limit 5 2>/dev/null || echo 'Нет задач'")

            return {
                "status": "success",
                "message": "PBS доступен",
                "backups": [],
                "last_tasks": stdout[:500] if stdout else 'Нет данных'
            }

        except Exception as e:
            logger.error(f"Ошибка получения статуса бэкапов: {e}")
            return {
                "status": "error",
                "message": str(e),
                "backups": []
            }


def get_proxmox_client(server_id: str) -> Optional[ProxmoxClient]:
    """Получить клиент Proxmox VE для сервера"""
    try:
        return ProxmoxClient(server_id)
    except Exception as e:
        logger.error(f"Ошибка создания клиента PVE для {server_id}: {e}")
        return None


def get_proxmox_backup_client(server_id: str) -> Optional[ProxmoxBackupClient]:
    """Получить клиент Proxmox Backup Server для сервера"""
    try:
        return ProxmoxBackupClient(server_id)
    except Exception as e:
        logger.error(f"Ошибка создания клиента PBS для {server_id}: {e}")
        return None


# Функции для обратной совместимости со старой версией
def get_vm_list(server_id='pve-main'):
    """Старая функция для получения списка VM"""
    client = get_proxmox_client(server_id)
    if client:
        result = client.get_vms_status()
        return {
            'success': result['status'] == 'success',
            'vms': result.get('vms', []),
            'error': result.get('message') if result['status'] != 'success' else None
        }
    return {'success': False, 'error': 'Клиент не создан', 'vms': []}


def check_pbs_backups(server_id='pbs-backup'):
    """Старая функция для проверки PBS бэкапов"""
    client = get_proxmox_backup_client(server_id)
    if client:
        result = client.get_backups_status()
        return {
            'success': result['status'] == 'success',
            'status': 'running' if result['status'] == 'success' else 'error',
            'last_tasks': result.get('last_tasks', 'Нет данных'),
            'error': result.get('message') if result['status'] != 'success' else None
        }
    return {'success': False, 'error': 'Клиент не создан'}
