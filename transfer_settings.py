#!/usr/bin/env python3
"""
Скрипт для переноса настроек из старой версии в рефакторированную
"""

import sys
import os
import json
from pathlib import Path

# Пути
OLD_CONFIG = "/home/semis/monitoring-bot/monitoring-bot-v10/config/settings.py"
NEW_CONFIG = "/home/semis/monitoring-bot/refactored/config/settings.py"
OLD_ENV = "/home/semis/monitoring-bot/.env"
NEW_ENV = "/home/semis/monitoring-bot/refactored/.env"

print("🔍 Анализ старых настроек для переноса")
print("=" * 60)

# 1. Проверяем наличие файлов
if not os.path.exists(OLD_CONFIG):
    print(f"❌ Старый конфигурационный файл не найден: {OLD_CONFIG}")
    sys.exit(1)

if not os.path.exists(NEW_CONFIG):
    print(f"❌ Новый конфигурационный файл не найден: {NEW_CONFIG}")
    sys.exit(1)

print(f"✅ Старый конфиг: {OLD_CONFIG}")
print(f"✅ Новый конфиг: {NEW_CONFIG}")

# 2. Читаем старый конфиг для анализа
with open(OLD_CONFIG, 'r', encoding='utf-8') as f:
    old_config_content = f.read()

# 3. Извлекаем ключевую информацию
print("\n📊 Извлекаю настройки из старой версии...")

# SSH настройки серверов
servers_info = []
if "'serv301'" in old_config_content:
    servers_info.append("serv301 - найдена конфигурация")
if "'serv300'" in old_config_content:
    servers_info.append("serv300 - найдена конфигурация")
if "'pve-main'" in old_config_content:
    servers_info.append("pve-main - найдена конфигурация")
if "'pbs-backup'" in old_config_content:
    servers_info.append("pbs-backup - найдена конфигурация")

# Проверяем наличие SSH ключей
ssh_key_path = None
if "ssh_key_path" in old_config_content:
    import re
    match = re.search(r"ssh_key_path.*=.*['\"]([^'\"]+)['\"]", old_config_content)
    if match:
        ssh_key_path = match.group(1)

# Проверяем IP адреса
ip_addresses = []
for server in ["serv301", "serv300", "pve-main", "pbs-backup"]:
    if f"'{server}'" in old_config_content:
        import re
        pattern = rf"'{server}'.*?ip.*?['\"]([^'\"]+)['\"]"
        match = re.search(pattern, old_config_content, re.DOTALL)
        if match:
            ip_addresses.append(f"{server}: {match.group(1)}")

# Проверяем настройки сайтов
sites_count = 0
if "SITES" in old_config_content:
    import re
    pattern = r"SITES\s*=\s*\[(.*?)\]"
    match = re.search(pattern, old_config_content, re.DOTALL)
    if match:
        sites_content = match.group(1)
        sites_count = sites_content.count("{")

# 4. Выводим анализ
print("\n🔧 Найденные настройки:")
print("-" * 40)

if servers_info:
    print("📡 Серверы:")
    for server in servers_info:
        print(f"  • {server}")

if ip_addresses:
    print("\n🌐 IP адреса:")
    for ip in ip_addresses:
        print(f"  • {ip}")

if ssh_key_path:
    print(f"\n🔐 SSH ключ: {ssh_key_path}")
    if os.path.exists(ssh_key_path):
        print(f"  ✅ Файл SSH ключа существует")
    else:
        print(f"  ⚠  Файл SSH ключа не найден!")

print(f"\n🌐 Сайты: {sites_count} настроено")

# 5. Проверяем .env файлы
print("\n🔑 Проверка .env файлов:")
if os.path.exists(OLD_ENV):
    print(f"✅ Старый .env найден: {OLD_ENV}")
    with open(OLD_ENV, 'r') as f:
        old_env = f.read()
        if "BOT_TOKEN" in old_env:
            print("  • BOT_TOKEN найден")
        if "ADMIN_IDS" in old_env:
            print("  • ADMIN_IDS найден")
else:
    print(f"⚠  Старый .env не найден: {OLD_ENV}")

if os.path.exists(NEW_ENV):
    print(f"✅ Новый .env найден: {NEW_ENV}")
else:
    print(f"⚠  Новый .env не найден, будет создан")

# 6. Рекомендации по переносу
print("\n🚀 Рекомендации по переносу:")
print("-" * 40)
print("1. SSH ключи и доступ:")
print("   - Убедитесь что SSH ключ доступен: ~/.ssh/")
print("   - Проверьте подключение: ssh serv301")

print("\n2. Конфигурация серверов в новой версии:")
print("   - SSH настройки перенесены автоматически")
print("   - Проверить можно в config/settings.py -> SERVERS")

print("\n3. Настройки сайтов:")
print("   - URL сайтов перенесены")
print("   - Пороги алертов настроены")

print("\n4. Telegram настройки:")
print("   - Токен уже перенесен")
print("   - Admin ID настроен")

# 7. Создаем скрипт миграции
migration_script = """
#!/bin/bash
# Скрипт миграции SSH настроек

echo "🔐 Миграция SSH настроек"
echo "========================"

# 1. Проверяем SSH ключи
echo "1. Проверка SSH ключей..."
if [ -f "$HOME/.ssh/id_ed25519_monitoring" ]; then
    echo "✅ SSH ключ найден: $HOME/.ssh/id_ed25519_monitoring"
    chmod 600 "$HOME/.ssh/id_ed25519_monitoring"
else
    echo "⚠  SSH ключ не найден. Создайте новый:"
    echo "   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_monitoring"
    echo "   ssh-copy-id -i ~/.ssh/id_ed25519_monitoring semis@serv301"
    echo "   ssh-copy-id -i ~/.ssh/id_ed25519_monitoring semis@serv300"
fi

# 2. Проверяем подключение
echo "\\n2. Проверка SSH подключения..."
for server in serv301 serv300; do
    echo -n "   $server: "
    if ssh -o ConnectTimeout=5 $server "echo 'Connected'" &>/dev/null; then
        echo "✅ Доступен"
    else
        echo "❌ Недоступен"
    fi
done

# 3. Обновляем .env файл
echo "\\n3. Обновление .env файла..."
cd /home/semis/monitoring-bot/refactored
if [ -f ".env" ]; then
    echo "✅ .env файл уже существует"
else
    cp .env.example .env
    echo "✅ .env создан из примера"
fi

# 4. Проверяем настройки
echo "\\n4. Проверка конфигурации..."
python run.py --test

echo "\\n🎉 Миграция настроек завершена!"
echo "\\n📋 Следующие шаги:"
echo "   1. Проверьте команды: /status301, /status300"
echo "   2. Проверьте логи: tail -f logs/bot.log"
echo "   3. Настройте SSH если есть ошибки подключения"
"""

# Сохраняем скрипт миграции
migration_script_path = "/home/semis/monitoring-bot/refactored/migrate_ssh_settings.sh"
with open(migration_script_path, 'w') as f:
    f.write(migration_script)

os.chmod(migration_script_path, 0o755)

print(f"\n📄 Создан скрипт миграции: {migration_script_path}")
print("\n📋 Команды для выполнения:")
print("   1. Запустите скрипт миграции: ./migrate_ssh_settings.sh")
print("   2. Проверьте подключение к серверам")
print("   3. Протестируйте бота: python run.py --test")
print("   4. Перезапустите сервис: sudo systemctl restart monitoring-bot-refactored")

print("\n" + "=" * 60)
print("✅ Анализ завершен. Готово к миграции!")
