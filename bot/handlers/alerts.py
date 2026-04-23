#!/usr/bin/env python3
"""
Обработчик команды /alerts - просмотр активных алертов
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button, get_back_button

logger = logging.getLogger(__name__)

# Временное хранилище алертов (в реальном проекте должно быть в БД)
_alerts_store: List[Dict[str, Any]] = []


def add_alert(alert_type: str, message: str, server_id: str = None) -> None:
    """
    Добавить алерт в хранилище.

    Args:
        alert_type: Тип алерта (critical, warning, info)
        message: Текст сообщения
        server_id: ID сервера (опционально)
    """
    _alerts_store.append({
        'id': len(_alerts_store) + 1,
        'type': alert_type,
        'message': message,
        'server_id': server_id,
        'created_at': datetime.now(),
        'resolved': False
    })
    
    # Ограничим размер хранилища
    if len(_alerts_store) > 100:
        _alerts_store[:] = _alerts_store[-100:]


def get_active_alerts() -> List[Dict[str, Any]]:
    """Получить список активных алертов"""
    return [a for a in _alerts_store if not a.get('resolved')]


def resolve_alert(alert_id: int) -> bool:
    """Пометить алерт как решённый"""
    for alert in _alerts_store:
        if alert.get('id') == alert_id:
            alert['resolved'] = True
            return True
    return False


def resolve_all_alerts() -> int:
    """Пометить все алерты как решённые"""
    count = 0
    for alert in _alerts_store:
        if not alert.get('resolved'):
            alert['resolved'] = True
            count += 1
    return count


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /alerts - просмотр активных алертов"""
    user_id = get_user_id(update)

    try:
        active_alerts = get_active_alerts()

        text = f"*{get_text(user_id, 'alerts', 'title')}:*\n\n"

        if not active_alerts:
            text += get_text(user_id, 'alerts', 'no_alerts')
        else:
            text += f"{get_text(user_id, 'common', 'total')}: {len(active_alerts)}\n\n"
            
            for alert in active_alerts[:10]:
                alert_type = alert.get('type', 'info')
                message = alert.get('message', 'Unknown')
                created_at = alert.get('created_at', datetime.now())
                
                # Форматируем время
                time_str = created_at.strftime('%H:%M %d.%m.%Y')
                
                # Добавляем префикс в зависимости от типа
                if alert_type == 'critical':
                    prefix = f"{get_text(user_id, 'common', 'error')}"
                elif alert_type == 'warning':
                    prefix = f"{get_text(user_id, 'common', 'warning')}"
                else:
                    prefix = f"{get_text(user_id, 'common', 'info')}"
                
                text += f"{prefix} {message}\n"
                text += f"  {get_text(user_id, 'alerts', 'created_at')}: {time_str}\n\n"
            
            if len(active_alerts) > 10:
                text += f"... {get_text(user_id, 'common', 'and_more')} {len(active_alerts) - 10}\n\n"

        # Цветные кнопки управления
        keyboard = []
        
        if active_alerts:
            keyboard.append([
                color_button(
                    get_text(user_id, 'alerts', 'clear_all'),
                    "alerts_clear_all",
                    "danger"
                )
            ])
        
        keyboard.append([
            color_button(
                get_text(user_id, "common", "back"),
                "menu",
                "primary"
            )
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в alerts_command: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def clear_all_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистить все алерты"""
    user_id = get_user_id(update)

    try:
        count = resolve_all_alerts()
        
        text = f"*{get_text(user_id, 'alerts', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'alerts', 'clear_all')}\n"
        text += f"{get_text(user_id, 'stats', 'total')}: {count}"

        reply_markup = get_back_button(get_text, user_id, "alerts")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в clear_all_alerts: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def show_alert_details(update: Update, context: ContextTypes.DEFAULT_TYPE, alert_id: int) -> None:
    """Показать детали алерта"""
    user_id = get_user_id(update)

    try:
        alert = None
        for a in _alerts_store:
            if a.get('id') == alert_id:
                alert = a
                break

        if not alert:
            await send_or_edit_message(
                update,
                f"{get_text(user_id, 'common', 'error')}: {get_text(user_id, 'common', 'no_data')}"
            )
            return

        text = f"*{get_text(user_id, 'alerts', 'title')} #{alert_id}:*\n\n"
        
        alert_type = alert.get('type', 'info')
        if alert_type == 'critical':
            text += f"{get_text(user_id, 'common', 'error')}\n"
        elif alert_type == 'warning':
            text += f"{get_text(user_id, 'common', 'warning')}\n"
        else:
            text += f"{get_text(user_id, 'common', 'info')}\n"
        
        text += f"\n{get_text(user_id, 'alerts', 'message')}: {alert.get('message', 'Unknown')}\n"
        
        if alert.get('server_id'):
            text += f"{get_text(user_id, 'pve', 'host')}: {alert.get('server_id')}\n"
        
        created_at = alert.get('created_at', datetime.now())
        text += f"{get_text(user_id, 'alerts', 'created_at')}: {created_at.strftime('%H:%M %d.%m.%Y')}\n"

        keyboard = [
            [
                color_button(
                    get_text(user_id, 'alerts', 'clear'),
                    f"alert_resolve_{alert_id}",
                    "danger"
                )
            ],
            [
                color_button(
                    get_text(user_id, "common", "back"),
                    "alerts",
                    "primary"
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в show_alert_details: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)


async def resolve_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, alert_id: int) -> None:
    """Пометить алерт как решённый"""
    user_id = get_user_id(update)

    try:
        if resolve_alert(alert_id):
            text = f"{get_text(user_id, 'common', 'success')}\n"
            text += f"{get_text(user_id, 'alerts', 'clear')} #{alert_id}"
        else:
            text = f"{get_text(user_id, 'common', 'error')}: {get_text(user_id, 'common', 'no_data')}"

        reply_markup = get_back_button(get_text, user_id, "alerts")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в resolve_alert_callback: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
