#!/usr/bin/env python3
"""
Универсальные обработчики команд Docker
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from config.settings import get_docker_servers
from checks.docker import get_docker_status, restart_docker_container, restart_all_servers_containers

logger = logging.getLogger(__name__)


async def docker_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню Docker"""
    user_id = get_user_id(update)
    
    text = f"*{get_text(user_id, 'docker', 'status')}:*\n\n"
    text += f"{get_text(user_id, 'common', 'select_action')}\n"
    
    docker_servers = get_docker_servers()
    keyboard = []
    
    # Кнопки проверки
    for server in docker_servers:
        server_name = server.upper()
        keyboard.append([
            InlineKeyboardButton(
                f"{get_text(user_id, 'docker', 'check')} {server_name}",
                callback_data=f"docker_check_{server}"
            )
        ])
    
    # Кнопка проверки всех
    keyboard.append([
        InlineKeyboardButton(
            get_text(user_id, 'common', 'check_all'),
            callback_data="docker_check_all"
        )
    ])
    
    # Кнопки перезапуска
    for server in docker_servers:
        server_name = server.upper()
        keyboard.append([
            InlineKeyboardButton(
                f"{get_text(user_id, 'docker', 'restart')} {server_name}",
                callback_data=f"docker_restart_{server}"
            )
        ])
    
    # Кнопка перезапуска всех
    keyboard.append([
        InlineKeyboardButton(
            get_text(user_id, 'common', 'restart_all'),
            callback_data="docker_restart_all"
        )
    ])
    
    # Кнопка назад
    keyboard.append([
        InlineKeyboardButton(
            get_text(user_id, "common", "back"),
            callback_data="menu"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, text, reply_markup=reply_markup)


async def docker_check_server(update: Update, context: ContextTypes.DEFAULT_TYPE, server_id: str) -> None:
    """Проверка Docker на сервере"""
    user_id = get_user_id(update)
    
    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'docker', 'checking')} {server_id.upper()}..."
    )
    
    status = get_docker_status(server_id)
    
    text = f"*{get_text(user_id, 'docker', 'server_status')} {server_id.upper()}:*\n\n"
    
    if status.get('status') == "success":
        containers = status.get('containers', [])
        running = sum(1 for c in containers if c.get('running'))
        total = len(containers)
        
        text += f"{get_text(user_id, 'docker', 'running')}: {running}/{total}\n\n"
        
        if containers:
            for container in containers[:10]:
                status_icon = '🟢' if container.get('running') else '🔴'
                name = container.get('name', 'Unknown')
                text += f"{status_icon} {name}\n"
    else:
        error_msg = status.get('error', 'Unknown')
        text += f"{get_text(user_id, 'common', 'error')}: {error_msg}"
    
    keyboard = [[
        InlineKeyboardButton(
            get_text(user_id, "common", "back"),
            callback_data="docker"
        )
    ]]
    
    await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def docker_check_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка Docker на всех серверах"""
    user_id = get_user_id(update)
    await send_or_edit_message(
        update,
        get_text(user_id, 'docker', 'checking_all')
    )
    
    docker_servers = get_docker_servers()
    text = f"*{get_text(user_id, 'docker', 'all_status')}:*\n\n"
    
    for server_id in docker_servers:
        status = get_docker_status(server_id)
        
        text += f"*{server_id.upper()}:*\n"
        
        if status.get('status') == "success":
            containers = status.get('containers', [])
            running = sum(1 for c in containers if c.get('running'))
            total = len(containers)
            text += f"{get_text(user_id, 'docker', 'running')}: {running}/{total}\n"
            
            if containers:
                for container in containers[:3]:
                    status_icon = '🟢' if container.get('running') else '🔴'
                    name = container.get('name', 'Unknown')
                    text += f"  {status_icon} {name}\n"
        else:
            text += f"{get_text(user_id, 'common', 'error')}\n"
        
        text += "\n"
    
    keyboard = [[
        InlineKeyboardButton(
            get_text(user_id, "common", "back"),
            callback_data="docker"
        )
    ]]
    
    await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def docker_restart_server(update: Update, context: ContextTypes.DEFAULT_TYPE, server_id: str) -> None:
    """Перезапуск Docker на сервере"""
    user_id = get_user_id(update)
    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'docker', 'restarting')} {server_id.upper()}..."
    )
    
    result = restart_docker_container(server_id)
    
    text = f"*{get_text(user_id, 'docker', 'restart_result')} {server_id.upper()}:*\n\n"
    
    if result.get("success"):
        text += f"{get_text(user_id, 'docker', 'restart_success')}\n"
        if result.get('output'):
            text += f"```\n{result.get('output')}\n```"
    else:
        text += f"{get_text(user_id, 'common', 'error')}: {result.get('error', 'Unknown')}\n"
    
    keyboard = [[
        InlineKeyboardButton(
            get_text(user_id, "common", "back"),
            callback_data="docker"
        )
    ]]
    
    await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def docker_restart_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перезапуск Docker на всех серверах"""
    user_id = get_user_id(update)
    await send_or_edit_message(
        update,
        get_text(user_id, 'docker', 'restarting_all')
    )
    
    result = restart_all_servers_containers()
    
    text = f"*{get_text(user_id, 'docker', 'restart_all_result')}:*\n\n"
    
    if result.get("success"):
        text += f"{get_text(user_id, 'docker', 'restart_success')}\n\n"
        
        servers_results = result.get("servers", {})
        for server_id, server_result in servers_results.items():
            if server_result.get("success"):
                text += f"🟢 {server_id.upper()}: OK\n"
            else:
                text += f"🔴 {server_id.upper()}: {server_result.get('error', 'Unknown')}\n"
    else:
        text += f"{get_text(user_id, 'common', 'error')}: {result.get('error', 'Unknown')}\n"
    
    keyboard = [[
        InlineKeyboardButton(
            get_text(user_id, "common", "back"),
            callback_data="docker"
        )
    ]]
    
    await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))
