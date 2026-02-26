# -*- coding: utf-8 -*-
"""
直接检查数据库文件
"""
import sqlite3
import os

# 数据库路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'device_management.db')

print(f"数据库路径: {DB_PATH}")
print(f"数据库存在: {os.path.exists(DB_PATH)}")

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查 users 表
    print("\n" + "=" * 60)
    print("Users 表:")
    print("=" * 60)
    try:
        cursor.execute("SELECT id, borrower_name, email FROM users WHERE is_deleted = 0")
        users = cursor.fetchall()
        print(f"共有 {len(users)} 个用户:")
        for user in users:
            print(f"  - ID: {user[0][:8]}..., 名称: {user[1]}, 邮箱: {user[2]}")
    except Exception as e:
        print(f"错误: {e}")
    
    # 检查 devices 表中的 borrower_id
    print("\n" + "=" * 60)
    print("Devices 表 (借出状态):")
    print("=" * 60)
    try:
        cursor.execute("SELECT id, name, borrower, borrower_id, status FROM devices WHERE status = '借出'")
        devices = cursor.fetchall()
        print(f"共有 {len(devices)} 个借出设备:")
        for device in devices:
            print(f"  - {device[1]}: borrower={device[2]}, borrower_id={device[3] if device[3] else '空'}")
    except Exception as e:
        print(f"错误: {e}")
    
    conn.close()
