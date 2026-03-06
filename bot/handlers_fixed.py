#!/usr/bin/env python3
"""
Обработчики команд и callback-ов для Telegram бота мониторинга
ИСПРАВЛЕННАЯ ВЕРСИЯ - без рекурсии
"""
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from .language import get_text, language_manager, get_language_name
from config.settings import TELEGRAM_TOKEN, FEATURES

logger = logging.getLogger(__name__)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_user_id(update: Update) -> int:
    """Получить ID пользователя из обновления"""
    if update.effective_user:
        return update.effective_user.id
    elif update.message and update.message.from_user:
        return update.message.from_user.id
    elif update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    else:
        return 0  # Анонимный пользователь

def format_server_status(status_data: dict, user_id: int) -> str:
    """Форматировать статус сервера для отображения"""
    if status_data.get('status') == 'error':
        return f"❌ {get_text(user_id, 'common', 'error')}: {status_data.get('error', 'Unknown error')}"
    
    if status_data.get('status') == 'offline':
        return f"🔴 {get_text(user_id, 'common', 'error')}: {status_data.get('error', 'Server offline')}"
    
    # Форматируем информацию о диске
    disk = status_data.get('disk', {})
    disk_alert = disk.get('alert', 'ok')
    disk_icon = '🟢' if disk_alert == 'ok' else ('🟡' if disk_alert == 'warning' else '🔴')
    
    # Форматируем информацию о памяти
    memory = status_data.get('memory', {})
    memory_alert = memory.get('alert', 'ok')
    memory_icon = '🟢' if memory_alert == 'ok' else ('🟡' if memory_alert == 'warning' else '🔴')
    
    # Форматируем информацию о CPU
    cpu = status_data.get('cpu', {})
    cpu_alert = cpu.get('alert', 'ok')
    cpu_icon = '🟢' if cpu_alert == 'ok' else ('🟡' if cpu_alert == 'warning' else '🔴')
    
    # Форматируем текст
    text = f"✅ *{status_data.get('name', 'Server')}*\n"
    text += f"📊 *Статус:* Онлайн\n"
    text += f"💾 *Диск:* {disk_icon} {disk.get('percent', 0)}% ({disk.get('free_gb', 0):.1f} GB свободно)\n"
    text += f"🧠 *Память:* {memory_icon} {memory.get('percent', 0)}% ({memory.get('free_gb', 0):.1f} GB свободно)\n"
    text += f"⚡ *CPU:* {cpu_icon} {cpu.get('percent', 0)}%\n"
    text += f"⏰ *Время работы:* {status_data.get('uptime', 'N/A')}"
    
    return text

async def safe_edit_message_text(query, text, parse_mode=None, reply_markup=None):
    """Безопасное редактирование сообщения с обработкой ошибки 'Message is not modified'"""
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # Игнорируем эту ошибку - сообщение уже имеет нужное содержимое
            logger.debug("Сообщение не было изменено (уже имеет актуальный текст)")
        else:
            # Пробрасываем другие ошибки
            raise

async def send_or_edit_message(update: Update, text: str, parse_mode="Markdown", reply_markup=None):
    """Отправить или отредактировать сообщение в зависимости от типа обновления"""
    if update.message:
        return await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.answer()
        await safe_edit_message_text(update.callback_query, text, parse_mode=parse_mode, reply_markup=reply_markup)
        return None

