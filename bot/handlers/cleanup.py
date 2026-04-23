#!/usr/bin/env python3
"""
Обработчик команды /cleanup - очистка старых данных
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button, get_back_button

logger = logging.getLogger(__name__)


class DataCleanup:
    """Класс для очистки старых данных"""

    def __init__(self):
        self.cleanup_stats = {
            'site_checks': 0,
            'system_checks': 0,
            'alerts_resolved': 0,
            'logs_rotated': 0
        }

    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """
        Очистить данные старше указанного количества дней.

        Args:
            days_to_keep: Сколько дней хранить данные

        Returns:
            Статистика очистки
        """
        # Здесь должна быть реальная логика очистки БД
        # Для примера возвращаем тестовые данные
        self.cleanup_stats = {
            'site_checks': 150,
            'system_checks': 75,
            'alerts_resolved': 25,
            'logs_rotated': 3
        }
        return self.cleanup_stats

    def cleanup_alerts(self) -> int:
        """Очистить старые алерты"""
        # Здесь должна быть реальная логика
        return 10

    def cleanup_logs(self) -> int:
        """Очистить старые логи"""
        # Здесь должна быть реальная логика
        return 2


# Глобальный экземпляр для cleanup
cleanup_manager = DataCleanup()


async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /cleanup - меню очистки данных"""
    user_id = get_user_id(update)

    try:
        text = f"*{get_text(user_id, 'cleanup', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'cleanup', 'confirm')}\n\n"
        
        days = context.args[0] if context.args else "30"
        text += f"{get_text(user_id, 'cleanup', 'days_to_keep')}: {days}"

        keyboard = [
            [
                color_button(
                    get_text(user_id, 'common', 'yes'),
                    "cleanup_confirm",
                    "danger"
                ),
                color_button(
                    get_text(user_id, 'common', 'no'),
                    "menu",
                    "primary"
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в cleanup_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def cleanup_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подтверждение и выполнение очистки"""
    user_id = get_user_id(update)

    try:
        await send_or_edit_message(
            update,
            f"{get_text(user_id, 'common', 'loading')}..."
        )

        # Выполняем очистку
        stats = cleanup_manager.cleanup_old_data(days_to_keep=30)

        text = f"*{get_text(user_id, 'cleanup', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'cleanup', 'result')}\n\n"

        text += f"*{get_text(user_id, 'stats', 'total')}:*\n"
        text += f"{get_text(user_id, 'cleanup', 'site_checks')}: {stats['site_checks']}\n"
        text += f"{get_text(user_id, 'cleanup', 'system_checks')}: {stats['system_checks']}\n"
        text += f"{get_text(user_id, 'cleanup', 'alerts_resolved')}: {stats['alerts_resolved']}\n"
        text += f"{get_text(user_id, 'logs', 'title')}: {stats['logs_rotated']}\n"

        reply_markup = get_back_button(get_text, user_id, "menu")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в cleanup_confirm: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def cleanup_alerts_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистить только алерты"""
    user_id = get_user_id(update)

    try:
        count = cleanup_manager.cleanup_alerts()

        text = f"*{get_text(user_id, 'cleanup', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'cleanup', 'alerts_resolved')}: {count}"

        reply_markup = get_back_button(get_text, user_id, "menu")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в cleanup_alerts_only: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def cleanup_logs_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистить только логи"""
    user_id = get_user_id(update)

    try:
        count = cleanup_manager.cleanup_logs()

        text = f"*{get_text(user_id, 'cleanup', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'logs', 'title')}: {count}"

        reply_markup = get_back_button(get_text, user_id, "menu")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в cleanup_logs_only: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def show_cleanup_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику очистки"""
    user_id = get_user_id(update)

    try:
        text = f"*{get_text(user_id, 'cleanup', 'title')}:*\n\n"
        text += f"*{get_text(user_id, 'stats', 'title')}:*\n\n"

        # Здесь должна быть реальная статистика из БД
        text += f"{get_text(user_id, 'cleanup', 'site_checks')}: 1250\n"
        text += f"{get_text(user_id, 'cleanup', 'system_checks')}: 850\n"
        text += f"{get_text(user_id, 'alerts', 'title')}: 45\n"
        text += f"{get_text(user_id, 'logs', 'title')}: 12 MB\n"

        reply_markup = get_back_button(get_text, user_id, "menu")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в show_cleanup_stats: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
