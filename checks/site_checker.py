"""
Модуль проверки доступности сайтов
"""

import requests
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.loader import get_sites

logger = logging.getLogger(__name__)

# Константы
DEFAULT_TIMEOUT = 10
DEFAULT_USER_AGENT = "Mozilla/5.0 Monitoring Bot"
HTTP_SUCCESS_MIN = 200
HTTP_SUCCESS_MAX = 399


class SiteChecker:
    """Класс для проверки доступности сайтов"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """
        Инициализация проверщика сайтов.

        Args:
            timeout: Таймаут запроса в секундах
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': DEFAULT_USER_AGENT
        })
        self.timeout: int = timeout

    def check_all_sites(self) -> Dict[str, Any]:
        """
        Проверить все сайты из конфигурации.

        Returns:
            Словарь с результатами проверки всех сайтов
        """
        try:
            sites = get_sites()
            logger.info(f"Проверка {len(sites)} сайтов")

            results: List[Dict[str, Any]] = []

            for site_config in sites:
                site_result = self.check_site(site_config)
                results.append(site_result)

            return {
                "success": True,
                "sites": results,
                "total": len(results),
                "timestamp": time.time()
            }

        except Exception as error:
            logger.error(f"Ошибка в check_all_sites: {error}")
            return {
                "success": False,
                "error": str(error),
                "sites": []
            }

    def check_site(self, site_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Проверить один сайт.

        Args:
            site_config: Конфигурация сайта из settings.py

        Returns:
            Результат проверки сайта
        """
        url: str = site_config.get('url', '')
        name: str = site_config.get('name', 'Unknown')
        server: str = site_config.get('server', '')
        timeout: int = site_config.get('timeout', self.timeout)

        logger.debug(f"Проверка сайта {name} ({url})")

        try:
            start_time: float = time.time()

            # Пробуем HTTPS сначала
            result = self._try_https_request(url, name, server, timeout, start_time)
            if result:
                return result

            # Если HTTPS не сработал, пробуем HTTP
            logger.debug(f"HTTPS не сработал для {url}, пробуем HTTP")
            return self._try_http_fallback(url, name, server, timeout, start_time)

        except Exception as error:
            error_msg = str(error)
            logger.error(f"Ошибка при проверке сайта {name}: {error_msg}")
            return self._create_error_result(
                name=name,
                url=url,
                server=server,
                error=error_msg
            )

    def _try_https_request(
        self,
        url: str,
        name: str,
        server: str,
        timeout: int,
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """
        Попробовать выполнить HTTPS запрос.
        """
        try:
            logger.debug(f"HTTPS запрос к {url}")
            response = self.session.get(
                url,
                timeout=timeout,
                verify=True,
                allow_redirects=True
            )

            return self._create_success_result(
                name, url, server, response, start_time
            )

        except requests.exceptions.SSLError as e:
            logger.debug(f"SSL ошибка для {url}: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)

    def _try_http_fallback(
        self,
        url: str,
        name: str,
        server: str,
        timeout: int,
        start_time: float
    ) -> Dict[str, Any]:
        """
        Попробовать выполнить HTTP запрос (fallback после HTTPS ошибки).
        """
        if not url.startswith('https://'):
            return self._create_error_result(name, url, server, "SSL error and not HTTPS")

        http_url: str = url.replace('https://', 'http://', 1)
        logger.debug(f"HTTP fallback к {http_url}")

        try:
            response = self.session.get(
                http_url,
                timeout=timeout,
                verify=False,
                allow_redirects=True
            )

            result = self._create_success_result(
                name, url, server, response, start_time
            )
            result["note"] = "SSL error, used HTTP"
            return result

        except requests.exceptions.ConnectionError as e:
            error_msg = f"HTTP fallback connection error: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)
        except requests.exceptions.Timeout as e:
            error_msg = f"HTTP fallback timeout: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP fallback request error: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)
        except Exception as e:
            error_msg = f"HTTP fallback unexpected error: {e}"
            logger.debug(error_msg)
            return self._create_error_result(name, url, server, error_msg)

    def _is_success_status(self, status_code: int) -> bool:
        """
        Проверить, является ли статус код успешным.
        """
        return HTTP_SUCCESS_MIN <= status_code <= HTTP_SUCCESS_MAX

    def _create_success_result(
        self,
        name: str,
        url: str,
        server: str,
        response: requests.Response,
        start_time: float
    ) -> Dict[str, Any]:
        """
        Создать результат успешной проверки.
        """
        status_code: int = response.status_code
        response_time: float = (time.time() - start_time) * 1000  # в мс
        is_up = self._is_success_status(status_code)

        return {
            "id": name,
            "name": name,
            "url": url,
            "success": is_up,  # ← ДОБАВЛЕНО поле success
            "status": "up" if is_up else "down",
            "status_code": status_code,
            "response_time": round(response_time, 2),
            "server": server,
            "error": "" if is_up else f"HTTP {status_code}",
            "timestamp": time.time()
        }

    def _create_error_result(
        self,
        name: str,
        url: str,
        server: str,
        error: str
    ) -> Dict[str, Any]:
        """
        Создать результат с ошибкой.
        """
        logger.debug(f"Создание ошибки для {name}: {error}")
        return {
            "id": name,
            "name": name,
            "url": url,
            "success": False,  # ← ДОБАВЛЕНО поле success
            "status": "down",
            "status_code": 0,
            "response_time": 0,
            "server": server,
            "error": error,
            "timestamp": time.time()
        }

    def check_sites_parallel(self, max_workers: int = 5) -> List[Dict[str, Any]]:
        """
        Проверить все сайты параллельно для ускорения.
        """
        sites = get_sites()
        logger.info(f"Параллельная проверка {len(sites)} сайтов")

        results: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_site = {
                executor.submit(self.check_site, site): site
                for site in sites
            }

            for future in as_completed(future_to_site):
                site = future_to_site[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as error:
                    error_msg = str(error)
                    logger.error(f"Ошибка при параллельной проверке {site.get('name')}: {error_msg}")
                    results.append(self._create_error_result(
                        name=site.get('name', 'Unknown'),
                        url=site.get('url', ''),
                        server=site.get('server', ''),
                        error=error_msg
                    ))

        return results


# ==================== АСИНХРОННЫЕ ФУНКЦИИ ДЛЯ ВЫЗОВА ИЗ БОТА ====================

_checker_instance = None

def get_checker() -> SiteChecker:
    """Получить или создать экземпляр SiteChecker"""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = SiteChecker()
    return _checker_instance


async def check_site(url: str) -> Dict[str, Any]:
    """
    Асинхронная функция для проверки одного сайта по URL.
    
    Args:
        url: URL сайта для проверки
        
    Returns:
        Результат проверки
    """
    logger.info(f"Асинхронная проверка сайта {url}")
    
    # Создаем временную конфигурацию сайта
    site_config = {
        'url': url,
        'name': url,
        'server': '',
        'timeout': DEFAULT_TIMEOUT
    }
    
    # Запускаем синхронную проверку в отдельном потоке
    loop = asyncio.get_event_loop()
    checker = get_checker()
    result = await loop.run_in_executor(None, checker.check_site, site_config)
    
    # Логируем результат
    if result.get('error'):
        logger.warning(f"Ошибка при проверке {url}: {result.get('error')}")
    else:
        logger.info(f"Сайт {url} ответил за {result.get('response_time')}ms")
    
    return result


async def check_site_by_config(site_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Асинхронная функция для проверки сайта по полной конфигурации.
    
    Args:
        site_config: Конфигурация сайта
        
    Returns:
        Результат проверки
    """
    loop = asyncio.get_event_loop()
    checker = get_checker()
    result = await loop.run_in_executor(None, checker.check_site, site_config)
    return result


async def check_all_sites() -> List[Dict[str, Any]]:
    """
    Асинхронная функция для проверки всех сайтов.
    
    Returns:
        Список результатов проверки
    """
    logger.info("Асинхронная проверка всех сайтов")
    loop = asyncio.get_event_loop()
    checker = get_checker()
    result = await loop.run_in_executor(None, checker.check_all_sites)
    sites = result.get('sites', [])
    logger.info(f"Проверено {len(sites)} сайтов")
    return sites
