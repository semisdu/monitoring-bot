#!/usr/bin/env python3
"""
Тест загрузки YAML конфигурации
"""

import sys
from pprint import pprint

# Добавляем путь к проекту
sys.path.insert(0, '/home/semis/monitoring-bot/refactored')

try:
    from config.loader import load_config, get_docker_servers, get_virtual_machines
    
    print("📂 Загружаем конфигурацию...")
    config = load_config()
    
    print("\n✅ Конфигурация загружена успешно!")
    print(f"📊 Telegram token: {config['telegram']['token'][:10]}...")
    print(f"👤 Admin chat ID: {config['telegram']['admin_chat_id']}")
    
    print(f"\n📡 Серверы ({len(config.get('servers', []))}):")
    for server in config.get('servers', []):
        print(f"  • {server.get('id')}: {server.get('name')}")
    
    print(f"\n🐳 Docker серверы: {get_docker_servers()}")
    print(f"💻 Виртуальные машины: {get_virtual_machines()}")
    
    print(f"\n🌐 Сайты ({len(config.get('sites', []))}):")
    for site in config.get('sites', []):
        print(f"  • {site.get('name')}: {site.get('url')}")
    
except FileNotFoundError as e:
    print(f"❌ {e}")
    print("\n📝 Скопируйте config.yml.example в config.yml:")
    print("cp config/config.yml.example config/config.yml")
except Exception as e:
    print(f"❌ Ошибка: {e}")
