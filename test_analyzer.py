#!/usr/bin/env python3
import logging
import sys
from pathlib import Path

# Настраиваем подробное логирование
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from analytics.error_analyzer import get_analyzer

print("="*50)
print("ТЕСТИРОВАНИЕ МОДУЛЯ АНАЛИТИКИ")
print("="*50)

try:
    analyzer = get_analyzer()
    print("✅ Модуль аналитики загружен")
    
    # Тестовые данные
    test_error = {
        'error_type': 'test_error',
        'message': 'Тестовая ошибка для проверки',
        'server_id': 'test-server',
        'severity': 'warning'
    }
    
    print(f"📝 Добавляем ошибку: {test_error}")
    error_id = analyzer.add_error(test_error)
    print(f"✅ Добавлена тестовая ошибка с ID: {error_id}")
    
    print("📋 Получаем активные проблемы...")
    problems = analyzer.get_active_problems()
    print(f"📋 Активных проблем: {len(problems)}")
    
    print("📈 Получаем тренды...")
    trends = analyzer.get_error_trends(days=1)
    print(f"📈 Тренды за день: {trends}")
    
    # Проверим, создалась ли база данных
    db_path = Path(__file__).parent / "database" / "errors.db"
    if db_path.exists():
        print(f"✅ База данных создана: {db_path}")
        print(f"   Размер: {db_path.stat().st_size} байт")
    else:
        print(f"❌ База данных НЕ создана: {db_path}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
