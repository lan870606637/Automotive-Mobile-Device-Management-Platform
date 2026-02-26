# -*- coding: utf-8 -*-
"""
检查数据库表结构
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'device_management.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 60)
print("Users 表结构:")
print("=" * 60)
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

print("\n" + "=" * 60)
print("Devices 表结构:")
print("=" * 60)
cursor.execute("PRAGMA table_info(devices)")
columns = cursor.fetchall()
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

conn.close()
