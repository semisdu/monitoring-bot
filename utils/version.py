#!/usr/bin/env python3
"""
Улучшенная система управления версиями
"""
import os
import json
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class VersionManager:
    """Менеджер версий проекта"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root or os.getcwd())
        self.version_file = self.project_root / "version.json"
        self.version_info = self._load_version()
    
    def _load_version(self) -> Dict[str, Any]:
        """Загрузить информацию о версии из файла или создать новую"""
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Не удалось загрузить version.json: {e}")
        
        # Создаем начальную версию
        return self._create_initial_version()
    
    def _create_initial_version(self) -> Dict[str, Any]:
        """Создать начальную версию"""
        now = datetime.now()
        return {
            "version": "v1.0.0-refactored",
            "major": 1,
            "minor": 0,
            "patch": 0,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "build": now.strftime("%H%M"),
            "description": "Рефакторинг версия Monitoring Bot",
            "changes_source": self._get_changes_source(),
            "components": self._get_components_info(),
            "git": self._get_git_info() if self._is_git_repo() else None
        }
    
    def _is_git_repo(self) -> bool:
        """Проверить, является ли директория git репозиторием"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _get_git_info(self) -> Optional[Dict[str, str]]:
        """Получить информацию из git"""
        try:
            git_info = {}
            
            # Хэш коммита
            git_hash = subprocess.check_output(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=self.project_root,
                text=True
            ).strip()
            git_info['commit'] = git_hash
            
            # Ветка
            git_branch = subprocess.check_output(
                ['git', 'branch', '--show-current'],
                cwd=self.project_root,
                text=True
            ).strip()
            git_info['branch'] = git_branch
            
            # Количество коммитов
            git_count = subprocess.check_output(
                ['git', 'rev-list', '--count', 'HEAD'],
                cwd=self.project_root,
                text=True
            ).strip()
            git_info['commits'] = git_count
            
            return git_info
            
        except (subprocess.SubprocessError, FileNotFoundError):
            return None
    
    def _get_changes_source(self) -> str:
        """Получить источник изменений (git хэш или хэш файлов)"""
        if self._is_git_repo():
            try:
                git_hash = subprocess.check_output(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=self.project_root,
                    text=True
                ).strip()
                return f"git:{git_hash}"
            except:
                pass
        
        # Создаем хэш на основе файлов проекта
        try:
            import hashlib
            hash_md5 = hashlib.md5()
            
            # Хэшируем основные файлы проекта
            files_to_hash = [
                "main.py",
                "bot/core.py",
                "bot/handlers.py",
                "bot/language.py",
                "config/settings.py",
                "config/languages.py"
            ]
            
            for file in files_to_hash:
                file_path = self.project_root / file
                if file_path.exists():
                    with open(file_path, 'rb') as f:
                        hash_md5.update(f.read())
            
            return f"hash:{hash_md5.hexdigest()[:8]}"
        except:
            return "unknown"
    
    def _get_components_info(self) -> Dict[str, str]:
        """Получить информацию о компонентах системы"""
        components = {
            "bot_core": "v1.0.0-refactored",
            "multi_language": "ru/uk/en",
            "config_system": "centralized",
            "database": "sqlite",
            "scheduler": "apscheduler"
        }
        
        # Проверяем наличие файлов для определения компонентов
        if (self.project_root / "config" / "languages.py").exists():
            components["language_system"] = "enabled"
        
        if (self.project_root / "database").exists():
            components["persistence"] = "enabled"
        
        return components
    
    def update_version(self, 
                      description: str = None,
                      bump_type: str = "patch") -> Dict[str, Any]:
        """
        Обновить версию проекта
        
        Args:
            description: Описание изменений
            bump_type: Тип обновления (major, minor, patch, build)
        
        Returns:
            Новая информация о версии
        """
        # Получаем текущие номера версий
        current = self.version_info
        
        if bump_type == "major":
            major = current.get("major", 0) + 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            major = current.get("major", 0)
            minor = current.get("minor", 0) + 1
            patch = 0
        elif bump_type == "patch":
            major = current.get("major", 0)
            minor = current.get("minor", 0)
            patch = current.get("patch", 0) + 1
        else:  # build
            major = current.get("major", 0)
            minor = current.get("minor", 0)
            patch = current.get("patch", 0)
        
        now = datetime.now()
        build = now.strftime("%H%M")
        
        # Создаем строку версии
        version_str = f"v{major}.{minor}.{patch}"
        if bump_type == "build":
            version_str = f"{current.get('version', 'v0.0.0')}.{build}"
        
        # Обновляем информацию
        new_version = {
            "version": version_str,
            "major": major,
            "minor": minor,
            "patch": patch,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "build": build,
            "description": description or f"Auto-updated {bump_type} version",
            "changes_source": self._get_changes_source(),
            "components": self._get_components_info(),
            "git": self._get_git_info() if self._is_git_repo() else None,
            "previous_version": current.get("version"),
            "updated_at": now.isoformat()
        }
        
        # Сохраняем
        self.version_info = new_version
        self._save_version()
        
        logger.info(f"Версия обновлена: {current.get('version')} -> {version_str}")
        return new_version
    
    def _save_version(self):
        """Сохранить информацию о версии в файл"""
        try:
            with open(self.version_file, 'w', encoding='utf-8') as f:
                json.dump(self.version_info, f, indent=2, ensure_ascii=False)
            logger.debug(f"Информация о версии сохранена в {self.version_file}")
        except IOError as e:
            logger.error(f"Не удалось сохранить version.json: {e}")
    
    def get_version_string(self) -> str:
        """Получить строку версии в удобном формате"""
        info = self.version_info
        components = []
        
        if "git" in info and info["git"]:
            git = info["git"]
            if "commit" in git:
                components.append(f"commit:{git['commit'][:8]}")
        
        version_str = f"{info['version']} ({info['date']})"
        if components:
            version_str += f" [{', '.join(components)}]"
        
        return version_str
    
    def get_detailed_info(self) -> str:
        """Получить подробную информацию о версии"""
        info = self.version_info
        lines = [
            "=" * 60,
            f"Monitoring Bot - {info['version']}",
            "=" * 60,
            f"Дата сборки: {info['date']} {info['time']}",
            f"Описание: {info['description']}",
            "",
            "Компоненты:"
        ]
        
        for name, version in info.get('components', {}).items():
            lines.append(f"  • {name}: {version}")
        
        if "git" in info and info["git"]:
            lines.append("")
            lines.append("Git информация:")
            for key, value in info["git"].items():
                lines.append(f"  • {key}: {value}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def create_backup(self, backup_dir: str = None) -> Optional[str]:
        """Создать backup текущей версии"""
        backup_dir = Path(backup_dir or self.project_root / "backups")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{self.version_info['version']}_{timestamp}"
        backup_path = backup_dir / backup_name
        
        try:
            # Здесь может быть логика создания бэкапа
            # Например, копирование ключевых файлов
            import shutil
            
            # Создаем директорию для бэкапа
            backup_path.mkdir(exist_ok=True)
            
            # Копируем version.json
            shutil.copy2(self.version_file, backup_path / "version.json")
            
            # Создаем readme для бэкапа
            readme = backup_path / "README.txt"
            with open(readme, 'w', encoding='utf-8') as f:
                f.write(f"Backup of {self.version_info['version']}\n")
                f.write(f"Created: {datetime.now()}\n")
                f.write(f"Description: {self.version_info['description']}\n")
            
            logger.info(f"Backup создан: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Не удалось создать backup: {e}")
            return None

# Глобальный экземпляр менеджера версий
_version_manager = None

def get_version_manager() -> VersionManager:
    """Получить глобальный экземпляр менеджера версий"""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager

def get_version() -> Dict[str, Any]:
    """Получить текущую версию"""
    return get_version_manager().version_info

def get_version_str() -> str:
    """Получить строку версии"""
    return get_version_manager().get_version_string()

def get_detailed_version() -> str:
    """Получить подробную информацию о версии"""
    return get_version_manager().get_detailed_info()
