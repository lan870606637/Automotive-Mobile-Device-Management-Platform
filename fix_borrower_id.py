# -*- coding: utf-8 -*-
"""
修复借出设备的 borrower_id
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import pymysql

print("=" * 60)
print("修复借出设备的 borrower_id")
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
    
    # 查找所有借出但 borrower_id 为空的设备
    cursor.execute("""
        SELECT d.id, d.name, d.borrower, d.borrower_id 
        FROM devices d 
        WHERE d.status = '借出' AND (d.borrower_id IS NULL OR d.borrower_id = '')
    """)
    devices = cursor.fetchall()
    
    print(f"\n找到 {len(devices)} 个需要修复的设备:")
    for device in devices:
        print(f"   - {device[1]}: borrower={device[2]}, borrower_id={device[3] if device[3] else '(空)'}")
    
    # 修复每个设备
    fixed_count = 0
    for device in devices:
        device_id = device[0]
        borrower_name = device[2]
        
        # 查找用户ID
        cursor.execute("SELECT id FROM users WHERE borrower_name = %s AND is_deleted = 0", (borrower_name,))
        user = cursor.fetchone()
        
        if user:
            user_id = user[0]
            cursor.execute("UPDATE devices SET borrower_id = %s WHERE id = %s", (user_id, device_id))
            print(f"   ✓ 修复 {device[1]}: borrower_id = {user_id[:8]}...")
            fixed_count += 1
        else:
            print(f"   ✗ 未找到用户: {borrower_name}")
    
    conn.commit()
    
    print(f"\n✓ 共修复 {fixed_count} 个设备")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("修复完成！")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
