#!/usr/bin/env python3
"""
Специфический мониторинг для course проекта (Django + PostgreSQL)
"""

import logging
import json
from typing import Dict, Any, Optional
from checks.docker import DockerMonitor

logger = logging.getLogger(__name__)

class CourseMonitor:
    """Мониторинг Django приложения course"""
    
    def __init__(self, server_id: str = "serv301"):
        self.server_id = server_id
        self.docker = DockerMonitor(server_id)
        self.app_container = "course_app"
        self.db_container = "course_postgres"
        
    def check_django_health(self) -> Dict[str, Any]:
        """Проверка здоровья Django приложения"""
        try:
            # Проверяем работает ли контейнер
            containers = self.docker.check_docker_containers()
            app_status = next(
                (c for c in containers.get("containers", []) 
                 if c.get("name") == self.app_container),
                None
            )
            
            if not app_status or not app_status.get("running"):
                return {
                    "status": "error",
                    "service": "django",
                    "message": "Django контейнер не запущен",
                    "details": app_status
                }
            
            # Проверяем внутреннюю команду Django
            cmd = f"docker exec {self.app_container} python manage.py check --deploy"
            result = self.docker._run_ssh_command(cmd)
            
            if result.get("success"):
                return {
                    "status": "ok",
                    "service": "django",
                    "message": "Django работает нормально",
                    "output": result.get("output", "")
                }
            else:
                return {
                    "status": "error",
                    "service": "django",
                    "message": "Ошибка проверки Django",
                    "error": result.get("error", "")
                }
                
        except Exception as e:
            logger.error(f"Ошибка проверки Django: {e}")
            return {
                "status": "error",
                "service": "django",
                "message": str(e)
            }
    
    def check_database_connection(self) -> Dict[str, Any]:
        """Проверка подключения к PostgreSQL"""
        try:
            # Проверяем работает ли контейнер БД
            containers = self.docker.check_docker_containers()
            db_status = next(
                (c for c in containers.get("containers", []) 
                 if c.get("name") == self.db_container),
                None
            )
            
            if not db_status or not db_status.get("running"):
                return {
                    "status": "error",
                    "service": "database",
                    "message": "PostgreSQL контейнер не запущен",
                    "details": db_status
                }
            
            # Проверяем подключение к БД через Django
            cmd = f"docker exec {self.db_container} psql -U adm_course -d course -c 'SELECT 1'"
            result = self.docker._run_ssh_command(cmd)
            
            if result.get("success"):
                return {
                    "status": "ok",
                    "service": "database",
                    "message": "Подключение к БД работает",
                    "output": result.get("output", "")
                }
            else:
                return {
                    "status": "error",
                    "service": "database",
                    "message": "Ошибка подключения к БД",
                    "error": result.get("error", "")
                }
                
        except Exception as e:
            logger.error(f"Ошибка проверки БД: {e}")
            return {
                "status": "error",
                "service": "database",
                "message": str(e)
            }
    
    def check_migrations(self) -> Dict[str, Any]:
        """Проверка наличия непримененных миграций"""
        try:
            cmd = f"docker exec {self.app_container} python manage.py showmigrations --plan"
            result = self.docker._run_ssh_command(cmd)
            
            if result.get("success"):
                output = result.get("output", "")
                # Ищем непримененные миграции [ ] вместо [X]
                pending = [line for line in output.split('\n') if '[ ]' in line]
                
                if pending:
                    return {
                        "status": "warning",
                        "service": "migrations",
                        "message": f"Есть непримененные миграции: {len(pending)}",
                        "pending": pending
                    }
                else:
                    return {
                        "status": "ok",
                        "service": "migrations",
                        "message": "Все миграции применены",
                        "pending": []
                    }
            else:
                return {
                    "status": "error",
                    "service": "migrations",
                    "message": "Ошибка проверки миграций",
                    "error": result.get("error", "")
                }
                
        except Exception as e:
            logger.error(f"Ошибка проверки миграций: {e}")
            return {
                "status": "error",
                "service": "migrations",
                "message": str(e)
            }
    
    def check_static_files(self) -> Dict[str, Any]:
        """Проверка наличия собранной статики"""
        try:
            cmd = f"docker exec {self.app_container} ls -la /src/staticfiles/ | wc -l"
            result = self.docker._run_ssh_command(cmd)
            
            if result.get("success"):
                files_count = result.get("output", "0").strip()
                if files_count.isdigit() and int(files_count) > 3:
                    return {
                        "status": "ok",
                        "service": "static",
                        "message": f"Статика собрана ({files_count} файлов)",
                        "files": int(files_count)
                    }
                else:
                    return {
                        "status": "warning",
                        "service": "static",
                        "message": "Статика не собрана или пуста",
                        "files": int(files_count) if files_count.isdigit() else 0
                    }
            else:
                return {
                    "status": "error",
                    "service": "static",
                    "message": "Ошибка проверки статики",
                    "error": result.get("error", "")
                }
                
        except Exception as e:
            logger.error(f"Ошибка проверки статики: {e}")
            return {
                "status": "error",
                "service": "static",
                "message": str(e)
            }
    
    def full_check(self) -> Dict[str, Any]:
        """Полная проверка course проекта"""
        results = {
            "server": self.server_id,
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "checks": {}
        }
        
        # Последовательно проверяем все компоненты
        results["checks"]["containers"] = self.docker.check_docker_containers()
        results["checks"]["django"] = self.check_django_health()
        results["checks"]["database"] = self.check_database_connection()
        results["checks"]["migrations"] = self.check_migrations()
        results["checks"]["static"] = self.check_static_files()
        
        # Общий статус
        all_ok = all(
            check.get("status") == "ok" 
            for check in results["checks"].values() 
            if isinstance(check, dict) and "status" in check
        )
        
        results["overall_status"] = "ok" if all_ok else "warning"
        
        return results

def monitor_course() -> Dict[str, Any]:
    """Удобная функция для вызова из бота"""
    monitor = CourseMonitor()
    return monitor.full_check()
