#!/usr/bin/env python3
"""
Загрузчик YAML конфигурации
Универсальный доступ ко всем секциям конфига
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yml')

# Кэш для конфига, чтобы не читать файл при каждом запросе
_config_cache: Optional[Dict[str, Any]] = None

def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Загрузить конфигурацию из YAML файла.
    
    Args:
        force_reload: Принудительно перечитать файл, игнорируя кэш
    
    Returns:
        Словарь с полной конфигурацией

    Raises:
        FileNotFoundError: если config.yml не найден
    """
    global _config_cache
    
    if not force_reload and _config_cache is not None:
        return _config_cache
        
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"❌ Конфигурационный файл не найден: {CONFIG_PATH}\n"
            f"Скопируйте config.yml.example в config.yml и заполните своими данными"
        )

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    _config_cache = config
    return config


def reload_config() -> Dict[str, Any]:
    """Принудительно перезагрузить конфигурацию"""
    return load_config(force_reload=True)


# ==================== БАЗОВЫЕ СЕКЦИИ ====================

def get_telegram_config() -> Dict[str, Any]:
    """Получить настройки Telegram"""
    config = load_config()
    return config.get('telegram', {})


def get_telegram_token() -> str:
    """Получить токен Telegram бота"""
    return get_telegram_config().get('token', '')


def get_admin_chat_id() -> int:
    """Получить ID администратора для уведомлений"""
    return get_telegram_config().get('admin_chat_id', 0)


def get_paths_config() -> Dict[str, str]:
    """Получить настройки путей"""
    config = load_config()
    return config.get('paths', {})


def get_ssh_keys_path() -> str:
    """Получить путь к директории с SSH ключами"""
    paths = get_paths_config()
    return paths.get('ssh_keys', '')


def find_ssh_key(key_name: str) -> Optional[str]:
    """
    Умный поиск SSH ключа в разных местах.
    
    Args:
        key_name: Имя файла ключа (например, "id_ed25519")
    
    Returns:
        Полный путь к ключу или None, если не найден
    """
    if not key_name:
        return None
    
    # 1. Проверяем по указанному в конфиге пути
    ssh_keys_path = get_ssh_keys_path()
    if ssh_keys_path:
        expanded_path = os.path.expanduser(ssh_keys_path)
        full_path = os.path.join(expanded_path, key_name)
        if os.path.exists(full_path):
            return full_path
    
    # 2. Проверяем в стандартной ~/.ssh/
    home_ssh = os.path.expanduser(f"~/.ssh/{key_name}")
    if os.path.exists(home_ssh):
        return home_ssh
    
    # 3. Проверяем в текущей директории
    local_path = os.path.join(os.getcwd(), key_name)
    if os.path.exists(local_path):
        return local_path
    
    # 4. Проверяем в директории проекта
    project_path = os.path.join(os.path.dirname(__file__), '..', 'keys', key_name)
    if os.path.exists(project_path):
        return project_path
    
    return None


def get_full_ssh_key_path(key_name: str) -> str:
    """
    Получить полный путь к SSH ключу по имени файла.
    Если ключ не найден, возвращает просто имя (для обратной совместимости).
    
    Args:
        key_name: Имя файла ключа
    
    Returns:
        Полный путь к ключу или просто имя, если не найден
    """
    found_path = find_ssh_key(key_name)
    if found_path:
        return found_path
    
    # Если не нашли, пробуем подставить в стандартный путь
    return os.path.expanduser(f"~/.ssh/{key_name}")


def get_features() -> Dict[str, bool]:
    """Получить настройки функций (включено/выключено)"""
    config = load_config()
    return config.get('features', {})


def get_schedule() -> Dict[str, str]:
    """Получить расписание проверок"""
    config = load_config()
    return config.get('schedule', {})


def get_alert_config() -> Dict[str, Any]:
    """Получить настройки алертов (пороги и т.д.)"""
    config = load_config()
    return config.get('alert_config', {})


def get_logging_config() -> Dict[str, Any]:
    """Получить настройки логирования"""
    config = load_config()
    return config.get('logging', {})


# ==================== СЕРВЕРЫ ====================

