#!/usr/bin/env python3
"""
Тестирование всей инфраструктуры
"""

import sys
sys.path.insert(0, '.')

from config.settings import (
    get_all_servers, 
    get_infrastructure_servers,
    get_application_servers,
    get_virtual_machines,
    get_ssh_command
)
from checks.servers import get_server_checker

def test_all_servers():
    """Протестировать все серверы"""
    print("🔍 ТЕСТИРОВАНИЕ ВСЕЙ ИНФРАСТРУКТУРЫ")
    print("=" * 60)
    
    checker = get_server_checker()
    
    # 1. Серверы приложений
    print("\n🚀 СЕРВЕРЫ ПРИЛОЖЕНИЙ:")
    app_servers = get_application_servers()
    for server_id in app_servers:
        print(f"\n📡 {server_id}:")
        status = checker.check_remote_server(server_id)
        
        if status.get('status') == 'online':
            print(f"   ✅ Онлайн - {status.get('name')}")
            disk = status.get('disk', {})
            memory = status.get('memory', {})
            cpu = status.get('cpu', {})
            print(f"      Диск: {disk.get('percent', 0)}% ({disk.get('free_gb', 0):.1f} GB свободно)")
            print(f"      Память: {memory.get('percent', 0)}% ({memory.get('free_gb', 0):.1f} GB свободно)")
            print(f"      CPU: {cpu.get('percent', 0)}%")
        else:
            print(f"   ❌ Оффлайн - {status.get('error', 'Unknown error')}")
    
    # 2. Виртуальные машины
    print("\n💻 ВИРТУАЛЬНЫЕ МАШИНЫ:")
    vm_servers = get_virtual_machines()
    for server_id in vm_servers:
        print(f"\n🖥  {server_id}:")
        status = checker.check_remote_server(server_id)
        
        if status.get('status') == 'online':
            print(f"   ✅ Онлайн - {status.get('name')}")
            disk = status.get('disk', {})
            print(f"      Диск: {disk.get('percent', 0)}% ({disk.get('free_gb', 0):.1f} GB свободно)")
            
            # Проверяем NGINX на server102
            if server_id == "server102":
                try:
                    ssh_cmd = get_ssh_command(server_id)
                    import subprocess
                    nginx_check = f"{ssh_cmd} 'systemctl is-active nginx'"
                    result = subprocess.run(nginx_check, shell=True, capture_output=True, text=True)
                    if "active" in result.stdout:
                        print("      🎯 NGINX: активен")
                    else:
                        print(f"      ⚠  NGINX: {result.stdout.strip()}")
                except:
                    print("      ⚠  NGINX: проверка не удалась")
        else:
            print(f"   ❌ Оффлайн - {status.get('error', 'Unknown error')}")
    
    # 3. Инфраструктурные серверы
    print("\n🏗  ИНФРАСТРУКТУРНЫЕ СЕРВЕРЫ:")
    infra_servers = get_infrastructure_servers()
    for server_id in infra_servers:
        print(f"\n⚙  {server_id}:")
        status = checker.check_remote_server(server_id)
        
        if status.get('status') == 'online':
            server_info = get_server_info(server_id)
            print(f"   ✅ Онлайн - {status.get('name')}")
            print(f"      Роль: {server_info.get('role', 'Unknown')}")
            print(f"      Тип: {server_info.get('type', 'Unknown')}")
            
            # Специфичные проверки
            if server_id == "pve-main":
                print("      📊 Proxmox VE: доступен через SSH")
            elif server_id == "pbs-backup":
                print("      💾 Proxmox Backup Server: доступен через SSH")
        else:
            print(f"   ❌ Оффлайн - {status.get('error', 'Unknown error')}")
    
    # 4. Сводка
    print("\n" + "=" * 60)
    print("📊 СВОДКА:")
    print(f"   Всего серверов: {len(get_all_servers())}")
    print(f"   Серверы приложений: {len(app_servers)}")
    print(f"   Виртуальные машины: {len(vm_servers)}")
    print(f"   Инфраструктурные серверы: {len(infra_servers)}")
    print("=" * 60)

def get_server_info(server_id):
    """Вспомогательная функция"""
    from config.settings import SERVERS
    return SERVERS.get(server_id, {})

if __name__ == "__main__":
    test_all_servers()
