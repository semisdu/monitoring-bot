#!/usr/bin/env python3
"""
Ядро Monitoring Bot
Содержит основную логику инициализации
"""

import logging
import sys
from typing import Optional, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config.settings import TELEGRAM_TOKEN, FEATURES
from bot.handlers import register_handlers
from .scheduler import setup_scheduler

logger = logging.getLogger(__name__)

# === ПАТЧ ДЛЯ WEAKREF ОШИБКИ В PYTHON 3.13 ===
import telegram.ext._jobqueue

original_set_application = telegram.ext._jobqueue.JobQueue.set_application


def patched_set_application(self: Any, application: Optional[Application]) -> None:
    """
    Патч для избежания weakref ошибки в Python 3.13.
    
    Сохраняет application напрямую, без weakref.
    
    Args:
        self: Экземпляр JobQueue
        application: Экземпляр Application
    """
    try:
        self._application = application  # Сохраняем напрямую, без weakref
    except Exception:
        self._application = None


telegram.ext._jobqueue.JobQueue.set_application = patched_set_application
# === КОНЕЦ ПАТЧА ===


class MonitoringBot:
    """Основной класс бота мониторинга"""
    
    def __init__(self) -> None:
        """Инициализация бота."""
        self.application: Optional[Application] = None
        self.job_queue: Optional[Any] = None
    
    def setup_application(self) -> None:
        """
        Настройка Telegram приложения.
        
        Создаёт Application, регистрирует обработчики команд
        и настраивает глобальный обработчик ошибок.
        """
        logger.info("Инициализация Telegram приложения...")
        
        # Создаем Application
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Регистрируем обработчики команд
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
        
        self.job_queue = self.application.job_queue
        setup_scheduler(self.job_queue)
        logger.info("Планировщик задач настроен")
    
    async def _error_handler(
        self,
        update: Optional[Update],
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Глобальный обработчик ошибок.
        
        Логирует все необработанные исключения.
        
        Args:
            update: Обновление от Telegram
            context: Контекст с ошибкой
        """
        logger.error(
            f"Исключение при обработке обновления {update}: {context.error}",
            exc_info=context.error
        )
    
    def run(self) -> None:
        """Запуск бота."""
        try:
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
            
            self.application.run_polling(
                poll_interval=3,
                timeout=30,
                drop_pending_updates=True
            )
            
        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем")
        except Exception as error:
            logger.error(f"Ошибка при запуске бота: {error}", exc_info=True)
            raise


# ==================== ТОЧКА ВХОДА ДЛЯ ТЕСТИРОВАНИЯ ====================

if __name__ == "__main__":
    """Запуск бота при прямом вызове."""
    bot = MonitoringBot()
    bot.run()
