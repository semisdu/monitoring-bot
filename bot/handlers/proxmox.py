#!/usr/bin/env python3
"""
Обработчики команд Proxmox и PBS
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from config.settings import get_pve_servers, get_pbs_servers, SERVERS

logger = logging.getLogger(__name__)


async def pve_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /pve_status"""
    user_id = get_user_id(update)

    try:
        from checks.proxmox import get_proxmox_client

        await send_or_edit_message(update, f"{get_text(user_id, 'pve', 'checking')}...")

        pve_servers = get_pve_servers()
        text = f"*{get_text(user_id, 'pve', 'status')}:*\n\n"

        for server_id in pve_servers:
            try:
                client = get_proxmox_client(server_id)
                if client and client.check_connection():
                    status = client.get_vms_status()
                    server_name = SERVERS.get(server_id, {}).get('name', server_id)

                    if status['status'] == 'success':
                        vms = status.get('vms', [])
                        running_vms = [vm for vm in vms if vm.get('status') == 'running']
                        stopped_vms = [vm for vm in vms if vm.get('status') == 'stopped']

                        text += f"✅ *{server_name}:* {get_text(user_id, 'pve', 'online')}\n"
                        text += f"📊 Всего VM: {len(vms)} | 🟢 Запущено: {len(running_vms)} | 🔴 Остановлено: {len(stopped_vms)}\n"

                        if running_vms:
                            text += "🖥 Запущенные VM:\n"
                            for vm in running_vms[:3]:
                                text += f"  • {vm['name']} (VMID: {vm['vmid']})\n"
                            if len(running_vms) > 3:
                                text += f"  ... и ещё {len(running_vms) - 3}\n"
                    else:
                        text += f"✅ *{server_name}:* {get_text(user_id, 'pve', 'online')}\n"
                        text += f"📛 {status.get('message', 'Нет данных')}\n"
                else:
                    text += f"🔴 *{server_id}:* {get_text(user_id, 'pve', 'offline')}\n"
            except Exception as e:
                text += f"🔴 *{server_id}:* {get_text(user_id, 'common', 'error')} - {str(e)[:50]}\n"

        if not pve_servers:
            text = f"*{get_text(user_id, 'pve', 'no_servers')}*"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        error_text = f"{get_text(user_id, 'common', 'error')} {get_text(user_id, 'pve', 'checking_status')}: {str(e)}"
        logger.error(f"Ошибка в pve_status_command: {e}")
        await send_or_edit_message(update, error_text)


async def pbs_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /pbs_status"""
    user_id = get_user_id(update)

    try:
        from checks.proxmox import get_proxmox_backup_client

        await send_or_edit_message(update, f"{get_text(user_id, 'pbs', 'checking')}...")

        pbs_servers = get_pbs_servers()
        text = f"*{get_text(user_id, 'pbs', 'status')}:*\n\n"

        for server_id in pbs_servers:
            try:
                client = get_proxmox_backup_client(server_id)
                if client and client.check_connection():
                    status = client.get_backups_status()
                    server_name = SERVERS.get(server_id, {}).get('name', server_id)

                    if status['status'] == 'success':
                        text += f"✅ *{server_name}:* {get_text(user_id, 'pbs', 'online')}\n"
                        text += f"📝 {status.get('message', 'Нет данных')}\n"

                        last_tasks = status.get('last_tasks', '')
                        if last_tasks and last_tasks != 'Нет данных' and len(last_tasks) > 10:
                            text += f"📋 Последние задачи:\n"
                            tasks_lines = last_tasks.split('\n')
                            for line in tasks_lines[:3]:
                                if line.strip():
                                    display_line = line[:50] + '...' if len(line) > 50 else line
                                    text += f"  {display_line}\n"
                    else:
                        text += f"✅ *{server_name}:* {get_text(user_id, 'pbs', 'online')}\n"
                        text += f"📛 {status.get('message', 'Нет данных')}\n"
                else:
                    text += f"🔴 *{server_id}:* {get_text(user_id, 'pbs', 'offline')}\n"
            except Exception as e:
                text += f"🔴 *{server_id}:* {get_text(user_id, 'common', 'error')} - {str(e)[:50]}\n"

        if not pbs_servers:
            text = f"*{get_text(user_id, 'pbs', 'no_servers')}*"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        error_text = f"{get_text(user_id, 'common', 'error')} {get_text(user_id, 'pbs', 'checking_status')}: {str(e)}"
        logger.error(f"Ошибка в pbs_status_command: {e}")
        await send_or_edit_message(update, error_text)
