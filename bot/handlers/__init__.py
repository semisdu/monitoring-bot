"""
Пакет обработчиков команд Telegram бота.
Экспортирует все функции для регистрации в основном приложении.
"""

# Базовые утилиты
from .common import get_user_id, send_or_edit_message

# Основные команды
from .start import start_command
from .help import help_command
from .sites import site_command

# Статус и информация
from .status import status_command, format_server_status
from .version import version_command
from .stats import stats_command

# Мониторинг
from .alerts import alerts_command
from .logs import logs_command
from .monitor import monitor_status_command, monitor_log_command
from .cleanup import cleanup_command

# Инфраструктура
from .proxmox import pve_status_command, pbs_status_command

# Универсальные Docker команды (поддерживают любые серверы)
from .docker import (
    docker_menu_command,
    docker_check_server,
    docker_check_all,
    docker_restart_server,
    docker_restart_all
)

# Callback обработчики
from .callbacks import (
    callback_handler,
    register_handlers,
    check_server_status
)


__all__ = [
    # Базовые утилиты
    'get_user_id',
    'send_or_edit_message',
    
    # Основные команды
    'start_command',
    'help_command',
    'site_command',
    
    # Статус и информация
    'status_command',
    'format_server_status',
    'version_command',
    'stats_command',
    
    # Мониторинг
    'alerts_command',
    'logs_command',
    'monitor_status_command',
    'monitor_log_command',
    'cleanup_command',
    
    # Инфраструктура
    'pve_status_command',
    'pbs_status_command',
    
    # Универсальные Docker команды
    'docker_menu_command',
    'docker_check_server',
    'docker_check_all',
    'docker_restart_server',
    'docker_restart_all',
    
    # Callback обработчики
    'callback_handler',
    'register_handlers',
    'check_server_status',
]
