#!/usr/bin/env python3
"""
Обработчики команд Proxmox и PBS
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from config.loader import get_pve_server_ids, get_pbs_server_ids, get_server_config, get_virtual_machines, get_backup_jobs

logger = logging.getLogger(__name__)


async def pve_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /pve_status"""
    user_id = get_user_id(update)

    try:
        from checks.proxmox import get_proxmox_client

        await send_or_edit_message(update, f"{get_text(user_id, 'pve', 'checking')}...")

        pve_servers = get_pve_server_ids()
        
        if not pve_servers:
            text = f"*{get_text(user_id, 'pve', 'status')}:*\n\n"
            text += f"{get_text(user_id, 'pve', 'no_servers')}"
            
            keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await send_or_edit_message(update, text, reply_markup=reply_markup)
            return

        text = f"*{get_text(user_id, 'pve', 'status')}:*\n\n"

        for server_id in pve_servers:
            try:
                server_config = get_server_config(server_id)
                server_name = server_config.get('name', server_id) if server_config else server_id
                
                client = get_proxmox_client(server_id)
                if client and client.check_connection():
                    status = client.get_vms_status()
                    
                    configured_vms = get_virtual_machines()
                    pve_vms = [vm for vm in configured_vms if vm.get('server_id') == server_id]
                    critical_vm_ids = [vm.get('vmid') for vm in pve_vms if vm.get('critical')]

                    if status['status'] == 'success':
                        all_vms = status.get('vms', [])
                        running_vms = [vm for vm in all_vms if vm.get('status') == 'running']
                        stopped_vms = [vm for vm in all_vms if vm.get('status') == 'stopped']
                        
                        critical_stopped = [
                            vm for vm in stopped_vms 
                            if vm.get('vmid') in critical_vm_ids
                        ]

                        text += f"*{server_name}:* {get_text(user_id, 'pve', 'online')}\n"
                        text += f"{get_text(user_id, 'pve', 'vms')}: {len(all_vms)} | "
                        text += f"{get_text(user_id, 'docker', 'running')}: {len(running_vms)} | "
                        text += f"{get_text(user_id, 'docker', 'restarting')}: {len(stopped_vms)}\n"

                        if critical_stopped:
                            text += f"{get_text(user_id, 'common', 'warning')} *{get_text(user_id, 'pve', 'vms')} {get_text(user_id, 'status', 'offline')}:*\n"
                            for vm in critical_stopped[:3]:
                                text += f"  • {vm.get('name', 'Unknown')} (VMID: {vm['vmid']})\n"
                            if len(critical_stopped) > 3:
                                text += f"  ... {get_text(user_id, 'common', 'and_more')} {len(critical_stopped) - 3}\n"

                        if running_vms:
                            text += f"{get_text(user_id, 'pve', 'vms')} {get_text(user_id, 'status', 'online')}:\n"
                            for vm in running_vms[:3]:
                                critical_mark = f" {get_text(user_id, 'common', 'warning')}" if vm.get('vmid') in critical_vm_ids else ""
                                text += f"  • {vm.get('name', 'Unknown')} (VMID: {vm['vmid']}){critical_mark}\n"
                            if len(running_vms) > 3:
                                text += f"  ... {get_text(user_id, 'common', 'and_more')} {len(running_vms) - 3}\n"
                    else:
                        text += f"*{server_name}:* {get_text(user_id, 'pve', 'online')}\n"
                        text += f"{get_text(user_id, 'common', 'info')}: {status.get('message', get_text(user_id, 'common', 'no_data'))}\n"
                else:
                    text += f"*{server_name}:* {get_text(user_id, 'pve', 'offline')}\n"
            except Exception as e:
                logger.error(f"Ошибка проверки PVE {server_id}: {e}")
                server_name = get_server_config(server_id).get('name', server_id) if get_server_config(server_id) else server_id
                text += f"*{server_name}:* {get_text(user_id, 'common', 'error')}\n"

            text += "\n"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        logger.error(f"Ошибка в pve_status_command: {e}")
        await send_or_edit_message(update, error_text)


async def pbs_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /pbs_status"""
    user_id = get_user_id(update)

    try:
        from checks.proxmox import get_proxmox_backup_client

        await send_or_edit_message(update, f"{get_text(user_id, 'pbs', 'checking')}...")

        pbs_servers = get_pbs_server_ids()
        
        if not pbs_servers:
            text = f"*{get_text(user_id, 'pbs', 'status')}:*\n\n"
            text += f"{get_text(user_id, 'pbs', 'no_servers')}"
            
            keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await send_or_edit_message(update, text, reply_markup=reply_markup)
            return

        text = f"*{get_text(user_id, 'pbs', 'status')}:*\n\n"
        
        backup_jobs = get_backup_jobs()

        for server_id in pbs_servers:
            try:
                server_config = get_server_config(server_id)
                server_name = server_config.get('name', server_id) if server_config else server_id
                
                server_jobs = [job for job in backup_jobs if job.get('server_id') == server_id]
                
                client = get_proxmox_backup_client(server_id)
                if client and client.check_connection():
                    status = client.get_backups_status()

                    if status['status'] == 'success':
                        text += f"*{server_name}:* {get_text(user_id, 'pbs', 'online')}\n"
                        
                        datastore = server_config.get('datastore', 'local')
                        text += f"{get_text(user_id, 'pbs', 'storage')}: `{datastore}`\n"
                        
                        if server_jobs:
                            text += f"{get_text(user_id, 'pbs', 'jobs')}: {len(server_jobs)}\n"
                            for job in server_jobs[:2]:
                                retention = job.get('retention_days', 7)
                                vms_count = len(job.get('vms', []))
                                text += f"  • {job.get('name', 'Backup')}: {vms_count} VM, {retention} {get_text(user_id, 'pbs', 'storage')}\n"
                            if len(server_jobs) > 2:
                                text += f"  ... {get_text(user_id, 'common', 'and_more')} {len(server_jobs) - 2}\n"
                        
                        last_tasks = status.get('last_tasks', '')
                        if last_tasks and last_tasks != 'Нет данных' and len(last_tasks) > 10:
                            text += f"{get_text(user_id, 'logs', 'view_alerts')}:\n"
                            tasks_lines = last_tasks.split('\n')
                            for line in tasks_lines[:3]:
                                if line.strip():
                                    display_line = line[:50] + '...' if len(line) > 50 else line
                                    text += f"  `{display_line}`\n"
                    else:
                        text += f"*{server_name}:* {get_text(user_id, 'pbs', 'online')}\n"
                        text += f"{get_text(user_id, 'common', 'info')}: {status.get('message', get_text(user_id, 'common', 'no_data'))}\n"
                else:
                    text += f"*{server_name}:* {get_text(user_id, 'pbs', 'offline')}\n"
            except Exception as e:
                logger.error(f"Ошибка проверки PBS {server_id}: {e}")
                server_name = get_server_config(server_id).get('name', server_id) if get_server_config(server_id) else server_id
                text += f"*{server_name}:* {get_text(user_id, 'common', 'error')}\n"

            text += "\n"

        keyboard = [[InlineKeyboardButton(get_text(user_id, "common", "back"), callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        logger.error(f"Ошибка в pbs_status_command: {e}")
        await send_or_edit_message(update, error_text)
