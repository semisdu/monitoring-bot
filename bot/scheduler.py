#!/usr/bin/env python3
"""
Планировщик задач для автоматического мониторинга
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import JobQueue

from config.loader import get_schedule, get_features, get_admin_chat_id, load_config
from bot.language import get_text
from bot.notifications import send_daily_report, send_alert
from analytics.error_analyzer import get_current_problems, get_trends, record_error
from checks.servers import get_server_checker
from checks.log_monitor import check_logs
from checks.container_log_monitor import check_container_logs
from checks.pbs_monitor import check_pbs
from checks.pve_monitor import check_pve
from checks.docker import check_all_docker_servers
from checks.site_checker import check_all_sites

logger = logging.getLogger(__name__)


class MonitoringScheduler:
    """Планировщик задач мониторинга"""

    def __init__(self, application):
        """
        Инициализация планировщика.

        Args:
            application: Telegram Application
        """
        self.application = application
        self.job_queue: Optional[JobQueue] = application.job_queue
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.config = load_config()
        self.schedule_config = self.config.get('schedule', {})
        self.features = self.config.get('features', {})
        self.notifications_config = self.config.get('notifications', {})
        self.admin_chat_id = get_admin_chat_id()

    def setup(self) -> None:
        """Настройка всех запланированных задач"""
        logger.info("Настройка планировщика задач...")

        if not self.job_queue:
            logger.warning("JobQueue не доступен, планировщик отключен")
            return

        # Проверка статуса серверов
        if self.features.get('enable_vm_monitoring', True):
            self._add_job(
                name="server_status_check",
                func=self._check_servers_status,
                cron=self.schedule_config.get('status_check', '*/5 * * * *'),
                description="Проверка статуса серверов"
            )

        # Проверка Docker
        if self.features.get('enable_docker', True):
            self._add_job(
                name="docker_check",
                func=self._check_docker,
                cron=self.schedule_config.get('docker_check', '*/10 * * * *'),
                description="Проверка Docker контейнеров"
            )

        # Проверка логов
        if self.features.get('enable_log_monitoring', False):
            self._add_job(
                name="log_check",
                func=self._check_logs,
                cron=self.schedule_config.get('log_check', '*/5 * * * *'),
                description="Проверка логов"
            )

        # Проверка логов контейнеров (НОВАЯ ЗАДАЧА)
        if self.config.get('container_log_monitoring', {}).get('enabled', True):
            self._add_job(
                name="container_log_check",
                func=self._check_container_logs,
                cron=self.schedule_config.get('log_check', '*/5 * * * *'),
                description="Проверка логов контейнеров"
            )

        # Проверка PVE
        if self.features.get('enable_proxmox', True):
            self._add_job(
                name="pve_check",
                func=self._check_pve,
                cron=self.schedule_config.get('vm_check', '0 */1 * * *'),
                description="Проверка PVE VM"
            )

        # Проверка PBS
        if self.features.get('enable_backup_check', True):
            self._add_job(
                name="pbs_check",
                func=self._check_pbs,
                cron=self.schedule_config.get('backup_check', '0 6 * * *'),
                description="Проверка PBS бэкапов"
            )

        # Проверка сайтов
        if self.features.get('enable_site_check', True):
            self._add_job(
                name="site_check",
                func=self._check_sites,
                cron=self.schedule_config.get('site_check', '*/15 * * * *'),
                description="Проверка сайтов"
            )

        # Ежедневный отчёт
        if self.notifications_config.get('daily_report', {}).get('enabled', True):
            report_time = self.notifications_config.get('daily_report', {}).get('time', '09:00')
            hour, minute = map(int, report_time.split(':'))
            self._add_job(
                name="daily_report",
                func=self._send_daily_report,
                cron=f"{minute} {hour} * * *",
                description="Ежедневный отчёт"
            )

        # Аналитика трендов (каждые 6 часов)
        self._add_job(
            name="trends_analysis",
            func=self._analyze_trends,
            cron="0 */6 * * *",
            description="Анализ трендов ошибок"
        )

        # Очистка старых данных (каждую неделю)
        if self.features.get('enable_cleanup', True):
            self._add_job(
                name="cleanup_old_data",
                func=self._cleanup_old_data,
                cron=self.schedule_config.get('cleanup', '0 2 * * 1'),
                description="Очистка старых данных"
            )

        logger.info(f"Настроено {len(self.jobs)} запланированных задач")

    def _add_job(self, name: str, func: Callable, cron: str, description: str) -> None:
        """
        Добавить задачу в планировщик.

        Args:
            name: Имя задачи
            func: Функция для выполнения
            cron: Cron выражение
            description: Описание задачи
        """
        try:
            trigger = CronTrigger.from_crontab(cron)
            job = self.scheduler.add_job(func, trigger, id=name)
            self.jobs[name] = {
                'job': job,
                'description': description,
                'cron': cron
            }
            logger.info(f"Задача '{name}' добавлена: {description} ({cron})")
        except Exception as e:
            logger.error(f"Ошибка добавления задачи {name}: {e}")

    async def _check_servers_status(self) -> None:
        """Проверить статус всех серверов"""
        logger.info("Запуск автоматической проверки статуса серверов...")
        try:
            checker = get_server_checker()
            servers = self.config.get('servers', [])
            
            for server in servers:
                server_id = server.get('id')
                if server_id:
                    status = checker.check_remote_server(server_id)
                    if status.get('status') != 'online':
                        record_error({
                            'error_type': 'connection_error',
                            'server_id': server_id,
                            'message': f"Сервер {server_id} недоступен",
                            'severity': 'critical' if server.get('critical') else 'warning'
                        })
        except Exception as e:
            logger.error(f"Ошибка при автоматической проверке статуса: {e}")

    async def _check_docker(self) -> None:
        """Проверить Docker контейнеры"""
        logger.info("Запуск проверки Docker контейнеров...")
        try:
            results = check_all_docker_servers()
            for server_id, result in results.items():
                if result.get('status') == 'success':
                    containers = result.get('containers', [])
                    running = result.get('running_containers', 0)
                    total = result.get('total_containers', 0)
                    critical_failed = result.get('critical_failed', 0)
                    
                    if critical_failed > 0:
                        logger.warning(f"Docker на {server_id}: {running}/{total} работают ({critical_failed} критических не работают)")
                        
                        for container in containers:
                            if not container.get('running') and container.get('critical'):
                                record_error({
                                    'error_type': 'docker_down',
                                    'server_id': server_id,
                                    'container_name': container.get('name'),
                                    'message': f"Критический контейнер {container.get('name')} остановлен",
                                    'severity': 'critical'
                                })
                    else:
                        logger.info(f"Docker на {server_id}: {running}/{total} работают")
                else:
                    logger.error(f"Ошибка проверки Docker на {server_id}: {result.get('error', 'Unknown')}")
                    record_error({
                        'error_type': 'connection_error',
                        'server_id': server_id,
                        'message': f"Ошибка проверки Docker: {result.get('error', 'Unknown')}",
                        'severity': 'warning'
                    })
        except Exception as e:
            logger.error(f"Ошибка при автоматической проверке Docker: {e}")

    async def _check_logs(self) -> None:
        """Проверить логи"""
        logger.info("Запуск проверки логов...")
        try:
            await check_logs()
        except Exception as e:
            logger.error(f"Ошибка при проверке логов: {e}")

    async def _check_container_logs(self) -> None:
        """Проверить логи контейнеров"""
        logger.info("Запуск проверки логов контейнеров...")
        try:
            await check_container_logs()
        except Exception as e:
            logger.error(f"Ошибка при проверке логов контейнеров: {e}")

    async def _check_pve(self) -> None:
        """Проверить PVE"""
        logger.info("Проверка PVE VM...")
        try:
            await check_pve()
        except Exception as e:
            logger.error(f"Ошибка проверки PVE: {e}")

    async def _check_pbs(self) -> None:
        """Проверить PBS"""
        logger.info("Проверка PBS бэкапов...")
        try:
            await check_pbs()
        except Exception as e:
            logger.error(f"Ошибка проверки PBS: {e}")

    async def _check_sites(self) -> None:
        """Проверить сайты"""
        logger.info("Проверка сайтов...")
        try:
            sites = self.config.get('sites', [])
            results = await check_all_sites()
            
            for site, result in zip(sites, results):
                if result.get('status') != 'up':
                    record_error({
                        'error_type': 'site_down',
                        'site_url': site.get('url'),
                        'server_id': site.get('server_id'),
                        'message': f"Сайт {site.get('name')} недоступен: {result.get('error', 'Unknown')}",
                        'severity': 'critical' if site.get('critical') else 'warning',
                        'status_code': result.get('status_code')
                    })
        except Exception as e:
            logger.error(f"Ошибка проверки сайтов: {e}")

    async def _send_daily_report(self) -> None:
        """Отправить ежедневный отчёт"""
        logger.info("Подготовка ежедневного отчёта...")
        try:
            await send_daily_report()
        except Exception as e:
            logger.error(f"Ошибка отправки ежедневного отчёта: {e}")

    async def _analyze_trends(self) -> None:
        """Анализ трендов ошибок"""
        logger.info("Анализ трендов ошибок...")
        try:
            trends = get_trends(days=7)
            
            if trends['total_errors'] > 0:
                logger.info(f"Тренды за неделю: {trends['total_errors']} ошибок, {trends['unique_errors']} уникальных")
        except Exception as e:
            logger.error(f"Ошибка при анализе трендов: {e}")

    async def _cleanup_old_data(self) -> None:
        """Очистка старых данных из БД аналитики"""
        logger.info("Очистка старых данных...")
        try:
            import sqlite3
            from analytics.error_analyzer import DB_PATH
            
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM errors
                WHERE created_at < datetime('now', '-30 days')
            ''')
            
            cursor.execute('''
                DELETE FROM error_trends
                WHERE date < date('now', '-30 days')
            ''')
            
            deleted_errors = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Очищено {deleted_errors} старых записей")
        except Exception as e:
            logger.error(f"Ошибка при очистке старых данных: {e}")

    def start(self) -> None:
        """Запустить планировщик"""
        if self.jobs:
            self.scheduler.start()
            logger.info("Планировщик успешно запущен")
        else:
            logger.warning("Нет задач для запуска")

    def stop(self) -> None:
        """Остановить планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")

    def get_jobs_info(self) -> List[Dict[str, Any]]:
        """Получить информацию о всех задачах"""
        jobs_info = []
        for name, info in self.jobs.items():
            jobs_info.append({
                'name': name,
                'description': info['description'],
                'cron': info['cron'],
                'next_run': None
            })
        return jobs_info

    async def run_job_now(self, job_name: str) -> bool:
        """
        Запустить задачу немедленно.

        Args:
            job_name: Имя задачи

        Returns:
            True если задача запущена, иначе False
        """
        if job_name in self.jobs:
            try:
                await self.jobs[job_name]['job'].func()
                logger.info(f"Задача '{job_name}' запущена вручную")
                return True
            except Exception as e:
                logger.error(f"Ошибка запуска задачи '{job_name}': {e}")
                return False
        return False


def setup_scheduler(application) -> Optional[MonitoringScheduler]:
    """
    Настройка и запуск планировщика.

    Args:
        application: Telegram Application

    Returns:
        Экземпляр планировщика или None
    """
    try:
        scheduler = MonitoringScheduler(application)
        scheduler.setup()
        scheduler.start()
        return scheduler
    except Exception as e:
        logger.error(f"Ошибка настройки планировщика: {e}")
        return None
