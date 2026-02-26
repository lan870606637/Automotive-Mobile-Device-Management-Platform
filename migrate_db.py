# -*- coding: utf-8 -*-
"""
手动迁移数据库，添加缺失的列
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'device_management.db')

print(f"数据库路径: {DB_PATH}")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. 检查并添加 users.email 列
print("\n1. 检查 users.email 列...")
cursor.execute("PRAGMA table_info(users)")
columns = [col[1] for col in cursor.fetchall()]
if 'email' not in columns:
    print("   添加 email 列...")
    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    print("   ✓ email 列已添加")
else:
    print("   ✓ email 列已存在")

# 2. 检查并添加 devices.borrower_id 列
print("\n2. 检查 devices.borrower_id 列...")
cursor.execute("PRAGMA table_info(devices)")
columns = [col[1] for col in cursor.fetchall()]
if 'borrower_id' not in columns:
    print("   添加 borrower_id 列...")
    cursor.execute("ALTER TABLE devices ADD COLUMN borrower_id TEXT")
    print("   ✓ borrower_id 列已添加")
else:
    print("   ✓ borrower_id 列已存在")

# 3. 检查并添加 devices.pre_ship_phone 列（如果有缺失）
print("\n3. 检查 devices.pre_ship_phone 列...")
if 'pre_ship_phone' not in columns:
    print("   添加 pre_ship_phone 列...")
    cursor.execute("ALTER TABLE devices ADD COLUMN pre_ship_phone TEXT")
    print("   ✓ pre_ship_phone 列已添加")
else:
    print("   ✓ pre_ship_phone 列已存在")

# 4. 检查并添加 devices.pre_ship_reason 列（如果有缺失）
print("\n4. 检查 devices.pre_ship_reason 列...")
if 'pre_ship_reason' not in columns:
    print("   添加 pre_ship_reason 列...")
    cursor.execute("ALTER TABLE devices ADD COLUMN pre_ship_reason TEXT")
    print("   ✓ pre_ship_reason 列已添加")
else:
    print("   ✓ pre_ship_reason 列已存在")

conn.commit()
conn.close()

print("\n" + "=" * 60)
print("数据库迁移完成！")
print("=" * 60)
