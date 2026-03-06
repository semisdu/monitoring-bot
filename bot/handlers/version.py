#!/usr/bin/env python3
"""
Обработчик команды /version
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from utils.version import get_version as get_version_info

logger = logging.getLogger(__name__)


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /version"""
    user_id = get_user_id(update)

    version_info = get_version_info()
    text = f"📦 *{get_text(user_id, 'version', 'title')}:*\n\n"
    text += f"• {get_text(user_id, 'version', 'bot_version')}: {version_info['bot_version']}\n"
    text += f"• {get_text(user_id, 'version', 'python_version')}: {version_info['python_version']}\n"
    text += f"• {get_text(user_id, 'version', 'start_time')}: {version_info['start_time']}\n"
    text += f"• {get_text(user_id, 'version', 'uptime')}: {version_info['uptime']}\n"

    keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_or_edit_message(update, text, reply_markup=reply_markup)
