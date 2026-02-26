# -*- coding: utf-8 -*-
"""
MySQL 数据库迁移 - 添加 custodian_id 字段
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import pymysql

print("=" * 60)
print("MySQL 数据库迁移 - 添加 custodian_id")
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
    
    # 检查并添加 devices.custodian_id 列
    print("\n1. 检查 devices.custodian_id 列...")
    cursor.execute("SHOW COLUMNS FROM devices LIKE 'custodian_id'")
    if not cursor.fetchone():
        print("   添加 custodian_id 列...")
        cursor.execute("ALTER TABLE devices ADD COLUMN custodian_id VARCHAR(64)")
        conn.commit()
        print("   ✓ custodian_id 列已添加")
    else:
        print("   ✓ custodian_id 列已存在")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("迁移完成！")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
