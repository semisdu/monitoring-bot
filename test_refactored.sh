#!/bin/bash
#
# Тестовый скрипт для проверки рефакторированной версии
#

echo "🧪 Тестирование рефакторированной версии Monitoring Bot"
echo "======================================================"

BASE_DIR="/home/semis/monitoring-bot/refactored"
cd "$BASE_DIR"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

echo ""
echo "1. Проверка структуры проекта..."
ERRORS=0

# Проверка основных директорий
for dir in bot checks config utils logs database; do
    if [ -d "$dir" ]; then
        echo -e "   ${GREEN}✓${NC} Директория $dir существует"
    else
        echo -e "   ${RED}✗${NC} Директория $dir отсутствует"
        ((ERRORS++))
    fi
done

# Проверка основных файлов
for file in main.py run.py requirements.txt config/settings.py config/languages.py; do
    if [ -f "$file" ]; then
        echo -e "   ${GREEN}✓${NC} Файл $file существует"
    else
        echo -e "   ${RED}✗${NC} Файл $file отсутствует"
        ((ERRORS++))
    fi
done

echo ""
echo "2. Проверка Python синтаксиса..."
python3 -m py_compile main.py && print_result 0 "main.py" || print_result 1 "main.py"
python3 -m py_compile run.py && print_result 0 "run.py" || print_result 1 "run.py"
python3 -m py_compile bot/core.py && print_result 0 "bot/core.py" || print_result 1 "bot/core.py"

echo ""
echo "3. Проверка импортов..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    import config.settings
    print('✅ config.settings')
except Exception as e:
    print('❌ config.settings:', e)
    sys.exit(1)

try:
    import bot.core
    print('✅ bot.core')
except Exception as e:
    print('❌ bot.core:', e)
    sys.exit(1)

try:
    import bot.handlers
    print('✅ bot.handlers')
except Exception as e:
    print('❌ bot.handlers:', e)
    sys.exit(1)

print('✅ Все импорты успешны')
"

echo ""
echo "4. Проверка конфигурации..."
if [ -f ".env" ]; then
    if grep -q "TELEGRAM_TOKEN" .env && ! grep -q "TELEGRAM_TOKEN=your_token_here" .env; then
        echo -e "${GREEN}✅ Токен Telegram настроен${NC}"
    else
        echo -e "${YELLOW}⚠  Токен Telegram не настроен или установлен по умолчанию${NC}"
    fi
else
    echo -e "${YELLOW}⚠  Файл .env не найден, создайте из .env.example${NC}"
fi

echo ""
echo "5. Проверка виртуального окружения..."
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ Виртуальное окружение существует${NC}"
    # Проверка основных зависимостей
    source venv/bin/activate
    python3 -c "
import pkg_resources
deps = ['python-telegram-bot', 'paramiko', 'psutil', 'APScheduler']
for dep in deps:
    try:
        pkg_resources.get_distribution(dep)
        print(f'✅ {dep}')
    except:
        print(f'❌ {dep}')
    "
    deactivate
else
    echo -e "${YELLOW}⚠  Виртуальное окружение не создано${NC}"
    echo "   Создайте: python3 -m venv venv"
    echo "   Установите зависимости: pip install -r requirements.txt"
fi

echo ""
echo "6. Проверка systemd сервиса..."
if [ -f "monitoring-bot-refactored.service" ]; then
    echo -e "${GREEN}✅ Файл сервиса существует${NC}"
    
    # Проверка пути к Python
    if grep -q "venv/bin/python" monitoring-bot-refactored.service; then
        echo -e "   ${GREEN}✓${NC} Правильный путь к Python"
    else
        echo -e "   ${YELLOW}⚠${NC} Проверьте путь к Python в сервисе"
    fi
    
    # Проверка рабочей директории
    if grep -q "WorkingDirectory=/home/semis/monitoring-bot/refactored" monitoring-bot-refactored.service; then
        echo -e "   ${GREEN}✓${NC} Правильная рабочая директория"
    else
        echo -e "   ${YELLOW}⚠${NC} Проверьте рабочую директорию в сервисе"
    fi
else
    echo -e "${YELLOW}⚠  Файл сервиса не найден${NC}"
fi

echo ""
echo "7. Тестирование функционала..."
echo "   Запуск тестового режима:"
python3 run.py --test

echo ""
echo "======================================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 Все базовые проверки пройдены успешно!${NC}"
    echo ""
    echo "Следующие шаги:"
    echo "1. Настройте .env файл (скопируйте из .env.example)"
    echo "2. Создайте виртуальное окружение: python3 -m venv venv"
    echo "3. Установите зависимости: pip install -r requirements.txt"
    echo "4. Запустите миграцию: ./migrate_from_old.sh"
    echo "5. Или запустите вручную: python run.py --log-file logs/bot.log"
else
    echo -e "${YELLOW}⚠  Найдено $ERRORS ошибок в структуре проекта${NC}"
    echo "Исправьте ошибки перед продолжением"
fi

echo ""
echo "📞 Команды для запуска:"
echo "   Тестовый режим: python run.py --test"
echo "   Запуск с логами: python run.py --log-file logs/bot.log"
echo "   Просмотр версии: python run.py --version"
echo ""
echo "🔧 Для systemd развертывания:"
echo "   sudo cp monitoring-bot-refactored.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable monitoring-bot-refactored.service"
echo "   sudo systemctl start monitoring-bot-refactored.service"
