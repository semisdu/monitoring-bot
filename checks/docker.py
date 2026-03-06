#!/usr/bin/env python3
"""
Модуль для мониторинга Docker контейнеров
"""

import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Константы
SSH_TIMEOUT = 30
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
        from config.settings import SERVERS, DOCKER_CONFIG
        
        self.server_id: str = server_id
        self.server_info: Dict[str, Any] = SERVERS.get(server_id, {})
        self.docker_config: Dict[str, Any] = DOCKER_CONFIG.get(server_id, {})
        
        # Параметры подключения
        self.ssh_key: Optional[str] = self.server_info.get('ssh_key_path')
        self.user: str = self.server_info.get('user', DEFAULT_USER)
        self.host: str = self.server_info.get('host') or self.server_info.get('ip', '')
        self.port: int = self.server_info.get('port', DEFAULT_SSH_PORT)
        
    def check_connection(self) -> bool:
        """Проверить подключение к серверу."""
        result: Dict[str, Any] = self._run_ssh_command("echo 'connection_test'")
        return result.get("success", False)
    
    def _run_ssh_command(self, command: str) -> Dict[str, Any]:
        """
        Выполнить команду через SSH.
        
        Args:
            command: Команда для выполнения
            
        Returns:
            Dict с результатами выполнения
        """
        try:
            ssh_cmd: str = (
                f"ssh -p {self.port} -i {self.ssh_key} "
                f"{self.user}@{self.host} '{command}'"
            )
            
            result = subprocess.run(
                ssh_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=SSH_TIMEOUT
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "SSH timeout"}
        except Exception as error:
            return {"success": False, "error": str(error)}
    
    def _parse_container_line(self, line: str) -> Optional[Dict[str, str]]:
        """
        Распарсить строку с информацией о контейнере.
        
        Args:
            line: Строка вида "name|status|image"
            
        Returns:
            Словарь с данными контейнера или None
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
        
        Args:
            status: Строка статуса из Docker
            
        Returns:
            Кортеж (running, restarting, exited)
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
        
        Returns:
            "critical", "warning" или "ok"
        """
        if exited and critical:
            return "critical"
        if exited or restarting:
            return "warning"
        return "ok"
    
    def check_docker_containers(self) -> Dict[str, Any]:
        """
        Проверить статус Docker контейнеров.
        
        Returns:
            Dict со статусами всех контейнеров
        """
        try:
            # Проверка доступности Docker
            docker_check: Dict[str, Any] = self._run_ssh_command("docker --version")
            if not docker_check.get("success"):
                return {
                    "status": "error",
                    "error": f"Docker не установлен: {docker_check.get('error', 'Unknown error')}",
                    "containers": []
                }
            
            # Получение списка контейнеров
            containers_result: Dict[str, Any] = self._run_ssh_command(
                'docker ps -a --format "{{.Names}}|{{.Status}}|{{.Image}}"'
            )
            
            if not containers_result.get("success"):
                return {
                    "status": "error",
                    "error": f"Не удалось получить список контейнеров: {containers_result.get('stderr', 'Unknown error')}",
                    "containers": []
                }
            
            # Парсим список всех контейнеров
            all_containers: List[Dict[str, str]] = []
            for line in containers_result.get("output", "").strip().split('\n'):
                container_data = self._parse_container_line(line)
                if container_data:
                    all_containers.append(container_data)
            
            # Мониторим только контейнеры из конфигурации
            monitored_containers: List[Dict[str, Any]] = self.docker_config.get("containers", [])
            container_statuses: List[Dict[str, Any]] = []
            
            for container_config in monitored_containers:
                status = self._check_single_container(
                    container_config,
                    all_containers
                )
                container_statuses.append(status)
            
            # Статистика
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
        all_containers: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Проверить отдельный контейнер.
        
        Args:
            container_config: Конфигурация контейнера
            all_containers: Список всех контейнеров на сервере
            
        Returns:
            Статус контейнера
        """
        container_name: str = container_config.get("name")
        critical: bool = container_config.get("critical", False)
        service_name: str = container_config.get("service_name", container_name)
        
        # Ищем контейнер в списке
        for container in all_containers:
            if container.get("name") == container_name:
                return self._process_found_container(
                    container, container_name, critical, service_name
                )
        
        # Контейнер не найден
        return self._process_missing_container(
            container_name, critical, service_name
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
        
        Args:
            container: Данные контейнера
            container_name: Имя контейнера
            critical: Критичность
            service_name: Имя сервиса
            
        Returns:
            Статус контейнера
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
        service_name: str
    ) -> Dict[str, Any]:
        """
        Обработать отсутствующий контейнер.
        
        Args:
            container_name: Имя контейнера
            critical: Критичность
            service_name: Имя сервиса
            
        Returns:
            Статус контейнера с ошибкой
        """
        # Проверяем, существует ли вообще контейнер
        check_exists: Dict[str, Any] = self._run_ssh_command(
            f"docker inspect {container_name} 2>/dev/null || echo 'NOT_FOUND'"
        )
        exists: bool = "NOT_FOUND" not in check_exists.get("output", "")
        
        return {
            "name": container_name,
            "status": "Not found" if not exists else "Unknown",
            "running": False,
            "restarting": False,
            "exited": True,
            "critical": critical,
            "service_name": service_name,
            "alert": "critical",
            "error": "Container not found" if not exists else "Status unknown"
        }
    
    def _build_status_report(self, container_statuses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Сформировать отчёт о статусе контейнеров.
        
        Args:
            container_statuses: Список статусов контейнеров
            
        Returns:
            Полный отчёт
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
        
        Args:
            container_name: Имя контейнера
            
        Returns:
            Результат операции
        """
        try:
            result: Dict[str, Any] = self._run_ssh_command(f"docker restart {container_name}")
            
            base_result: Dict[str, Any] = {
                "success": result.get("success", False),
                "container": container_name,
                "output": result.get("output", "")
            }
            
            if result.get("success"):
                base_result["message"] = f"Контейнер {container_name} успешно перезапущен"
            else:
                base_result["error"] = (
                    f"Ошибка при перезапуске контейнера {container_name}: "
                    f"{result.get('error', 'Неизвестная ошибка')}"
                )
            
            return base_result
            
        except Exception as error:
            return {
                "success": False,
                "error": f"Исключение при перезапуске контейнера {container_name}: {str(error)}",
                "container": container_name
            }
    
    def restart_all_containers(self) -> Dict[str, Any]:
        """
        Перезапустить все Docker контейнеры на сервере.
        
        Returns:
            Результат операции
        """
        try:
            if not self.check_connection():
                return {"success": False, "error": "Не удалось подключиться к серверу"}
            
            result: Dict[str, Any] = self._run_ssh_command("docker restart $(docker ps -q)")
            
            base_result: Dict[str, Any] = {
                "success": result.get("success", False),
                "output": result.get("output", "")
            }
            
            if result.get("success"):
                base_result["message"] = f"Все контейнеры на сервере {self.server_id} успешно перезапущены"
            else:
                base_result["error"] = (
                    f"Ошибка при перезапуске контейнеров: "
                    f"{result.get('error', 'Неизвестная ошибка')}"
                )
            
            return base_result
            
        except Exception as error:
            return {
                "success": False,
                "error": f"Исключение при перезапуске контейнеров: {str(error)}"
            }


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_docker_monitor(server_id: str) -> DockerMonitor:
    """Получить экземпляр монитора Docker для сервера."""
    return DockerMonitor(server_id)


def check_all_docker_servers() -> Dict[str, Any]:
    """
    Проверить Docker на всех серверах.
    
    Returns:
        Словарь с результатами для каждого сервера
    """
    from config.settings import get_docker_servers
    
    results: Dict[str, Any] = {}
    all_servers: List[str] = get_docker_servers()
    
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
    
    Args:
        server_id: Идентификатор сервера
        
    Returns:
        Статус Docker контейнеров
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
    
    Args:
        server_id: Идентификатор сервера
        container_name: Имя контейнера (если None - перезапустить все)
        
    Returns:
        Результат операции
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
    
    Returns:
        Сводный результат по всем серверам
    """
    from config.settings import get_docker_servers
    
    results: Dict[str, Any] = {}
    servers: List[str] = get_docker_servers()
    
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
    
    Args:
        server_id: Идентификатор сервера
        
    Returns:
        Список имён контейнеров
    """
    from config.settings import DOCKER_CONFIG
    
    server_config: Dict[str, Any] = DOCKER_CONFIG.get(server_id, {})
    containers: List[Dict[str, Any]] = server_config.get("containers", [])
    
    return [
        container.get("name") 
        for container in containers 
        if container.get("name")
    ]
