#!/usr/bin/env python3
"""
Точка входа для Monitoring Bot
"""

import asyncio
import logging
import sys
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)

sys.path.insert(0, str(Path(__file__).parent))

from bot.core import MonitoringBot

async def run_bot():
    """Запуск бота."""
    bot = MonitoringBot()
    await bot.run()

def main():
    """Основная функция."""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
