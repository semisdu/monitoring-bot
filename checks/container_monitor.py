#!/usr/bin/env python3
"""
Мониторинг Docker контейнеров в реальном времени
Отправляет алерты при падении контейнеров
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from telegram import Bot

from config.settings import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from checks.docker import get_docker_status

logger = logging.getLogger(__name__)

# Константы
ALERT_COOLDOWN_MINUTES = 30
CONTAINERS_CONFIG = {
    "serv301": [
        {"name": "course_postgres", "critical": True},
        {"name": "course_app", "critical": True}
    ],
    "serv300": [
        {"name": "profcompetitions-nginx", "critical": True},
        {"name": "competitions", "critical": True}
    ]
}

# Кэш для отслеживания уже отправленных алертов
_alert_cache: Dict[str, datetime] = {}
_alert_cooldown: timedelta = timedelta(minutes=ALERT_COOLDOWN_MINUTES)


class ContainerMonitor:
    """Монітор для Docker контейнерів"""
    
    def __init__(self) -> None:
        """Ініціалізація монітора"""
        self.bot: Bot = Bot(token=TELEGRAM_TOKEN)
        self.containers_config: Dict[str, List[Dict[str, Any]]] = CONTAINERS_CONFIG
        
    async def check_all_containers(self) -> None:
        """
        Перевірити всі контейнери та відправити алерти.
        
        Проходить по всіх серверах з контейнерами,
        отримує статус Docker та перевіряє кожен контейнер.
        """
        logger.info("🔍 Перевірка стану Docker контейнерів...")
        
        for server_id, containers in self.containers_config.items():
            try:
                # Отримуємо статус Docker на сервері
                docker_status: Dict[str, Any] = get_docker_status(server_id)
                
                if docker_status.get('status') != 'success':
                    await self._send_alert(
                        f"❌ *Помилка доступу до Docker на {server_id.upper()}*\n"
                        f"Причина: {docker_status.get('error', 'Невідома помилка')}"
                    )
                    continue
                
                # Перевіряємо кожен контейнер
                for container_config in containers:
                    container_name: str = container_config["name"]
                    await self._check_container(server_id, container_name, docker_status)
                    
            except Exception as error:
                logger.error(f"Помилка перевірки {server_id}: {error}")
    
    async def _check_container(
        self, 
        server_id: str, 
        container_name: str, 
        docker_status: Dict[str, Any]
    ) -> None:
        """
        Перевірити конкретний контейнер.
        
        Args:
            server_id: Ідентифікатор сервера
            container_name: Назва контейнера
            docker_status: Статус Docker на сервері
        """
        global _alert_cache
        
        # Шукаємо контейнер в результатах
        container: Optional[Dict[str, Any]] = None
        for container_data in docker_status.get('containers', []):
            if container_data.get('name') == container_name:
                container = container_data
                break
        
        cache_key: str = f"{server_id}:{container_name}"
        now: datetime = datetime.now()
        
        # Якщо контейнер не знайдено
        if not container:
            await self._handle_missing_container(server_id, container_name, cache_key, now)
            return
        
        # Перевіряємо статус контейнера
        await self._handle_container_status(server_id, container_name, container, cache_key, now)
    
    async def _handle_missing_container(
        self,
        server_id: str,
        container_name: str,
        cache_key: str,
        now: datetime
    ) -> None:
        """Обробка випадку, коли контейнер не знайдено"""
        if cache_key not in _alert_cache or now - _alert_cache[cache_key] > _alert_cooldown:
            await self._send_alert(
                f"🚨 *Критична помилка!*\n"
                f"Сервер: {server_id.upper()}\n"
                f"Контейнер: `{container_name}`\n"
                f"Статус: *НЕ ЗНАЙДЕНО*\n"
                f"Перевірте чи існує контейнер!"
            )
            _alert_cache[cache_key] = now
    
    async def _handle_container_status(
        self,
        server_id: str,
        container_name: str,
        container: Dict[str, Any],
        cache_key: str,
        now: datetime
    ) -> None:
        """Обробка статусу контейнера"""
        running: bool = container.get('running', False)
        status_text: str = container.get('status', 'unknown')
        
        if not running:
            # Контейнер не працює - відправляємо алерт
            if cache_key not in _alert_cache or now - _alert_cache[cache_key] > _alert_cooldown:
                await self._send_alert(
                    f"🚨 *Контейнер зупинено!*\n"
                    f"Сервер: {server_id.upper()}\n"
                    f"Контейнер: `{container_name}`\n"
                    f"Статус: `{status_text}`\n"
                    f"Потрібне втручання!"
                )
                _alert_cache[cache_key] = now
                logger.warning(
                    f"⚠ Контейнер {container_name} на {server_id} не працює: {status_text}"
                )
        else:
            # Контейнер працює - видаляємо з кешу якщо був
            if cache_key in _alert_cache:
                del _alert_cache[cache_key]
    
    async def _send_alert(self, message: str) -> None:
        """
        Відправити алерт в Telegram.
        
        Args:
            message: Текст повідомлення
        """
        try:
            await self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Алерт відправлено: {message[:50]}...")
        except Exception as error:
            logger.error(f"❌ Помилка відправки алерту: {error}")


# Функції для зовнішнього використання
async def check_containers() -> None:
    """Запустити перевірку контейнерів (асинхронна версія)"""
    monitor = ContainerMonitor()
    await monitor.check_all_containers()


def run_container_check() -> None:
    """Запустити перевірку контейнерів (синхронна версія для ручного запуску)"""
    asyncio.run(check_containers())


if __name__ == "__main__":
    # Для тестування
    asyncio.run(check_containers())
