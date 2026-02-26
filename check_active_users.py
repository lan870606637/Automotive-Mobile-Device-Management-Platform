# -*- coding: utf-8 -*-
"""
检查活跃用户信息
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import pymysql

print("=" * 60)
print("检查活跃用户（未删除）")
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
    
    # 检查未删除用户
    print("\n1. 未删除用户 (is_deleted = 0):")
    cursor.execute("SELECT id, borrower_name, email, is_deleted FROM users WHERE is_deleted = 0")
    users = cursor.fetchall()
    print(f"   共有 {len(users)} 个未删除用户:")
    for user in users:
        print(f"   - ID: {user[0][:8]}..., 名称: {user[1]}, 邮箱: {user[2]}")
    
    if len(users) == 0:
        print("   ⚠ 没有未删除的用户！")
        print("\n2. 所有用户（包括已删除）:")
        cursor.execute("SELECT id, borrower_name, email, is_deleted FROM users")
        all_users = cursor.fetchall()
        print(f"   共有 {len(all_users)} 个用户:")
        for user in all_users:
            status = '正常' if user[3] == 0 else '已删除'
            print(f"   - ID: {user[0][:8]}..., 名称: {user[1]}, 邮箱: {user[2]}, 状态: {status}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
