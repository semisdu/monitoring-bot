#!/usr/bin/env python3
"""
Центральный обработчик callback запросов
Универсальная обработка для всех типов команд
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from config.languages import LANGUAGE_NAMES
from config.loader import (
    get_application_server_ids,
    get_virtual_machine_ids,
    get_all_servers,
    get_docker_server_ids,
    get_server_config
)
from bot.language import language_manager, get_text
from checks.servers import get_server_checker

# Импортируем все команды
from .common import get_user_id, send_or_edit_message
from .start import start_command
from .help import help_command
from .status import status_command
from .sites import site_command
from .version import version_command
from .alerts import alerts_command
from .stats import stats_command
from .logs import logs_command
from .monitor import monitor_status_command, monitor_log_command
from .cleanup import cleanup_command
from .proxmox import pve_status_command, pbs_status_command
from .docker import (
    docker_menu_command,
    docker_check_server,
    docker_check_all,
    docker_restart_server,
    docker_restart_all
)

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Универсальный обработчик всех callback запросов.
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user_id = get_user_id(update)

    logger.info(f"Обработан callback: {callback_data} для пользователя {user_id}")

    # ===== МЕНЮ =====
    if callback_data == "menu":
        await start_command(update, context)

    # ===== HELP =====
    elif callback_data == "help":
        await help_command(update, context)

    # ===== САЙТЫ =====
    elif callback_data == "sites":
        await site_command(update, context)

    # ===== СТАТУС =====
    elif callback_data == "status":
        await status_command(update, context)
    elif callback_data == "status_app_servers":
        await show_app_servers_status(update, context)
    elif callback_data == "status_virtual_machines":
        await show_virtual_machines_status(update, context)
    elif callback_data.startswith("check_server_"):
        server_id = callback_data.replace("check_server_", "")
        await check_server_status(update, context, server_id)

    # ===== DOCKER =====
    elif callback_data == "docker":
        await docker_menu_command(update, context)
    elif callback_data == "docker_check_all":
        await docker_check_all(update, context)
    elif callback_data == "docker_restart_all":
        await docker_restart_all(update, context)
    elif callback_data.startswith("docker_check_"):
        server_id = callback_data.replace("docker_check_", "")
        await docker_check_server(update, context, server_id)
    elif callback_data.startswith("docker_restart_"):
        server_id = callback_data.replace("docker_restart_", "")
        await docker_restart_server(update, context, server_id)

    # ===== ЯЗЫК =====
    elif callback_data == "language":
        await show_language_menu(update, context)
    elif callback_data.startswith("set_lang_"):
        lang_code = callback_data.replace("set_lang_", "")
        await set_language(update, context, lang_code)

    # ===== PVE/PBS =====
    elif callback_data == "pve_status":
        await pve_status_command(update, context)
    elif callback_data == "pbs_status":
        await pbs_status_command(update, context)

    # ===== ЛОГИ =====
    elif callback_data == "logs":
        await logs_command(update, context)

    # ===== АЛЕРТЫ =====
    elif callback_data == "alerts":
        await alerts_command(update, context)

    # ===== СТАТИСТИКА =====
    elif callback_data == "stats":
        await stats_command(update, context)

    # ===== ВЕРСИЯ =====
    elif callback_data == "version":
        await version_command(update, context)

    # ===== DONATE =====
    elif callback_data == "donate":
        from .donate import donate_command
        await donate_command(update, context)

    # ===== МОНИТОРИНГ =====
    elif callback_data == "monitor_status":
        await monitor_status_command(update, context)
    elif callback_data == "monitor_log":
        await monitor_log_command(update, context)

    # ===== ОЧИСТКА =====
    elif callback_data == "cleanup":
        await cleanup_command(update, context)

    else:
        logger.warning(f"Неизвестный callback: {callback_data}")


async def show_app_servers_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статус всех серверов приложений"""
    user_id = get_user_id(update)
    
    app_servers = get_application_server_ids()
    
    if not app_servers:
        text = f"*{get_text(user_id, 'status', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'common', 'no_servers')}"
        
        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    await status_command(update, context)


async def show_virtual_machines_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статус виртуальных машин"""
    user_id = get_user_id(update)
    
    vms = get_virtual_machine_ids()
    
    if not vms:
        text = f"*{get_text(user_id, 'status', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'common', 'no_vms')}"
        
        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    await status_command(update, context)


async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню выбора языка."""
    user_id = get_user_id(update)

    keyboard = []
    for lang_code, lang_name in LANGUAGE_NAMES.items():
        keyboard.append([
            InlineKeyboardButton(
                lang_name,
                callback_data=f"set_lang_{lang_code}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            get_text(user_id, "common", "back"),
            callback_data="menu"
        )
    ])

    await send_or_edit_message(
        update,
        get_text(user_id, "language", "select"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str) -> None:
    """Установить язык пользователя."""
    user_id = get_user_id(update)
    language_manager.set_user_language(user_id, lang_code)

    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'language', 'changed')}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                get_text(user_id, "common", "back"),
                callback_data="menu"
            )
        ]])
    )


async def check_server_status(update: Update, context: ContextTypes.DEFAULT_TYPE, server_id: str) -> None:
    """Проверить статус конкретного сервера."""
    user_id = get_user_id(update)

    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'status', 'checking_server', server=server_id)}..."
    )

    checker = get_server_checker()
    server_config = get_server_config(server_id)

    if not server_config:
        await send_or_edit_message(
            update,
            f"{get_text(user_id, 'common', 'error')}: {get_text(user_id, 'common', 'no_servers')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    get_text(user_id, "common", "back"),
                    callback_data="status"
                )
            ]])
        )
        return

    result = checker.check_remote_server(server_id)

    text = f"*{server_config.get('name', server_id)}*\n\n"

    if result.get('status') == 'online':
        text += f"{get_text(user_id, 'status', 'online')}\n\n"

        if 'cpu' in result:
            cpu = result['cpu'].get('percent', 0)
            text += f"{get_text(user_id, 'status', 'cpu')}: {cpu}%\n"

        if 'memory' in result:
            mem = result['memory'].get('percent', 0)
            text += f"{get_text(user_id, 'status', 'memory')}: {mem}%\n"

        if 'disk' in result:
            disk = result['disk'].get('percent', 0)
            text += f"{get_text(user_id, 'status', 'disk')}: {disk}%\n"
    else:
        text += f"{get_text(user_id, 'status', 'offline')}\n"
        text += f"{get_text(user_id, 'common', 'error')}: {result.get('error', 'Unknown')}"

    keyboard = [[
        InlineKeyboardButton(
            get_text(user_id, "common", "back"),
            callback_data="status"
        )
    ]]

    await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))


def register_handlers(application):
    """Регистрация всех обработчиков команд и callback'ов."""
    logger.info("Регистрация обработчиков команд...")

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("sites", site_command))
    application.add_handler(CommandHandler("docker", docker_menu_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("version", version_command))
    application.add_handler(CommandHandler("monitor", monitor_status_command))
    application.add_handler(CommandHandler("cleanup", cleanup_command))
    application.add_handler(CommandHandler("pve", pve_status_command))
    application.add_handler(CommandHandler("pbs", pbs_status_command))

    application.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Обработчики команд зарегистрированы")
