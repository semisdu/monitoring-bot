#!/usr/bin/env python3
import sys
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'database' / 'monitoring.db'

try:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    conn.close()
    print("OK")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
