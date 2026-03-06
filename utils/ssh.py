#!/usr/bin/env python3
"""
SSH клиент для подключения к серверам
"""
import logging
import paramiko
from typing import Optional
from config.settings import get_server_info

logger = logging.getLogger(__name__)

class SSHClient:
    """Клиент для SSH подключений"""
    
    def __init__(self, server_id: str):
        self.server_id = server_id
        self.server_info = get_server_info(server_id)
        self.client = None
        
    def _connect(self) -> bool:
        """Установить SSH соединение"""
        try:
            if not self.server_info:
                logger.error(f"Сервер {self.server_id} не найден в конфигурации")
                return False
            
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            host = self.server_info.get('host') or self.server_info.get('ip')
            user = self.server_info.get('user', 'semis')
            port = self.server_info.get('port', 22)
            key_path = self.server_info.get('ssh_key_path')
            
            if key_path:
                key = paramiko.Ed25519Key.from_private_key_file(key_path)
                self.client.connect(
                    hostname=host,
                    port=port,
                    username=user,
                    pkey=key,
                    timeout=10
                )
            else:
                self.client.connect(
                    hostname=host,
                    port=port,
                    username=user,
                    timeout=10
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка SSH подключения к {self.server_id}: {e}")
            return False
    
    def execute_command(self, command: str) -> str:
        """Выполнить команду на сервере"""
        try:
            if not self.client and not self._connect():
                return f"ERROR: Не удалось подключиться к {self.server_id}"
            
            stdin, stdout, stderr = self.client.exec_command(command, timeout=30)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                logger.warning(f"Stderr от {self.server_id}: {error}")
            
            return output if output else error
            
        except Exception as e:
            logger.error(f"Ошибка выполнения команды на {self.server_id}: {e}")
            return f"ERROR: {e}"
    
    def close(self):
        """Закрыть соединение"""
        if self.client:
            self.client.close()
            self.client = None
    
    def __enter__(self):
        self._connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
