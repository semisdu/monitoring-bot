#!/usr/bin/env python3
"""
Обработчики команд для отчётов и аналитики
"""

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.language import get_text
from bot.handlers.common import get_user_id, send_or_edit_message
from bot.keyboards import color_button, get_back_button
from bot.notifications import send_daily_report, send_test
from analytics.error_analyzer import get_current_problems, get_trends, resolve_error

logger = logging.getLogger(__name__)


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /report - меню отчётов"""
    user_id = get_user_id(update)

    text = f"*{get_text(user_id, 'report', 'title')}:*\n\n"
    text += f"{get_text(user_id, 'common', 'select_action')}\n"

    keyboard = [
        [
            color_button(
                get_text(user_id, 'report', 'now'),
                "report_now",
                "success"
            )
        ],
        [
            color_button(
                get_text(user_id, 'trends', 'title'),
                "show_trends",
                "primary"
            )
        ],
        [
            color_button(
                get_text(user_id, 'alerts', 'title'),
                "show_active_problems",
                "danger"
            )
        ],
        [
            color_button(
                get_text(user_id, 'report', 'test'),
                "report_test",
                "primary"
            )
        ],
        [
            color_button(
                get_text(user_id, "common", "back"),
                "menu",
                "primary"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, text, reply_markup=reply_markup)


async def report_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сформировать отчёт сейчас"""
    user_id = get_user_id(update)

    await send_or_edit_message(
        update,
        get_text(user_id, 'report', 'generating')
    )

    try:
        await send_daily_report()
        
        text = f"*{get_text(user_id, 'report', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'report', 'generated')}\n\n"
        text += f"{get_text(user_id, 'common', 'select_action')}\n"

        keyboard = [
            [
                color_button(
                    get_text(user_id, 'report', 'now'),
                    "report_now",
                    "success"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'trends', 'title'),
                    "show_trends",
                    "primary"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'alerts', 'title'),
                    "show_active_problems",
                    "danger"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'report', 'test'),
                    "report_test",
                    "primary"
                )
            ],
            [
                color_button(
                    get_text(user_id, "common", "back"),
                    "menu",
                    "primary"
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit_message(update, text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Ошибка при формировании отчёта: {e}")
        await send_or_edit_message(
            update,
            f"{get_text(user_id, 'common', 'error')}: {get_text(user_id, 'report', 'failed')}"
        )


async def show_trends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать тренды ошибок"""
    user_id = get_user_id(update)

    await send_or_edit_message(
        update,
        f"{get_text(user_id, 'common', 'loading')}..."
    )

    try:
        trends = get_trends(days=7)

        text = f"*{get_text(user_id, 'trends', 'title')}*\n\n"

        text += f"*{get_text(user_id, 'analytics', 'daily_report_summary')}:*\n"
        text += f"• {get_text(user_id, 'analytics', 'daily_report_total_errors')}: {trends['total_errors']}\n"
        text += f"• {get_text(user_id, 'analytics', 'daily_report_unique_problems')}: {trends['unique_errors']}\n"
        text += f"• {get_text(user_id, 'analytics', 'daily_report_resolved')}: {trends['resolved']}\n\n"

        if trends['by_type']:
            text += f"*{get_text(user_id, 'trends', 'by_type')}:*\n"
            for t in trends['by_type']:
                error_type_key = f"error_types_{t['type']}"
                error_type = get_text(user_id, 'analytics', error_type_key)
                text += f"• {error_type}: {t['count']}\n"
            text += "\n"

        if trends['by_day']:
            text += f"*{get_text(user_id, 'trends', 'by_day')}:*\n"
            for d in trends['by_day']:
                total_errors_text = get_text(user_id, 'analytics', 'daily_report_total_errors').lower()
                text += f"• {d['date']}: {d['count']} {total_errors_text}\n"
            text += "\n"

        problems = get_current_problems(limit=5)
        if problems:
            text += f"*{get_text(user_id, 'analytics', 'daily_report_active')}:*\n"
            for p in problems:
                severity_icon = "🚨" if p['severity'] == 'critical' else "⚠"
                error_type_key = f"error_types_{p['error_type']}"
                error_type = get_text(user_id, 'analytics', error_type_key)
                text += f"{severity_icon} {error_type} (x{p['occurrence_count']})\n"

        reply_markup = get_back_button(get_text, user_id, "report")
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при показе трендов: {e}")
        await send_or_edit_message(
            update,
            f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        )


async def show_active_problems(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать активные проблемы"""
    user_id = get_user_id(update)

    try:
        problems = get_current_problems(limit=20)

        text = f"*{get_text(user_id, 'alerts', 'title')}:*\n\n"

        if not problems:
            text += get_text(user_id, 'alerts', 'no_alerts')
        else:
            for i, p in enumerate(problems, 1):
                severity_icon = "🚨" if p['severity'] == 'critical' else "⚠"
                error_type_key = f"error_types_{p['error_type']}"
                error_type = get_text(user_id, 'analytics', error_type_key)

                text += f"{i}. {severity_icon} *{error_type}*\n"
                text += f"   📝 {p['message'][:100]}\n"

                if p['server_id']:
                    text += f"   🖥 {p['server_id']}\n"
                if p['container_name']:
                    text += f"   📦 {p['container_name']}\n"
                if p['site_url']:
                    text += f"   🌐 {p['site_url']}\n"

                text += f"   🔄 {get_text(user_id, 'common', 'total')}: {p['occurrence_count']}\n"
                text += f"   ⏰ {p['last_seen'][:19]}\n\n"

        if problems:
            if len(problems) == 1:
                keyboard = [
                    [
                        color_button(
                            get_text(user_id, 'alerts', 'clear'),
                            f"resolve_error_{problems[0]['id']}",
                            "danger"
                        )
                    ],
                    [
                        color_button(
                            get_text(user_id, "common", "back"),
                            "report",
                            "primary"
                        )
                    ]
                ]
            else:
                keyboard = [
                    [
                        color_button(
                            get_text(user_id, 'alerts', 'clear_all'),
                            "resolve_all_errors",
                            "danger"
                        )
                    ],
                    [
                        color_button(
                            get_text(user_id, "common", "back"),
                            "report",
                            "primary"
                        )
                    ]
                ]
        else:
            keyboard = [[
                color_button(
                    get_text(user_id, "common", "back"),
                    "report",
                    "primary"
                )
            ]]

        await send_or_edit_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка при показе активных проблем: {e}")
        await send_or_edit_message(
            update,
            f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        )


async def resolve_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, error_id: int) -> None:
    """Пометить ошибку как решённую"""
    user_id = get_user_id(update)

    try:
        if resolve_error(error_id):
            text = f"{get_text(user_id, 'common', 'success')}\n"
            text += f"{get_text(user_id, 'alerts', 'clear')} #{error_id}"
        else:
            text = f"{get_text(user_id, 'common', 'error')}: {get_text(user_id, 'common', 'no_data')}"

        await show_active_problems(update, context)

    except Exception as e:
        logger.error(f"Ошибка при разрешении ошибки {error_id}: {e}")
        await send_or_edit_message(
            update,
            f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        )


async def resolve_all_errors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пометить все ошибки как решённые"""
    user_id = get_user_id(update)

    try:
        problems = get_current_problems()
        count = 0

        for p in problems:
            if resolve_error(p['id']):
                count += 1

        text = f"*{get_text(user_id, 'report', 'title')}:*\n\n"
        text += f"{get_text(user_id, 'common', 'success')}\n"
        text += f"{get_text(user_id, 'alerts', 'clear_all')}: {count}\n\n"
        text += f"{get_text(user_id, 'common', 'select_action')}\n"

        keyboard = [
            [
                color_button(
                    get_text(user_id, 'report', 'now'),
                    "report_now",
                    "success"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'trends', 'title'),
                    "show_trends",
                    "primary"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'alerts', 'title'),
                    "show_active_problems",
                    "danger"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'report', 'test'),
                    "report_test",
                    "primary"
                )
            ],
            [
                color_button(
                    get_text(user_id, "common", "back"),
                    "menu",
                    "primary"
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_or_edit_message(update, text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при разрешении всех ошибок: {e}")
        await send_or_edit_message(
            update,
            f"{get_text(user_id, 'common', 'error')}: {str(e)}"
        )


async def report_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправить тестовое уведомление"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    user_id = get_user_id(update)
    
    # Редактируем текущее сообщение - показываем загрузку
    await query.edit_message_text(
        text=f"🔄 {get_text(user_id, 'common', 'loading')}...",
        parse_mode="Markdown"
    )
    
    try:
        result = await send_test()
        
        if result:
            result_text = get_text(user_id, 'notifications', 'test_success')
        else:
            result_text = f"⚠ {get_text(user_id, 'notifications', 'test_fail')}\n\nВозможно, сработал кулдаун. Подождите 30 минут."
        
        # Показываем результат и меню отчётов с кнопкой "Назад"
        final_text = f"*{get_text(user_id, 'report', 'title')}:*\n\n"
        final_text += f"{result_text}\n\n"
        final_text += f"{get_text(user_id, 'common', 'select_action')}\n"
        
        keyboard = [
            [
                color_button(
                    get_text(user_id, 'report', 'now'),
                    "report_now",
                    "success"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'trends', 'title'),
                    "show_trends",
                    "primary"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'alerts', 'title'),
                    "show_active_problems",
                    "danger"
                )
            ],
            [
                color_button(
                    get_text(user_id, 'report', 'test'),
                    "report_test",
                    "primary"
                )
            ],
            [
                color_button(
                    get_text(user_id, "common", "back"),
                    "menu",
                    "primary"
                )
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Редактируем то же сообщение - показываем результат + меню
        await query.edit_message_text(
            text=final_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отправке тестового уведомления: {e}")
        await query.edit_message_text(
            text=f"{get_text(user_id, 'common', 'error')}: {str(e)}",
            parse_mode="Markdown"
        )
