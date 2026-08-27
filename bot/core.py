#!/usr/bin/env python3
"""
Основной класс бота
"""

import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Optional, Dict, List
from collections import defaultdict

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config.settings import TELEGRAM_TOKEN, FEATURES
from bot.handlers import register_handlers
from bot.notifications import init_notification_manager, send_daily_report
from .scheduler import setup_scheduler

logger = logging.getLogger(__name__)


class RateLimiter:
    """Ограничитель частоты запросов"""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60, ban_seconds: int = 300):
        """
        Args:
            max_requests: Максимальное количество запросов за окно
            window_seconds: Длительность окна в секундах
            ban_seconds: Время блокировки при превышении
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.ban_seconds = ban_seconds
        self.requests: Dict[int, List[float]] = defaultdict(list)
        self.banned: Dict[int, float] = {}
    
    def is_allowed(self, user_id: int) -> bool:
        """Проверить, разрешён ли запрос"""
        now = time.time()
        
        # Проверяем, не забанен ли пользователь
        if user_id in self.banned:
            ban_until = self.banned[user_id]
            if now < ban_until:
                logger.warning(f"Пользователь {user_id} забанен до {datetime.fromtimestamp(ban_until)}")
                return False
            else:
                # Бан истёк
                del self.banned[user_id]
                self.requests[user_id] = []
        
        # Очищаем старые запросы
        if user_id in self.requests:
            self.requests[user_id] = [
                t for t in self.requests[user_id] 
                if now - t < self.window_seconds
            ]
        else:
            self.requests[user_id] = []
        
        # Проверяем лимит
        if len(self.requests[user_id]) >= self.max_requests:
            # Баним пользователя
            self.banned[user_id] = now + self.ban_seconds
            logger.warning(f"Пользователь {user_id} забанен на {self.ban_seconds}с (превышен лимит {self.max_requests} запросов за {self.window_seconds}с)")
            return False
        
        # Добавляем запрос
        self.requests[user_id].append(now)
        return True
    
    def get_remaining(self, user_id: int) -> int:
        """Получить количество оставшихся запросов"""
        now = time.time()
        
        if user_id in self.banned:
            return 0
        
        if user_id in self.requests:
            # Очищаем старые запросы
            self.requests[user_id] = [
                t for t in self.requests[user_id] 
                if now - t < self.window_seconds
            ]
            return max(0, self.max_requests - len(self.requests[user_id]))
        
        return self.max_requests


class MonitoringBot:
    """Основной класс приложения бота"""

    def __init__(self):
        """Инициализация бота."""
        self.application: Optional[Application] = None
        self.job_queue = None
        self.scheduler = None
        self.config = None
        self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60, ban_seconds=300)

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

    async def _check_rate_limit(self, update: Update) -> bool:
        """Проверить rate limit для пользователя"""
        if not update.effective_user:
            return True
        
        user_id = update.effective_user.id
        
        # Администраторы не ограничиваются
        admin_chat_id = self.config.get('telegram', {}).get('admin_chat_id')
        if admin_chat_id and str(user_id) == str(admin_chat_id):
            return True
        
        if not self.rate_limiter.is_allowed(user_id):
            remaining = self.rate_limiter.get_remaining(user_id)
            
            # Отправляем сообщение о блокировке
            try:
                if update.callback_query:
                    await update.callback_query.answer(
                        "⏳ Слишком много запросов! Подождите 5 минут.",
                        show_alert=True
                    )
                else:
                    await update.message.reply_text(
                        "⏳ Слишком много запросов!\n"
                        "Пожалуйста, подождите 5 минут перед новыми командами."
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения о блокировке: {e}")
            
            return False
        
        return True

    def setup_scheduler(self) -> None:
        """Настройка планировщика задач."""
        if not FEATURES.get("enable_log_monitoring", True):
            logger.info("Планировщик отключен в настройках")
            return

        logger.info("Настройка планировщика задач...")

        if not self.application:
            logger.error("Application не инициализирован")
            return

        self.scheduler = setup_scheduler()

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
        
        # Отправляем пользователю сообщение об ошибке
        if update and update.effective_user:
            try:
                if update.callback_query:
                    await update.callback_query.answer(
                        "❌ Произошла ошибка. Попробуйте позже.",
                        show_alert=True
                    )
                elif update.message:
                    await update.message.reply_text(
                        "❌ Произошла ошибка при обработке запроса.\n"
                        "Пожалуйста, попробуйте позже."
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения об ошибке: {e}")

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
        
        # Запускаем фоновую задачу очистки rate limit
        async def cleanup_rate_limits():
            while True:
                await asyncio.sleep(60)  # Раз в минуту
                # Очищаем старые записи
                now = time.time()
                for user_id in list(self.rate_limiter.requests.keys()):
                    self.rate_limiter.requests[user_id] = [
                        t for t in self.rate_limiter.requests[user_id]
                        if now - t < self.rate_limiter.window_seconds
                    ]
                    if not self.rate_limiter.requests[user_id]:
                        del self.rate_limiter.requests[user_id]
        
        # Запускаем очистку в фоне
        cleanup_task = asyncio.create_task(cleanup_rate_limits())
        
        try:
            # Ожидаем завершения (бесконечное ожидание без нагрузки)
            stop_event = asyncio.Event()
            await stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Бот остановлен")
        finally:
            cleanup_task.cancel()
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()


# Глобальный экземпляр для доступа из других модулей
_bot_instance: Optional[MonitoringBot] = None

def get_bot_instance() -> Optional[MonitoringBot]:
    """Получить экземпляр бота"""
    return _bot_instance
