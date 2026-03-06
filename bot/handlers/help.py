#!/usr/bin/env python3
"""
Обработчик команды /help
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message

logger = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    user_id = get_user_id(update)
    text = get_text(user_id, 'menu', 'help_text')

    keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_or_edit_message(update, text, reply_markup=reply_markup)
