#!/usr/bin/env python3
"""
Планировщик задач для мониторинга
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.loader import load_config, get_schedule
from checks.servers import get_server_checker
from checks.docker import check_all_docker_servers
from checks.pve_monitor import check_pve
from checks.pbs_monitor import check_pbs
from checks.site_checker import check_all_sites
from checks.container_log_monitor import check_container_logs
from analytics.error_analyzer import record_error, resolve_error_by_server, resolve_error_by_site_url
from bot.notifications import send_daily_report, send_alert

logger = logging.getLogger(__name__)


class MonitoringScheduler:
    """Планировщик задач мониторинга"""

    def __init__(self) -> None:
        self.config = load_config()
        self.schedule_config = get_schedule()
        self.notifications_config = self.config.get('notifications', {})
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self) -> None:
        """Настраивает все запланированные задачи"""
        logger.info("Настройка планировщика задач...")

        jobs = [
            {
                'name': 'server_status_check',
                'func': self._check_servers_status,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('status_check', '*/5 * * * *')),
                'priority': 5,
                'description': 'Проверка статуса серверов'
            },
            {
                'name': 'docker_check',
                'func': self._check_docker,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('docker_check', '*/10 * * * *')),
                'priority': 5,
                'description': 'Проверка Docker контейнеров'
            },
            {
                'name': 'log_check',
                'func': self._check_logs,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('log_check', '*/5 * * * *')),
                'priority': 5,
                'description': 'Проверка логов'
            },
            {
                'name': 'container_log_check',
                'func': self._check_container_logs,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('log_check', '*/5 * * * *')),
                'priority': 5,
                'description': 'Проверка логов контейнеров'
            },
            {
                'name': 'pve_check',
                'func': self._check_pve,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('vm_check', '0 */1 * * *')),
                'priority': 5,
                'description': 'Проверка PVE VM'
            },
            {
                'name': 'pbs_check',
                'func': self._check_pbs,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('backup_check', '0 6 * * *')),
                'priority': 5,
                'description': 'Проверка PBS бэкапов'
            },
            {
                'name': 'site_check',
                'func': self._check_sites,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('site_check', '*/15 * * * *')),
                'priority': 5,
                'description': 'Проверка сайтов'
            },
            {
                'name': 'daily_report',
                'func': self._send_daily_report,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('daily_report', '0 8 * * *')),
                'priority': 10,
                'description': 'Ежедневный отчёт'
            },
            {
                'name': 'trends_analysis',
                'func': self._analyze_trends,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('trends_check', '0 */6 * * *')),
                'priority': 3,
                'description': 'Анализ трендов ошибок'
            },
            {
                'name': 'cleanup_old_data',
                'func': self._cleanup_old_data,
                'trigger': CronTrigger.from_crontab(self.schedule_config.get('cleanup', '0 2 * * 1')),
                'priority': 2,
                'description': 'Очистка старых данных'
            },
        ]

        for job_config in jobs:
            try:
                self.scheduler.add_job(
                    job_config['func'],
                    trigger=job_config['trigger'],
                    id=job_config['name'],
                    name=job_config['name'],
                    replace_existing=True,
                    misfire_grace_time=300,
                    coalesce=True
                )
                logger.info(f"Задача '{job_config['name']}' добавлена: {job_config['description']} ({job_config['trigger']}), приоритет {job_config['priority']}")
            except Exception as e:
                logger.error(f"Ошибка добавления задачи {job_config['name']}: {e}")

        logger.info(f"Настроено {len(jobs)} запланированных задач")

    async def _check_servers_status(self) -> None:
        """Автоматическая проверка статуса серверов"""
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
                    else:
                        # Сервер доступен — резолвим ошибки подключения
                        resolve_error_by_server(server_id)
        except Exception as e:
            logger.error(f"Ошибка при автоматической проверке статуса: {e}")

    async def _check_docker(self) -> None:
        """Проверка Docker контейнеров"""
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
                                    'message': f"Контейнер {container.get('name')} остановлен",
                                    'severity': 'critical'
                                })
                    else:
                        logger.info(f"Docker на {server_id}: {running}/{total} работают")
        except Exception as e:
            logger.error(f"Ошибка при проверке Docker: {e}")

    async def _check_logs(self) -> None:
        """Проверка логов"""
        logger.info("Запуск проверки логов...")
        # Логика проверки логов пока не реализована
        logger.debug("Проверка логов пока не реализована")

    async def _check_container_logs(self) -> None:
        """Проверка логов контейнеров"""
        logger.info("Запуск проверки логов контейнеров...")
        try:
            await check_container_logs()
        except Exception as e:
            logger.error(f"Ошибка при проверке логов контейнеров: {e}")

    async def _check_pve(self) -> None:
        """Проверка PVE VM"""
        logger.info("Запуск проверки PVE VM...")
        try:
            await check_pve()
        except Exception as e:
            logger.error(f"Ошибка при проверке PVE: {e}")

    async def _check_pbs(self) -> None:
        """Проверка PBS бэкапов"""
        logger.info("Запуск проверки PBS бэкапов...")
        try:
            await check_pbs()
        except Exception as e:
            logger.error(f"Ошибка при проверке PBS: {e}")

    async def _check_sites(self) -> None:
        """Проверка сайтов"""
        logger.info("Запуск проверки сайтов...")
        try:
            results = await check_all_sites()
            for result in results:
                if not result.get('success'):
                    record_error({
                        'error_type': 'site_down',
                        'server_id': result.get('server', 'unknown'),
                        'site_url': result.get('url'),
                        'message': f"Сайт {result.get('name')} недоступен: {result.get('error')}",
                        'severity': 'critical',
                        'status_code': result.get('status_code', 0),
                        'response_time': result.get('response_time', 0)
                    })
                else:
                    # Сайт доступен — резолвим ошибки сайта
                    resolve_error_by_site_url(result.get('url'))
        except Exception as e:
            logger.error(f"Ошибка при проверке сайтов: {e}")

    async def _send_daily_report(self) -> None:
        """Отправка ежедневного отчёта"""
        logger.info("Отправка ежедневного отчёта...")
        try:
            # Проверяем, не был ли уже отправлен отчёт сегодня
            flag_file = os.path.join(
                os.path.dirname(__file__), '..', 'database', '.daily_report_sent'
            )
            today = datetime.now().strftime('%Y-%m-%d')
            
            if os.path.exists(flag_file):
                with open(flag_file, 'r') as f:
                    last_sent = f.read().strip()
                    if last_sent == today:
                        logger.info(f"Ежедневный отчёт за {today} уже был отправлен")
                        return
            
            # Отправляем отчёт
            await send_daily_report()
            
            # Сохраняем флаг
            with open(flag_file, 'w') as f:
                f.write(today)
                
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного отчёта: {e}")

    async def _analyze_trends(self) -> None:
        """Анализ трендов ошибок"""
        logger.info("Запуск анализа трендов ошибок...")
        # Логика анализа трендов пока не реализована

    async def _cleanup_old_data(self) -> None:
        """Очистка старых данных"""
        logger.info("Запуск очистки старых данных...")
        # Логика очистки старых данных пока не реализована

    def start(self) -> None:
        """Запуск планировщика"""
        self.scheduler.start()
        logger.info("Планировщик успешно запущен")

    def stop(self) -> None:
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")


def setup_scheduler() -> MonitoringScheduler:
    """Создать и настроить планировщик"""
    scheduler = MonitoringScheduler()
    scheduler.start()
    return scheduler
