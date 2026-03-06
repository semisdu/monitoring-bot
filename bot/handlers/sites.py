#!/usr/bin/env python3
"""
Обработчики команд для проверки сайтов
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message

logger = logging.getLogger(__name__)


async def site_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /sites - проверка статуса сайтов"""
    user_id = get_user_id(update)

    try:
        from checks.site_checker import SiteChecker
        site_checker = SiteChecker()

        await send_or_edit_message(update, f"🔍 {get_text(user_id, 'common', 'loading')}")

        site_checks = site_checker.check_all_sites()

        text = f"🌐 *{get_text(user_id, 'sites', 'title')}:*\n\n"

        if site_checks.get("success"):
            sites = site_checks.get("sites", [])

            for site in sites:
                url = site.get("url", "")
                status = site.get("status", "unknown")
                response_time = site.get("response_time", 0)
                error = site.get("error", "")

                if status == "up":
                    text += f"🟢 {url}\n"
                    text += f"   📡 HTTP {site.get('status_code', '?')} ({response_time}ms)\n"
                elif status == "down":
                    text += f"🔴 {url}\n"
                    text += f"   ⚠️ {error}\n"
                else:
                    text += f"🟡 {url}\n"
                    text += f"   ❓ {error}\n"

                server = site.get("server", "")
                if server:
                    text += f"   🖥️ Сервер: {server}\n"

                text += "\n"

            text += f"📊 Всего: {len(sites)} сайтов\n"

        else:
            text += f"❌ {get_text(user_id, 'common', 'error')}: {site_checks.get('error', 'Неизвестная ошибка')}\n"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        error_text = f"❌ {get_text(user_id, 'common', 'error')}: {str(e)}"
        logger.error(f"Ошибка в site_command: {e}")
        await send_or_edit_message(update, error_text)
