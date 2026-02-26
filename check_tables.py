# -*- coding: utf-8 -*-
"""
检查SQLite表结构
"""
import sqlite3

conn = sqlite3.connect('device_management.db')
cursor = conn.cursor()

# 获取所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("SQLite数据库表结构:")
print("=" * 60)

for table in tables:
    table_name = table[0]
    print(f"\n表: {table_name}")
    print("-" * 40)
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        print(f"  {col_name} ({col_type})")

conn.close()
