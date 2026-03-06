#!/usr/bin/env python3
"""
Обработчик команды /alerts
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message

logger = logging.getLogger(__name__)


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /alerts"""
    user_id = get_user_id(update)

    try:
        from database.monitoring_db import get_db
        db = get_db()

        # Используем правильное название метода
        alerts = db.get_unresolved_alerts()

        if alerts:
            text = f"*{get_text(user_id, 'alerts', 'title')} ({len(alerts)}):*\n\n"
            for alert in alerts[:10]:
                created = datetime.fromisoformat(alert['created_at']).strftime('%Y-%m-%d %H:%M')
                text += f"🔵 {alert['message']}\n"
                text += f"   ⏰ {created}\n\n"
        else:
            text = f"*{get_text(user_id, 'alerts', 'title')}:*\n\n"
            text += f"{get_text(user_id, 'alerts', 'no_alerts')}"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)
        db.log_command(user_id, 'alerts')

    except Exception as e:
        logger.error(f"Ошибка в alerts_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
