#!/usr/bin/env python3
"""
Обработчик команды /alerts - просмотр активных алертов
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button, get_back_button
from database.monitoring_db import get_db

logger = logging.getLogger(__name__)


def add_alert(alert_type: str, message: str, server_id: Optional[str] = None) -> None:
    """
    Добавить алерт в базу данных.

    Args:
        alert_type: Тип алерта (critical, warning, info)
        message: Текст сообщения
        server_id: ID сервера (опционально)
    """
    try:
        db = get_db()
        # Используем alert_type как title для совместимости с БД
        db.add_alert(alert_type, message[:50], message, alert_type)
        logger.info(f"Добавлен алерт: {alert_type} - {message[:50]}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении алерта в БД: {e}")


def get_active_alerts() -> List[Dict[str, Any]]:
    """Получить список активных алертов из БД"""
    try:
        db = get_db()
        alerts = db.get_unresolved_alerts(limit=100)
        logger.debug(f"Получено {len(alerts)} активных алертов")
        return alerts
    except Exception as e:
        logger.error(f"Ошибка при получении алертов из БД: {e}")
        return []


def resolve_alert(alert_id: int) -> bool:
    """Пометить алерт как решённый"""
    try:
        db = get_db()
        return db.resolve_alert(alert_id)
    except Exception as e:
        logger.error(f"Ошибка при разрешении алерта {alert_id}: {e}")
        return False


def resolve_all_alerts() -> int:
    """Пометить все алерты как решённые"""
    try:
        db = get_db()
        return db.resolve_all_alerts()
    except Exception as e:
        logger.error(f"Ошибка при разрешении всех алертов: {e}")
        return 0


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
                alert_id = alert.get('id', '?')
                severity = alert.get('severity', 'info')
                title = alert.get('title', 'Unknown')
                message = alert.get('message', '')
                created_at = alert.get('created_at', datetime.now())
                
                # Форматируем время
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace(' ', 'T'))
                    except:
                        created_at = datetime.now()
                time_str = created_at.strftime('%H:%M %d.%m.%Y')
                
                # Добавляем префикс в зависимости от типа
                if severity == 'critical':
                    prefix = f"{get_text(user_id, 'common', 'error')}"
                elif severity == 'warning':
                    prefix = f"{get_text(user_id, 'common', 'warning')}"
                else:
                    prefix = f"{get_text(user_id, 'common', 'info')}"
                
                display_text = message if message else title
                text += f"{prefix} #{alert_id} {display_text}\n"
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
        db = get_db()
        alert = db.get_alert_by_id(alert_id)

        if not alert:
            await send_or_edit_message(
                update,
                f"{get_text(user_id, 'common', 'error')}: {get_text(user_id, 'common', 'no_data')}"
            )
            return

        text = f"*{get_text(user_id, 'alerts', 'title')} #{alert_id}:*\n\n"
        
        severity = alert.get('severity', 'info')
        if severity == 'critical':
            text += f"🔴 {get_text(user_id, 'common', 'error')}\n"
        elif severity == 'warning':
            text += f"🟡 {get_text(user_id, 'common', 'warning')}\n"
        else:
            text += f"🔵 {get_text(user_id, 'common', 'info')}\n"
        
        text += f"\n{get_text(user_id, 'alerts', 'message')}: {alert.get('message', alert.get('title', 'Unknown'))}\n"
        
        created_at = alert.get('created_at', datetime.now())
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace(' ', 'T'))
            except:
                created_at = datetime.now()
        text += f"{get_text(user_id, 'alerts', 'created_at')}: {created_at.strftime('%H:%M %d.%m.%Y')}\n"

        # Показываем статус
        resolved = alert.get('resolved', False)
        if resolved:
            text += f"\n✅ {get_text(user_id, 'alerts', 'resolved')}"
            resolved_at = alert.get('resolved_at')
            if resolved_at:
                if isinstance(resolved_at, str):
                    try:
                        resolved_at = datetime.fromisoformat(resolved_at.replace(' ', 'T'))
                    except:
                        resolved_at = datetime.now()
                text += f" {resolved_at.strftime('%H:%M %d.%m.%Y')}"

        keyboard = []
        if not resolved:
            keyboard.append([
                color_button(
                    get_text(user_id, 'alerts', 'clear'),
                    f"alert_resolve_{alert_id}",
                    "danger"
                )
            ])
        
        keyboard.append([
            color_button(
                get_text(user_id, "common", "back"),
                "alerts",
                "primary"
            )
        ])

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
            text = f"✅ {get_text(user_id, 'common', 'success')}\n"
            text += f"{get_text(user_id, 'alerts', 'clear')} #{alert_id}"
        else:
            text = f"❌ {get_text(user_id, 'common', 'error')}: {get_text(user_id, 'common', 'no_data')}"

        reply_markup = get_back_button(get_text, user_id, "alerts")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в resolve_alert_callback: {e}")
        error_text = f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        await send_or_edit_message(update, error_text)
