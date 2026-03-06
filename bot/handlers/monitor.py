#!/usr/bin/env python3
"""
Обработчики команд мониторинга
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message

logger = logging.getLogger(__name__)


async def monitor_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /monitor_status"""
    user_id = get_user_id(update)

    try:
        text = f"📈 *{get_text(user_id, 'monitor', 'status_title')}:*\n\n"
        text += f"{get_text(user_id, 'monitor', 'description')}\n\n"
        text += f"📊 *{get_text(user_id, 'monitor', 'what_monitored')}*\n"
        text += f"• {get_text(user_id, 'monitor', 'sites')}: {get_text(user_id, 'monitor', 'every_5_min')}\n"
        text += f"• {get_text(user_id, 'monitor', 'system_metrics')}: {get_text(user_id, 'monitor', 'every_5_min')}\n"
        text += f"• {get_text(user_id, 'monitor', 'docker')}: {get_text(user_id, 'monitor', 'every_5_min')}\n\n"
        text += f"📈 *{get_text(user_id, 'monitor', 'current_status')}*\n"
        text += f"✅ {get_text(user_id, 'monitor', 'database_works')}\n"
        text += f"✅ {get_text(user_id, 'monitor', 'modules_ready')}\n"
        text += f"⏳ {get_text(user_id, 'monitor', 'scheduler_will_be_added')}\n\n"
        text += f"🚀 *{get_text(user_id, 'monitor', 'use_commands')}*\n"
        text += f"/sites - {get_text(user_id, 'monitor', 'check_sites')}\n"
        text += f"/status - {get_text(user_id, 'monitor', 'full_check')}\n"
        text += f"/status301, /status300 - {get_text(user_id, 'monitor', 'check_servers')}"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

        from database.monitoring_db import get_db
        get_db().log_command(user_id, 'monitor_status')

    except Exception as e:
        logger.error(f"Ошибка в monitor_status_command: {e}")
        error_text = f"❌ {get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def monitor_log_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /monitor_log"""
    user_id = get_user_id(update)

    try:
        text = f"📋 *{get_text(user_id, 'monitor', 'log_title')}:*\n\n"
        text += f"{get_text(user_id, 'monitor', 'log_description')}\n\n"
        text += f"{get_text(user_id, 'monitor', 'in_development')}\n"
        text += f"⏰ *{get_text(user_id, 'common', 'time')}:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

        from database.monitoring_db import get_db
        get_db().log_command(user_id, 'monitor_log')

    except Exception as e:
        logger.error(f"Ошибка в monitor_log_command: {e}")
        error_text = f"❌ {get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
