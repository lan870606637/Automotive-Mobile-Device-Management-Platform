# -*- coding: utf-8 -*-
"""
检查 MySQL 数据库中的用户数据
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import pymysql

print("=" * 60)
print("检查 MySQL 用户数据")
print("=" * 60)

try:
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # 检查 users 表结构
    print("\n1. Users 表结构:")
    cursor.execute("SHOW COLUMNS FROM users")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[0]} ({col[1]})")
    
    # 检查所有用户
    print("\n2. 所有用户数据:")
    cursor.execute("SELECT id, borrower_name, email, is_deleted FROM users")
    users = cursor.fetchall()
    print(f"   共有 {len(users)} 个用户:")
    for user in users:
        email_str = user[2] if user[2] else '(空)'
        deleted_str = '已删除' if user[3] else '正常'
        print(f"   - ID: {user[0][:8]}..., 名称: {user[1]}, 邮箱: {email_str}, 状态: {deleted_str}")
    
    # 检查借出设备
    print("\n3. 借出设备:")
    cursor.execute("SELECT id, name, borrower, borrower_id, status FROM devices WHERE status = '借出'")
    devices = cursor.fetchall()
    print(f"   共有 {len(devices)} 个借出设备:")
    for device in devices:
        borrower_id_str = device[3][:8] + '...' if device[3] else '(空)'
        print(f"   - {device[1]}: borrower={device[2]}, borrower_id={borrower_id_str}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
