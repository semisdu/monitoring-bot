#!/usr/env python3
"""
Модуль уведомлений и алертов
Отправляет мгновенные уведомления о проблемах и ежедневные отчёты
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from config.loader import load_config, get_telegram_token, get_admin_chat_id
from analytics.error_analyzer import get_current_problems, get_trends

logger = logging.getLogger(__name__)


class NotificationManager:
    """Менеджер уведомлений"""

    def __init__(self, bot: Bot):
        """Инициализация менеджера уведомлений с передачей бота извне"""
        self.config = load_config()
        self.notifications_config = self.config.get('notifications', {})
        self.bot = bot  # <-- ИСПОЛЬЗУЕМ ПЕРЕДАННОГО БОТА
        self.admin_chat_id = get_admin_chat_id()
        
        # Кэш для предотвращения спама
        self._alert_cache = {}
        self._cache_cleanup_task = None

    async def send_instant_alert(self, error_data: Dict[str, Any]) -> bool:
        """Отправляет мгновенное уведомление об ошибке."""
        try:
            if not self.notifications_config.get('instant_alerts', {}).get('enabled', True):
                return False

            cooldown = self.notifications_config.get('instant_alerts', {}).get('cooldown_minutes', 30)
            cache_key = self._get_cache_key(error_data)
            
            if cache_key in self._alert_cache:
                last_sent = self._alert_cache[cache_key]
                if datetime.now() - last_sent < timedelta(minutes=cooldown):
                    logger.debug(f"Уведомление {cache_key} в кулдауне")
                    return False

            message = await self._format_instant_alert(error_data)
            
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            self._alert_cache[cache_key] = datetime.now()
            
            if self.notifications_config.get('instant_alerts', {}).get('group_during_cooldown', True):
                asyncio.create_task(self._schedule_cache_cleanup(cache_key, cooldown))
            
            logger.info(f"Отправлено мгновенное уведомление: {error_data.get('error_type')}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
            return False

    def _get_cache_key(self, error_data: Dict[str, Any]) -> str:
        return f"{error_data.get('error_type')}_{error_data.get('server_id')}_{error_data.get('container_name')}"

    async def _schedule_cache_cleanup(self, cache_key: str, minutes: int):
        await asyncio.sleep(minutes * 60)
        if cache_key in self._alert_cache:
            del self._alert_cache[cache_key]

    async def _format_instant_alert(self, error_data: Dict[str, Any]) -> str:
        error_type = error_data.get('error_type', 'unknown')
        severity = error_data.get('severity', 'warning')
        
        icon = "🚨" if severity == 'critical' else "⚠" if severity == 'warning' else "ℹ"
        
        message = f"{icon} *{self._get_error_title(error_type)}*\n\n"
        
        if error_data.get('server_id'):
            message += f"🖥 Сервер: `{error_data['server_id']}`\n"
        if error_data.get('container_name'):
            message += f"📦 Контейнер: `{error_data['container_name']}`\n"
        if error_data.get('site_url'):
            message += f"🌐 Сайт: {error_data['site_url']}\n"
        if error_data.get('message'):
            message += f"\n📝 {error_data['message']}\n"
        
        message += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        return message

    def _get_error_title(self, error_type: str) -> str:
        titles = {
            'docker_down': 'Контейнер остановлен',
            'site_down': 'Сайт недоступен',
            'high_cpu': 'Высокая нагрузка CPU',
            'disk_full': 'Заканчивается место на диске',
            'backup_old': 'Устаревший бэкап',
            'connection_error': 'Ошибка подключения',
            'test_error': 'Тестовое уведомление'
        }
        return titles.get(error_type, 'Обнаружена проблема')

    async def send_daily_report(self) -> bool:
        """Отправляет ежедневный отчёт."""
        try:
            if not self.notifications_config.get('daily_report', {}).get('enabled', True):
                return False

            report = await self._generate_daily_report()
            
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=report,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            logger.info("Ежедневный отчёт отправлен")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного отчёта: {e}")
            return False

    async def _generate_daily_report(self) -> str:
        now = datetime.now()
        date_str = now.strftime('%d.%m.%Y')
        
        problems = get_current_problems()
        trends = get_trends(days=7)
        
        report = f"📊 *ЕЖЕДНЕВНЫЙ ОТЧЁТ* 📊\n"
        report += f"📅 {date_str}\n\n"
        report += f"*📈 ОБЩАЯ СТАТИСТИКА:*\n"
        report += f"• Всего ошибок за неделю: {trends['total_errors']}\n"
        report += f"• Уникальных проблем: {trends['unique_errors']}\n"
        report += f"• Решено: {trends['resolved']}\n\n"
        
        if problems:
            report += f"*🔴 АКТИВНЫЕ ПРОБЛЕМЫ:*\n"
            for i, p in enumerate(problems[:5], 1):
                severity_icon = "🚨" if p['severity'] == 'critical' else "⚠"
                report += f"{i}. {severity_icon} *{self._get_error_title(p['error_type'])}*\n"
                report += f"   📝 {p['message'][:100]}\n"
                if p['server_id']:
                    report += f"   🖥 {p['server_id']}\n"
                if p['occurrence_count'] > 1:
                    report += f"   🔄 Повторений: {p['occurrence_count']}\n"
                report += "\n"
        
        if trends['by_type']:
            report += f"*📊 РАСПРЕДЕЛЕНИЕ ПО ТИПАМ:*\n"
            for t in trends['by_type'][:5]:
                report += f"• {self._get_error_title(t['type'])}: {t['count']}\n"
            report += "\n"
        
        if trends['by_day']:
            report += f"*📈 ДИНАМИКА ЗА НЕДЕЛЮ:*\n"
            for d in trends['by_day']:
                report += f"• {d['date']}: {d['count']} ошибок\n"
        
        return report

    async def send_test_notification(self) -> bool:
        """Отправляет тестовое уведомление."""
        try:
            test_data = {
                'error_type': 'test_error',
                'severity': 'info',
                'message': 'Это тестовое уведомление. Если вы это видите — всё работает!',
                'server_id': 'test-server'
            }
            return await self.send_instant_alert(test_data)
        except Exception as e:
            logger.error(f"Ошибка при отправке тестового уведомления: {e}")
            return False


# Глобальный экземпляр (будет установлен из core.py)
_notification_manager: Optional[NotificationManager] = None


def init_notification_manager(bot: Bot) -> None:
    """Инициализирует менеджер уведомлений с переданным ботом"""
    global _notification_manager
    _notification_manager = NotificationManager(bot)


def get_notification_manager() -> NotificationManager:
    """Получить экземпляр менеджера уведомлений"""
    global _notification_manager
    if _notification_manager is None:
        raise RuntimeError("NotificationManager не инициализирован. Вызови init_notification_manager()")
    return _notification_manager


async def send_alert(error_data: Dict[str, Any]) -> bool:
    return await get_notification_manager().send_instant_alert(error_data)


async def send_daily_report() -> bool:
    return await get_notification_manager().send_daily_report()


async def send_test() -> bool:
    return await get_notification_manager().send_test_notification()
