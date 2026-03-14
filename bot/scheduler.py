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

from config.loader import get_schedule, get_features, get_admin_chat_id
from bot.language import get_text
from bot.handlers.common import get_user_id
from checks.servers import get_server_checker
from checks.log_monitor import check_logs
from checks.container_monitor import check_containers
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
        self.schedule_config = get_schedule()
        self.features = get_features()
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

        # Ежедневный отчет
        if self.features.get('enable_daily_reports', True):
            self._add_job(
                name="daily_report",
                func=self._send_daily_report,
                cron=self.schedule_config.get('daily_report', '0 9 * * *'),
                description="Ежедневный отчет"
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
                'cron': cron,
                'next_run': job.next_run_time
            }
            logger.info(f"Задача '{name}' добавлена: {description} ({cron})")
        except Exception as e:
            logger.error(f"Ошибка добавления задачи {name}: {e}")

    async def _check_servers_status(self) -> None:
        """Проверить статус всех серверов"""
        logger.info("Запуск автоматической проверки статуса серверов...")
        try:
            checker = get_server_checker()
            # Здесь логика проверки серверов
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
                    else:
                        logger.info(f"Docker на {server_id}: {running}/{total} работают")
                else:
                    logger.error(f"Ошибка проверки Docker на {server_id}: {result.get('error', 'Unknown')}")
        except Exception as e:
            logger.error(f"Ошибка при автоматической проверке Docker: {e}")

    async def _check_logs(self) -> None:
        """Проверить логи"""
        logger.info("Запуск проверки логов...")
        try:
            await check_logs()
        except Exception as e:
            logger.error(f"Ошибка при проверке логов: {e}")

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
            await check_all_sites()
        except Exception as e:
            logger.error(f"Ошибка проверки сайтов: {e}")

    async def _send_daily_report(self) -> None:
        """Отправить ежедневный отчет"""
        logger.info("Подготовка ежедневного отчета...")
        try:
            text = "*ЩОДЕННИЙ ЗВІТ МОНІТОРИНГУ*\n"
            text += f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

            # Проверка сайтов
            sites_results = await check_all_sites()
            text += "*🌐 САЙТЫ:*\n"
            if sites_results:
                for site in sites_results[:5]:
                    status = '✅' if site.get('success') else '❌'
                    text += f"{status} {site.get('url', 'Unknown')}\n"
            else:
                text += "Нет данных\n"

            # Docker статус
            text += "\n*🐳 DOCKER:*\n"
            docker_results = check_all_docker_servers()
            if docker_results:
                for server_id, result in docker_results.items():
                    if result.get('status') == 'success':
                        running = result.get('running_containers', 0)
                        total = result.get('total_containers', 0)
                        text += f"{server_id.upper()}: {running}/{total}\n"
                    else:
                        text += f"{server_id.upper()}: Ошибка\n"
            else:
                text += "Нет данных\n"

            # Отправка
            if self.admin_chat_id:
                await self.application.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=text,
                    parse_mode='Markdown'
                )
                logger.info("Ежедневный отчет отправлен")
            else:
                logger.warning("Не указан admin_chat_id для отправки отчета")

        except Exception as e:
            logger.error(f"Ошибка отправки ежедневного отчета: {e}")

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
                'next_run': info['job'].next_run_time
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
