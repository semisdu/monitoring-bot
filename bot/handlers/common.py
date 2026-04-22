#!/usr/bin/env python3
"""
Общие утилиты для обработчиков команд
"""

import logging
from typing import Optional

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def get_user_id(update: Update) -> int:
    """Получить ID пользователя из обновления"""
    if update.callback_query:
        return update.callback_query.from_user.id
    elif update.message:
        return update.message.from_user.id
    elif update.effective_user:
        return update.effective_user.id
    else:
        raise ValueError("Не удалось получить ID пользователя")


async def send_or_edit_message(update: Update, text: str, parse_mode: str = "Markdown",
                               reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    """Отправить или редактировать сообщение"""
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        elif update.message:
            await update.message.reply_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        else:
            logger.error("Нет callback_query и нет message в update")
    except Exception as e:
        logger.error(f"Ошибка отправки/редактирования сообщения: {e}")
