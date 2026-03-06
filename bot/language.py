#!/usr/bin/env python3
"""
Менеджер мультиязычности на JSON-файлах
"""

import json
import logging
import os
import sqlite3
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ==================== КОНСТАНТЫ ====================

BASE_DIR: str = os.path.dirname(os.path.dirname(__file__))
LOCALES_DIR: str = os.path.join(BASE_DIR, 'config', 'locales')
DB_PATH: str = os.path.join(BASE_DIR, 'database', 'language.db')

DEFAULT_LANGUAGE: str = 'ru'
SUPPORTED_LANGUAGES: List[str] = ['ru', 'en', 'uk']
LANGUAGE_NAMES: Dict[str, str] = {
    'ru': 'Русский',
    'en': 'English',
    'uk': 'Українська'
}

# Кэш для загруженных языков
_language_cache: Dict[str, Dict[str, Any]] = {}


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

def load_language(lang_code: str) -> Dict[str, Any]:
    """
    Загрузить языковой файл в кэш.
    
    Args:
        lang_code: Код языка (ru, en, uk)
        
    Returns:
        Словарь с текстами для указанного языка
    """
    global _language_cache
    
    # Если уже загружен, возвращаем из кэша
    if lang_code in _language_cache:
        return _language_cache[lang_code]
    
    # Пытаемся загрузить файл
    file_path: str = os.path.join(LOCALES_DIR, f"{lang_code}.json")
    
    if not os.path.exists(file_path):
        logger.warning(
            f"Языковой файл {file_path} не найден, загружаем русский"
        )
        return _load_default_language()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data: Dict[str, Any] = json.load(file)
            _language_cache[lang_code] = data
            logger.info(
                f"Загружен язык {lang_code} ({len(data)} категорий)"
            )
            return data
    except json.JSONDecodeError as error:
        logger.error(f"Ошибка парсинга JSON для {lang_code}: {error}")
    except Exception as error:
        logger.error(f"Ошибка загрузки языка {lang_code}: {error}")
    
    return _load_default_language()


def _load_default_language() -> Dict[str, Any]:
    """Загрузить язык по умолчанию (русский)."""
    file_path: str = os.path.join(LOCALES_DIR, f"{DEFAULT_LANGUAGE}.json")
    
    if not os.path.exists(file_path):
        logger.error("Критическая ошибка: русский языковой файл не найден!")
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data: Dict[str, Any] = json.load(file)
            _language_cache[DEFAULT_LANGUAGE] = data
            return data
    except Exception as error:
        logger.error(f"Ошибка загрузки русского языка: {error}")
        return {}


def get_text(user_id: int, category: str, key: str, **kwargs) -> str:
    """
    Получить текст для указанного пользователя по категории и ключу.
    
    Поддерживает плейсхолдеры в формате {name}.
    
    Args:
        user_id: ID пользователя Telegram
        category: Категория текста (например, 'start', 'docker')
        key: Ключ текста в категории (например, 'welcome', 'status')
        **kwargs: Параметры для подстановки в текст
        
    Returns:
        Текст на языке пользователя
        
    Example:
        >>> get_text(12345, 'start', 'welcome', name='Иван')
        '👋 Привет, Иван!'
    """
    # Получаем язык пользователя
    lang_code: str = language_manager.get_user_language(user_id)
    
    # Загружаем язык
    lang_data: Dict[str, Any] = load_language(lang_code)
    
    # Ищем текст
    text: str = _find_text(lang_data, lang_code, category, key)
    
    # Подставляем параметры
    if kwargs and text:
        try:
            text = text.format(**kwargs)
        except KeyError as error:
            logger.error(
                f"Ошибка форматирования текста [{category}.{key}]: "
                f"отсутствует параметр {error}"
            )
    
    return text


def _find_text(
    lang_data: Dict[str, Any],
    lang_code: str,
    category: str,
    key: str
) -> str:
    """
    Найти текст в языковых данных.
    
    Args:
        lang_data: Данные языка
        lang_code: Код языка
        category: Категория
        key: Ключ
        
    Returns:
        Найденный текст или заглушка
    """
    try:
        text: str = lang_data.get(category, {}).get(key, "")
        
        # Если текст не найден, пробуем на русском
        if not text and lang_code != DEFAULT_LANGUAGE:
            logger.debug(
                f"Текст [{category}.{key}] не найден в {lang_code}, "
                f"ищем в {DEFAULT_LANGUAGE}"
            )
            ru_data: Dict[str, Any] = load_language(DEFAULT_LANGUAGE)
            text = ru_data.get(category, {}).get(key, "")
        
        # Если всё ещё не найден, возвращаем заглушку
        if not text:
            logger.warning(
                f"Текст [{category}.{key}] не найден ни в одном языке"
            )
            return f"[{category}.{key}]"
        
        return text
        
    except Exception as error:
        logger.error(f"Ошибка получения текста [{category}.{key}]: {error}")
        return f"[{category}.{key}]"


# ==================== МЕНЕДЖЕР ЯЗЫКОВ ====================

class LanguageManager:
    """Менеджер языковых настроек пользователей."""
    
    def __init__(self) -> None:
        """Инициализация менеджера языков."""
        self._init_db()
        self._cache: Dict[int, str] = {}  # Кэш языков пользователей
    
    def _init_db(self) -> None:
        """Инициализация базы данных для хранения языков."""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_language (
                    user_id INTEGER PRIMARY KEY,
                    language_code TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
        
        logger.info("База данных языковых настроек инициализирована")
    
    def get_user_language(self, user_id: int) -> str:
        """
        Получить язык пользователя (с кэшированием).
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Код языка (ru, en, uk)
        """
        # Проверяем кэш
        if user_id in self._cache:
            return self._cache[user_id]
        
        # Ищем в БД
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT language_code FROM user_language WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
        
        # Если найден, сохраняем в кэш
        if result:
            lang_code: str = result[0]
            self._cache[user_id] = lang_code
            return lang_code
        
        # По умолчанию - русский
        return DEFAULT_LANGUAGE
    
    def set_user_language(self, user_id: int, language_code: str) -> None:
        """
        Установить язык пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            language_code: Код языка (ru, en, uk)
        """
        # Проверяем поддерживается ли язык
        if language_code not in SUPPORTED_LANGUAGES:
            logger.warning(
                f"Попытка установить неподдерживаемый язык {language_code}"
            )
            language_code = DEFAULT_LANGUAGE
        
        # Сохраняем в БД
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_language 
                (user_id, language_code, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, language_code))
            conn.commit()
        
        # Обновляем кэш
        self._cache[user_id] = language_code
        logger.info(f"Установлен язык '{language_code}' для пользователя {user_id}")


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_language_name(lang_code: str) -> str:
    """
    Получить название языка на его родном языке.
    
    Args:
        lang_code: Код языка
        
    Returns:
        Название языка
    """
    return LANGUAGE_NAMES.get(lang_code, LANGUAGE_NAMES[DEFAULT_LANGUAGE])


def reload_languages() -> None:
    """Принудительно перезагрузить все языки из файлов."""
    global _language_cache
    _language_cache.clear()
    for lang in SUPPORTED_LANGUAGES:
        load_language(lang)
    logger.info("Все языки перезагружены")


def get_supported_languages() -> List[str]:
    """
    Получить список поддерживаемых языков.
    
    Returns:
        Список кодов языков
    """
    return SUPPORTED_LANGUAGES.copy()


# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

language_manager: LanguageManager = LanguageManager()

# Для обратной совместимости
get_user_language = language_manager.get_user_language
set_user_language = language_manager.set_user_language
