#!/usr/bin/env python3
"""
Загрузчик YAML конфигурации
"""

import os
import yaml
from typing import Dict, Any, Optional

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yml')

def load_config() -> Dict[str, Any]:
    """
    Загрузить конфигурацию из YAML файла.
    
    Returns:
        Словарь с конфигурацией
    
    Raises:
        FileNotFoundError: если config.yml не найден
    """
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"❌ Конфигурационный файл не найден: {CONFIG_PATH}\n"
            f"Скопируйте config.yml.example в config.yml и заполните своими данными"
        )
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def get_server_config(server_id: str) -> Optional[Dict[str, Any]]:
    """
    Получить конфигурацию конкретного сервера.
    
    Args:
        server_id: ID сервера
        
    Returns:
        Конфигурация сервера или None
    """
    config = load_config()
    servers = config.get('servers', [])
    
    for server in servers:
        if server.get('id') == server_id:
            return server
    
    return None


def get_docker_servers() -> list:
    """
    Получить список серверов с Docker.
    
    Returns:
        Список ID серверов с Docker
    """
    config = load_config()
    servers = config.get('servers', [])
    
    return [
        server['id'] for server in servers 
        if server.get('docker_enabled', False)
    ]


def get_pve_servers() -> list:
    """
    Получить список PVE серверов.
    
    Returns:
        Список ID PVE серверов
    """
    config = load_config()
    servers = config.get('servers', [])
    
    return [
        server['id'] for server in servers 
        if server.get('type') == 'pve'
    ]


def get_pbs_servers() -> list:
    """
    Получить список PBS серверов.
    
    Returns:
        Список ID PBS серверов
    """
    config = load_config()
    servers = config.get('servers', [])
    
    return [
        server['id'] for server in servers 
        if server.get('type') == 'pbs'
    ]


def get_virtual_machines() -> list:
    """
    Получить список виртуальных машин.
    
    Returns:
        Список ID VM
    """
    config = load_config()
    servers = config.get('servers', [])
    
    return [
        server['id'] for server in servers 
        if server.get('type') == 'vm'
    ]
