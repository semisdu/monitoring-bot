#!/bin/bash
#
# Скрипт проверки всех SSH подключений
#

echo "🔍 Проверка всех SSH подключений"
echo "================================"

cd /home/semis/monitoring-bot/refactored

echo ""
echo "1. Проверка SSH ключа..."
if [ -f "/home/semis/.ssh/id_ed25519_monitoring" ]; then
    echo "✅ SSH ключ найден"
    chmod 600 /home/semis/.ssh/id_ed25519_monitoring 2>/dev/null
else
    echo "❌ SSH ключ не найден!"
fi

echo ""
echo "2. Проверка подключений к серверам..."
echo ""

servers=(
    "serv301:semis@serv301"
    "serv300:semis@192.168.110.70"
    "server102:semis@192.168.110.102"
    "pve-main:semis@192.168.110.99"
    "pbs-backup:root@192.168.110.37"
)

for server in "${servers[@]}"; do
    name="${server%%:*}"
    connection="${server##*:}"
    
    echo -n "   $name ($connection): "
    
    # Пробуем подключиться с SSH ключом
    if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no \
       -i /home/semis/.ssh/id_ed25519_monitoring "$connection" "echo OK" 2>/dev/null; then
        echo "✅ Доступен"
    else
        # Пробуем без ключа
        if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no \
           "$connection" "echo OK" 2>/dev/null; then
            echo "⚠  Доступен без ключа"
        else
            echo "❌ Недоступен"
        fi
    fi
done

echo ""
echo "3. Тестирование через Python модуль..."
python3 -c "
import sys
sys.path.insert(0, '.')
from config.settings import check_ssh_connection

servers = ['serv301', 'serv300', 'pve-main', 'pbs-backup', 'server102']
for server in servers:
    result = check_ssh_connection(server)
    status = '✅' if result else '❌'
    print(f'   {server}: {status} SSH доступен')
"

echo ""
echo "4. Проверка IP адресов в /etc/hosts..."
if grep -q "192.168.110" /etc/hosts; then
    echo "✅ Записи для 192.168.110.* найдены в /etc/hosts"
    grep "192.168.110" /etc/hosts
else
    echo "⚠  Записи для 192.168.110.* не найдены в /etc/hosts"
fi

echo ""
echo "📋 Итоговая конфигурация подключений:"
echo "   • serv301: serv301 (192.168.110.69) - основной сервер"
echo "   • serv300: 192.168.110.70 - резервный сервер"
echo "   • server102: 192.168.110.102 - NGINX VM (предполагаемый IP)"
echo "   • pve-main: 192.168.110.99 - Proxmox VE гипервизор"
echo "   • pbs-backup: 192.168.110.37 - Proxmox Backup Server"
echo ""
echo "🔧 Для настройки отсутствующих подключений:"
echo "   1. Проверьте правильность IP адресов"
echo "   2. Убедитесь что SSH ключ скопирован на удаленные серверы:"
echo "      ssh-copy-id -i ~/.ssh/id_ed25519_monitoring user@host"
echo "   3. Добавьте записи в /etc/hosts при необходимости"
echo "   4. Проверьте брандмауэр и сетевые настройки"
