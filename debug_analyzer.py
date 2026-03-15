#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "database" / "errors.db"

def simple_add():
    print("="*50)
    print("УПРОЩЁННЫЙ ТЕСТ")
    print("="*50)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 1. Проверяем вставку в errors
    print("\n1. Тест вставки в errors...")
    try:
        cursor.execute('''
            INSERT INTO errors (
                error_type, error_hash, message, server_id,
                container_name, site_url, severity, status_code,
                response_time, recommendations
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'test_error', 'hash123', 'test message', 'server1',
            None, None, 'warning', None, None,
            json.dumps(['rec1', 'rec2'])
        ))
        error_id = cursor.lastrowid
        print(f"   ✅ Успешно! ID: {error_id}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 2. Проверяем вставку в error_trends
    print("\n2. Тест вставки в error_trends...")
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO error_trends (error_hash, date, occurrences)
            VALUES (?, ?, ?)
        ''', ('hash123', today, 1))
        print(f"   ✅ Успешно!")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 3. Проверяем SELECT
    print("\n3. Тест SELECT...")
    try:
        cursor.execute('SELECT * FROM errors')
        rows = cursor.fetchall()
        print(f"   ✅ Найдено записей в errors: {len(rows)}")
        
        cursor.execute('SELECT * FROM error_trends')
        rows = cursor.fetchall()
        print(f"   ✅ Найдено записей в error_trends: {len(rows)}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    simple_add()
