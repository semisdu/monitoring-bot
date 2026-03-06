
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
echo "\n2. Проверка SSH подключения..."
for server in serv301 serv300; do
    echo -n "   $server: "
    if ssh -o ConnectTimeout=5 $server "echo 'Connected'" &>/dev/null; then
        echo "✅ Доступен"
    else
        echo "❌ Недоступен"
    fi
done

# 3. Обновляем .env файл
echo "\n3. Обновление .env файла..."
cd /home/semis/monitoring-bot/refactored
if [ -f ".env" ]; then
    echo "✅ .env файл уже существует"
else
    cp .env.example .env
    echo "✅ .env создан из примера"
fi

# 4. Проверяем настройки
echo "\n4. Проверка конфигурации..."
python run.py --test

echo "\n🎉 Миграция настроек завершена!"
echo "\n📋 Следующие шаги:"
echo "   1. Проверьте команды: /status301, /status300"
echo "   2. Проверьте логи: tail -f logs/bot.log"
echo "   3. Настройте SSH если есть ошибки подключения"