def get_all_servers() -> List[Dict[str, Any]]:
    """Получить список всех серверов"""
    config = load_config()
    return config.get('servers', [])


def get_server_config(server_id: str) -> Optional[Dict[str, Any]]:
    """
    Получить конфигурацию конкретного сервера.

    Args:
        server_id: ID сервера

    Returns:
        Конфигурация сервера или None
    """
    servers = get_all_servers()
    for server in servers:
        if server.get('id') == server_id:
            return server
    return None


def get_servers_by_type(server_type: str) -> List[Dict[str, Any]]:
    """
    Получить серверы определённого типа
    
    Args:
        server_type: Тип сервера ('vm', 'pve', 'pbs')
    
    Returns:
        Список серверов указанного типа
    """
    servers = get_all_servers()
    return [s for s in servers if s.get('type') == server_type]


def get_server_ids_by_type(server_type: str) -> List[str]:
    """
    Получить ID серверов определённого типа
    
    Args:
        server_type: Тип сервера ('vm', 'pve', 'pbs')
    
    Returns:
        Список ID серверов указанного типа
    """
    return [s['id'] for s in get_servers_by_type(server_type)]


def get_application_servers() -> List[Dict[str, Any]]:
    """Получить серверы приложений (тип 'vm')"""
    return get_servers_by_type('vm')


def get_application_server_ids() -> List[str]:
    """Получить ID серверов приложений"""
    return get_server_ids_by_type('vm')


def get_infrastructure_servers() -> List[Dict[str, Any]]:
    """Получить инфраструктурные серверы (PVE и PBS)"""
    servers = get_all_servers()
    return [s for s in servers if s.get('type') in ['pve', 'pbs']]


def get_infrastructure_server_ids() -> List[str]:
    """Получить ID инфраструктурных серверов"""
    return [s['id'] for s in get_infrastructure_servers()]


def get_pve_servers() -> List[Dict[str, Any]]:
    """Получить PVE серверы"""
    return get_servers_by_type('pve')


def get_pve_server_ids() -> List[str]:
    """Получить ID PVE серверов"""
    return get_server_ids_by_type('pve')


def get_pbs_servers() -> List[Dict[str, Any]]:
    """Получить PBS серверы"""
    return get_servers_by_type('pbs')


def get_pbs_server_ids() -> List[str]:
    """Получить ID PBS серверов"""
    return get_server_ids_by_type('pbs')


def get_docker_servers() -> List[Dict[str, Any]]:
    """
    Получить серверы с Docker.
    
    Returns:
        Список серверов, у которых включен Docker
    """
    servers = get_all_servers()
    return [s for s in servers if s.get('docker_enabled', False)]


def get_docker_server_ids() -> List[str]:
    """Получить ID серверов с Docker"""
    return [s['id'] for s in get_docker_servers()]


def get_server_containers(server_id: str) -> List[Dict[str, Any]]:
    """
    Получить список контейнеров для конкретного сервера
    
    Args:
        server_id: ID сервера
    
    Returns:
        Список контейнеров или пустой список
    """
    server = get_server_config(server_id)
    if server:
        return server.get('containers', [])
    return []


# ==================== ВИРТУАЛЬНЫЕ МАШИНЫ ====================

def get_virtual_machines() -> List[Dict[str, Any]]:
    """
    Получить список всех виртуальных машин с детальной информацией
    
    Returns:
        Список VM из секции virtual_machines
    """
    config = load_config()
    return config.get('virtual_machines', [])


def get_virtual_machine(vm_id: str) -> Optional[Dict[str, Any]]:
    """
    Получить информацию о конкретной виртуальной машине
    
    Args:
        vm_id: ID виртуальной машины (например, "vm101-nextcloud")
    
    Returns:
        Информация о VM или None
    """
    vms = get_virtual_machines()
    for vm in vms:
        if vm.get('id') == vm_id:
            return vm
    return None


def get_virtual_machines_by_server(server_id: str) -> List[Dict[str, Any]]:
    """
    Получить все VM, принадлежащие конкретному серверу PVE
    
    Args:
        server_id: ID PVE сервера
    
    Returns:
        Список VM на этом PVE
    """
    vms = get_virtual_machines()
    return [vm for vm in vms if vm.get('server_id') == server_id]


