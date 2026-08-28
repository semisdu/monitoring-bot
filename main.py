#!/usr/bin/env python3
"""
Точка входа для Monitoring Bot
"""

import asyncio
import logging
import sys
from pathlib import Path

# Настройка пути
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import setup_logging

# Настраиваем логирование в JSON формате
setup_logging(json_format=True)

from bot.core import MonitoringBot

async def run_bot():
    """Запуск бота."""
    bot = MonitoringBot()
    await bot.run()

def main():
    """Главная функция."""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
