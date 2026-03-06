# -*- coding: utf-8 -*-
"""
调试逾期设备查询问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

print("=" * 60)
print("调试逾期设备查询")
print("=" * 60)
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # 1. 查看所有借用中的设备
    print("1. 所有借用中的设备:")
    cursor.execute("""
        SELECT id, name, borrower_id, expected_return_date, status, is_deleted
        FROM devices 
        WHERE status = '借出' AND is_deleted = 0
        LIMIT 10
    """)
    devices = cursor.fetchall()
    for d in devices:
        print(f"   ID:{d['id']} | {d['name']} | 归还时间:{d['expected_return_date']} | 状态:{d['status']}")
    print()
    
    # 2. 查看有预期归还时间的设备
    print("2. 借用中且有预期归还时间的设备:")
    cursor.execute("""
        SELECT id, name, borrower_id, expected_return_date, status
        FROM devices 
        WHERE status = '借出' 
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
        LIMIT 10
    """)
    devices = cursor.fetchall()
    for d in devices:
        print(f"   ID:{d['id']} | {d['name']} | 归还时间:{d['expected_return_date']}")
    print()
    
    # 3. 查看逾期的设备（关键查询）
    print("3. 逾期设备（expected_return_date < NOW()）:")
    cursor.execute("""
        SELECT id, name, borrower_id, expected_return_date, status
        FROM devices 
        WHERE status = '借出' 
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
        AND expected_return_date < NOW()
        LIMIT 10
    """)
    overdue = cursor.fetchall()
    print(f"   找到 {len(overdue)} 个逾期设备")
    for d in overdue:
        print(f"   ID:{d['id']} | {d['name']} | 应还时间:{d['expected_return_date']}")
    print()
    
    # 4. 检查时间对比
    print("4. 时间对比检查:")
    cursor.execute("SELECT NOW() as now_time")
    now_result = cursor.fetchone()
    print(f"   数据库当前时间: {now_result['now_time']}")
    
    if overdue:
        cursor.execute("""
            SELECT expected_return_date 
            FROM devices 
            WHERE status = '借出' AND expected_return_date IS NOT NULL
            ORDER BY expected_return_date DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()
        print(f"   最晚的预期归还时间: {latest['expected_return_date']}")
        print(f"   是否逾期: {latest['expected_return_date'] < now_result['now_time']}")
    print()
    
    # 5. 查看所有借用设备的预期归还时间（不管是否逾期）
    print("5. 所有借用设备的预期归还时间（前20个）:")
    cursor.execute("""
        SELECT id, name, expected_return_date, 
               CASE WHEN expected_return_date < NOW() THEN '已逾期' ELSE '未逾期' END as overdue_status
        FROM devices 
        WHERE status = '借出' 
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
        ORDER BY expected_return_date
        LIMIT 20
    """)
    all_devices = cursor.fetchall()
    for d in all_devices:
        print(f"   {d['name']}: {d['expected_return_date']} [{d['overdue_status']}]")

print()
print("=" * 60)
