#!/usr/bin/env python3
"""
Тестирование основных функций бота
"""
import sys
sys.path.insert(0, '.')

from checks.servers import get_server_checker
from config.settings import get_all_servers, get_application_servers, get_infrastructure_servers

def test_server_checker():
    """Тестирование проверки серверов"""
    print("🔍 Тестирование проверки серверов...")
    
    checker = get_server_checker()
    
    # 1. Проверка локального сервера
    print("\n1. 📍 Локальный сервер (SERV301):")
    try:
        local_status = checker.check_local_server()
        if local_status:
            disk = local_status.get('disk', {})
            memory = local_status.get('memory', {})
            cpu = local_status.get('cpu', {})
            print(f"   ✅ Диск: {disk.get('percent', 0)}% ({disk.get('free_gb', 0):.1f} GB свободно)")
            print(f"   ✅ Память: {memory.get('percent', 0)}% ({memory.get('free_gb', 0):.1f} GB свободно)")
            print(f"   ✅ CPU: {cpu.get('percent', 0)}%")
        else:
            print("   ❌ Ошибка при проверке локального сервера")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 2. Проверка удаленных серверов
    print("\n2. 🌐 Удаленные серверы:")
    for server_id in get_all_servers():
        if server_id != "serv301":  # Локальный уже проверили
            try:
                status = checker.check_remote_server(server_id)
                if status.get('status') == 'online':
                    disk = status.get('disk', {})
                    print(f"   ✅ {server_id}: Онлайн (Диск: {disk.get('percent', 0)}%)")
                else:
                    print(f"   ❌ {server_id}: Оффлайн - {status.get('error', 'Unknown')}")
            except Exception as e:
                print(f"   ❌ {server_id}: Ошибка - {e}")

def test_settings():
    """Тестирование настроек"""
    print("\n📋 Тестирование настроек...")
    
    all_servers = get_all_servers()
    app_servers = get_application_servers()
    infra_servers = get_infrastructure_servers()
    
    print(f"   Всего серверов: {len(all_servers)}")
    print(f"   Серверы приложений: {len(app_servers)}")
    print(f"   Инфраструктурные серверы: {len(infra_servers)}")
    
    print("\n   📍 Список серверов:")
    for server in all_servers:
        print(f"   • {server}")

if __name__ == "__main__":
    print("🚀 ТЕСТИРОВАНИЕ МОНИТОРИНГ БОТА")
    print("=" * 50)
    
    test_settings()
    test_server_checker()
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
    print("\n🤖 Для проверки Telegram бота:")
    print("   1. Отправьте /start в @edupost_monitor_bot")
    print("   2. Используйте кнопку меню для навигации")
    print("   3. Проверьте статус серверов через меню")
