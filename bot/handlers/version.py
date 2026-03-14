#!/usr/bin/env python3
"""
Обработчик команды /version - информация о версии бота
"""

import logging
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot import __version__

logger = logging.getLogger(__name__)

# Время запуска бота (устанавливается при инициализации модуля)
START_TIME = datetime.now()


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /version - информация о версии бота"""
    user_id = get_user_id(update)

    try:
        # Вычисляем время работы
        uptime = datetime.now() - START_TIME
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds // 60) % 60

        text = f"*{get_text(user_id, 'version', 'title')}:*\n\n"

        # Версия бота
        text += f"*{get_text(user_id, 'version', 'bot_version')}:*\n"
        text += f"v{__version__}\n\n"

        # Версия Python
        text += f"*{get_text(user_id, 'version', 'python_version')}:*\n"
        text += f"{sys.version.split()[0]}\n\n"

        # Время запуска
        text += f"*{get_text(user_id, 'version', 'start_time')}:*\n"
        text += f"{START_TIME.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Время работы
        text += f"*{get_text(user_id, 'version', 'uptime')}:*\n"
        if days > 0:
            text += f"{days} {get_text(user_id, 'common', 'and_more')} {hours}:{minutes:02d}\n"
        else:
            text += f"{hours}:{minutes:02d}\n"

        # Кнопка назад
        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в version_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def show_system_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать детальную информацию о системе"""
    user_id = get_user_id(update)

    try:
        import platform
        import os

        text = f"*{get_text(user_id, 'version', 'title')}:*\n\n"

        # Информация о системе
        text += f"*{get_text(user_id, 'common', 'info')}:*\n"
        text += f"OS: {platform.system()} {platform.release()}\n"
        text += f"Host: {platform.node()}\n\n"

        # Информация о процессе
        text += f"*{get_text(user_id, 'monitor', 'current_status')}:*\n"
        text += f"PID: {os.getpid()}\n"
        text += f"CWD: {os.getcwd()}\n"

        keyboard = [[
            InlineKeyboardButton(
                get_text(user_id, "common", "back"),
                callback_data="version"
            )
        ]]

        await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка в show_system_info: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def show_dependencies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список зависимостей"""
    user_id = get_user_id(update)

    try:
        import pkg_resources

        text = f"*{get_text(user_id, 'version', 'title')}:*\n\n"
        text += f"*{get_text(user_id, 'common', 'info')}:*\n"

        # Основные зависимости
        deps = [
            'python-telegram-bot',
            'paramiko',
            'pyyaml',
            'apscheduler',
            'requests'
        ]

        installed = []
        for dep in deps:
            try:
                version = pkg_resources.get_distribution(dep).version
                installed.append(f"{dep}=={version}")
            except:
                installed.append(f"{dep} - {get_text(user_id, 'common', 'no')}")

        text += "\n".join(installed)

        keyboard = [[
            InlineKeyboardButton(
                get_text(user_id, "common", "back"),
                callback_data="version"
            )
        ]]

        await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка в show_dependencies: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
