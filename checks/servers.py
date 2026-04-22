#!/usr/bin/env python3
"""
Модуль проверки состояния серверов
Поддержка SSH ключей из конфигурации
"""

import logging
import paramiko
import psutil
import os
import socket
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from config.settings import SERVERS, ALERT_CONFIG

logger = logging.getLogger(__name__)

# Константы
SSH_TIMEOUT = 10
SSH_BANNER_TIMEOUT = 10
SSH_COMMAND_TIMEOUT = 5
LOCALHOST = 'localhost'


class ServerChecker:
    """Класс для проверки состояния серверов"""
    
    def __init__(self) -> None:
        """Инициализация проверщика серверов"""
        self.ssh_clients: Dict[str, dict] = {}
        self.ssh_max_age = 300  # 5 минут
    
    def _get_ssh_client(self, server_name: str) -> Optional[paramiko.SSHClient]:
        """
        Получить или создать SSH клиент для сервера с поддержкой ключей.
        
        Args:
            server_name: Имя сервера из конфигурации
            
        Returns:
            SSH клиент или None при ошибке
        """
        import time
        now = time.time()
        
        if server_name in self.ssh_clients:
            entry = self.ssh_clients[server_name]
            client = entry['client']
            created = entry['created']
            age = now - created
            if age < self.ssh_max_age and self._is_connection_alive(client):
                logger.info(f"[CACHE] Использую существующее SSH соединение для {server_name} (возраст {age:.0f}с)")
                return client
            logger.info(f"[CLOSE] Закрываю старое SSH соединение для {server_name} (возраст {age:.0f}с)")
            self._close_client(server_name, client)
        
        if server_name not in SERVERS:
            logger.error(f"Сервер '{server_name}' не найден в конфигурации")
            return None
        
        server_config: Dict[str, Any] = SERVERS[server_name]
        
        try:
            client = self._create_ssh_client(server_name, server_config)
            if client:
                self.ssh_clients[server_name] = {'client': client, 'created': now}
                logger.info(f"SSH подключение установлено для {server_name}")
            return client
            
        except Exception as error:
            logger.error(f"Ошибка подключения к {server_name}: {error}")
            return None
    
    def _is_connection_alive(self, client: paramiko.SSHClient) -> bool:
        """Проверить живо ли SSH соединение."""
        try:
            transport = client.get_transport()
            return transport is not None and transport.is_active()
        except:
            return False
    
    def _close_client(self, server_name: str, client: paramiko.SSHClient) -> None:
        """Закрыть SSH клиент."""
        try:
            client.close()
        except:
            pass
        finally:
            self.ssh_clients.pop(server_name, None)
    
    def _create_ssh_client(
        self,
        server_name: str,
        server_config: Dict[str, Any]
    ) -> Optional[paramiko.SSHClient]:
        """
        Создать SSH клиент для сервера.
        
        Args:
            server_name: Имя сервера
            server_config: Конфигурация сервера
            
        Returns:
            SSH клиент или None
        """
        host: str = server_config.get('host') or server_config.get('ip', '')
        port: int = server_config.get('port', 22)
        username: str = server_config.get('user', 'semis')
        ssh_key_path: Optional[str] = server_config.get('ssh_key_path')
        
        logger.info(f"Подключаюсь к {server_name} ({host}) как {username}")
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Пробуем подключиться с SSH ключом
        if ssh_key_path and os.path.exists(ssh_key_path):
            try:
                return self._connect_with_key(
                    client, host, port, username, ssh_key_path
                )
            except Exception as key_error:
                logger.warning(f"Ошибка подключения с ключом к {server_name}: {key_error}")
                # Пробуем без ключа
        
        # Подключаемся без ключа
        return self._connect_without_key(client, host, port, username)
    
    def _connect_with_key(
        self,
        client: paramiko.SSHClient,
        host: str,
        port: int,
        username: str,
        ssh_key_path: str
    ) -> paramiko.SSHClient:
        """Подключиться с SSH ключом."""
        logger.debug(f"Использую SSH ключ: {ssh_key_path}")
        key = paramiko.Ed25519Key.from_private_key_file(ssh_key_path)
        client.connect(
            hostname=host,
            port=port,
            username=username,
            pkey=key,
            timeout=SSH_TIMEOUT,
            banner_timeout=SSH_BANNER_TIMEOUT
        )
        return client
    
    def _connect_without_key(
        self,
        client: paramiko.SSHClient,
        host: str,
        port: int,
        username: str
    ) -> paramiko.SSHClient:
        """Подключиться без SSH ключа."""
        logger.debug(f"Подключаюсь без SSH ключа к {host}")
        client.connect(
            hostname=host,
            port=port,
            username=username,
            timeout=SSH_TIMEOUT,
            banner_timeout=SSH_BANNER_TIMEOUT
        )
        return client
    
    def check_local_server(self) -> Dict[str, Any]:
        """Проверить локальный сервер (где запущен бот)."""
        try:
            disk_info = self._get_local_disk_info()
            memory_info = self._get_local_memory_info()
            cpu_info = self._get_local_cpu_info()
            system_info = self._get_local_system_info()
            
            return {
                'hostname': socket.gethostname(),
                'server': LOCALHOST,
                'status': 'online',
                'disk': disk_info,
                'memory': memory_info,
                'cpu': cpu_info,
                'system': system_info
            }
            
        except Exception as error:
            logger.error(f"Ошибка проверки локального сервера: {error}")
            return {
                'hostname': LOCALHOST,
                'server': LOCALHOST,
                'status': 'error',
                'error': str(error)
            }
    
    def _get_local_disk_info(self) -> Dict[str, Any]:
        """Получить информацию о диске локально."""
        disk_usage = psutil.disk_usage('/')
        percent = disk_usage.percent
        
        return {
            'total_gb': round(disk_usage.total / (1024**3), 1),
            'used_gb': round(disk_usage.used / (1024**3), 1),
            'free_gb': round(disk_usage.free / (1024**3), 1),
            'percent': percent,
            'alert': self._check_disk_alert(percent)
        }
    
    def _get_local_memory_info(self) -> Dict[str, Any]:
        """Получить информацию о памяти локально."""
        memory = psutil.virtual_memory()
        percent = memory.percent
        
        return {
            'total_gb': round(memory.total / (1024**3), 1),
            'used_gb': round(memory.used / (1024**3), 1),
            'free_gb': round(memory.available / (1024**3), 1),
            'percent': percent,
            'alert': self._check_memory_alert(percent)
        }
    
    def _get_local_cpu_info(self) -> Dict[str, Any]:
        """Получить информацию о CPU локально."""
        cpu_percent = psutil.cpu_percent(interval=1)
        load_avg = psutil.getloadavg()
        
        return {
            'percent': cpu_percent,
            'load_1min': load_avg[0],
            'load_5min': load_avg[1],
            'load_15min': load_avg[2],
            'alert': self._check_cpu_alert(cpu_percent)
        }
    
    def _get_local_system_info(self) -> Dict[str, Any]:
        """Получить системную информацию локально."""
        uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
        
        return {
            'processes': len(psutil.pids()),
            'uptime_days': uptime.days,
            'uptime_hours': uptime.seconds // 3600,
            'timestamp': datetime.now().isoformat()
        }
    
    def check_remote_server(self, server_name: str) -> Dict[str, Any]:
        """
        Проверить удаленный сервер через SSH.
        
        Args:
            server_name: Имя сервера из конфигурации
            
        Returns:
            Информация о состоянии сервера
        """
        server_config: Dict[str, Any] = SERVERS.get(server_name, {})
        server_display_name: str = server_config.get('name', server_name)
        
        ssh_client = self._get_ssh_client(server_name)
        if not ssh_client:
            return self._create_offline_result(server_name, server_display_name)
        
        try:
            commands: Dict[str, str] = {
                'hostname': "hostname",
                'disk': "df -h / | tail -1",
                'memory': "free -h | grep Mem",
                'cpu': "top -bn1 | grep 'Cpu(s)'",
                'load': "cat /proc/loadavg",
                'uptime': "uptime -p || uptime",
                'processes': "ps aux | wc -l"
            }
            
            results: Dict[str, str] = self._execute_remote_commands(
                ssh_client, server_name, commands
            )
            
            return self._parse_remote_results(
                server_name, server_display_name, results
            )
            
        except Exception as error:
            logger.error(f"Ошибка проверки сервера {server_name}: {error}")
            return {
                'server': server_name,
                'name': server_display_name,
                'status': 'error',
                'error': str(error),
                'timestamp': datetime.now().isoformat()
            }
    
    def _execute_remote_commands(
        self,
        ssh_client: paramiko.SSHClient,
        server_name: str,
        commands: Dict[str, str]
    ) -> Dict[str, str]:
        """Выполнить команды на удаленном сервере."""
        results: Dict[str, str] = {}
        
        for key, cmd in commands.items():
            try:
                stdin, stdout, stderr = ssh_client.exec_command(
                    cmd, timeout=SSH_COMMAND_TIMEOUT
                )
                output: str = stdout.read().decode().strip()
                error: str = stderr.read().decode().strip()
                
                if error and "Warning" not in error:
                    logger.warning(
                        f"Ошибка выполнения команды {cmd} на {server_name}: {error}"
                    )
                
                results[key] = output
            except Exception as cmd_error:
                logger.warning(
                    f"Ошибка выполнения команды {key} на {server_name}: {cmd_error}"
                )
                results[key] = ""
        
        return results
    
    def _create_offline_result(
        self,
        server_name: str,
        server_display_name: str
    ) -> Dict[str, Any]:
        """Создать результат для офлайн сервера."""
        return {
            'server': server_name,
            'name': server_display_name,
            'status': 'offline',
            'error': 'SSH connection failed',
            'timestamp': datetime.now().isoformat()
        }
    
    def _parse_remote_results(
        self,
        server_name: str,
        server_display_name: str,
        results: Dict[str, str]
    ) -> Dict[str, Any]:
        """Распарсить результаты удаленных команд."""
        hostname: str = results.get('hostname', server_name)
        
        disk_info: Dict[str, Any] = self._parse_disk_output(results.get('disk', ''))
        memory_info: Dict[str, Any] = self._parse_memory_output(results.get('memory', ''))
        cpu_info: Dict[str, Any] = self._parse_cpu_output(results.get('cpu', ''))
        load_info: Dict[str, float] = self._parse_load_output(results.get('load', ''))
        
        return {
            'server': server_name,
            'name': server_display_name,
            'hostname': hostname,
            'status': 'online',
            'disk': {
                **disk_info,
                'alert': self._check_disk_alert(disk_info.get('percent', 0))
            },
            'memory': {
                **memory_info,
                'alert': self._check_memory_alert(memory_info.get('percent', 0))
            },
            'cpu': {
                **cpu_info,
                'alert': self._check_cpu_alert(cpu_info.get('percent', 0))
            },
            'system': {
                'load': load_info,
                'uptime': results.get('uptime', ''),
                'processes': self._parse_processes_count(results.get('processes', '0')),
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def _parse_processes_count(self, output: str) -> int:
        """Распарсить количество процессов."""
        try:
            return int(output) - 1 if output else 0
        except:
            return 0
    
    def _parse_disk_output(self, output: str) -> Dict[str, Any]:
        """
        Парсить вывод команды df.
        
        Пример: /dev/sda1 100G 80G 20G 80% /
        """
        try:
            parts = output.split()
            if len(parts) >= 5:
                total = self._parse_size(parts[1])
                used = self._parse_size(parts[2])
                free = self._parse_size(parts[3])
                percent = int(parts[4].replace('%', ''))
                
                return {
                    'total_gb': total,
                    'used_gb': used,
                    'free_gb': free,
                    'percent': percent
                }
        except Exception as error:
            logger.error(f"Ошибка парсинга диска: {error}")
        
        return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}
    
    def _parse_memory_output(self, output: str) -> Dict[str, Any]:
        """
        Парсить вывод команды free.
        
        Пример: Mem: 7.6Gi 2.1Gi 5.5Gi 300Mi 5.0Gi 4.9Gi
        """
        try:
            parts = output.split()
            if len(parts) >= 7:
                total = self._parse_size(parts[1])
                used = self._parse_size(parts[2])
                free = self._parse_size(parts[3])
                
                percent = round((used / total) * 100, 1) if total > 0 else 0
                
                return {
                    'total_gb': total,
                    'used_gb': used,
                    'free_gb': free,
                    'percent': percent
                }
        except Exception as error:
            logger.error(f"Ошибка парсинга памяти: {error}")
        
        return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}
    
    def _parse_cpu_output(self, output: str) -> Dict[str, Any]:
        """
        Парсить вывод команды top.
        
        Пример: %Cpu(s): 12.3 us, 4.5 sy, 0.0 ni, 83.2 id, ...
        """
        try:
            match = re.search(r'(\d+\.\d+)\s+id', output)
            if match:
                idle = float(match.group(1))
                usage = round(100 - idle, 1)
                return {'percent': usage}
        except Exception as error:
            logger.error(f"Ошибка парсинга CPU: {error}")
        
        return {'percent': 0}
    
    def _parse_load_output(self, output: str) -> Dict[str, float]:
        """
        Парсить вывод команды loadavg.
        
        Пример: 0.12 0.23 0.34 1/123 45678
        """
        try:
            parts = output.split()
            if len(parts) >= 3:
                return {
                    '1min': float(parts[0]),
                    '5min': float(parts[1]),
                    '15min': float(parts[2])
                }
        except Exception as error:
            logger.error(f"Ошибка парсинга loadavg: {error}")
        
        return {'1min': 0, '5min': 0, '15min': 0}
    
    def _parse_size(self, size_str: str) -> float:
        """
        Преобразовать размер в гигабайты.
        
        Поддерживает: G, Gi, M, Mi, T, Ti
        """
        try:
            size_str = size_str.upper()
            
            if 'G' in size_str or 'GI' in size_str:
                return float(size_str.replace('G', '').replace('I', '').replace('B', ''))
            elif 'M' in size_str or 'MI' in size_str:
                return float(size_str.replace('M', '').replace('I', '').replace('B', '')) / 1024
            elif 'T' in size_str or 'TI' in size_str:
                return float(size_str.replace('T', '').replace('I', '').replace('B', '')) * 1024
            else:
                return float(size_str) / (1024**3)
        except:
            return 0
    
    def _check_disk_alert(self, percent: float) -> str:
        """Проверить необходимость алерта для диска."""
        if percent >= ALERT_CONFIG['disk_critical_percent']:
            return 'critical'
        elif percent >= ALERT_CONFIG['disk_warning_percent']:
            return 'warning'
        return 'ok'
    
    def _check_memory_alert(self, percent: float) -> str:
        """Проверить необходимость алерта для памяти."""
        if percent >= ALERT_CONFIG['memory_critical_percent']:
            return 'critical'
        elif percent >= ALERT_CONFIG['memory_warning_percent']:
            return 'warning'
        return 'ok'
    
    def _check_cpu_alert(self, percent: float) -> str:
        """Проверить необходимость алерта для CPU."""
        if percent >= ALERT_CONFIG['cpu_critical_percent']:
            return 'critical'
        elif percent >= ALERT_CONFIG['cpu_warning_percent']:
            return 'warning'
        return 'ok'
    
    def close_connections(self) -> None:
        """Закрыть все SSH соединения."""
        for server_name, client in list(self.ssh_clients.items()):
            try:
                client.close()
                logger.debug(f"SSH соединение закрыто для {server_name}")
            except:
                pass
        self.ssh_clients.clear()


# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

_server_checker: Optional[ServerChecker] = None


def get_server_checker() -> ServerChecker:
    """Получить глобальный экземпляр ServerChecker."""
    global _server_checker
    if _server_checker is None:
        _server_checker = ServerChecker()
    return _server_checker


def test_ssh_connection(server_name: str) -> Dict[str, Any]:
    """
    Тестировать SSH подключение к серверу.
    
    Args:
        server_name: Имя сервера из конфигурации
        
    Returns:
        Результат тестирования
    """
    checker: ServerChecker = get_server_checker()
    server_config: Dict[str, Any] = SERVERS.get(server_name, {})
    
    result: Dict[str, Any] = {
        'server': server_name,
        'name': server_config.get('name', server_name),
        'status': 'testing',
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        client = checker._get_ssh_client(server_name)
        if client:
            stdin, stdout, stderr = client.exec_command(
                "echo 'SSH Test OK'", timeout=SSH_COMMAND_TIMEOUT
            )
            output = stdout.read().decode().strip()
            
            if "SSH Test OK" in output:
                result['status'] = 'success'
                result['message'] = 'SSH connection successful'
            else:
                result['status'] = 'error'
                result['message'] = f'Unexpected output: {output}'
        else:
            result['status'] = 'error'
            result['message'] = 'Failed to create SSH client'
            
    except Exception as error:
        result['status'] = 'error'
        result['message'] = str(error)
    
    return result
