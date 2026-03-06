#!/usr/bin/env python3
"""
Планировщик задач для автоматического мониторинга
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram.ext import JobQueue

from config.settings import SCHEDULE, FEATURES

logger = logging.getLogger(__name__)


class MonitoringScheduler:
    """Планировщик задач мониторинга"""
    
    def __init__(self, job_queue: JobQueue) -> None:
        """
        Инициализация планировщика.
        
        Args:
            job_queue: JobQueue из Telegram приложения
        """
        self.job_queue: JobQueue = job_queue
        self.jobs: Dict[str, Dict[str, Any]] = {}
        
    def setup_scheduled_tasks(self) -> None:
        """Настройка всех запланированных задач."""
        logger.info("Настройка запланированных задач...")
        
        # === ПРОВЕРКА СТАТУСА СЕРВЕРОВ ===
        if FEATURES.get("enable_log_monitoring", True):
            self._add_job(
                "status_check",
                SCHEDULE["status_check"],
                self.check_servers_status,
                "Проверка статуса серверов"
            )
        
        # === ПРОВЕРКА ЛОГОВ НА ХОСТЕ ===
        if FEATURES.get("enable_log_monitoring", True):
            self._add_job(
                "log_check", 
                SCHEDULE["log_check"],
                self.check_logs,
                "Проверка логов на критические ошибки"
            )
        
        # === ПРОВЕРКА DOCKER КОНТЕЙНЕРОВ (СТАТУС) ===
        if FEATURES.get("enable_docker", True):
            self._add_job(
                "docker_check",
                SCHEDULE["docker_check"],
                self.check_docker,
                "Проверка Docker контейнеров"
            )
        
        # === ПРОВЕРКА СТАТУСА КРИТИЧЕСКИХ КОНТЕЙНЕРОВ (UP/DOWN) ===
        self._add_job(
            "containers_check",
            "*/5 * * * *",
            self.check_containers_status,
            "Перевірка статусу критичних контейнерів"
        )
        
        # === 🔥 НОВОЕ: ПРОВЕРКА ЛОГОВ ВНУТРИ КОНТЕЙНЕРОВ ===
        self._add_job(
            "container_logs_check",
            "*/10 * * * *",  # Каждые 10 минут
            self.check_container_logs,
            "Перевірка логів Docker контейнерів на помилки"
        )
        
        # === ПРОВЕРКА PVE VM ===
        self._add_job(
            "pve_check",
            "*/10 * * * *",
            self.check_pve_vms,
            "Перевірка VM в PVE"
        )
        
        # === ПРОВЕРКА PBS БЭКАПОВ ===
        self._add_job(
            "pbs_check",
            "0 */6 * * *",
            self.check_pbs_backups,
            "Перевірка бэкапів PBS"
        )
        
        # === ЕЖЕДНЕВНЫЙ ОТЧЕТ ===
        if FEATURES.get("enable_daily_reports", True):
            self._add_job(
                "daily_report",
                SCHEDULE["daily_report"],
                self.send_daily_report,
                "Ежедневный отчет"
            )
        
        # === ОЧИСТКА СТАРЫХ ДАННЫХ ===
        self._add_job(
            "cleanup",
            SCHEDULE["cleanup"],
            self.cleanup_old_data,
            "Очистка старых данных"
        )
        
        logger.info(f"✅ Настроено {len(self.jobs)} запланированных задач")
    
    def _add_job(self, name: str, cron_expr: str, callback, description: str) -> None:
        """
        Добавить задачу в планировщик.
        
        Args:
            name: Имя задачи
            cron_expr: Cron выражение
            callback: Функция для выполнения
            description: Описание задачи
        """
        try:
            parts = cron_expr.split()
            if len(parts) != 5:
                logger.error(f"❌ Некорректное cron выражение для задачи {name}: {cron_expr}")
                return
            
            job = self.job_queue.run_custom(
                callback=callback,
                job_kwargs={
                    'trigger': 'cron',
                    'minute': parts[0],
                    'hour': parts[1],
                    'day': parts[2],
                    'month': parts[3],
                    'day_of_week': parts[4],
                    'name': name,
                    'misfire_grace_time': 86400,
                    'coalesce': True
                }
            )
            
            self.jobs[name] = {
                'job': job,
                'description': description,
                'schedule': cron_expr,
                'next_run': job.next_t
            }
            
            logger.info(f"✅ Задача '{name}' добавлена: {description} ({cron_expr})")
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления задачи {name}: {e}")
    
    # ==================== ОСНОВНЫЕ ЗАДАЧИ ====================
    
    async def check_servers_status(self, context) -> None:
        """Проверка статуса серверов."""
        logger.info("🔍 Запуск автоматической проверки статуса серверов...")
        # TODO: Реализовать проверку серверов
        pass
    
    async def check_logs(self, context) -> None:
        """Проверка логов на критические ошибки (на хосте)."""
        logger.info("📝 Запуск автоматической проверки логов...")
        # TODO: Реализовать проверку логов
        pass
    
    async def check_docker(self, context) -> None:
        """Проверка статуса Docker контейнеров."""
        logger.info("🐳 Запуск автоматической проверки Docker контейнеров...")
        
        try:
            from checks.docker import check_all_docker_servers
            results = check_all_docker_servers()
            
            for server_id, result in results.items():
                if result.get("status") == "success":
                    total = result.get("total_containers", 0)
                    running = result.get("running_containers", 0)
                    critical_failed = result.get("critical_failed", 0)
                    
                    if critical_failed > 0:
                        logger.warning(f"⚠️ Docker на {server_id}: {running}/{total} работают ({critical_failed} критических не работают)")
                    elif running == total:
                        logger.info(f"✅ Docker на {server_id}: {running}/{total} работают")
                else:
                    logger.error(f"❌ Ошибка проверки Docker на {server_id}: {result.get('error', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Ошибка при автоматической проверке Docker: {e}")
    
    async def check_containers_status(self, context) -> None:
        """Проверка статуса критических контейнеров (UP/DOWN)."""
        logger.info("🔍 Запуск перевірки статусу контейнерів...")
        
        try:
            from checks.container_monitor import check_containers
            await check_containers()
        except Exception as e:
            logger.error(f"❌ Помилка перевірки контейнерів: {e}")
    
    # ==================== 🔥 НОВАЯ ЗАДАЧА ====================
    
    async def check_container_logs(self, context) -> None:
        """
        Проверка логов Docker контейнеров на наличие ошибок.
        Анализирует логи ИЗНУТРИ каждого контейнера.
        """
        logger.info("🔍 Запуск перевірки логів Docker контейнерів...")
        
        try:
            from checks.container_log_monitor import check_container_logs
            await check_container_logs()
            logger.info("✅ Перевірка логів контейнерів завершена")
        except ImportError as e:
            logger.error(f"❌ Модуль container_log_monitor не знайдено: {e}")
        except Exception as e:
            logger.error(f"❌ Помилка перевірки логів контейнерів: {e}")
    
    # ==================== PVE/PBS ЗАДАЧИ ====================
    
    async def check_pve_vms(self, context) -> None:
        """Проверка виртуальных машин в PVE."""
        logger.info("🔍 Перевірка PVE VM...")
        
        try:
            from checks.pve_monitor import check_pve
            await check_pve()
        except Exception as e:
            logger.error(f"❌ Помилка перевірки PVE: {e}")
    
    async def check_pbs_backups(self, context) -> None:
        """Проверка бэкапов PBS."""
        logger.info("💾 Перевірка PBS бэкапів...")
        
        try:
            from checks.pbs_monitor import check_pbs
            await check_pbs()
        except Exception as e:
            logger.error(f"❌ Помилка перевірки PBS: {e}")
    
    # ==================== ОТЧЕТЫ ====================
    
    async def send_daily_report(self, context) -> None:
        """Отправка ежедневного отчета в 9:00."""
        logger.info("📊 Подготовка ежедневного отчета...")
        
        try:
            from config.settings import ADMIN_CHAT_ID
            from datetime import datetime
            from checks.site_checker import SiteChecker
            from checks.docker import check_all_docker_servers
            
            site_checker = SiteChecker()
            sites_result = site_checker.check_all_sites()
            docker_result = check_all_docker_servers()
            
            text = "📊 *ЩОДЕННИЙ ЗВІТ МОНІТОРИНГУ*\n"
            text += f"📅 {datetime.now().strftime('%d.%m.%Y')}\n"
            text += "═" * 30 + "\n\n"
            
            # Сайты
            text += "*🌐 САЙТИ:*\n"
            if sites_result.get('sites'):
                for site in sites_result['sites']:
                    status = '✅' if site.get('success') else '❌'
                    name = site.get('name', 'Unknown')
                    code = site.get('status_code', 'ERR')
                    text += f"{status} {name}: {code}\n"
            else:
                text += "❌ Немає даних\n"
            
            # Docker
            text += "\n*🐳 DOCKER:*\n"
            if docker_result:
                for server_id, result in docker_result.items():
                    if result.get('status') == 'success':
                        running = result.get('running_containers', 0)
                        total = result.get('total_containers', 0)
                        text += f"🟢 {server_id.upper()}: {running}/{total}\n"
                    else:
                        text += f"🔴 {server_id.upper()}: Помилка\n"
            else:
                text += "❌ Немає даних\n"
            
            text += "\n" + "═" * 30
            text += "\n🕒 Звіт сформовано автоматично"
            
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=text,
                parse_mode='Markdown'
            )
            
            logger.info("✅ Ежедневный отчет отправлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ежедневного отчета: {e}")
    
    async def cleanup_old_data(self, context) -> None:
        """Очистка старых данных."""
        logger.info("🧹 Запуск очистки старых данных...")
        # TODO: Реализовать очистку
        pass
    
    # ==================== СЛУЖЕБНЫЕ МЕТОДЫ ====================
    
    def get_scheduled_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить информацию о всех запланированных задачах.
        
        Returns:
            Словарь с информацией о задачах
        """
        jobs_info = {}
        for name, info in self.jobs.items():
            jobs_info[name] = {
                'description': info['description'],
                'schedule': info['schedule'],
                'next_run': info['next_run'].isoformat() if info['next_run'] else None,
                'enabled': True
            }
        return jobs_info
    
    def run_job_now(self, name: str) -> bool:
        """
        Запустить задачу немедленно (для тестирования).
        
        Args:
            name: Имя задачи
            
        Returns:
            True если успешно, False если ошибка
        """
        if name not in self.jobs:
            logger.error(f"❌ Задача '{name}' не найдена")
            return False
        
        try:
            job = self.jobs[name]['job']
            job.run(self.job_queue._application)
            logger.info(f"✅ Задача '{name}' запущена вручную")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка запуска задачи '{name}': {e}")
            return False


def setup_scheduler(job_queue: JobQueue) -> Optional[MonitoringScheduler]:
    """
    Настроить планировщик задач.
    
    Args:
        job_queue: JobQueue из Telegram приложения
        
    Returns:
        Экземпляр планировщика или None при ошибке
    """
    if not job_queue:
        logger.warning("⚠️ JobQueue не доступен, планировщик отключен")
        return None
    
    try:
        scheduler = MonitoringScheduler(job_queue)
        scheduler.setup_scheduled_tasks()
        logger.info("✅ Планировщик успешно настроен")
        return scheduler
    except Exception as e:
        logger.error(f"❌ Ошибка настройки планировщика: {e}")
        return None
