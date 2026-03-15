#!/usr/bin/env python3
"""
Обработчик команды /start
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import language_manager, get_text
from bot.handlers.common import get_user_id, send_or_edit_message

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user_id = get_user_id(update)

    # Получаем имя пользователя
    if update.message:
        name = update.message.from_user.first_name or "Пользователь"
    elif update.callback_query:
        name = update.callback_query.from_user.first_name or "Пользователь"
    else:
        name = "Пользователь"

    # Устанавливаем язык по умолчанию если не установлен
    if not language_manager.get_user_language(user_id):
        language_manager.set_user_language(user_id, 'ru')

    logger.info(f"Пользователь {user_id} запустил бота")

    text = get_text(user_id, 'start', 'welcome', name=name)
    
    # Создаём клавиатуру с кнопками
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, "menu", "status"), callback_data="status")],
        [InlineKeyboardButton(get_text(user_id, "menu", "docker"), callback_data="docker")],
        [InlineKeyboardButton(get_text(user_id, "menu", "sites"), callback_data="sites")],
        [
            InlineKeyboardButton(get_text(user_id, "menu", "pve"), callback_data="pve_status"),
            InlineKeyboardButton(get_text(user_id, "menu", "pbs"), callback_data="pbs_status")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "menu", "alerts"), callback_data="alerts"),
            InlineKeyboardButton(get_text(user_id, "menu", "stats"), callback_data="stats")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "menu", "logs"), callback_data="logs"),
            InlineKeyboardButton(get_text(user_id, "menu", "reports"), callback_data="report")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "menu", "language"), callback_data="language"),
            InlineKeyboardButton(get_text(user_id, "menu", "donate"), callback_data="donate")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_or_edit_message(update, text, reply_markup=reply_markup)
