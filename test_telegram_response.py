#!/usr/bin/env python3
"""
Тестирование ответов бота на команды
"""
import sys
sys.path.insert(0, '.')

from checks.servers import get_server_checker
from config.settings import get_all_servers

def test_server_responses():
    """Тестирование ответов которые бот должен отправлять"""
    print("🤖 Тестирование ответов бота")
    print("=" * 50)
    
    checker = get_server_checker()
    
    # 1. Тест SERV301
    print("\n1. 📍 SERV301:")
    try:
        status = checker.check_remote_server("serv301")
        if status.get("status") == "online":
            disk = status.get("disk", {})
            memory = status.get("memory", {})
            cpu = status.get("cpu", {})
            
            print("   ✅ Онлайн")
            print(f"   Диск: {disk.get('percent', 0)}% ({disk.get('free_gb', 0):.1f} GB свободно)")
            print(f"   Память: {memory.get('percent', 0)}% ({memory.get('free_gb', 0):.1f} GB свободно)")
            print(f"   CPU: {cpu.get('percent', 0)}%")
        else:
            print(f"   ❌ Оффлайн: {status.get('error')}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 2. Тест всех серверов
    print("\n2. 🌐 Все серверы:")
    all_servers = get_all_servers()
    online_count = 0
    
    for server_id in all_servers:
        try:
            status = checker.check_remote_server(server_id)
            if status.get("status") == "online":
                online_count += 1
                print(f"   ✅ {server_id}: Онлайн")
            else:
                print(f"   ❌ {server_id}: Оффлайн")
        except Exception as e:
            print(f"   ❌ {server_id}: Ошибка - {str(e)[:50]}")
    
    print(f"\n📈 Итог: {online_count}/{len(all_servers)} серверов онлайн")
    
    # 3. Тест форматирования сообщений
    print("\n3. 📝 Тест форматирования сообщений:")
    test_status = {
        'status': 'online',
        'name': 'TEST SERVER',
        'disk': {'percent': 45, 'free_gb': 50.5, 'alert': 'ok'},
        'memory': {'percent': 65, 'free_gb': 8.2, 'alert': 'warning'},
        'cpu': {'percent': 25, 'alert': 'ok'},
        'uptime': '15 days, 3:45:21'
    }
    
    from bot.handlers import format_server_status
    formatted = format_server_status(test_status, 70107570)
    print("   Пример форматированного сообщения:")
    print("   " + "=" * 40)
    for line in formatted.split('\n'):
        print(f"   {line}")
    print("   " + "=" * 40)

if __name__ == "__main__":
    test_server_responses()
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
    print("\n📱 Теперь протестируйте бота в Telegram:")
    print("   1. Отправьте /start")
    print("   2. Нажмите 'Меню'")
    print("   3. Выберите 'Статус серверов'")
    print("   4. Проверьте любой сервер")
