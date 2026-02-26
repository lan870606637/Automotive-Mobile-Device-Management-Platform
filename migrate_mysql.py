# -*- coding: utf-8 -*-
"""
MySQL 数据库迁移脚本 - 添加缺失的列
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import pymysql

print("=" * 60)
print("MySQL 数据库迁移")
print("=" * 60)
print(f"\n连接信息:")
print(f"  主机: {MYSQL_HOST}")
print(f"  端口: {MYSQL_PORT}")
print(f"  数据库: {MYSQL_DATABASE}")
print(f"  用户: {MYSQL_USER}")

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
    
    # 1. 检查并添加 users.email 列
    print("\n1. 检查 users.email 列...")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'email'")
    if not cursor.fetchone():
        print("   添加 email 列...")
        cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE")
        conn.commit()
        print("   ✓ email 列已添加")
    else:
        print("   ✓ email 列已存在")
    
    # 2. 检查并添加 devices.borrower_id 列
    print("\n2. 检查 devices.borrower_id 列...")
    cursor.execute("SHOW COLUMNS FROM devices LIKE 'borrower_id'")
    if not cursor.fetchone():
        print("   添加 borrower_id 列...")
        cursor.execute("ALTER TABLE devices ADD COLUMN borrower_id VARCHAR(64)")
        conn.commit()
        print("   ✓ borrower_id 列已添加")
    else:
        print("   ✓ borrower_id 列已存在")
    
    # 3. 检查并添加 devices.pre_ship_phone 列
    print("\n3. 检查 devices.pre_ship_phone 列...")
    cursor.execute("SHOW COLUMNS FROM devices LIKE 'pre_ship_phone'")
    if not cursor.fetchone():
        print("   添加 pre_ship_phone 列...")
        cursor.execute("ALTER TABLE devices ADD COLUMN pre_ship_phone VARCHAR(20)")
        conn.commit()
        print("   ✓ pre_ship_phone 列已添加")
    else:
        print("   ✓ pre_ship_phone 列已存在")
    
    # 4. 检查并添加 devices.pre_ship_reason 列
    print("\n4. 检查 devices.pre_ship_reason 列...")
    cursor.execute("SHOW COLUMNS FROM devices LIKE 'pre_ship_reason'")
    if not cursor.fetchone():
        print("   添加 pre_ship_reason 列...")
        cursor.execute("ALTER TABLE devices ADD COLUMN pre_ship_reason TEXT")
        conn.commit()
        print("   ✓ pre_ship_reason 列已添加")
    else:
        print("   ✓ pre_ship_reason 列已存在")
    
    # 5. 检查并添加 users.is_first_login 列
    print("\n5. 检查 users.is_first_login 列...")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'is_first_login'")
    if not cursor.fetchone():
        print("   添加 is_first_login 列...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_first_login INT DEFAULT 1")
        conn.commit()
        print("   ✓ is_first_login 列已添加")
    else:
        print("   ✓ is_first_login 列已存在")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("MySQL 数据库迁移完成！")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
