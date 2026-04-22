# Ротация логов

Логи ротируются через systemd logrotate.

## Конфигурация

Файл: /etc/logrotate.d/monitoring-bot

sudo cat /etc/logrotate.d/monitoring-bot

## Проверка

sudo logrotate -d /etc/logrotate.d/monitoring-bot

## Принудительная ротация

sudo logrotate -f /etc/logrotate.d/monitoring-bot
