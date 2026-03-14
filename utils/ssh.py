#!/usr/bin/env python3
"""
SSH клиент для подключения к серверам
"""
import logging
import paramiko
import os
from typing import Optional

from config.loader import get_server_config, get_full_ssh_key_path

logger = logging.getLogger(__name__)


class SSHClient:
    """Клиент для SSH подключений"""

    def __init__(self, server_id: str):
        """
        Инициализация SSH клиента

        Args:
            server_id: ID сервера из конфигурации
        """
        self.server_id = server_id
        self.server_info = get_server_config(server_id)
        self.client = None
        self.connected = False

        if not self.server_info:
            logger.error(f"Сервер {self.server_id} не найден в конфигурации")

    def _get_connection_params(self) -> dict:
        """
        Получить параметры подключения из конфигурации сервера

        Returns:
            Словарь с параметрами для connect()
        """
        if not self.server_info:
            return {}

        # Определяем хост
        host = self.server_info.get('host') or self.server_info.get('ip')
        if not host:
            logger.error(f"Для сервера {self.server_id} не указан host или ip")
            return {}

        # Базовые параметры
        params = {
            'hostname': host,
            'port': self.server_info.get('port', 22),
            'username': self.server_info.get('user', 'semis'),
            'timeout': 10,
            'allow_agent': False,
            'look_for_keys': False
        }

        # Добавляем ключ, если указан
        ssh_key_name = self.server_info.get('ssh_key')
        if ssh_key_name:
            key_path = get_full_ssh_key_path(ssh_key_name)
            if os.path.exists(key_path):
                try:
                    # Пробуем разные типы ключей
                    for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
                        try:
                            key = key_class.from_private_key_file(key_path)
                            params['pkey'] = key
                            logger.debug(f"Загружен SSH ключ {ssh_key_name} как {key_class.__name__}")
                            break
                        except paramiko.ssh_exception.SSHException:
                            continue
                except Exception as e:
                    logger.error(f"Ошибка загрузки SSH ключа {key_path}: {e}")
            else:
                logger.warning(f"SSH ключ не найден: {key_path}")

        return params

    def _connect(self) -> bool:
        """
        Установить SSH соединение

        Returns:
            True если соединение установлено, иначе False
        """
        if self.connected and self.client:
            return True

        if not self.server_info:
            logger.error(f"Сервер {self.server_id} не найден в конфигурации")
            return False

        params = self._get_connection_params()
        if not params:
            return False

        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(**params)
            self.connected = True
            logger.debug(f"SSH подключение к {self.server_id} установлено")
            return True

        except paramiko.AuthenticationException as e:
            logger.error(f"Ошибка аутентификации SSH для {self.server_id}: {e}")
        except paramiko.SSHException as e:
            logger.error(f"SSH ошибка для {self.server_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка SSH подключения к {self.server_id}: {e}")

        return False

    def execute_command(self, command: str, timeout: int = 30) -> str:
        """
        Выполнить команду на сервере

        Args:
            command: Команда для выполнения
            timeout: Таймаут в секундах

        Returns:
            Вывод команды (stdout) или сообщение об ошибке
        """
        if not self._connect():
            return f"ERROR: Не удалось подключиться к {self.server_id}"

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # Читаем вывод
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()

            if error:
                # Некоторые команды пишут в stderr даже при успехе
                # Логируем, но не возвращаем как ошибку
                logger.debug(f"Stderr от {self.server_id}: {error}")

            return output if output else error

        except paramiko.SSHException as e:
            logger.error(f"SSH ошибка при выполнении команды на {self.server_id}: {e}")
            # Возможно соединение оборвалось - сбросим флаг для переподключения
            self.connected = False
            return f"ERROR: SSH ошибка: {e}"
        except Exception as e:
            logger.error(f"Ошибка выполнения команды на {self.server_id}: {e}")
            return f"ERROR: {e}"

    def execute_command_with_exit_code(self, command: str, timeout: int = 30) -> tuple:
        """
        Выполнить команду и вернуть (stdout, stderr, exit_code)

        Args:
            command: Команда для выполнения
            timeout: Таймаут в секундах

        Returns:
            Кортеж (stdout, stderr, exit_code)
        """
        if not self._connect():
            return "", f"ERROR: Не удалось подключиться к {self.server_id}", -1

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            exit_code = stdout.channel.recv_exit_status()

            return output, error, exit_code

        except Exception as e:
            logger.error(f"Ошибка выполнения команды на {self.server_id}: {e}")
            return "", str(e), -1

    def close(self):
        """Закрыть соединение"""
        if hasattr(self, 'client') and self.client:
            try:
                self.client.close()
            except:
                pass
            finally:
                self.client = None
                self.connected = False
                # Проверяем, что logger существует перед использованием
                if 'logger' in globals() or 'logger' in locals():
                    try:
                        logger.debug(f"SSH соединение с {self.server_id} закрыто")
                    except:
                        pass

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        """Деструктор для гарантированного закрытия соединения"""
        # В деструктоне не используем logger, так как он может быть уже удалён
        if hasattr(self, 'client') and self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
            self.connected = False
