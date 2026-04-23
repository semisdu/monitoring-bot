#!/usr/bin/env python3
"""
Обработчик команды /sites
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button, get_back_button
from config.loader import get_sites, get_server_config, get_server_containers
from checks.site_checker import check_site
from checks.docker import get_docker_status

logger = logging.getLogger(__name__)


async def check_server_health(server_id: str) -> tuple:
    """
    Проверить здоровье сервера и его контейнеров.
    
    Returns:
        (has_problems, problems_description)
    """
    if not server_id:
        return False, ""
    
    # Проверяем Docker контейнеры на сервере
    docker_status = get_docker_status(server_id)
    
    if docker_status.get('status') != 'success':
        return True, f"Docker error: {docker_status.get('error', 'Unknown')}"
    
    containers = docker_status.get('containers', [])
    problems = []
    
    for container in containers:
        if not container.get('running', False):
            container_name = container.get('name', 'Unknown')
            critical = container.get('critical', False)
            if critical:
                problems.append(f"Critical container {container_name} is down")
            else:
                problems.append(f"Container {container_name} is down")
    
    return len(problems) > 0, "; ".join(problems)


async def site_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /sites - проверка всех сайтов"""
    user_id = get_user_id(update)

    try:
        await send_or_edit_message(update, f"{get_text(user_id, 'common', 'loading')}...")

        sites = get_sites()

        if not sites:
            text = f"*{get_text(user_id, 'sites', 'title')}:*\n\n"
            text += f"{get_text(user_id, 'common', 'no_data')}"

            reply_markup = get_back_button(get_text, user_id, "menu")
            await send_or_edit_message(update, text, reply_markup=reply_markup)
            return

        text = f"*{get_text(user_id, 'sites', 'title')}:*\n\n"

        for site in sites:
            url = site.get('url', 'Unknown')
            server_id = site.get('server_id') or site.get('server')
            critical = site.get('critical', False)

            # Проверяем сам сайт
            result = await check_site(url)
            
            # Проверяем здоровье сервера (контейнеры и т.д.)
            has_problems, problems_desc = await check_server_health(server_id) if server_id else (False, "")

            text += f"{url}\n"

            # Статус сайта
            if result.get('status_code', 0) > 0:
                status_code = result.get('status_code')
                response_time = result.get('response_time', 0)
                
                if 200 <= status_code < 400:
                    text += f"  {get_text(user_id, 'sites', 'up')} ({response_time}ms)\n"
                else:
                    text += f"  {get_text(user_id, 'sites', 'down')} (HTTP {status_code})\n"
            else:
                error = result.get('error', 'Unknown error')
                text += f"  {get_text(user_id, 'common', 'error')}: {error}\n"

            # Информация о сервере
            if server_id:
                server_config = get_server_config(server_id)
                if server_config:
                    server_name = server_config.get('name', server_id)
                    text += f"  {get_text(user_id, 'pve', 'host')}: {server_name}\n"
                    
                    # Если есть проблемы с сервером/контейнерами - показываем предупреждение
                    if has_problems:
                        text += f"  {get_text(user_id, 'common', 'warning')}: {problems_desc}\n"

            text += "\n"

        total = len(sites)
        text += f"{get_text(user_id, 'stats', 'total')}: {total} {get_text(user_id, 'sites', 'title').lower()}"

        reply_markup = get_back_button(get_text, user_id, "menu")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в site_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def check_site_status(update: Update, context: ContextTypes.DEFAULT_TYPE, site_url: str) -> None:
    """Проверить статус конкретного сайта"""
    user_id = get_user_id(update)

    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'sites', 'checking')} {site_url}..."
    )

    result = await check_site(site_url)

    text = f"*{get_text(user_id, 'sites', 'status')}: {site_url}*\n\n"

    if result.get('status_code', 0) > 0:
        status_code = result.get('status_code')
        response_time = result.get('response_time', 0)
        
        if 200 <= status_code < 400:
            text += f"{get_text(user_id, 'sites', 'up')}\n"
        else:
            text += f"{get_text(user_id, 'sites', 'down')}\n"
        
        text += f"{get_text(user_id, 'sites', 'response_time')}: {response_time}ms\n"
        text += f"{get_text(user_id, 'sites', 'http_code')}: {status_code}\n"
    else:
        text += f"{get_text(user_id, 'common', 'error')}: {result.get('error', 'Unknown')}\n"

    reply_markup = get_back_button(get_text, user_id, "sites")
    await send_or_edit_message(update, text, reply_markup=reply_markup)
