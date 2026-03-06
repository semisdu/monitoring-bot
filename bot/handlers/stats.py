#!/usr/bin/env python3
"""
Обработчик команды /stats
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats"""
    user_id = get_user_id(update)

    try:
        from checks.site_checker import SiteChecker
        from database.monitoring_db import get_db

        await send_or_edit_message(update, f"{get_text(user_id, 'common', 'loading')}...")

        site_checker = SiteChecker()
        site_result = site_checker.check_all_sites()
        db = get_db()
        command_stats = db.get_command_stats()

        text = f"*{get_text(user_id, 'stats', 'title')}:*\n\n"

        # Статус сайтов
        if site_result.get('success'):
            sites = site_result.get('sites', [])
            successful = sum(1 for s in sites if s.get('status') == 'up')
            total = len(sites)

            text += f"*{get_text(user_id, 'sites', 'title')}:*\n"
            for site in sites[:3]:
                status_icon = '🟢' if site.get('status') == 'up' else '🔴'
                response_time = site.get('response_time', 0)
                text += f"{status_icon} {site.get('name', 'Unknown')}: {response_time:.0f}ms\n"

            if total > 3:
                text += f"   ... {get_text(user_id, 'common', 'and_more')} {total - 3}\n"

            text += f"\n✅ *{get_text(user_id, 'stats', 'total')}:* {successful}/{total} {get_text(user_id, 'sites', 'title').lower()}\n"
            if total > 0:
                availability = (successful / total) * 100
                text += f"{get_text(user_id, 'stats', 'availability')}: {availability:.1f}%\n"

        # Статистика команд
        text += f"\n*{get_text(user_id, 'stats', 'commands')}:*\n"
        text += f"{get_text(user_id, 'stats', 'total_commands')}: {command_stats.get('total_commands', 0)}\n"

        # Топ команд
        command_stats_list = command_stats.get('command_stats', [])
        if command_stats_list:
            text += f"\n*{get_text(user_id, 'stats', 'popular')}:*\n"
            for i, stat in enumerate(command_stats_list[:5], 1):
                text += f"{i}. {stat['command']}: {stat['count']}\n"

        # Время
        text += f"\n{get_text(user_id, 'common', 'time')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)
        db.log_command(user_id, 'stats')

    except Exception as e:
        logger.error(f"Ошибка в stats_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
