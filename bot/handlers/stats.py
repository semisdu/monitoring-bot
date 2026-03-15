#!/usr/bin/env python3
"""
Обработчик команды /stats - статистика системы
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from config.loader import get_all_servers, get_sites, get_docker_server_ids
from checks.site_checker import check_all_sites
from checks.docker import check_all_docker_servers

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats - статистика системы"""
    user_id = get_user_id(update)

    try:
        await send_or_edit_message(update, f"{get_text(user_id, 'common', 'loading')}...")

        text = f"*{get_text(user_id, 'stats', 'title')}:*\n\n"

        # ===== ОБЩАЯ ИНФОРМАЦИЯ =====
        servers = get_all_servers()
        sites = get_sites()
        docker_servers = get_docker_server_ids()

        text += f"*{get_text(user_id, 'common', 'info')}:*\n"
        text += f"{get_text(user_id, 'pve', 'vms')}: {len(servers)}\n"
        text += f"{get_text(user_id, 'sites', 'title')}: {len(sites)}\n"
        text += f"{get_text(user_id, 'docker', 'containers')}: {len(docker_servers)} {get_text(user_id, 'docker', 'status')}\n\n"

        # ===== СТАТИСТИКА ПО САЙТАМ =====
        text += f"*{get_text(user_id, 'sites', 'title')}:*\n"
        sites_results = await check_all_sites()

        if sites_results:
            successful = sum(1 for s in sites_results if s.get('status') == 'up')
            total = len(sites_results)

            for site in sites_results[:5]:
                url = site.get('url', 'Unknown')
                status = site.get('status', 'down')
                response_time = site.get('response_time', 0)

                if status == 'up':
                    text += f"{url} - {get_text(user_id, 'sites', 'up')} ({response_time}ms)\n"
                else:
                    error = site.get('error', 'Unknown error')
                    text += f"{url} - {get_text(user_id, 'sites', 'down')}: {error}\n"

            if total > 5:
                text += f"... {get_text(user_id, 'common', 'and_more')} {total - 5}\n"

            text += f"\n{get_text(user_id, 'stats', 'total')}: {successful}/{total}\n\n"
        else:
            text += f"{get_text(user_id, 'common', 'no_data')}\n\n"

        # ===== СТАТИСТИКА ПО DOCKER =====
        text += f"*{get_text(user_id, 'docker', 'containers')}:*\n"
        docker_results = check_all_docker_servers()

        if docker_results:
            total_containers = 0
            running_containers = 0

            for server_id, result in docker_results.items():
                if result.get('status') == 'success':
                    total = result.get('total_containers', 0)
                    running = result.get('running_containers', 0)
                    total_containers += total
                    running_containers += running

                    if running == total:
                        text += f"{server_id}: {running}/{total}\n"
                    else:
                        text += f"{server_id}: {running}/{total}\n"
                        containers = result.get('containers', [])
                        problem_containers = [c for c in containers if not c.get('running')]
                        for c in problem_containers[:2]:
                            name = c.get('name', 'Unknown')
                            critical = c.get('critical', False)
                            if critical:
                                text += f"  • {name} ({get_text(user_id, 'common', 'warning')})\n"
                            else:
                                text += f"  • {name}\n"
                        if len(problem_containers) > 2:
                            text += f"  ... {get_text(user_id, 'common', 'and_more')} {len(problem_containers) - 2}\n"
                else:
                    text += f"{server_id}: {get_text(user_id, 'common', 'error')}\n"

            text += f"\n{get_text(user_id, 'stats', 'total')}: {running_containers}/{total_containers}\n"
        else:
            text += f"{get_text(user_id, 'common', 'no_data')}\n"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в stats_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def show_site_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать детальную статистику по сайтам"""
    user_id = get_user_id(update)

    try:
        sites = get_sites()
        sites_results = await check_all_sites()

        text = f"*{get_text(user_id, 'sites', 'title')} ({get_text(user_id, 'stats', 'detailed')}):*\n\n"

        if sites_results and len(sites_results) == len(sites):
            for site, result in zip(sites, sites_results):
                url = site.get('url', 'Unknown')
                name = site.get('name', url)
                critical = site.get('critical', False)

                text += f"*{name}*\n"
                text += f"URL: {url}\n"

                if result.get('status') == 'up':
                    text += f"  {get_text(user_id, 'sites', 'up')}: {result.get('response_time', 0)}ms\n"
                    if result.get('status_code'):
                        text += f"  HTTP {result.get('status_code')}\n"
                else:
                    text += f"  {get_text(user_id, 'sites', 'down')}: {result.get('error', 'Unknown')}\n"

                if critical:
                    text += f"  {get_text(user_id, 'common', 'warning')}\n"
                text += "\n"
        else:
            text += get_text(user_id, 'common', 'no_data')

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в show_site_stats: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def show_docker_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать детальную статистику по Docker"""
    user_id = get_user_id(update)

    try:
        docker_results = check_all_docker_servers()

        text = f"*{get_text(user_id, 'docker', 'containers')} ({get_text(user_id, 'stats', 'detailed')}):*\n\n"

        if docker_results:
            for server_id, result in docker_results.items():
                text += f"*{server_id}:*\n"

                if result.get('status') == 'success':
                    containers = result.get('containers', [])
                    running = result.get('running_containers', 0)
                    total = result.get('total_containers', 0)

                    text += f"  {get_text(user_id, 'docker', 'running')}: {running}/{total}\n"

                    for container in containers:
                        name = container.get('name', 'Unknown')
                        running = container.get('running', False)
                        critical = container.get('critical', False)
                        status = container.get('status', 'unknown')

                        if running:
                            text += f"  {name}\n"
                        else:
                            text += f"  {name} ({status})\n"
                            if critical:
                                text += f"    {get_text(user_id, 'common', 'warning')}\n"
                else:
                    text += f"  {get_text(user_id, 'common', 'error')}: {result.get('error', 'Unknown')}\n"

                text += "\n"
        else:
            text += get_text(user_id, 'common', 'no_data')

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в show_docker_stats: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
