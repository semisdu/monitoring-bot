#!/bin/bash
echo "🚀 Быстрая проверка Monitoring Bot"
echo "===================================="

# 1. Проверка сервиса
echo "1. Проверяем systemd сервис..."
if systemctl is-active --quiet monitoring-bot-refactored; then
    echo "   ✅ Сервис активен"
else
    echo "   ❌ Сервис не активен"
fi

# 2. Проверка SSH ключа
echo "2. Проверяем SSH ключ..."
if [ -f "/home/semis/.ssh/id_ed25519_monitoring" ]; then
    echo "   ✅ SSH ключ найден"
    echo "   👉 Разрешения: $(stat -c "%a" /home/semis/.ssh/id_ed25519_monitoring)"
else
    echo "   ❌ SSH ключ не найден"
fi

# 3. Проверка конфигурации
echo "3. Проверяем конфигурацию..."
if [ -f "/home/semis/monitoring-bot/refactored/config/settings.py" ]; then
    echo "   ✅ Конфигурационный файл найден"
    SERVERS_COUNT=$(grep -c '"host":' /home/semis/monitoring-bot/refactored/config/settings.py)
    echo "   👉 Серверов настроено: $SERVERS_COUNT"
else
    echo "   ❌ Конфигурационный файл не найден"
fi

# 4. Проверка логов
echo "4. Проверяем логи..."
if [ -f "/home/semis/monitoring-bot/refactored/logs/bot.log" ]; then
    echo "   ✅ Логи найдены"
    LOG_SIZE=$(du -h /home/semis/monitoring-bot/refactored/logs/bot.log | cut -f1)
    echo "   👉 Размер логов: $LOG_SIZE"
else
    echo "   ❌ Логи не найдены"
fi

# 5. Проверка версии Python
echo "5. Проверяем окружение..."
VENV_PYTHON=$(/home/semis/monitoring-bot/refactored/venv/bin/python --version 2>&1)
echo "   👉 $VENV_PYTHON"

echo "===================================="
echo "📊 Сводка:"
echo "Для полной проверки запустите:"
echo "  python test_infrastructure.py"
echo ""
echo "Для проверки Telegram бота:"
echo "  Отправьте команду /start в @edupost_monitor_bot"
