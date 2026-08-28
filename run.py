#!/usr/bin/env python3
"""
Запуск Monitoring Bot через asyncio
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в PATH
sys.path.insert(0, str(Path(__file__).parent))

from main import main

if __name__ == "__main__":
    main()
