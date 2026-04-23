#!/usr/bin/env python3
"""
Обработчик команды /logs
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button

logger = logging.getLogger(__name__)


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /logs"""
    user_id = get_user_id(update)

    try:
        from database.monitoring_db import get_db
        db = get_db()

        text = f"*{get_text(user_id, 'logs', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'logs', 'info')}\n\n"
        text += f"*{get_text(user_id, 'logs', 'paths')}:*\n"
        text += f"• {get_text(user_id, 'logs', 'db_path')}: `database/monitoring.db`\n"
        text += f"• {get_text(user_id, 'logs', 'log_files')}: `logs/`\n\n"
        text += f"*{get_text(user_id, 'logs', 'view_alerts')}:*\n"
        text += f"/alerts - {get_text(user_id, 'alerts', 'title')}\n\n"
        text += f"*{get_text(user_id, 'logs', 'cleanup')}:*\n"
        text += f"/cleanup - {get_text(user_id, 'cleanup', 'title')}"

        keyboard = [
            [
                color_button(
                    get_text(user_id, 'alerts', 'title'),
                    "alerts",
                    "danger"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'cleanup', 'title'),
                    "cleanup_confirm",
                    "primary"
                )
            ],
            [
                color_button(
                    get_text(user_id, "common", "back"),
                    "menu",
                    "primary"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)
        db.log_command(user_id, 'logs')

    except Exception as e:
        logger.error(f"Ошибка в logs_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
