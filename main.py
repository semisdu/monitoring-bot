#!/usr/bin/env python3
"""
Monitoring Bot - основной файл запуска
Чистая рефакторинговая версия
"""
import sys
import os
import logging
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем конфигурацию
from config.settings import LOGGING, BASE_DIR

# Настраиваем логирование
os.makedirs(BASE_DIR / "logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOGGING["level"]),
    format=LOGGING["format"],
    handlers=[
        logging.FileHandler(LOGGING["file"]),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Основная функция запуска"""
    logger.info("=" * 60)
    logger.info("🚀 Monitoring Bot - Запуск рефакторинг версии")
    logger.info("=" * 60)
    
    try:
        # Импортируем и инициализируем бота
        from bot.core import MonitoringBot
        bot = MonitoringBot()
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
