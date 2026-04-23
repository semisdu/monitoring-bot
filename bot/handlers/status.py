#!/usr/bin/env python3
"""
Обработчик команды /status
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import get_back_button
from config.loader import (
    get_application_server_ids,
    get_server_config,
    get_virtual_machine
)
from checks.servers import get_server_checker

logger = logging.getLogger(__name__)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status - показывает все VM"""
    user_id = get_user_id(update)

    try:
        await send_or_edit_message(update, f"{get_text(user_id, 'common', 'loading')}...")

        text = f"*{get_text(user_id, 'status', 'title')}:*\n\n"

        # Получаем все серверы приложений
        all_servers = get_application_server_ids()
        
        if not all_servers:
            text += f"{get_text(user_id, 'common', 'no_servers')}\n"
        else:
            for server_id in all_servers:
                server_info = get_server_config(server_id)
                vm_info = get_virtual_machine(server_id)
                
                if server_info:
                    status_data = await check_server_status(server_id)
                    text += format_server_status(user_id, server_id, server_info, vm_info, status_data)
                    text += "\n"

        # Цветная кнопка "Назад"
        reply_markup = get_back_button(get_text, user_id, "menu")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в status_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def check_server_status(server_id: str) -> dict:
    """Проверить статус сервера"""
    checker = get_server_checker()
    return checker.check_remote_server(server_id)


def format_server_status(
    user_id: int,
    server_id: str,
    server_info: dict,
    vm_info: dict,
    status_data: dict
) -> str:
    """
    Форматировать статус сервера для вывода

    Args:
        user_id: ID пользователя для языка
        server_id: ID сервера
        server_info: Информация о сервере из секции servers
        vm_info: Информация о VM из секции virtual_machines (может быть None)
        status_data: Данные о статусе от check_server_status
    """
    # Используем имя из server_info, если есть, иначе из vm_info, иначе server_id
    server_name = server_info.get('name') or (vm_info.get('name') if vm_info else None) or server_id
    
    # Статус сервера (онлайн/офлайн)
    if status_data.get('status') == 'online':
        status_text = get_text(user_id, 'status', 'online')
    else:
        status_text = get_text(user_id, 'status', 'offline')
    
    text = f"*{server_name}* {status_text}\n"

    if status_data.get('status') == 'online':
        # Диск
        disk = status_data.get('disk', {})
        disk_percent = disk.get('percent', 0)
        disk_free = disk.get('free_gb', 0)
        
        text += f"{get_text(user_id, 'status', 'disk')}: {disk_percent}% ({disk_free} GB)\n"

        # Память
        memory = status_data.get('memory', {})
        mem_percent = memory.get('percent', 0)
        mem_free = memory.get('free_gb', 0)
            
        text += f"{get_text(user_id, 'status', 'memory')}: {mem_percent}% ({mem_free} GB)\n"

        # CPU
        cpu = status_data.get('cpu', {})
        cpu_percent = cpu.get('percent', 0)
            
        text += f"{get_text(user_id, 'status', 'cpu')}: {cpu_percent}%\n"
        
        # Добавляем информацию о критичности, если есть
        if vm_info and vm_info.get('critical'):
            text += f"{get_text(user_id, 'common', 'warning')}\n"
    else:
        text += f"{get_text(user_id, 'common', 'error')}: {status_data.get('error', 'Unknown')}\n"

    return text
