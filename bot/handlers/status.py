#!/usr/bin/env python3
"""
Обработчик команды /status
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from config.settings import get_virtual_machines, get_server_info
from checks.servers import get_server_checker

logger = logging.getLogger(__name__)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status - показывает все VM"""
    user_id = get_user_id(update)
    
    try:
        await send_or_edit_message(update, f"{get_text(user_id, 'common', 'loading')}...")
        
        text = f"*{get_text(user_id, 'status', 'title')}:*\n\n"
        
        # Получаем все виртуальные машины
        all_vms = get_virtual_machines()
        
        for server_id in all_vms:
            server_info = get_server_info(server_id)
            if server_info:
                status_data = await check_server_status(server_id)
                text += format_server_status(user_id, server_id, server_info, status_data)
                text += "\n"
        
        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await send_or_edit_message(update, text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Ошибка в status_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def check_server_status(server_id: str) -> dict:
    """Проверить статус сервера"""
    checker = get_server_checker()
    return checker.check_remote_server(server_id)


def format_server_status(user_id: int, server_id: str, server_info: dict, status_data: dict) -> str:
    """Форматировать статус сервера для вывода"""
    text = f"📡 *{server_info.get('name', server_id)}*\n"
    
    if status_data.get('status') == 'online':
        # Диск
        disk = status_data.get('disk', {})
        text += f"{get_text(user_id, 'status', 'disk')}: {disk.get('percent', 0)}% ({disk.get('free_gb', 0)} GB свободно)\n"
        
        # Память
        memory = status_data.get('memory', {})
        text += f"{get_text(user_id, 'status', 'memory')}: {memory.get('percent', 0)}% ({memory.get('free_gb', 0)} GB свободно)\n"
        
        # CPU
        cpu = status_data.get('cpu', {})
        text += f"{get_text(user_id, 'status', 'cpu')}: {cpu.get('percent', 0)}%\n"
    else:
        text += f"{get_text(user_id, 'common', 'error')}: {status_data.get('error', 'Unknown')}\n"
    
    return text
