#!/usr/bin/env python3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional, Callable

def color_button(text: str, callback_data: str, style: Optional[str] = None) -> InlineKeyboardButton:
    if style and style in ['primary', 'success', 'danger']:
        return InlineKeyboardButton(text, callback_data=callback_data, style=style)
    return InlineKeyboardButton(text, callback_data=callback_data)

def get_back_button(get_text_func: Callable, user_id: int, callback: str = "menu") -> InlineKeyboardMarkup:
    keyboard = [[color_button(get_text_func(user_id, "common", "back"), callback, "primary")]]
    return InlineKeyboardMarkup(keyboard)
