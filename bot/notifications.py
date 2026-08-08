#!/usr/bin/env python3
"""
Модуль уведомлений и алертов
Отправляет мгновенные уведомления о проблемах и ежедневные отчёты
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from telegram import Bot

from config.loader import load_config, get_telegram_token, get_admin_chat_id
from analytics.error_analyzer import get_current_problems, get_trends
from bot.language import get_text, get_user_language

logger = logging.getLogger(__name__)


class NotificationManager:
    """Менеджер уведомлений"""

    def __init__(self, bot: Bot):
        """Инициализация менеджера уведомлений с передачей бота извне"""
        self.config = load_config()
        self.notifications_config = self.config.get('notifications', {})
        self.bot = bot
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

    async def send_daily_report(self, chat_id: Optional[int] = None) -> bool:
        """
        Отправляет ежедневный отчёт.
        
        Args:
            chat_id: ID получателя. Если None — отправляется админу.
        """
        try:
            if not self.notifications_config.get('daily_report', {}).get('enabled', True):
                return False

            target_chat_id = chat_id if chat_id is not None else self.admin_chat_id
            
            # Определяем язык пользователя
            user_lang = get_user_language(target_chat_id)
            
            report = await self._generate_daily_report(target_chat_id, user_lang)
            
            await self.bot.send_message(
                chat_id=target_chat_id,
                text=report,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            logger.info(f"Ежедневный отчёт отправлен пользователю {target_chat_id} на языке {user_lang}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного отчёта: {e}")
            return False

    async def _run_pre_report_checks(self) -> None:
        """Запускает все проверки перед формированием отчёта"""
        try:
            from checks.site_checker import check_all_sites
            from checks.pve_monitor import check_pve
            from checks.pbs_monitor import check_pbs
            from checks.docker import check_all_docker_servers
            from checks.container_log_monitor import check_container_logs
            
            # Запускаем все проверки параллельно
            results = await asyncio.gather(
                check_all_sites(),
                check_pve(),
                check_pbs(),
                asyncio.to_thread(check_all_docker_servers),
                check_container_logs(),
                return_exceptions=True
            )
            
            # Логируем результат
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Ошибка при проверке #{i}: {result}")
            
            logger.info("✅ Предварительные проверки для отчёта выполнены")
        except Exception as e:
            logger.error(f"Ошибка при выполнении предварительных проверок: {e}")

    async def _generate_daily_report(self, chat_id: int, lang: str) -> str:
        """Генерирует ежедневный отчёт на указанном языке"""
        # 🔄 Сначала делаем свежие проверки
        await self._run_pre_report_checks()
        
        # Теперь берём данные из БД (они уже обновлены)
        now = datetime.now()
        date_str = now.strftime('%d.%m.%Y')
        
        problems = get_current_problems()
        trends = get_trends(days=7)
        
        # Используем get_text с переданным chat_id для определения языка
        t = lambda key: get_text(chat_id, 'daily_report', key)
        
        report = f"📊 {t('title')} 📊\n"
        report += f"📅 {date_str}\n\n"
        report += f"*{t('summary')}:*\n"
        report += f"• {t('total_errors')}: {trends['total_errors']}\n"
        report += f"• {t('unique_problems')}: {trends['unique_errors']}\n"
        report += f"• {t('resolved')}: {trends['resolved']}\n\n"
        
        if problems:
            report += f"*{t('active')}:*\n"
            for i, p in enumerate(problems[:5], 1):
                severity_icon = "🚨" if p['severity'] == 'critical' else "⚠"
                # Получаем название типа ошибки из языкового файла
                error_title = get_text(chat_id, 'analytics', 'error_types', key=p['error_type'])
                report += f"{i}. {severity_icon} *{error_title}*\n"
                report += f"   📝 {p['message'][:100]}\n"
                if p['server_id']:
                    report += f"   🖥 {p['server_id']}\n"
                if p['occurrence_count'] > 1:
                    report += f"   🔄 Повторений: {p['occurrence_count']}\n"
                report += "\n"
        else:
            report += f"*{t('no_active_problems')}*\n\n"
        
        if trends['by_type']:
            report += f"*{t('distribution')}:*\n"
            for item in trends['by_type'][:5]:
                error_title = get_text(chat_id, 'analytics', 'error_types', key=item['error_type'])
                report += f"• {error_title}: {item['count']}\n"
            report += "\n"
        
        if trends['by_day']:
            report += f"*{t('dynamics')}:*\n"
            for d in trends['by_day']:
                report += f"• {d['date']}: {d['count']} {t('errors_count')}\n"
        
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


async def send_daily_report(chat_id: Optional[int] = None) -> bool:
    return await get_notification_manager().send_daily_report(chat_id)


async def send_test() -> bool:
    return await get_notification_manager().send_test_notification()
