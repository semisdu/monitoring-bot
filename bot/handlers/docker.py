#!/usr/bin/env python3
"""
Универсальные обработчики команд Docker
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button, get_back_button
from config.loader import get_docker_server_ids, get_server_config
from checks.docker import get_docker_status, restart_docker_container, restart_all_servers_containers

logger = logging.getLogger(__name__)


async def docker_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню Docker"""
    user_id = get_user_id(update)

    text = f"*{get_text(user_id, 'docker', 'status')}:*\n\n"
    text += f"{get_text(user_id, 'common', 'select_action')}\n"

    docker_servers = get_docker_server_ids()
    
    if not docker_servers:
        text = f"*{get_text(user_id, 'docker', 'status')}:*\n\n"
        text += f"{get_text(user_id, 'common', 'no_servers')}\n"
        reply_markup = get_back_button(get_text, user_id, "menu")
        await send_or_edit_message(update, text, reply_markup=reply_markup)
        return

    keyboard = []

    # Кнопки проверки для каждого сервера
    for server_id in docker_servers:
        server_config = get_server_config(server_id)
        server_name = server_config.get('name', server_id.upper()) if server_config else server_id.upper()
        
        keyboard.append([
            color_button(
                f"{get_text(user_id, 'docker', 'check')} {server_name}",
                f"docker_check_{server_id}",
                "primary"
            )
        ])

    # Кнопка проверки всех
    keyboard.append([
        color_button(
            get_text(user_id, 'common', 'check_all'),
            "docker_check_all",
            "success"
        )
    ])

    # Кнопки перезапуска для каждого сервера
    for server_id in docker_servers:
        server_config = get_server_config(server_id)
        server_name = server_config.get('name', server_id.upper()) if server_config else server_id.upper()
        
        keyboard.append([
            color_button(
                f"{get_text(user_id, 'docker', 'restart')} {server_name}",
                f"docker_restart_{server_id}",
                "danger"
            )
        ])

    # Кнопка перезапуска всех
    keyboard.append([
        color_button(
            get_text(user_id, 'common', 'restart_all'),
            "docker_restart_all",
            "danger"
        )
    ])

    # Кнопка назад
    keyboard.append([
        color_button(
            get_text(user_id, "common", "back"),
            "menu",
            "primary"
        )
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, text, reply_markup=reply_markup)


async def docker_check_server(update: Update, context: ContextTypes.DEFAULT_TYPE, server_id: str) -> None:
    """Проверка Docker на сервере"""
    user_id = get_user_id(update)
    
    server_config = get_server_config(server_id)
    server_name = server_config.get('name', server_id.upper()) if server_config else server_id.upper()

    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'docker', 'checking')} {server_name}..."
    )

    status = get_docker_status(server_id)

    text = f"*{get_text(user_id, 'docker', 'server_status')} {server_name}:*\n\n"

    if status.get('status') == "success":
        containers = status.get('containers', [])
        running = sum(1 for c in containers if c.get('running'))
        total = len(containers)

        if total == 0:
            text += f"{get_text(user_id, 'common', 'no_containers')}\n"
        else:
            text += f"{get_text(user_id, 'docker', 'running')}: {running}/{total}\n\n"

            if containers:
                for container in containers[:10]:
                    running = container.get('running', False)
                    name = container.get('name', 'Unknown')
                    critical = container.get('critical', False)
                    
                    # Добавляем отметку о критичности
                    critical_mark = f" {get_text(user_id, 'common', 'warning')}" if critical and not running else ""
                    text += f"{name}{critical_mark}\n"
    else:
        error_msg = status.get('error', 'Unknown')
        text += f"{get_text(user_id, 'common', 'error')}: {error_msg}"

    reply_markup = get_back_button(get_text, user_id, "docker")
    await send_or_edit_message(update, text, reply_markup=reply_markup)


async def docker_check_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка Docker на всех серверах"""
    user_id = get_user_id(update)
    await send_or_edit_message(
        update,
        get_text(user_id, 'docker', 'checking_all')
    )

    docker_servers = get_docker_server_ids()
    text = f"*{get_text(user_id, 'docker', 'all_status')}:*\n\n"

    if not docker_servers:
        text += f"{get_text(user_id, 'common', 'no_servers')}\n"
    else:
        for server_id in docker_servers:
            server_config = get_server_config(server_id)
            server_name = server_config.get('name', server_id.upper()) if server_config else server_id.upper()
            
            status = get_docker_status(server_id)

            text += f"*{server_name}:*\n"

            if status.get('status') == "success":
                containers = status.get('containers', [])
                running = sum(1 for c in containers if c.get('running'))
                total = len(containers)
                
                if total == 0:
                    text += f"  {get_text(user_id, 'common', 'no_containers')}\n"
                else:
                    text += f"  {get_text(user_id, 'docker', 'running')}: {running}/{total}\n"

                    # Показываем только проблемные контейнеры (не запущенные) для краткости
                    problem_containers = [c for c in containers if not c.get('running')]
                    if problem_containers:
                        for container in problem_containers[:3]:
                            name = container.get('name', 'Unknown')
                            critical = container.get('critical', False)
                            critical_mark = f" {get_text(user_id, 'common', 'warning')}" if critical else ""
                            text += f"  {name}{critical_mark}\n"
                        
                        if len(problem_containers) > 3:
                            text += f"  ... {get_text(user_id, 'common', 'and_more')} {len(problem_containers) - 3}\n"
                    else:
                        text += f"  {get_text(user_id, 'common', 'success')}\n"
            else:
                text += f"  {get_text(user_id, 'common', 'error')}\n"

            text += "\n"

    reply_markup = get_back_button(get_text, user_id, "docker")
    await send_or_edit_message(update, text, reply_markup=reply_markup)


async def docker_restart_server(update: Update, context: ContextTypes.DEFAULT_TYPE, server_id: str) -> None:
    """Перезапуск Docker на сервере"""
    user_id = get_user_id(update)
    
    server_config = get_server_config(server_id)
    server_name = server_config.get('name', server_id.upper()) if server_config else server_id.upper()
    
    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'docker', 'restarting')} {server_name}..."
    )

    result = restart_docker_container(server_id)

    text = f"*{get_text(user_id, 'docker', 'restart_result')} {server_name}:*\n\n"

    if result.get("success"):
        text += f"{get_text(user_id, 'common', 'success')}\n"
        if result.get('output'):
            output = result.get('output', '')
            if len(output) > 200:
                output = output[:200] + "..."
            text += f"```\n{output}\n```"
    else:
        text += f"{get_text(user_id, 'common', 'error')}: {result.get('error', 'Unknown')}\n"

    reply_markup = get_back_button(get_text, user_id, "docker")
    await send_or_edit_message(update, text, reply_markup=reply_markup)


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
        text += f"{get_text(user_id, 'common', 'success')}\n\n"

        servers_results = result.get("servers", {})
        for server_id, server_result in servers_results.items():
            server_config = get_server_config(server_id)
            server_name = server_config.get('name', server_id.upper()) if server_config else server_id.upper()
            
            if server_result.get("success"):
                text += f"{server_name}: {get_text(user_id, 'common', 'success')}\n"
            else:
                text += f"{server_name}: {get_text(user_id, 'common', 'error')} - {server_result.get('error', 'Unknown')}\n"
    else:
        text += f"{get_text(user_id, 'common', 'error')}: {result.get('error', 'Unknown')}\n"

    reply_markup = get_back_button(get_text, user_id, "docker")
    await send_or_edit_message(update, text, reply_markup=reply_markup)
