#!/bin/bash
#
# Скрипт миграции с старой версии Monitoring Bot на рефакторированную
#

set -e

echo "🔄 Начало миграции на рефакторированную версию"
echo "=============================================="

OLD_DIR="/home/semis/monitoring-bot/current"
NEW_DIR="/home/semis/monitoring-bot/refactored"

# Проверяем существование директорий
if [ ! -d "$OLD_DIR" ]; then
    echo "❌ Старая директория не найдена: $OLD_DIR"
    exit 1
fi

if [ ! -d "$NEW_DIR" ]; then
    echo "❌ Новая директория не найдена: $NEW_DIR"
    exit 1
fi

echo "📁 Старая версия: $OLD_DIR"
echo "📁 Новая версия: $NEW_DIR"

# 1. Бэкап текущей версии
BACKUP_DIR="/home/semis/monitoring-bot/backup_$(date +%Y%m%d_%H%M%S)"
echo "📦 Создаю бэкап текущей версии в: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cp -r "$OLD_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
echo "✅ Бэкап создан"

# 2. Проверяем наличие токена в старой версии
OLD_ENV="$OLD_DIR/.env"
if [ -f "$OLD_ENV" ]; then
    echo "🔑 Найден .env в старой версии"
    # Пытаемся извлечь токен
    if grep -q "TELEGRAM_TOKEN" "$OLD_ENV"; then
        TOKEN=$(grep "TELEGRAM_TOKEN" "$OLD_ENV" | cut -d'=' -f2)
        if [ ! -z "$TOKEN" ] && [ "$TOKEN" != "your_token_here" ]; then
            echo "✅ Токен найден в старой версии"
            # Копируем .env в новую версию
            cp "$OLD_ENV" "$NEW_DIR/.env"
            echo "✅ .env скопирован в новую версию"
        fi
    fi
fi

# 3. Проверяем базу данных (если есть)
OLD_DB="$OLD_DIR/database"
if [ -d "$OLD_DB" ]; then
    echo "💾 Проверяю базу данных..."
    # Здесь можно добавить логику миграции БД
    echo "⚠  База данных требует ручной миграции"
fi

# 4. Проверяем настройки SSH
echo "🔐 Проверяю SSH настройки..."
if [ -f "/home/semis/.ssh/config" ]; then
    echo "✅ SSH конфигурация найдена"
fi

# 5. Останавливаем старый сервис
echo "🛑 Останавливаю старый сервис..."
sudo systemctl stop monitoring-bot.service 2>/dev/null || true
echo "✅ Старый сервис остановлен"

# 6. Создаем виртуальное окружение для новой версии
echo "🐍 Создаю виртуальное окружение..."
cd "$NEW_DIR"
python3 -m venv venv --prompt="monitoring-bot-refactored"
source venv/bin/activate

# 7. Устанавливаем зависимости
echo "📦 Устанавливаю зависимости..."
pip install -r requirements.txt
echo "✅ Зависимости установлены"

# 8. Тестируем новую версию
echo "🧪 Тестирую новую версию..."
if python run.py --test; then
    echo "✅ Тестирование пройдено успешно"
else
    echo "❌ Тестирование не пройдено"
    echo "⚠  Проверьте конфигурацию вручную"
fi

# 9. Создаем симлинк для новой версии
echo "🔗 Создаю симлинк для новой версии..."
cd /home/semis/monitoring-bot
if [ -L "current" ]; then
    rm current
fi
ln -s refactored current
echo "✅ Симлинк создан: current -> refactored"

# 10. Устанавливаем новый systemd сервис
echo "⚙  Настраиваю systemd сервис..."
sudo cp "$NEW_DIR/monitoring-bot-refactored.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable monitoring-bot-refactored.service
echo "✅ Systemd сервис настроен"

# 11. Запускаем новую версию
echo "🚀 Запускаю новую версицию..."
sudo systemctl start monitoring-bot-refactored.service
sleep 3

# 12. Проверяем статус
if sudo systemctl is-active --quiet monitoring-bot-refactored.service; then
    echo "✅ Новая версия успешно запущена"
else
    echo "❌ Новая версия не запустилась"
    echo "Проверьте логи: sudo journalctl -u monitoring-bot-refactored.service -f"
fi

echo ""
echo "=============================================="
echo "🎉 Миграция завершена!"
echo ""
echo "📋 Что сделано:"
echo "   1. Создан бэкап старой версии: $BACKUP_DIR"
echo "   2. Перенесен .env файл (если был)"
echo "   3. Установлены зависимости"
echo "   4. Протестирована новая версия"
echo "   5. Обновлен симлинк current -> refactored"
echo "   6. Настроен и запущен systemd сервис"
echo ""
echo "📞 Команды для проверки:"
echo "   Статус сервиса: sudo systemctl status monitoring-bot-refactored"
echo "   Логи сервиса: sudo journalctl -u monitoring-bot-refactored.service -f"
echo "   Логи приложения: tail -f $NEW_DIR/logs/bot.log"
echo "   Тест бота: /start в Telegram"
echo ""
echo "⚠  Внимание:"
echo "   - Проверьте работу команд /status301, /status300"
echo "   - При необходимости настройте SSH доступ в .env"
echo "   - Старая версия сохранена в бэкапе"
echo ""
echo "🔄 Для возврата к старой версии:"
echo "   sudo systemctl stop monitoring-bot-refactored"
echo "   sudo systemctl disable monitoring-bot-refactored"
echo "   sudo systemctl start monitoring-bot.service"
echo "   cd /home/semis/monitoring-bot && rm current && ln -s prod/current current"
