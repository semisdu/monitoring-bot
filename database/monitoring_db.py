#!/usr/bin/env python3
"""
База данных для мониторинга - исправленная версия
"""

import sqlite3
import logging
import os
import datetime
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

class MonitoringDB:
    """Управление базой данных мониторинга"""
    
    def __init__(self, db_path: str = "database/monitoring.db"):
        self.db_path = db_path
        self.init_database()
    
    def _get_connection(self):
        """Получить соединение с базой данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализировать базу данных и таблицы"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Таблица пользователей
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'ru',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Таблица алертов
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT,
                    severity TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Таблица логов команд
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS command_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Таблица проверок сайтов
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS site_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_time INTEGER,
                    status_code INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Таблица проверок системы
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    disk_percent REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Создаем индексы
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_command_logs_user ON command_logs(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_site_checks_timestamp ON site_checks(timestamp)')
                
                conn.commit()
                
            logger.info(f"База данных инициализирована: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
    
    def log_command(self, user_id: int, command: str):
        """Записать выполнение команды в логи"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO command_logs (user_id, command) VALUES (?, ?)",
                    (user_id, command)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка записи лога команды: {e}")
    
    def add_alert(self, alert_type: str, title: str, message: str = "", severity: str = "warning"):
        """Добавить новый алерт"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO alerts (alert_type, title, message, severity, resolved) 
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (alert_type, title, message, severity)
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка добавления алерта: {e}")
            return None
    
    def get_unresolved_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить нерешенные алерты"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT severity, title, message, created_at 
                    FROM alerts 
                    WHERE resolved = 0 
                    ORDER BY created_at DESC 
                    LIMIT ?
                    """,
                    (limit,)
                )
                
                alerts = []
                for row in cursor.fetchall():
                    alerts.append({
                        'severity': row[0],
                        'title': row[1],
                        'message': row[2],
                        'created_at': row[3]
                    })
                
                return alerts
        except Exception as e:
            logger.error(f"Ошибка получения алертов: {e}")
            return []
    
    def resolve_old_alerts(self, days_old: int = 30) -> int:
        """Пометить старые алерты как решенные"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE alerts 
                    SET resolved = 1, resolved_at = CURRENT_TIMESTAMP 
                    WHERE created_at < ? AND resolved = 0
                    """,
                    (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
                )
                resolved_count = cursor.rowcount
                conn.commit()
                return resolved_count
        except Exception as e:
            logger.error(f"Ошибка разрешения старых алертов: {e}")
            return 0
    
    def cleanup_old_checks(self, days_old: int = 30) -> Dict[str, int]:
        """Очистить старые проверки"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Удаляем старые проверки сайтов
                cursor.execute("DELETE FROM site_checks WHERE timestamp < ?", (cutoff_str,))
                site_deleted = cursor.rowcount
                
                # Удаляем старые проверки системы
                cursor.execute("DELETE FROM system_checks WHERE timestamp < ?", (cutoff_str,))
                system_deleted = cursor.rowcount
                
                # Помечаем старые алерты как решенные
                alerts_resolved = self.resolve_old_alerts(days_old)
                
                conn.commit()
                
                return {
                    'site_checks': site_deleted,
                    'system_checks': system_deleted,
                    'alerts_resolved': alerts_resolved
                }
                
        except Exception as e:
            logger.error(f"Ошибка очистки старых проверок: {e}")
            return {'site_checks': 0, 'system_checks': 0, 'alerts_resolved': 0}
    
    def get_command_stats(self, days: int = 7) -> Dict[str, Any]:
        """Получить статистику команд"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Общее количество команд
                cursor.execute(
                    "SELECT COUNT(*) as count FROM command_logs WHERE timestamp > ?",
                    (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
                )
                row = cursor.fetchone()
                total_commands = row[0] if row else 0
                
                # Команды по пользователям
                cursor.execute(
                    """
                    SELECT user_id, COUNT(*) as count 
                    FROM command_logs 
                    WHERE timestamp > ? 
                    GROUP BY user_id 
                    ORDER BY count DESC
                    """,
                    (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
                )
                user_stats = []
                for row in cursor.fetchall():
                    user_stats.append({'user_id': row[0], 'count': row[1]})
                
                # Популярные команды
                cursor.execute(
                    """
                    SELECT command, COUNT(*) as count 
                    FROM command_logs 
                    WHERE timestamp > ? 
                    GROUP BY command 
                    ORDER BY count DESC 
                    LIMIT 10
                    """,
                    (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
                )
                command_stats = []
                for row in cursor.fetchall():
                    command_stats.append({'command': row[0], 'count': row[1]})
                
                return {
                    'total_commands': total_commands,
                    'user_stats': user_stats,
                    'command_stats': command_stats,
                    'days': days
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики команд: {e}")
            return {'total_commands': 0, 'user_stats': [], 'command_stats': [], 'days': days}

# Глобальный экземпляр базы данных
db_instance = MonitoringDB()

def get_db() -> MonitoringDB:
    """Получить экземпляр базы данных"""
    return db_instance
