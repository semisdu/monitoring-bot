#!/usr/bin/env python3
"""
Модуль анализа ошибок и проблем инфраструктуры
Собирает, группирует и анализирует ошибки, выявляет тренды и даёт рекомендации
"""

import json
import sqlite3
import logging
import difflib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from config.loader import load_config

logger = logging.getLogger(__name__)

# Путь к базе данных для хранения истории ошибок
DB_PATH = Path(__file__).parent.parent / "database" / "errors.db"


class ErrorAnalyzer:
    """Анализатор ошибок и проблем инфраструктуры"""

    def __init__(self, user_id: Optional[int] = None):
        """
        Инициализация анализатора.

        Args:
            user_id: ID пользователя для мультиязычности (опционально)
        """
        self.user_id = user_id
        self.config = load_config()
        self.analytics_config = self.config.get('analytics', {})
        self._init_database()

    def _init_database(self):
        """Инициализация базы данных для хранения ошибок"""
        try:
            # Создаём директорию для БД, если её нет
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            # Таблица для хранения ошибок
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
            str(error_data.get('error_type', 'unknown')),
            str(error_data.get('server_id', '')),
            str(error_data.get('container_name', '')),
            str(error_data.get('site_url', '')),
            str(error_data.get('status_code', 0))
        ]

        # Для сообщений используем дифф-подход
        message = error_data.get('message', '')
        if message and self.analytics_config.get('error_tracking', {}).get('group_similar', True):
            # Нормализуем сообщение (убираем цифры, время и т.д.)
            import re
            normalized = re.sub(r'\d+', 'N', message)
            normalized = re.sub(r'\d+\.\d+', 'N.N', normalized)
            normalized = re.sub(r'0x[0-9a-f]+', '0x...', normalized)
            key_fields.append(normalized[:100])

        hash_string = '|'.join(key_fields)
        return str(abs(hash(hash_string)) % 10**8)

    def _get_similarity_score(self, text1: str, text2: str) -> float:
        """Оценивает схожесть двух текстов."""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def add_error(self, error_data: Dict[str, Any]) -> int:
        """
        Добавляет ошибку в базу для анализа.
        """
        try:
            # Подготовка данных
            error_hash = self._generate_error_hash(error_data)
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            
            # Подготовка значений с проверкой на None
            error_type = error_data.get('error_type', 'unknown')
            message = error_data.get('message', '')
            server_id = error_data.get('server_id')
            container_name = error_data.get('container_name')
            site_url = error_data.get('site_url')
            severity = error_data.get('severity', 'warning')
            status_code = error_data.get('status_code')
            response_time = error_data.get('response_time')
            
            # Генерируем рекомендации
            recommendations = json.dumps(self._generate_recommendations(error_data))
            
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            # Проверяем, есть ли уже такая ошибка за последние 24 часа
            cursor.execute('''
                SELECT id, occurrence_count FROM errors
                WHERE error_hash = ? AND is_resolved = 0
                AND datetime(last_seen) > datetime('now', '-1 day')
                ORDER BY last_seen DESC LIMIT 1
            ''', (error_hash,))

            existing = cursor.fetchone()

            if existing:
                # Обновляем существующую ошибку
                error_id, count = existing
                cursor.execute('''
                    UPDATE errors
                    SET occurrence_count = ?, last_seen = ?
                    WHERE id = ?
                ''', (count + 1, now.isoformat(), error_id))
                logger.debug(f"Обновлена существующая ошибка {error_id} (всего: {count + 1})")
            else:
                # Добавляем новую ошибку
                cursor.execute('''
                    INSERT INTO errors (
                        error_type, error_hash, message, server_id,
                        container_name, site_url, severity, status_code,
                        response_time, recommendations
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    error_type, error_hash, message, server_id,
                    container_name, site_url, severity, status_code,
                    response_time, recommendations
                ))
                error_id = cursor.lastrowid
                logger.info(f"Добавлена новая ошибка {error_id} типа {error_type}")

            # Обновляем тренды
            # Проверяем, есть ли запись за сегодня
            cursor.execute('''
                SELECT occurrences FROM error_trends
                WHERE error_hash = ? AND date = ?
            ''', (error_hash, today))

            existing_trend = cursor.fetchone()

            if existing_trend:
                # Обновляем существующую
                cursor.execute('''
                    UPDATE error_trends
                    SET occurrences = occurrences + 1
                    WHERE error_hash = ? AND date = ?
                ''', (error_hash, today))
            else:
                # Создаём новую
                cursor.execute('''
                    INSERT INTO error_trends (error_hash, date, occurrences)
                    VALUES (?, ?, 1)
                ''', (error_hash, today))

            conn.commit()
            conn.close()

            # Проверяем, не пора ли отправить групповое уведомление
            self._check_for_bulk_alert(error_hash)

            return error_id

        except Exception as e:
            logger.error(f"Ошибка при добавлении ошибки в БД: {e}")
            import traceback
            traceback.print_exc()
            return -1

    def _check_for_bulk_alert(self, error_hash: str):
        """Проверяет, не превышен ли порог для группового уведомления."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) FROM errors
                WHERE error_hash = ? AND is_resolved = 0
                AND datetime(last_seen) > datetime('now', '-1 hour')
            ''', (error_hash,))

            count = cursor.fetchone()[0]
            conn.close()

            if count >= 3:
                logger.warning(f"Обнаружена повторяющаяся ошибка {error_hash} — {count} раз за час")
        except Exception as e:
            logger.error(f"Ошибка при проверке групповых алертов: {e}")

    def _generate_recommendations(self, error_data: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации на основе типа ошибки."""
        error_type = error_data.get('error_type', '')
        recommendations = []

        if error_type == 'docker_down':
            container = error_data.get('container_name', 'unknown')
            recommendations.append(f"Перезапустить контейнер {container}")
            recommendations.append("Проверить логи контейнера на наличие ошибок")
            recommendations.append("Увеличить лимиты памяти, если проблема в OOM")

        elif error_type == 'site_down':
            url = error_data.get('site_url', 'unknown')
            recommendations.append(f"Проверить доступность сайта {url} вручную")
            recommendations.append("Проверить логи NGINX на сервере")
            recommendations.append("Проверить статус Docker контейнеров приложения")

        elif error_type == 'high_cpu':
            server = error_data.get('server_id', 'unknown')
            recommendations.append(f"Проверить процессы на сервере {server} (top/htop)")
            recommendations.append("Проверить, нет ли утечек памяти в приложениях")
            recommendations.append("Рассмотреть возможность увеличения ресурсов")

        elif error_type == 'disk_full':
            server = error_data.get('server_id', 'unknown')
            recommendations.append(f"Очистить диск на сервере {server} (старые логи, бэкапы)")
            recommendations.append("Проверить, какие директории занимают больше всего места")
            recommendations.append("Настроить ротацию логов")

        elif error_type == 'backup_old':
            server = error_data.get('server_id', 'unknown')
            recommendations.append(f"Проверить статус бэкапов на сервере {server}")
            recommendations.append("Запустить бэкап вручную")
            recommendations.append("Проверить свободное место в хранилище")

        elif error_type == 'connection_error':
            server = error_data.get('server_id', 'unknown')
            recommendations.append(f"Проверить сетевое соединение с {server}")
            recommendations.append("Проверить, запущен ли SSH на сервере")
            recommendations.append("Проверить файервол и доступность порта")

        return recommendations

    def resolve_error(self, error_id: int) -> bool:
        """
        Помечает ошибку как решённую.

        Args:
            error_id: ID ошибки

        Returns:
            True если успешно
        """
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE errors
                SET is_resolved = 1, resolved_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), error_id))

            conn.commit()
            conn.close()
            logger.info(f"Ошибка {error_id} помечена как решённая")
            return True

        except Exception as e:
            logger.error(f"Ошибка при разрешении ошибки {error_id}: {e}")
            return False

    def get_active_problems(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Возвращает список активных проблем."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    id, error_type, message, server_id, container_name,
                    site_url, severity, occurrence_count, created_at, last_seen,
                    recommendations
                FROM errors
                WHERE is_resolved = 0
                ORDER BY occurrence_count DESC, last_seen DESC
                LIMIT ?
            ''', (limit,))

            problems = []
            for row in cursor.fetchall():
                problems.append({
                    'id': row[0],
                    'error_type': row[1],
                    'message': row[2],
                    'server_id': row[3],
                    'container_name': row[4],
                    'site_url': row[5],
                    'severity': row[6],
                    'occurrence_count': row[7],
                    'created_at': row[8],
                    'last_seen': row[9],
                    'recommendations': json.loads(row[10]) if row[10] else []
                })

            conn.close()
            return problems
        except Exception as e:
            logger.error(f"Ошибка при получении активных проблем: {e}")
            return []

    def get_error_trends(self, days: int = 7) -> Dict[str, Any]:
        """Анализирует тренды ошибок за указанный период."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            # Общая статистика
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) as resolved,
                    COUNT(DISTINCT error_hash) as unique_errors
                FROM errors
                WHERE created_at > datetime('now', ?)
            ''', (f'-{days} days',))

            row = cursor.fetchone()
            total_stats = row if row else (0, 0, 0)

            # Ошибки по типам
            cursor.execute('''
                SELECT error_type, COUNT(*) as count
                FROM errors
                WHERE created_at > datetime('now', ?)
                GROUP BY error_type
                ORDER BY count DESC
            ''', (f'-{days} days',))

            by_type = [{'type': row[0], 'count': row[1]} for row in cursor.fetchall()]

            # По дням
            cursor.execute('''
                SELECT date, SUM(occurrences) as daily_total
                FROM error_trends
                WHERE date >= date('now', ?)
                GROUP BY date
                ORDER BY date
            ''', (f'-{days} days',))

            by_day = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]

            conn.close()

            return {
                'period_days': days,
                'total_errors': total_stats[0] if total_stats[0] else 0,
                'resolved': total_stats[1] if total_stats[1] else 0,
                'unique_errors': total_stats[2] if total_stats[2] else 0,
                'by_type': by_type,
                'by_day': by_day
            }
        except Exception as e:
            logger.error(f"Ошибка при анализе трендов: {e}")
            return {
                'period_days': days,
                'total_errors': 0,
                'resolved': 0,
                'unique_errors': 0,
                'by_type': [],
                'by_day': []
            }


# ==================== Singleton для доступа из других модулей ====================

_analyzer_instance = None


def get_analyzer(user_id: Optional[int] = None) -> ErrorAnalyzer:
    """Получить экземпляр анализатора (синглтон)"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ErrorAnalyzer(user_id)
    return _analyzer_instance


# ==================== Удобные функции для вызова из checks ====================

def record_error(error_data: Dict[str, Any]) -> int:
    """
    Удобная функция для записи ошибки из модулей checks.

    Args:
        error_data: Данные об ошибке

    Returns:
        ID ошибки
    """
    analyzer = get_analyzer()
    return analyzer.add_error(error_data)


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
