import logging
import paramiko
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SSHConnectionPool:
    def __init__(self, max_age_seconds: int = 300):
        self.connections: Dict[str, dict] = {}
        self.max_age = max_age_seconds

    def get_connection(self, host: str, user: str, port: int, key_path: Path) -> Optional[paramiko.SSHClient]:
        now = datetime.now()
        key = f"{user}@{host}:{port}"

        if key in self.connections:
            conn_info = self.connections[key]
            age = (now - conn_info['created']).total_seconds()
            if age < self.max_age and conn_info['client'].get_transport() and conn_info['client'].get_transport().is_active():
                logger.debug(f"Использую существующее SSH для {key}")
                return conn_info['client']
            self.close_connection(key)

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, port=port, username=user, key_filename=str(key_path), timeout=10)
            self.connections[key] = {'client': client, 'created': now}
            logger.debug(f"Новое SSH соединение для {key}")
            return client
        except Exception as e:
            logger.error(f"Ошибка SSH для {key}: {e}")
            return None

    def close_connection(self, key: str):
        if key in self.connections:
            try:
                self.connections[key]['client'].close()
            except:
                pass
            del self.connections[key]

    def close_all(self):
        for key in list(self.connections.keys()):
            self.close_connection(key)

ssh_pool = SSHConnectionPool()
