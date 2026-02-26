# -*- coding: utf-8 -*-
"""
恢复所有已删除用户
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import pymysql

print("=" * 60)
print("恢复所有已删除用户")
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
    
    # 统计已删除用户
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_deleted = 1")
    deleted_count = cursor.fetchone()[0]
    print(f"\n共有 {deleted_count} 个已删除用户")
    
    # 恢复所有用户
    cursor.execute("UPDATE users SET is_deleted = 0 WHERE is_deleted = 1")
    conn.commit()
    
    print(f"✓ 已恢复 {cursor.rowcount} 个用户")
    
    # 验证
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_deleted = 0")
    active_count = cursor.fetchone()[0]
    print(f"\n现在有 {active_count} 个活跃用户")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("恢复完成！")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
