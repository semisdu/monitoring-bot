#!/usr/bin/env python3
"""
Планировщик задач для мониторинга
"""

import logging
import os
import asyncio
from datetime import datetime, timedelta
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
from database.monitoring_db import get_db

logger = logging.getLogger(__name__)


class MonitoringScheduler:
    """Планировщик задач мониторинга"""

    def __init__(self) -> None:
        self.config = load_config()
        self.schedule_config = get_schedule()
        self.notifications_config = self.config.get('notifications', {})
        self.scheduler = AsyncIOScheduler()
        self.admin_chat_id = self.config.get('telegram', {}).get('admin_chat_id')
        self._error_counts: Dict[str, int] = {}
        self._last_error_time: Dict[str, datetime] = {}
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
                self._notify_error(f"❌ Ошибка добавления задачи {job_config['name']}: {e}")

        logger.info(f"Настроено {len(jobs)} запланированных задач")

    def _should_notify(self, job_name: str) -> bool:
        """Проверить, нужно ли отправлять уведомление об ошибке"""
        now = datetime.now()
        
        # Проверяем количество ошибок за последние 5 минут
        if job_name in self._error_counts:
            # Сбрасываем счётчик, если прошло больше 5 минут
            if job_name in self._last_error_time:
                elapsed = (now - self._last_error_time[job_name]).total_seconds()
                if elapsed > 300:  # 5 минут
                    self._error_counts[job_name] = 0
            
            # Если ошибок больше 3 за 5 минут — не спамим
            if self._error_counts.get(job_name, 0) >= 3:
                return False
        
        return True

    def _notify_error(self, message: str, job_name: str = "unknown") -> None:
        """Отправить уведомление об ошибке с защитой от спама"""
        try:
            # Увеличиваем счётчик ошибок
            self._error_counts[job_name] = self._error_counts.get(job_name, 0) + 1
            self._last_error_time[job_name] = datetime.now()
            
            # Проверяем, нужно ли отправлять уведомление
            if not self._should_notify(job_name):
                logger.warning(f"Уведомление об ошибке подавлено (спам-защита): {message[:50]}...")
                return
            
            # Отправляем уведомление
            if self.admin_chat_id:
                asyncio.create_task(send_alert(message))
                logger.info(f"Отправлено уведомление об ошибке: {message[:100]}")
            
            # Сохраняем в БД
            try:
                db = get_db()
                db.add_alert('error', f"[{job_name}] {message[:50]}", message, 'critical')
            except Exception as e:
                logger.error(f"Ошибка сохранения алерта в БД: {e}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")

    async def _run_with_error_handling(self, func, job_name: str, *args, **kwargs) -> Any:
        """Выполнить функцию с обработкой ошибок и ретраями"""
        max_retries = 2
        retry_delay = 5
        
        for attempt in range(max_retries + 1):
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                
                # Если ошибка была, но сейчас всё ок — резолвим
                if job_name in self._error_counts and self._error_counts.get(job_name, 0) > 0:
                    self._error_counts[job_name] = 0
                    
                return result
                
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                logger.error(f"Ошибка в задаче {job_name} (попытка {attempt + 1}/{max_retries + 1}): {error_msg}")
                
                # Если это не последняя попытка — ждём и пробуем снова
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                
                # Если все попытки провалились — отправляем уведомление
                self._notify_error(
                    f"❌ Задача '{job_name}' упала после {max_retries + 1} попыток: {error_msg}",
                    job_name
                )
                
                # Добавляем в БД
                try:
                    db = get_db()
                    db.add_alert(
                        'scheduler_error',
                        f"[{job_name}] Ошибка выполнения",
                        f"Задача {job_name}: {error_msg} (попыток: {attempt + 1})",
                        'critical'
                    )
                except Exception as db_error:
                    logger.error(f"Ошибка сохранения алерта: {db_error}")
                
                return None

    async def _check_servers_status(self) -> None:
        """Автоматическая проверка статуса серверов"""
        logger.info("Запуск автоматической проверки статуса серверов...")
        await self._run_with_error_handling(
            self._do_check_servers_status, "server_status_check"
        )

    async def _do_check_servers_status(self) -> None:
        """Реальная проверка статуса серверов"""
        try:
            checker = get_server_checker()
            servers = self.config.get('servers', [])
            
            for server in servers:
                server_id = server.get('id')
                if server_id:
                    try:
                        status = checker.check_remote_server(server_id)
                        if status.get('status') != 'online':
                            record_error({
                                'error_type': 'connection_error',
                                'server_id': server_id,
                                'message': f"Сервер {server_id} недоступен",
                                'severity': 'critical' if server.get('critical') else 'warning'
                            })
                            # Сохраняем в БД
                            try:
                                db = get_db()
                                db.add_alert(
                                    'connection_error',
                                    f"Сервер {server_id} недоступен",
                                    f"Сервер {server.get('name', server_id)} не отвечает",
                                    'critical' if server.get('critical') else 'warning'
                                )
                            except Exception as e:
                                logger.error(f"Ошибка сохранения алерта: {e}")
                        else:
                            # Сервер доступен — резолвим ошибки подключения
                            resolve_error_by_server(server_id)
                    except Exception as e:
                        logger.error(f"Ошибка проверки сервера {server_id}: {e}")
                        self._notify_error(
                            f"⚠️ Ошибка проверки сервера {server_id}: {e}",
                            "server_status_check"
                        )
        except Exception as e:
            logger.error(f"Ошибка при автоматической проверке статуса: {e}")
            raise

    async def _check_docker(self) -> None:
        """Проверка Docker контейнеров"""
        logger.info("Запуск проверки Docker контейнеров...")
        await self._run_with_error_handling(self._do_check_docker, "docker_check")

    async def _do_check_docker(self) -> None:
        """Реальная проверка Docker"""
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
                                # Сохраняем в БД
                                try:
                                    db = get_db()
                                    db.add_alert(
                                        'docker_down',
                                        f"Контейнер {container.get('name')} остановлен",
                                        f"Критический контейнер {container.get('name')} на {server_id} не работает",
                                        'critical'
                                    )
                                except Exception as e:
                                    logger.error(f"Ошибка сохранения алерта: {e}")
                    else:
                        logger.info(f"Docker на {server_id}: {running}/{total} работают")
                else:
                    error = result.get('error', 'Unknown error')
                    logger.warning(f"Docker на {server_id}: ошибка - {error}")
                    self._notify_error(
                        f"⚠️ Ошибка Docker на {server_id}: {error}",
                        "docker_check"
                    )
        except Exception as e:
            logger.error(f"Ошибка при проверке Docker: {e}")
            raise

    async def _check_logs(self) -> None:
        """Проверка логов"""
        logger.info("Запуск проверки логов...")
        # Логика проверки логов пока не реализована
        logger.debug("Проверка логов пока не реализована")

    async def _check_container_logs(self) -> None:
        """Проверка логов контейнеров"""
        logger.info("Запуск проверки логов контейнеров...")
        await self._run_with_error_handling(
            self._do_check_container_logs, "container_log_check"
        )

    async def _do_check_container_logs(self) -> None:
        """Реальная проверка логов контейнеров"""
        try:
            await check_container_logs()
        except Exception as e:
            logger.error(f"Ошибка при проверке логов контейнеров: {e}")
            raise

    async def _check_pve(self) -> None:
        """Проверка PVE VM"""
        logger.info("Запуск проверки PVE VM...")
        await self._run_with_error_handling(self._do_check_pve, "pve_check")

    async def _do_check_pve(self) -> None:
        """Реальная проверка PVE"""
        try:
            await check_pve()
        except Exception as e:
            logger.error(f"Ошибка при проверке PVE: {e}")
            raise

    async def _check_pbs(self) -> None:
        """Проверка PBS бэкапов"""
        logger.info("Запуск проверки PBS бэкапов...")
        await self._run_with_error_handling(self._do_check_pbs, "pbs_check")

    async def _do_check_pbs(self) -> None:
        """Реальная проверка PBS"""
        try:
            await check_pbs()
        except Exception as e:
            logger.error(f"Ошибка при проверке PBS: {e}")
            raise

    async def _check_sites(self) -> None:
        """Проверка сайтов"""
        logger.info("Запуск проверки сайтов...")
        await self._run_with_error_handling(self._do_check_sites, "site_check")

    async def _do_check_sites(self) -> None:
        """Реальная проверка сайтов"""
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
                    # Сохраняем в БД
                    try:
                        db = get_db()
                        db.add_alert(
                            'site_down',
                            f"Сайт {result.get('name')} недоступен",
                            f"{result.get('url')}: {result.get('error')}",
                            'critical'
                        )
                    except Exception as e:
                        logger.error(f"Ошибка сохранения алерта: {e}")
                else:
                    # Сайт доступен — резолвим ошибки сайта
                    resolve_error_by_site_url(result.get('url'))
        except Exception as e:
            logger.error(f"Ошибка при проверке сайтов: {e}")
            raise

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
            self._notify_error(
                f"⚠️ Ошибка отправки ежедневного отчёта: {e}",
                "daily_report"
            )

    async def _analyze_trends(self) -> None:
        """Анализ трендов ошибок"""
        logger.info("Запуск анализа трендов ошибок...")
        # Логика анализа трендов пока не реализована

    async def _cleanup_old_data(self) -> None:
        """Очистка старых данных"""
        logger.info("Запуск очистки старых данных...")
        try:
            db = get_db()
            result = db.cleanup_old_checks(days_old=30)
            logger.info(f"Очистка данных завершена: {result}")
        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")
            self._notify_error(
                f"⚠️ Ошибка очистки старых данных: {e}",
                "cleanup_old_data"
            )

    def start(self) -> None:
        """Запуск планировщика"""
        try:
            self.scheduler.start()
            logger.info("Планировщик успешно запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска планировщика: {e}")
            self._notify_error(f"❌ Ошибка запуска планировщика: {e}", "scheduler_start")

    def stop(self) -> None:
        """Остановка планировщика"""
        try:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки планировщика: {e}")


def setup_scheduler() -> MonitoringScheduler:
    """Создать и настроить планировщик"""
    scheduler = MonitoringScheduler()
    scheduler.start()
    return scheduler
