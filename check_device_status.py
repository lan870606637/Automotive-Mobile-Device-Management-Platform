# -*- coding: utf-8 -*-
"""
检查设备状态字段的所有可能值
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

print("=" * 60)
print("检查设备状态字段")
print("=" * 60)
print()

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # 1. 查看所有不同的状态值
    print("1. 设备表中所有不同的状态值:")
    cursor.execute("""
        SELECT DISTINCT status, COUNT(*) as count
        FROM devices 
        WHERE is_deleted = 0
        GROUP BY status
        ORDER BY count DESC
    """)
    statuses = cursor.fetchall()
    for s in statuses:
        print(f"   状态 '{s['status']}': {s['count']} 个设备")
    print()
    
    # 2. 查看所有设备（前20个）
    print("2. 所有设备列表（前20个）:")
    cursor.execute("""
        SELECT id, name, status, borrower, expected_return_date
        FROM devices 
        WHERE is_deleted = 0
        ORDER BY id
        LIMIT 20
    """)
    devices = cursor.fetchall()
    for d in devices:
        borrower = d['borrower'] or '无'
        return_date = d['expected_return_date'] or '无'
        print(f"   {d['name']}: 状态={d['status']}, 借用人={borrower}, 应还={return_date}")
    print()
    
    # 3. 检查是否有大小写问题
    print("3. 检查大小写不同的BORROWED状态:")
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN status = 'BORROWED' THEN 1 ELSE 0 END) as upper_count,
            SUM(CASE WHEN status = 'borrowed' THEN 1 ELSE 0 END) as lower_count,
            SUM(CASE WHEN status LIKE '%borrow%' THEN 1 ELSE 0 END) as like_count
        FROM devices 
        WHERE is_deleted = 0
    """)
    result = cursor.fetchone()
    print(f"   BORROWED (大写): {result['upper_count']} 个")
    print(f"   borrowed (小写): {result['lower_count']} 个")
    print(f"   包含 borrow: {result['like_count']} 个")

print()
print("=" * 60)
