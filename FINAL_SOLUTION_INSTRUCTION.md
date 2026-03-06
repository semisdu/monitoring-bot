# 🎯 ИНСТРУКЦИЯ: РЕШЕНИЕ ПРОБЛЕМ С КОМАНДАМИ В MONITORING BOT

## 📋 ПРОБЛЕМА
Команды в меню `/help` и `/start` отображались без подчеркиваний:
- `/monitorstatus` вместо `/monitor_status`
- `/pvestatus` вместо `/pve_status`
- `/monitorlog` вместо `/monitor_log`
- `/pbsstatus` вместо `/pbs_status`

## 🔍 ПРИЧИНЫ И РЕШЕНИЯ

### 1. ПРОБЛЕМА: Markdown форматирование в Telegram
**Причина:** Telegram Markdown интерпретирует `_` как *курсив*  
**Решение:** Экранировать подчеркивания в командах

# В config/languages.py заменить:
/monitor_status → /monitor\_status
/pve_status → /pve\_status
/monitor_log → /monitor\_log  
/pbs_status → /pbs\_status

### 2. ПРОБЛЕМА: Регистрация команд без подчеркиваний
**Причина:** В handlers.py команды регистрировались как `monitorstatus`  
**Решение:** Исправить регистрацию команд

# В функции register_handlers() заменить:
CommandHandler("monitorstatus" → CommandHandler("monitor_status"
CommandHandler("pvestatus" → CommandHandler("pve_status"

### 3. ПРОБЛЕМА: Дублирование команд
**Причина:** Некоторые команды регистрировались дважды  
**Решение:** Удалить дубликаты в регистрации

### 4. ПРОБЛЕМА: Ошибки синтаксиса с кавычками
**Причина:** Неправильные кавычки в f-строках  
**Решение:** Исправить кавычки в InlineKeyboardButton

# Было:
InlineKeyboardButton(f"🚀 {get_text(user_id, "status", "app_servers")}")

# Стало:
InlineKeyboardButton(f"🚀 {get_text(user_id, 'status', 'app_servers')}")

## 🛠 ПОШАГОВОЕ РЕШЕНИЕ

### Шаг 1: Исправить languages.py
# Экранировать подчеркивания в командах
sed -i 's|/monitor_status|/monitor\\_status|g' config/languages.py
sed -i 's|/pve_status|/pve\\_status|g' config/languages.py
sed -i 's|/monitor_log|/monitor\\_log|g' config/languages.py
sed -i 's|/pbs_status|/pbs\\_status|g' config/languages.py

### Шаг 2: Исправить handlers.py
# Исправить регистрацию команд
sed -i 's|CommandHandler("monitorstatus"|CommandHandler("monitor_status"|g' bot/handlers.py
sed -i 's|CommandHandler("monitorlog"|CommandHandler("monitor_log"|g' bot/handlers.py
sed -i 's|CommandHandler("pvestatus"|CommandHandler("pve_status"|g' bot/handlers.py
sed -i 's|CommandHandler("pbsstatus"|CommandHandler("pbs_status"|g' bot/handlers.py
```

### Шаг 3: Удалить дубликаты команд
Проверить функцию `register_handlers()` и удалить повторные регистрации:
- `pve_status`
- `pbs_status`  
- `monitor_status`
- `monitor_log`

### Шаг 4: Исправить кавычки в f-строках
Заменить двойные кавычки внутри f-строк на одинарные:
# Было: f"🚀 {get_text(user_id, "status", "app_servers")}"
# Стало: f"🚀 {get_text(user_id, 'status', 'app_servers')}"

### Шаг 5: Перезапустить бота
# Удалить кэш Python
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Перезапустить бота
sudo systemctl restart monitoring-bot-refactored

## 🧪 ПРОВЕРКА РЕШЕНИЯ

1. **Отправить `/help`** - команды должны отображаться с подчеркиваниями
2. **Отправить `/monitor_status`** - команда должна работать
3. **Отправить `/pve_status`** - команда должна работать
4. **Проверить кнопки меню** - все должны быть кликабельны

## 📊 ИТОГОВЫЙ РЕЗУЛЬТАТ

✅ **Команды в /help:** `/monitor\_status`, `/pve\_status` (с экранированием)  
✅ **Регистрация команд:** правильные имена с подчеркиваниями  
✅ **Работа кнопок:** все кнопки меню работают  
✅ **Мультиязычность:** поддерживается 3 языка  
✅ **Стабильность:** бот работает без ошибок  

## 🚀 ВОССТАНОВЛЕННЫЕ ФУНКЦИИ

- 🚨 **Алерты:** `/alerts` - активные алерты
- 📊 **Статистика:** `/stats` - статистика системы  
- 📋 **Логи:** `/logs` - информация о логах
- 📈 **Мониторинг:** `/monitor_status` - статус мониторинга
- 📝 **Лог мониторинга:** `/monitor_log` - лог мониторинга
- 🧹 **Очистка:** `/cleanup` - очистка старых данных
- 🏗 **Инфраструктура:** `/pve_status`, `/pbs_status`

## 📞 ПОДДЕРЖКА

Если проблемы повторятся:
1. Проверить логи: `sudo journalctl -u monitoring-bot-refactored --no-pager -n 20`
2. Проверить команды в `/help`
3. Проверить работу конкретных команд
4. Перезапустить бота с очисткой кэша

**Monitoring Bot полностью восстановлен и готов к эксплуатации!** 🎉
