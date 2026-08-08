"""
Анализатор ошибок для сбора статистики и трендов
"""

import sqlite3
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "database" / "errors.db"


class ErrorAnalyzer:
    """Класс для анализа и хранения ошибок"""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Инициализирует базу данных"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Таблица ошибок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT NOT NULL,
                    error_hash TEXT NOT NULL,
                    message TEXT NOT NULL,
                    server_id TEXT,
                    container_name TEXT,
                    site_url TEXT,
                    severity TEXT DEFAULT 'warning',
                    status_code INTEGER,
                    response_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    is_resolved INTEGER DEFAULT 0,
                    occurrence_count INTEGER DEFAULT 1,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    recommendations TEXT
                )
            ''')

            # Таблица для группировки похожих ошибок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS error_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_hash TEXT UNIQUE,
                    group_name TEXT,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    total_occurrences INTEGER DEFAULT 1,
                    affected_servers TEXT,
                    typical_recommendation TEXT,
                    is_active INTEGER DEFAULT 1
                )
            ''')

            # Таблица для трендов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS error_trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_hash TEXT,
                    date TEXT,
                    occurrences INTEGER DEFAULT 0,
                    UNIQUE(error_hash, date)
                )
            ''')

            conn.commit()
            conn.close()
            logger.info("База данных аналитики инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД аналитики: {e}")

    def _generate_error_hash(self, error_data: Dict[str, Any]) -> str:
        """
        Генерирует хеш ошибки для группировки похожих.
        """
        # Ключевые поля для группировки
        key_fields = [
            error_data.get('error_type', 'unknown'),
            error_data.get('server_id', ''),
            error_data.get('container_name', ''),
            error_data.get('site_url', ''),
        ]
        key_string = '|'.join(str(f) for f in key_fields)
        return hashlib.md5(key_string.encode()).hexdigest()

    def add_error(self, error_data: Dict[str, Any]) -> int:
        """
        Добавляет ошибку в базу данных.

        Args:
            error_data: Данные об ошибке

        Returns:
            ID добавленной ошибки
        """
        try:
            error_hash = self._generate_error_hash(error_data)
            error_type = error_data.get('error_type', 'unknown')
            message = error_data.get('message', '')
            server_id = error_data.get('server_id')
            container_name = error_data.get('container_name')
            site_url = error_data.get('site_url')
            severity = error_data.get('severity', 'warning')
            status_code = error_data.get('status_code')
            response_time = error_data.get('response_time')
            recommendations = error_data.get('recommendations')

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Проверяем, есть ли уже такая ошибка (не resolved)
            cursor.execute('''
                SELECT id, occurrence_count FROM errors
                WHERE error_hash = ? AND is_resolved = 0
            ''', (error_hash,))

            existing = cursor.fetchone()

            if existing:
                # Обновляем существующую ошибку
                error_id, count = existing
                cursor.execute('''
                    UPDATE errors
                    SET occurrence_count = occurrence_count + 1,
                        last_seen = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (error_id,))
                conn.commit()
                conn.close()
                return error_id
            else:
                # Добавляем новую ошибку
                cursor.execute('''
                    INSERT INTO errors (
                        error_type, error_hash, message, server_id,
                        container_name, site_url, severity, status_code,
                        response_time, recommendations
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (error_type, error_hash, message, server_id,
                      container_name, site_url, severity, status_code,
                      response_time, recommendations))

                error_id = cursor.lastrowid
                conn.commit()
                conn.close()
                return error_id

        except Exception as e:
            logger.error(f"Ошибка добавления ошибки в БД: {e}")
            return -1

    def resolve_error(self, error_id: int) -> bool:
        """
        Помечает ошибку как решённую.

        Args:
            error_id: ID ошибки

        Returns:
            True если успешно
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE errors
                SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (error_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Ошибка при отметке ошибки как решённой: {e}")
            return False

    def resolve_error_by_site_url(self, site_url: str) -> bool:
        """
        Помечает все активные ошибки для данного сайта как решённые.

        Args:
            site_url: URL сайта

        Returns:
            True если успешно
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE errors
                SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
                WHERE site_url = ? AND error_type = 'site_down' AND is_resolved = 0
            ''', (site_url,))

            affected = cursor.rowcount
            conn.commit()
            conn.close()

            if affected > 0:
                logger.info(f"Помечено {affected} ошибок как решённых для сайта {site_url}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отметке ошибок сайта как решённых: {e}")
            return False

    def resolve_error_by_server(self, server_id: str) -> bool:
        """
        Помечает все активные ошибки для данного сервера как решённые.

        Args:
            server_id: ID сервера

        Returns:
            True если успешно
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE errors
                SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
                WHERE server_id = ? AND error_type = 'connection_error' AND is_resolved = 0
            ''', (server_id,))

            affected = cursor.rowcount
            conn.commit()
            conn.close()

            if affected > 0:
                logger.info(f"Помечено {affected} ошибок как решённых для сервера {server_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отметке ошибок сервера как решённых: {e}")
            return False

    def get_active_problems(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получить активные проблемы.

        Args:
            limit: Максимальное количество

        Returns:
            Список активных проблем
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT *
                FROM errors
                WHERE is_resolved = 0
                ORDER BY severity DESC, last_seen DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Ошибка получения активных проблем: {e}")
            return []

    def get_error_trends(self, days: int = 7) -> Dict[str, Any]:
        """
        Получить тренды ошибок за последние N дней.

        Args:
            days: Количество дней

        Returns:
            Словарь со статистикой
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Общая статистика
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) as resolved,
                    COUNT(DISTINCT error_hash) as unique_errors
                FROM errors
                WHERE created_at >= date('now', ?)
            ''', (f'-{days} days',))

            total_stats = cursor.fetchone()

            # Распределение по типам
            cursor.execute('''
                SELECT
                    error_type,
                    COUNT(*) as count
                FROM errors
                WHERE created_at >= date('now', ?) AND is_resolved = 0
                GROUP BY error_type
                ORDER BY count DESC
                LIMIT 5
            ''', (f'-{days} days',))

            by_type = [dict(row) for row in cursor.fetchall()]

            # Динамика по дням
            cursor.execute('''
                SELECT
                    date(created_at) as date,
                    COUNT(*) as count
                FROM errors
                WHERE created_at >= date('now', ?)
                GROUP BY date(created_at)
                ORDER BY date ASC
            ''', (f'-{days} days',))

            by_day = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return {
                'total_errors': total_stats[0] if total_stats else 0,
                'resolved': total_stats[1] if total_stats else 0,
                'unique_errors': total_stats[2] if total_stats else 0,
                'by_type': by_type,
                'by_day': by_day
            }

        except Exception as e:
            logger.error(f"Ошибка получения трендов: {e}")
            return {
                'total_errors': 0,
                'resolved': 0,
                'unique_errors': 0,
                'by_type': [],
                'by_day': []
            }


# Глобальный экземпляр
_analyzer_instance: Optional[ErrorAnalyzer] = None


def get_analyzer() -> ErrorAnalyzer:
    """Получить экземпляр анализатора"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ErrorAnalyzer()
    return _analyzer_instance


def add_error(error_data: Dict[str, Any]) -> int:
    """
    Добавить ошибку в аналитику.

    Args:
        error_data: Данные об ошибке

    Returns:
        ID ошибки
    """
    analyzer = get_analyzer()
    return analyzer.add_error(error_data)


def record_error(error_data: Dict[str, Any]) -> int:
    """
    Записать ошибку в аналитику (алиас для add_error).

    Args:
        error_data: Данные об ошибке

    Returns:
        ID ошибки
    """
    return add_error(error_data)


def get_current_problems(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить текущие активные проблемы"""
    analyzer = get_analyzer()
    return analyzer.get_active_problems(limit)


def get_trends(days: int = 7) -> Dict[str, Any]:
    """Получить тренды ошибок"""
    analyzer = get_analyzer()
    return analyzer.get_error_trends(days)


def resolve_error(error_id: int) -> bool:
    """
    Пометить ошибку как решённую.

    Args:
        error_id: ID ошибки

    Returns:
        True если успешно
    """
    analyzer = get_analyzer()
    return analyzer.resolve_error(error_id)


def resolve_error_by_site_url(site_url: str) -> bool:
    """
    Пометить все ошибки для сайта как решённые.

    Args:
        site_url: URL сайта

    Returns:
        True если успешно
    """
    analyzer = get_analyzer()
    return analyzer.resolve_error_by_site_url(site_url)


def resolve_error_by_server(server_id: str) -> bool:
    """
    Пометить все ошибки для сервера как решённые.

    Args:
        server_id: ID сервера

    Returns:
        True если успешно
    """
    analyzer = get_analyzer()
    return analyzer.resolve_error_by_server(server_id)
