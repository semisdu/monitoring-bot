#!/usr/bin/env python3
"""
Основной класс бота
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config.settings import TELEGRAM_TOKEN, FEATURES
from bot.handlers import register_handlers
from bot.notifications import init_notification_manager, send_daily_report
from .scheduler import setup_scheduler

logger = logging.getLogger(__name__)


class MonitoringBot:
    """Основной класс приложения бота"""

    def __init__(self):
        """Инициализация бота."""
        self.application: Optional[Application] = None
        self.job_queue = None
        self.scheduler = None
        self.config = None

    def setup_application(self) -> None:
        """Настройка Telegram приложения."""
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN не установлен!")
            sys.exit(1)

        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.job_queue = self.application.job_queue
        
        # Загружаем конфиг
        from config.loader import load_config
        self.config = load_config()
        
        # Инициализируем NotificationManager с ботом из Application
        init_notification_manager(self.application.bot)

        register_handlers(self.application)
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

        self.scheduler = setup_scheduler(self.application)

        if self.scheduler:
            logger.info("Планировщик задач настроен")
        else:
            logger.warning("Планировщик задач не настроен")

    async def _check_missed_daily_report(self) -> None:
        """Проверка пропущенного ежедневного отчёта при старте бота."""
        try:
            # Получаем настройки отчёта из конфига
            notifications = self.config.get('notifications', {})
            daily_config = notifications.get('daily_report', {})
            
            if not daily_config.get('enabled', True):
                logger.info("Ежедневные отчёты отключены в конфиге")
                return
            
            # Время отправки из конфига (по умолчанию 08:00)
            report_time = daily_config.get('time', '08:00')
            target_hour, target_minute = map(int, report_time.split(':'))
            
            now = datetime.now()
            
            # Если текущее время больше или равно времени отправки
            if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
                # Проверяем, был ли уже отправлен отчёт сегодня
                # Используем простой файл-флаг в папке database
                import os
                flag_file = os.path.join(os.path.dirname(__file__), '..', 'database', '.daily_report_sent')
                today = now.strftime('%Y-%m-%d')
                
                last_sent = None
                if os.path.exists(flag_file):
                    with open(flag_file, 'r') as f:
                        last_sent = f.read().strip()
                
                if last_sent != today:
                    logger.info(f"Пропущен ежедневный отчёт за {today}. Отправляю сейчас...")
                    await send_daily_report()
                    # Записываем флаг
                    with open(flag_file, 'w') as f:
                        f.write(today)
                    logger.info("Ежедневный отчёт отправлен при старте бота")
                else:
                    logger.info(f"Ежедневный отчёт за {today} уже был отправлен")
            else:
                logger.info(f"Текущее время {now.strftime('%H:%M')} раньше времени отправки {report_time}. Отчёт не требуется")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке пропущенного отчёта: {e}")

    async def _error_handler(
        self,
        update: Optional[Update],
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Глобальный обработчик ошибок."""
        logger.error(f"Исключение при обработке обновления {update}: {context.error}")

    async def run(self) -> None:
        """Запуск бота."""
        self.setup_application()

        if FEATURES.get("enable_log_monitoring", True):
            self.setup_scheduler()

        logger.info("Запуск бота...")

        if not self.application:
            logger.error("Application не инициализирован")
            return

        # Проверяем пропущенный отчёт перед запуском polling
        await self._check_missed_daily_report()

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            poll_interval=3,
            timeout=30,
            allowed_updates=["message", "callback_query"]
        )
        
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Бот остановлен")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
