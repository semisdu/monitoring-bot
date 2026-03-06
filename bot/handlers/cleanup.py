#!/usr/bin/env python3
"""
Обработчик команды /cleanup
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message

logger = logging.getLogger(__name__)


async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /cleanup"""
    user_id = get_user_id(update)

    try:
        from database.monitoring_db import get_db
        db = get_db()

        # Выполняем очистку
        result = db.cleanup_old_checks()

        text = f"🧹 *{get_text(user_id, 'cleanup', 'title')}:*\n\n"
        text += f"✅ {get_text(user_id, 'cleanup', 'result')}\n"
        text += f"• {get_text(user_id, 'cleanup', 'site_checks')}: {result['site_checks']}\n"
        text += f"• {get_text(user_id, 'cleanup', 'system_checks')}: {result['system_checks']}\n"
        text += f"• {get_text(user_id, 'cleanup', 'alerts_resolved')}: {result['alerts_resolved']}"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)
        db.log_command(user_id, 'cleanup')

    except Exception as e:
        logger.error(f"Ошибка в cleanup_command: {e}")
        error_text = f"❌ {get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