def get_virtual_machine_ids() -> List[str]:
    """Получить список ID всех виртуальных машин"""
    return [vm['id'] for vm in get_virtual_machines()]


def is_critical_vm(vm_id: str) -> bool:
    """
    Проверить, является ли VM критической
    
    Args:
        vm_id: ID виртуальной машины
    
    Returns:
        True если критическая, False в противном случае
    """
    vm = get_virtual_machine(vm_id)
    return vm.get('critical', False) if vm else False


# ==================== БЭКАПЫ ====================

def get_backup_jobs() -> List[Dict[str, Any]]:
    """
    Получить список заданий бэкапов
    
    Returns:
        Список заданий бэкапов из секции backup_jobs
    """
    config = load_config()
    return config.get('backup_jobs', [])


def get_backup_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Получить конкретное задание бэкапа
    
    Args:
        job_id: ID задания бэкапа
    
    Returns:
        Задание бэкапа или None
    """
    jobs = get_backup_jobs()
    for job in jobs:
        if job.get('id') == job_id:
            return job
    return None


def get_backup_jobs_for_server(server_id: str) -> List[Dict[str, Any]]:
    """
    Получить задания бэкапа для конкретного PBS сервера
    
    Args:
        server_id: ID PBS сервера
    
    Returns:
        Список заданий бэкапа на этом сервере
    """
    jobs = get_backup_jobs()
    return [job for job in jobs if job.get('server_id') == server_id]


def get_vms_in_backup_jobs() -> List[int]:
    """
    Получить список всех VM, которые участвуют в бэкапах
    
    Returns:
        Список VMID
    """
    jobs = get_backup_jobs()
    vms = []
    for job in jobs:
        vms.extend(job.get('vms', []))
    return list(set(vms))  # уникальные значения


# ==================== МОНИТОРИНГ ЛОГОВ ====================

def get_log_monitoring_config() -> Dict[str, Any]:
    """
    Получить конфигурацию мониторинга логов
    
    Returns:
        Настройки мониторинга логов из секции log_monitoring
    """
    config = load_config()
    return config.get('log_monitoring', {})


def is_log_monitoring_enabled() -> bool:
    """Проверить, включён ли мониторинг логов"""
    return get_log_monitoring_config().get('enabled', False)


def get_log_paths() -> Dict[str, List[str]]:
    """
    Получить пути к логам для каждого сервера
    
    Returns:
        Словарь {server_id: [список путей к логам]}
    """
    return get_log_monitoring_config().get('log_paths', {})


def get_log_paths_for_server(server_id: str) -> List[str]:
    """
    Получить пути к логам для конкретного сервера
    
    Args:
        server_id: ID сервера
    
    Returns:
        Список путей к логам или пустой список
    """
    paths = get_log_paths()
    return paths.get(server_id, [])


def get_critical_patterns() -> List[str]:
    """
    Получить список критических паттернов для поиска в логах
    
    Returns:
        Список regex паттернов
    """
    return get_log_monitoring_config().get('critical_patterns', [])


def get_log_check_interval() -> int:
    """Получить интервал проверки логов в секундах"""
    return get_log_monitoring_config().get('check_interval', 300)


def get_log_alert_cooldown() -> int:
    """Получить время охлаждения алертов по логам в секундах"""
    return get_log_monitoring_config().get('alert_cooldown', 3600)


# ==================== САЙТЫ ====================

def get_sites() -> List[Dict[str, Any]]:
    """Получить список сайтов для мониторинга"""
    config = load_config()
    return config.get('sites', [])


def get_sites_by_server(server_id: str) -> List[Dict[str, Any]]:
    """
    Получить сайты, привязанные к конкретному серверу
    
    Args:
        server_id: ID сервера
    
    Returns:
        Список сайтов на этом сервере
    """
    sites = get_sites()
    return [site for site in sites if site.get('server_id') == server_id]


def get_external_sites() -> List[Dict[str, Any]]:
    """Получить внешние сайты (не привязанные к серверу)"""
    sites = get_sites()
    return [site for site in sites if site.get('type') == 'external']
