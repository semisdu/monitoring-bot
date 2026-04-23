#!/usr/bin/env python3
"""
Обработчик команды /start
"""

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import language_manager, get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button

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
    
    # Компактная клавиатура: по 2 кнопки в ряд (новый порядок)
    keyboard = [
        [
            color_button(get_text(user_id, "menu", "status"), "status", "primary"),
            color_button(get_text(user_id, "menu", "docker"), "docker", "primary")
        ],
        [
            color_button(get_text(user_id, "menu", "pve"), "pve_status", "primary"),
            color_button(get_text(user_id, "menu", "pbs"), "pbs_status", "primary")
        ],
        [
            color_button(get_text(user_id, "menu", "stats"), "stats", "success"),
            color_button(get_text(user_id, "menu", "reports"), "report", "success")
        ],
        [
            color_button(get_text(user_id, "menu", "sites"), "sites", "primary"),
            color_button(get_text(user_id, "menu", "logs"), "logs", "primary")
        ],
        [
            color_button(get_text(user_id, "menu", "alerts"), "alerts", "danger"),
            color_button(get_text(user_id, "menu", "language"), "language", "primary")
        ],
        [
            color_button(get_text(user_id, "menu", "donate"), "donate", "primary")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, text, reply_markup=reply_markup)
