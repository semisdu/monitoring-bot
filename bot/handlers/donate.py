#!/usr/bin/env python3
"""
Обработчик команды /donate
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import language_manager, get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button

logger = logging.getLogger(__name__)


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать реквизиты для донатов"""
    user_id = get_user_id(update)
    
    # Определяем язык пользователя
    lang = language_manager.get_user_language(user_id)
    
    if lang == 'uk':
        text = (
            "💰 *Підтримати проєкт*\n\n"
            "Якщо бот допомагає вам у роботі, "
            "ви можете подякувати автору:\n\n"
            
            "🌍 *Міжнародні*\n"
            "• PayPal: `duhast89@gmail.com`\n\n"
            
            "💎 *Криптовалюта*\n"
            "• TON: `UQCRwgcrOBjEUV79ISt6swrHp2U9Yv2t8o2vANxQRBFeVEjx`\n"
            "• USDT (TRC-20): `TSxk8tgR5JjPn8xJakuejjrJcSnTdZAhFa`\n"
            "• BTC: `bc1q9rjhewccuzhj2drga3gqmrqjdfc362xjsa6hwy`\n\n"
        )
    elif lang == 'en':
        text = (
            "💰 *Support the project*\n\n"
            "If the bot helps you in your work, "
            "you can thank the author:\n\n"
            
            "🌍 *International*\n"
            "• PayPal: `duhast89@gmail.com`\n\n"
            
            "💎 *Cryptocurrency*\n"
            "• TON: `UQCRwgcrOBjEUV79ISt6swrHp2U9Yv2t8o2vANxQRBFeVEjx`\n"
            "• USDT (TRC-20): `TSxk8tgR5JjPn8xJakuejjrJcSnTdZAhFa`\n"
            "• BTC: `bc1q9rjhewccuzhj2drga3gqmrqjdfc362xjsa6hwy`\n\n"
        )
    else:  # русский по умолчанию
        text = (
            "💰 *Поддержать проект*\n\n"
            "Если бот помогает вам в работе, "
            "вы можете отблагодарить автора:\n\n"
            
            "🌍 *Международные*\n"
            "• PayPal: `duhast89@gmail.com`\n\n"
            
            "💎 *Криптовалюта*\n"
            "• TON: `UQCRwgcrOBjEUV79ISt6swrHp2U9Yv2t8o2vANxQRBFeVEjx`\n"
            "• USDT (TRC-20): `TSxk8tgR5JjPn8xJakuejjrJcSnTdZAhFa`\n"
            "• BTC: `bc1q9rjhewccuzhj2drga3gqmrqjdfc362xjsa6hwy`\n\n"
        )
    
    keyboard = [[color_button("🔙 Назад", "menu", "primary")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_message(update, text, reply_markup=reply_markup)
