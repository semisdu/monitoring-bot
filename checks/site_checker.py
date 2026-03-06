"""
Модуль проверки доступности сайтов
"""

import requests
import time
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            from config.settings import SITES
            
            results: List[Dict[str, Any]] = []
            
            for site_config in SITES:
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
        try:
            url: str = site_config.get('url', '')
            name: str = site_config.get('name', 'Unknown')
            server: str = site_config.get('server', '')
            timeout: int = site_config.get('timeout', self.timeout)
            
            start_time: float = time.time()
            
            # Пробуем HTTPS сначала
            result = self._try_https_request(url, name, server, timeout, start_time)
            if result:
                return result
            
            # Если HTTPS не сработал, пробуем HTTP
            return self._try_http_fallback(url, name, server, timeout, start_time)
            
        except Exception as error:
            logger.error(f"Ошибка при проверке сайта {site_config.get('name')}: {error}")
            return self._create_error_result(
                name=site_config.get('name', 'Unknown'),
                url=site_config.get('url', ''),
                server=site_config.get('server', ''),
                error=str(error)
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
        
        Args:
            url: URL сайта
            name: Название сайта
            server: Сервер
            timeout: Таймаут
            start_time: Время начала запроса
            
        Returns:
            Результат проверки или None если нужно пробовать HTTP
        """
        try:
            response = self.session.get(
                url,
                timeout=timeout,
                verify=True,
                allow_redirects=True
            )
            
            return self._create_success_result(
                name, url, server, response, start_time
            )
            
        except requests.exceptions.SSLError:
            # SSL ошибка - пробуем HTTP
            return None
        except Exception as error:
            # Другие ошибки - возвращаем результат с ошибкой
            return self._create_error_result(name, url, server, str(error))
    
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
        
        Args:
            url: URL сайта
            name: Название сайта
            server: Сервер
            timeout: Таймаут
            start_time: Время начала запроса
            
        Returns:
            Результат проверки
        """
        if not url.startswith('https://'):
            return self._create_error_result(name, url, server, "SSL error")
        
        http_url: str = url.replace('https://', 'http://', 1)
        
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
            
        except Exception as error:
            return self._create_error_result(name, url, server, str(error))
    
    def _is_success_status(self, status_code: int) -> bool:
        """
        Проверить, является ли статус код успешным.
        
        Args:
            status_code: HTTP статус код
            
        Returns:
            True если статус в диапазоне 200-399
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
        
        Args:
            name: Название сайта
            url: URL сайта
            server: Сервер
            response: HTTP ответ
            start_time: Время начала запроса
            
        Returns:
            Результат проверки
        """
        status_code: int = response.status_code
        response_time: float = (time.time() - start_time) * 1000  # в мс
        
        return {
            "id": name,
            "name": name,
            "url": url,
            "status": "up" if self._is_success_status(status_code) else "down",
            "status_code": status_code,
            "response_time": round(response_time, 2),
            "server": server,
            "error": "" if self._is_success_status(status_code) else f"HTTP {status_code}",
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
        
        Args:
            name: Название сайта
            url: URL сайта
            server: Сервер
            error: Текст ошибки
            
        Returns:
            Результат проверки с ошибкой
        """
        return {
            "id": name,
            "name": name,
            "url": url,
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
        
        Args:
            max_workers: Максимальное количество параллельных потоков
            
        Returns:
            Список результатов проверки
        """
        from config.settings import SITES
        
        results: List[Dict[str, Any]] = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_site = {
                executor.submit(self.check_site, site): site 
                for site in SITES
            }
            
            for future in as_completed(future_to_site):
                site = future_to_site[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as error:
                    logger.error(f"Ошибка при параллельной проверке {site.get('name')}: {error}")
                    results.append(self._create_error_result(
                        name=site.get('name', 'Unknown'),
                        url=site.get('url', ''),
                        server=site.get('server', ''),
                        error=str(error)
                    ))
        
        return results
