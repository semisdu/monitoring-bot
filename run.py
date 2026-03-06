#!/usr/bin/env python3
"""
Скрипт запуска Monitoring Bot с поддержкой различных режимов
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

def setup_logging(verbose: bool = False, log_file: str = None):
    """Настройка логирования"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    handlers = [logging.StreamHandler()]
    
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Уменьшаем verbosity для некоторых библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Monitoring Bot - система мониторинга")
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробный вывод (DEBUG уровень)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Путь к файлу логов"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Путь к конфигурационному файлу (опционально)"
    )
    
    parser.add_argument(
        "--version",
        action="store_true",
        help="Показать версию и выйти"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Тестовый режим (проверка конфигурации)"
    )
    
    args = parser.parse_args()
    
    # Показ версии
    if args.version:
        from bot import __version__
        print(f"Monitoring Bot v{__version__}")
        sys.exit(0)
    
    # Настройка логирования
    setup_logging(args.verbose, args.log_file)
    logger = logging.getLogger(__name__)
    
    # Тестовый режим
    if args.test:
        logger.info("🔧 Запуск в тестовом режиме...")
        
        try:
            # Проверяем импорты
            import importlib
            modules = [
                'config.settings',
                'bot.core',
                'bot.handlers',
                'bot.language'
            ]
            
            for module in modules:
                importlib.import_module(module)
                logger.info(f"✅ Модуль {module} загружен")
            
            # Проверяем конфигурацию
            from config.settings import TELEGRAM_TOKEN, ADMIN_CHAT_ID
            if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "your_token_here":
                logger.info(f"✅ Токен Telegram настроен (длина: {len(TELEGRAM_TOKEN)})")
            else:
                logger.warning("⚠️  Токен Telegram не настроен или установлен по умолчанию")
            
            logger.info("✅ Все проверки пройдены успешно")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при тестировании: {e}", exc_info=True)
            sys.exit(1)
    
    # Обычный запуск
    logger.info("=" * 60)
    logger.info("🚀 Monitoring Bot - Запуск рефакторинг версии")
    logger.info("=" * 60)
    
    try:
        from main import main as bot_main
        bot_main()
        
    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
