# 📋 Руководство по миграции на рефакторированную версию

## Обзор изменений

### 🎯 Что улучшено:
1. **Чистая архитектура** - модульная структура, разделение ответственности
2. **Централизованная конфигурация** - все настройки в `config/settings.py`
3. **Мультиязычность** - поддержка русского, украинского, английского
4. **Улучшенная система версий** - автоматическое управление версиями
5. **Безопасность** - изолированное виртуальное окружение, systemd hardening
6. **Логирование** - структурированные логи с ротацией

### 🔄 Изменения в структуре:
Старая структура:                     Новая структура:
monitoring-bot-v10/                   refactored/
├── множество файлов                  ├── main.py
├── bot/                              ├── bot/
│   ├── handlers.py                   │   ├── core.py
│   ├── main.py                       │   ├── handlers.py
│   └── ...                           │   ├── language.py
├── config/                           │   └── scheduler.py
│   └── ...                           ├── config/
└── ...                               │   ├── settings.py
                                      │   └── languages.py
                                      ├── checks/
                                      │   └── servers.py
                                      └── utils/
                                          └── version.py

## 📋 Пошаговая инструкция миграции

### Этап 1: Подготовка
cd /home/semis/monitoring-bot

# 1. Убедитесь что старая версия работает
systemctl status monitoring-bot.service

# 2. Проверьте наличие рефакторированной версии
ls -la refactored/

### Этап 2: Автоматическая миграция
# Запустите скрипт миграции
cd /home/semis/monitoring-bot/refactored
./migrate_from_old.sh

### Этап 3: Ручная проверка
1. **Проверьте токен Telegram** в `.env` файле:
   cat /home/semis/monitoring-bot/refactored/.env
   
2. **Проверьте SSH доступ** к серверам:
   ssh serv301 "echo 'SSH доступ к serv301: OK'"
   ssh serv300 "echo 'SSH доступ к serv300: OK'"

3. **Протестируйте команды бота**:
   - `/start` - главное меню
   - `/status301` - проверка SERV301
   - `/status300` - проверка SERV300  
   - `/version` - информация о версии

### Этап 4: Мониторинг после миграции
# Проверьте логи
tail -f /home/semis/monitoring-bot/refactored/logs/bot.log

# Проверьте systemd сервис
sudo journalctl -u monitoring-bot-refactored.service -f

# Проверьте состояние сервиса
sudo systemctl status monitoring-bot-refactored.service

## ⚠️ Потенциальные проблемы и решения

### Проблема 1: Отсутствует SSH доступ
**Симптомы:** Команды `/status301`, `/status300` возвращают ошибки
**Решение:**
1. Проверьте SSH ключи: `ls -la ~/.ssh/`
2. Настройте SSH доступ: `ssh-copy-id semis@serv301`
3. Или настройте пароль в `.env` (менее безопасно)

### Проблема 2: Не работает мультиязычность  
**Симптомы:** Все тексты на русском, не меняется язык
**Решение:**
1. Проверьте файл `config/languages.py`
2. Проверьте БД: `ls -la database/`
3. Используйте команду `/language` для смены языка

### Проблема 3: Не запускается systemd сервис
**Симптомы:** `systemctl status` показывает ошибки
**Решение:**
# Проверьте права
sudo chown -R semis:semis /home/semis/monitoring-bot/refactored

# Проверьте виртуальное окружение
ls -la /home/semis/monitoring-bot/refactored/venv/

# Переустановите зависимости
cd /home/semis/monitoring-bot/refactored
source venv/bin/activate
pip install -r requirements.txt

# Перезапустите сервис
sudo systemctl restart monitoring-bot-refactored.service

## 🔄 Откат на старую версию

Если новая версия не работает, можно вернуться:

# 1. Остановите новую версию
sudo systemctl stop monitoring-bot-refactored.service
sudo systemctl disable monitoring-bot-refactored.service

# 2. Восстановите старый симлинк
cd /home/semis/monitoring-bot
rm current
ln -s prod/current current

# 3. Запустите старую версию
sudo systemctl start monitoring-bot.service
sudo systemctl enable monitoring-bot.service

# 4. Проверьте работу
systemctl status monitoring-bot.service

## 📞 Техническая поддержка

### Проверка работы:
1. **Базовые команды:**
   # Проверка версии
   cd /home/semis/monitoring-bot/refactored
   python run.py --version
   
   # Тестирование конфигурации
   python run.py --test


2. **Проверка зависимостей:**
   source venv/bin/activate
   pip list | grep -E "telegram|paramiko|psutil"


3. **Проверка SSH:**
   # Проверка подключения
   python -c "import paramiko; print('Paramiko version:', paramiko.__version__)"
   
   # Тест SSH подключения
   python -c "
   import paramiko
   client = paramiko.SSHClient()
   client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   try:
       client.connect('serv301', username='semis', timeout=5)
       print('SSH to serv301: OK')
       client.close()
   except Exception as e:
       print('SSH to serv301: FAILED', e)
   "

### Логи и диагностика:
- **Логи приложения:** `tail -f logs/bot.log`
- **Systemd логи:** `sudo journalctl -u monitoring-bot-refactored.service -f`
- **Логи ошибок:** `sudo journalctl -u monitoring-bot-refactored.service -p err`

## 🎯 Заключение

Рефакторированная версия предоставляет:
1. ✅ Чистый и поддерживаемый код
2. ✅ Мультиязычный интерфейс
3. ✅ Централизованную конфигурацию
4. ✅ Улучшенную безопасность
5. ✅ Автоматическое управление версиями
6. ✅ Структурированное логирование

Для успешной миграции:
1. Выполните автоматический скрипт миграции
2. Проверьте критический функционал
3. Настройте мониторинг работы
4. При необходимости используйте инструкцию по откату

**Дата миграции:** $(date)
**Версия:** v1.0.0-refactored
