# -*- coding: utf-8 -*-
"""
直接检查 MySQL 数据库中的 borrower_id
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import pymysql

print("=" * 60)
print("检查 MySQL 借出设备的 borrower_id")
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
    
    # 检查借出设备的 borrower_id
    print("\n借出设备:")
    cursor.execute("SELECT id, name, borrower, borrower_id, status FROM devices WHERE status = '借出'")
    devices = cursor.fetchall()
    print(f"共有 {len(devices)} 个借出设备:")
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