# ==================== КОМАНДЫ ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user_id = get_user_id(update)
    
    # Устанавливаем язык пользователя если его еще нет
    if update.effective_user and update.effective_user.language_code:
        lang = update.effective_user.language_code
        if lang in ['ru', 'en']:
            language_manager.set_user_language(user_id, lang)
    
    welcome_text = get_text(user_id, 'start', 'welcome').format(
        name=update.effective_user.first_name if update.effective_user else ''
    )
    
    # Добавляем кнопку меню
    keyboard = [[InlineKeyboardButton(get_text(user_id, 'menu', 'open'), callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_message(update, welcome_text, reply_markup=reply_markup)
    logger.info(f"Пользователь {user_id} запустил бота")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    user_id = get_user_id(update)
    help_text = get_text(user_id, 'help', 'commands')
    await send_or_edit_message(update, help_text)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /menu"""
    user_id = get_user_id(update)
    
    keyboard = [
        [InlineKeyboardButton("📊 Статус серверов", callback_data="status")],
        [InlineKeyboardButton("🐳 Docker", callback_data="docker")],
        [InlineKeyboardButton("🌐 Сайты", callback_data="sites")],
        [
            InlineKeyboardButton("🌍 Язык", callback_data="language"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="help")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_message(
        update,
        "📱 *Главное меню:*\nВыберите действие:",
        reply_markup=reply_markup
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status"""
    user_id = get_user_id(update)
    
    # Показываем меню выбора сервера для проверки
    keyboard = [
        [
            InlineKeyboardButton("SERV301 🖥", callback_data="check_serv301"),
            InlineKeyboardButton("SERV300 🖥", callback_data="check_serv300")
        ],
        [
            InlineKeyboardButton("Все серверы 🔍", callback_data="check_all"),
            InlineKeyboardButton("Назад ↩", callback_data="back_to_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_message(
        update,
        "🔍 *Выберите сервер для проверки:*",
        reply_markup=reply_markup
    )

async def check_server_status(update: Update, context: ContextTypes.DEFAULT_TYPE, server_id: str) -> None:
    """Проверка статуса сервера (общая функция)"""
    user_id = get_user_id(update)
    
    try:
        from checks.servers import get_server_checker
        
        # Показываем сообщение о проверке
        await send_or_edit_message(update, f"Проверяю {server_id}... ⏳")
        
        checker = get_server_checker()
        
        if server_id == "serv301" and update.message and update.message.chat.id == user_id:
            # Локальная проверка для SERV301
            status = checker.check_local_server()
        else:
            # Удаленная проверка
            status = checker.check_remote_server(server_id)
        
        text = format_server_status(status, user_id)
        await send_or_edit_message(update, text)
        
    except Exception as e:
        error_text = f"❌ Ошибка при проверке {server_id}: {str(e)}"
        logger.error(f"Ошибка при проверке {server_id}: {e}")
        await send_or_edit_message(update, error_text)

async def status301_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status301"""
    await check_server_status(update, context, "serv301")

async def status300_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status300"""
    await check_server_status(update, context, "serv300")

async def check_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status или /check_all"""
    user_id = get_user_id(update)
    
    try:
        from checks.servers import get_server_checker
        from config.settings import get_all_servers
        
        await send_or_edit_message(update, "Проверяю все серверы... ⏳")
        
        checker = get_server_checker()
        all_servers = get_all_servers()
        
        results = []
        for server_id in all_servers:
            try:
                status = checker.check_remote_server(server_id)
                if status.get("status") == "online":
                    results.append(f"✅ {status.get('name', server_id)} - Онлайн")
                else:
                    results.append(f"❌ {status.get('name', server_id)} - Оффлайн")
            except Exception as e:
                results.append(f"⚠️ {server_id} - Ошибка: {str(e)[:50]}")
        
        text = "📊 *Статус всех серверов:*\n\n"
        text += "\n".join(results)
        text += f"\n\n📈 *Всего серверов:* {len(all_servers)}"
        
        await send_or_edit_message(update, text)
        
    except Exception as e:
        error_text = f"❌ Ошибка при проверке всех серверов: {str(e)}"
        logger.error(f"Ошибка в check_all_command: {e}")
        await send_or_edit_message(update, error_text)

async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /disk"""
    user_id = get_user_id(update)
    
    try:
        from checks.servers import get_server_checker
        
        checker = get_server_checker()
        local_status = checker.check_local_server()
        disk_info = local_status.get('disk', {})
        
        text = f"💾 *Информация о диске (SERV301):*\n\n"
        text += f"📁 *Файловая система:* {disk_info.get('filesystem', 'N/A')}\n"
        text += f"📊 *Использовано:* {disk_info.get('percent', 0)}%\n"
        text += f"📈 *Всего:* {disk_info.get('total_gb', 0):.1f} GB\n"
        text += f"📉 *Использовано:* {disk_info.get('used_gb', 0):.1f} GB\n"
        text += f"💚 *Свободно:* {disk_info.get('free_gb', 0):.1f} GB"
        
        await update.message.reply_text(text, parse_mode="Markdown")
        
    except Exception as e:
        error_text = f"❌ Ошибка при получении информации о диске: {str(e)}"
        logger.error(f"Ошибка в disk_command: {e}")
        await update.message.reply_text(error_text)

async def docker_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /docker"""
    user_id = get_user_id(update)
    await send_or_edit_message(
        update,
        f"🐳 {get_text(user_id, 'menu', 'docker')}...\n"
        f"{get_text(user_id, 'common', 'not_implemented')}"
    )

async def site_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /site"""
    user_id = get_user_id(update)
    await send_or_edit_message(
        update,
        f"🌐 {get_text(user_id, 'menu', 'sites')}...\n"
        f"{get_text(user_id, 'common', 'not_implemented')}"
    )

async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /version"""
    user_id = get_user_id(update)
    version_info = get_text(user_id, 'version', 'info').format(
        version="1.0.0",
        python_version=sys.version.split()[0],
        author="Ruslan Semis"
    )
    await update.message.reply_text(version_info, parse_mode="Markdown")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /logs (только для админа)"""
    user_id = get_user_id(update)
    
    # Проверка прав (можно добавить проверку списка админов)
    if user_id != 70107570:  # Только для администратора
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    
    try:
        import subprocess
        # Получаем последние 10 строк логов
        result = subprocess.run(
            ['tail', '-n', '20', 'logs/bot.log'],
            capture_output=True,
            text=True
        )
        
        logs = result.stdout if result.stdout else result.stderr
        if len(logs) > 4000:  # Ограничение Telegram
            logs = logs[-4000:]
        
        await update.message.reply_text(f"📋 *Последние логи:*\n```\n{logs}\n```", parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при чтении логов: {str(e)}")

# ==================== CALLBACK ОБРАБОТЧИКИ ====================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = get_user_id(update)
    callback_data = query.data
    
    logger.info(f"Обработан callback: {callback_data} для пользователя {user_id}")
    
    if callback_data == "menu":
        await menu_command(update, context)
        
    elif callback_data == "status":
        await status_command(update, context)
        
    elif callback_data == "check_serv301":
        await status301_command(update, context)
        
    elif callback_data == "check_serv300":
        await status300_command(update, context)
        
    elif callback_data == "check_all":
        await check_all_command(update, context)
        
    elif callback_data == "docker":
        await docker_command(update, context)
        
    elif callback_data == "sites":
        await site_command(update, context)
        
    elif callback_data == "help":
        await help_command(update, context)
        
    elif callback_data == "language":
        # Показываем выбор языка
        keyboard = [
            [
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
            ],
            [
                InlineKeyboardButton("Назад ↩", callback_data="back_to_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
            "🌍 Выберите язык / Select language:",
            reply_markup=reply_markup
        )
        
    elif callback_data.startswith("lang_"):
        # Установка языка
        lang = callback_data.replace("lang_", "")
        success = language_manager.set_user_language(user_id, lang)
        
        if success:
            await safe_edit_message_text(
                query,
                get_text(user_id, "language", "changed").format(language=get_language_name(lang))
            )
        else:
            await safe_edit_message_text(
                query,
                "❌ Ошибка при смене языка. Попробуйте еще раз."
            )
        
    elif callback_data == "back_to_menu":
        await menu_command(update, context)
        
    else:
        await safe_edit_message_text(
            query,
            f"❌ Неизвестная команда: {callback_data}"
        )

# ==================== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ====================

def register_handlers(application):
    """Регистрация всех обработчиков команд"""
    
    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("status301", status301_command))
    application.add_handler(CommandHandler("status300", status300_command))
    application.add_handler(CommandHandler("disk", disk_command))
    application.add_handler(CommandHandler("docker", docker_command))
    application.add_handler(CommandHandler("site", site_command))
    application.add_handler(CommandHandler("version", version_command))
    application.add_handler(CommandHandler("logs", logs_command))
    
    # Callback обработчики
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("Обработчики команд зарегистрированы")
