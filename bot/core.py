#!/usr/bin/env python3
"""
Основной класс бота
"""

import asyncio
import logging
import sys
from typing import Optional, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config.settings import TELEGRAM_TOKEN, FEATURES
from bot.handlers import register_handlers
from .scheduler import setup_scheduler

logger = logging.getLogger(__name__)


class MonitoringBot:
    """Основной класс приложения бота"""

    def __init__(self):
        """Инициализация бота."""
        self.application: Optional[Application] = None
        self.job_queue = None
        self.scheduler = None

    def setup_application(self) -> None:
        """Настройка Telegram приложения."""
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN не установлен!")
            sys.exit(1)

        # Создаём приложение
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.job_queue = self.application.job_queue

        # Регистрируем обработчики
        register_handlers(self.application)

        # Настраиваем обработчик ошибок
        self.application.add_error_handler(self._error_handler)

        logger.info("Telegram приложение инициализировано")

    def setup_scheduler(self) -> None:
        """Настройка планировщика задач."""
        if not FEATURES.get("enable_log_monitoring", True):
            logger.info("Планировщик отключен в настройках")
            return

        logger.info("Настройка планировщика задач...")

        if not self.application:
            logger.error("Application не инициализирован")
            return

        # Передаём application в планировщик
        self.scheduler = setup_scheduler(self.application)

        if self.scheduler:
            logger.info("Планировщик задач настроен")
        else:
            logger.warning("Планировщик задач не настроен")

    async def _error_handler(
        self,
        update: Optional[Update],
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Глобальный обработчик ошибок."""
        logger.error(f"Исключение при обработке обновления {update}: {context.error}")

    async def run(self) -> None:
        """Запуск бота."""
        # Инициализация
        self.setup_application()

        # Настройка планировщика (если включено)
        if FEATURES.get("enable_log_monitoring", True):
            self.setup_scheduler()

        # Запуск
        logger.info("Запуск бота...")

        if not self.application:
            logger.error("Application не инициализирован")
            return

        # Запускаем polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            poll_interval=3,
            timeout=30,
            allowed_updates=["message", "callback_query"]
        )
        
        # Держим бота запущенным
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Бот остановлен")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
