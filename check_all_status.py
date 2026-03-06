# -*- coding: utf-8 -*-
"""
检查所有设备状态值
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

print("=" * 60)
print("检查所有设备状态值")
print("=" * 60)
print()

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT status, COUNT(*) as count
        FROM devices 
        WHERE is_deleted = 0
        GROUP BY status
        ORDER BY count DESC
    """)
    statuses = cursor.fetchall()
    
    print("数据库中实际使用的状态值:")
    for s in statuses:
        print(f"   '{s['status']}': {s['count']} 个设备")

print()
print("=" * 60)
