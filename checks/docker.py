#!/usr/bin/env python3
"""
Модуль для мониторинга Docker контейнеров
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from config.loader import (
    get_server_config,
    get_server_containers,
    get_docker_server_ids,
    get_alert_config
)
from utils.ssh import SSHClient

logger = logging.getLogger(__name__)

DEFAULT_SSH_PORT = 22
DEFAULT_USER = "semis"


class DockerMonitor:
    """Мониторинг Docker контейнеров"""

    def __init__(self, server_id: str) -> None:
        """
        Инициализация монитора Docker.

        Args:
            server_id: Идентификатор сервера из конфигурации
        """
        self.server_id: str = server_id
        self.server_info: Dict[str, Any] = get_server_config(server_id) or {}
        
        self.containers_config: List[Dict[str, Any]] = get_server_containers(server_id)
        
        self.ssh_key_name: Optional[str] = self.server_info.get('ssh_key')
        self.user: str = self.server_info.get('user', DEFAULT_USER)
        self.host: str = self.server_info.get('host') or self.server_info.get('ip', '')
        self.port: int = self.server_info.get('port', DEFAULT_SSH_PORT)
        
        alert_config = get_alert_config()
        self.restart_threshold: int = alert_config.get('container_restart_threshold', 3)

    def _get_ssh_client(self) -> SSHClient:
        """Получить SSH клиент для сервера"""
        return SSHClient(self.server_id)

    def check_connection(self) -> bool:
        """Проверить подключение к серверу."""
        ssh = self._get_ssh_client()
        result = ssh.execute_command("echo 'connection_test'")
        return result.strip() == "connection_test"

    def _parse_container_line(self, line: str) -> Optional[Dict[str, str]]:
        """
        Распарсить строку с информацией о контейнере.
        """
        if not line or '|' not in line:
            return None

        parts = line.split('|', 2)
        if len(parts) < 3:
            return None

        return {
            "name": parts[0],
            "status": parts[1],
            "image": parts[2]
        }

    def _analyze_container_status(self, status: str) -> Tuple[bool, bool, bool]:
        """
        Проанализировать статус контейнера.
        """
        return (
            "Up" in status,
            "Restarting" in status,
            "Exited" in status
        )

    def _get_container_alert_level(
        self,
        exited: bool,
        restarting: bool,
        critical: bool
    ) -> str:
        """
        Определить уровень алерта для контейнера.
        """
        if exited and critical:
            return "critical"
        if exited or restarting:
            return "warning"
        return "ok"

    def check_docker_containers(self) -> Dict[str, Any]:
        """
        Проверить статус Docker контейнеров.
        """
        try:
            if not self.containers_config:
                return {
                    "status": "success",
                    "server": self.server_id,
                    "message": "Нет контейнеров для мониторинга",
                    "containers": []
                }

            ssh = self._get_ssh_client()
            
            docker_check = ssh.execute_command("docker --version 2>/dev/null || echo 'DOCKER_NOT_FOUND'")
            if "DOCKER_NOT_FOUND" in docker_check or "not found" in docker_check:
                return {
                    "status": "error",
                    "error": "Docker не установлен на сервере",
                    "containers": []
                }

            containers_result = ssh.execute_command(
                'docker ps -a --format "{{.Names}}|{{.Status}}|{{.Image}}" 2>/dev/null || echo "ERROR"'
            )

            if "ERROR" in containers_result:
                return {
                    "status": "error",
                    "error": "Не удалось получить список контейнеров",
                    "containers": []
                }

            all_containers: List[Dict[str, str]] = []
            for line in containers_result.strip().split('\n'):
                if line:
                    container_data = self._parse_container_line(line)
                    if container_data:
                        all_containers.append(container_data)

            containers_dict = {c["name"]: c for c in all_containers if "name" in c}

            container_statuses: List[Dict[str, Any]] = []

            for container_config in self.containers_config:
                status = self._check_single_container(
                    container_config,
                    containers_dict,
                    ssh
                )
                container_statuses.append(status)

            return self._build_status_report(container_statuses)

        except Exception as error:
            logger.error(f"Ошибка при проверке Docker на {self.server_id}: {error}")
            return {
                "status": "error",
                "error": str(error),
                "containers": []
            }

    def _check_single_container(
        self,
        container_config: Dict[str, Any],
        containers_dict: Dict[str, Dict[str, str]],
        ssh: SSHClient
    ) -> Dict[str, Any]:
        """
        Проверить отдельный контейнер.
        """
        container_name: str = container_config.get("name", "")
        critical: bool = container_config.get("critical", False)
        service_name: str = container_config.get("service_name", container_name)

        container = containers_dict.get(container_name)
        
        if container:
            return self._process_found_container(
                container, container_name, critical, service_name
            )

        return self._process_missing_container(
            container_name, critical, service_name, ssh
        )

    def _process_found_container(
        self,
        container: Dict[str, str],
        container_name: str,
        critical: bool,
        service_name: str
    ) -> Dict[str, Any]:
        """
        Обработать найденный контейнер.
        """
        status: str = container.get("status", "")
        running, restarting, exited = self._analyze_container_status(status)

        container_info: Dict[str, Any] = {
            "name": container_name,
            "status": status,
            "running": running,
            "restarting": restarting,
            "exited": exited,
            "image": container.get("image", ""),
            "critical": critical,
            "service_name": service_name
        }

        container_info["alert"] = self._get_container_alert_level(
            exited, restarting, critical
        )

        return container_info

    def _process_missing_container(
        self,
        container_name: str,
        critical: bool,
        service_name: str,
        ssh: SSHClient
    ) -> Dict[str, Any]:
        """
        Обработать отсутствующий контейнер.
        """
        inspect_result = ssh.execute_command(
            f"docker inspect {container_name} 2>/dev/null || echo 'NOT_FOUND'"
        )
        exists: bool = "NOT_FOUND" not in inspect_result

        return {
            "name": container_name,
            "status": "Not found" if not exists else "Unknown",
            "running": False,
            "restarting": False,
            "exited": True,
            "critical": critical,
            "service_name": service_name,
            "alert": "critical" if critical else "warning",
            "error": "Container not found" if not exists else "Status unknown"
        }

    def _build_status_report(self, container_statuses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Сформировать отчёт о статусе контейнеров.
        """
        total: int = len(container_statuses)
        running: int = sum(1 for c in container_statuses if c.get("running"))
        critical: int = sum(1 for c in container_statuses if c.get("critical", False))
        critical_failed: int = sum(
            1 for c in container_statuses
            if c.get("critical", False) and not c.get("running")
        )

        return {
            "status": "success",
            "server": self.server_id,
            "total_containers": total,
            "running_containers": running,
            "critical_containers": critical,
            "critical_failed": critical_failed,
            "containers": container_statuses,
            "docker_available": True
        }

    def restart_container(self, container_name: str) -> Dict[str, Any]:
        """
        Перезапустить Docker контейнер.
        """
        try:
            ssh = self._get_ssh_client()
            result = ssh.execute_command(f"docker restart {container_name} 2>&1")
            success = "error" not in result.lower() and "not found" not in result.lower()

            return {
                "success": success,
                "container": container_name,
                "output": result if success else "",
                "error": result if not success else "",
                "message": f"Контейнер {container_name} успешно перезапущен" if success else None
            }

        except Exception as error:
            return {
                "success": False,
                "error": f"Исключение при перезапуске контейнера {container_name}: {str(error)}",
                "container": container_name
            }

    def restart_all_containers(self) -> Dict[str, Any]:
        """
        Перезапустить все Docker контейнеры на сервере.
        """
        try:
            if not self.check_connection():
                return {"success": False, "error": "Не удалось подключиться к серверу"}

            ssh = self._get_ssh_client()
            result = ssh.execute_command("docker restart $(docker ps -q) 2>&1")
            success = "error" not in result.lower()

            return {
                "success": success,
                "output": result if success else "",
                "error": result if not success else "",
                "message": f"Все контейнеры на сервере {self.server_id} успешно перезапущены" if success else None
            }

        except Exception as error:
            return {
                "success": False,
                "error": f"Исключение при перезапуске контейнеров: {str(error)}"
            }


def get_docker_monitor(server_id: str) -> DockerMonitor:
    """Получить экземпляр монитора Docker для сервера."""
    return DockerMonitor(server_id)


def check_all_docker_servers() -> Dict[str, Any]:
    """
    Проверить Docker на всех серверах.
    """
    results: Dict[str, Any] = {}
    all_servers: List[str] = get_docker_server_ids()

    for server_id in all_servers:
        try:
            monitor: DockerMonitor = DockerMonitor(server_id)
            results[server_id] = monitor.check_docker_containers()
        except Exception as error:
            results[server_id] = {
                "status": "error",
                "error": str(error)
            }

    return results


def get_docker_status(server_id: str) -> Dict[str, Any]:
    """
    Получить статус Docker контейнеров на указанном сервере.
    """
    try:
        monitor: DockerMonitor = DockerMonitor(server_id)
        return monitor.check_docker_containers()
    except Exception as error:
        logger.error(f"Ошибка в get_docker_status для {server_id}: {error}")
        return {
            "success": False,
            "error": str(error),
            "containers": []
        }


def restart_docker_container(
    server_id: str,
    container_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Перезапустить Docker контейнер или все контейнеры на сервере.
    """
    try:
        monitor: DockerMonitor = DockerMonitor(server_id)

        if container_name:
            result = monitor.restart_container(container_name)
        else:
            result = monitor.restart_all_containers()

        result["server"] = server_id
        return result

    except Exception as error:
        logger.error(f"Ошибка в restart_docker_container для {server_id}: {error}")
        return {
            "success": False,
            "error": str(error),
            "server": server_id
        }


def restart_all_servers_containers() -> Dict[str, Any]:
    """
    Перезапустить все контейнеры на всех серверах.
    """
    results: Dict[str, Any] = {}
    servers: List[str] = get_docker_server_ids()

    for server_id in servers:
        try:
            monitor: DockerMonitor = DockerMonitor(server_id)
            results[server_id] = monitor.restart_all_containers()
        except Exception as error:
            results[server_id] = {
                "success": False,
                "error": str(error)
            }

    all_success: bool = all(
        result.get("success", False)
        for result in results.values()
    )

    return {
        "success": all_success,
        "servers": results,
        "message": "Все контейнеры перезапущены" if all_success else "Были ошибки при перезапуске"
    }


def get_server_containers_list(server_id: str) -> List[str]:
    """
    Получить список контейнеров для сервера из конфигурации.
    """
    containers = get_server_containers(server_id)
    return [c.get("name", "") for c in containers if c.get("name")]
