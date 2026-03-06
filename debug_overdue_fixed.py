# -*- coding: utf-8 -*-
"""
修复后的逾期设备查询调试脚本
问题：原脚本使用 'BORROWED' 查询，但数据库存储的是 '借出'
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

print("=" * 60)
print("修复后的逾期设备查询调试")
print("=" * 60)
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

with get_db_connection() as conn:
    cursor = conn.cursor()

    # 1. 查看数据库中实际的状态值
    print("1. 数据库中所有不同的状态值:")
    cursor.execute("""
        SELECT DISTINCT status, COUNT(*) as count
        FROM devices
        WHERE is_deleted = 0
        GROUP BY status
    """)
    statuses = cursor.fetchall()
    for s in statuses:
        print(f"   '{s['status']}': {s['count']} 个设备")
    print()

    # 2. 使用正确的中文'借出'查询
    print("2. 使用 '借出' 查询借用中的设备:")
    cursor.execute("""
        SELECT id, name, borrower_id, borrower, expected_return_date, status, is_deleted
        FROM devices
        WHERE status = '借出' AND is_deleted = 0
        LIMIT 10
    """)
    devices = cursor.fetchall()
    print(f"   找到 {len(devices)} 个设备")
    for d in devices:
        print(f"   ID:{d['id']} | {d['name']} | 借用人:{d['borrower']} | 归还时间:{d['expected_return_date']} | 状态:{d['status']}")
    print()

    # 3. 使用英文'BORROWED'查询（错误的方式）
    print("3. 使用 'BORROWED' 查询（错误方式，应该返回0条）:")
    cursor.execute("""
        SELECT id, name, borrower_id, expected_return_date, status
        FROM devices
        WHERE status = 'BORROWED' AND is_deleted = 0
        LIMIT 10
    """)
    devices_wrong = cursor.fetchall()
    print(f"   找到 {len(devices_wrong)} 个设备")
    print()

    # 4. 查看有预期归还时间的设备（使用正确的中文'借出'）
    print("4. 借用中且有预期归还时间的设备:")
    cursor.execute("""
        SELECT id, name, borrower_id, borrower, expected_return_date, status
        FROM devices
        WHERE status = '借出'
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
        LIMIT 10
    """)
    devices = cursor.fetchall()
    print(f"   找到 {len(devices)} 个设备")
    for d in devices:
        print(f"   ID:{d['id']} | {d['name']} | 借用人:{d['borrower']} | 归还时间:{d['expected_return_date']}")
    print()

    # 5. 查看逾期的设备（关键查询 - 使用正确的中文'借出'）
    print("5. 逾期设备（expected_return_date < NOW()）:")
    cursor.execute("""
        SELECT id, name, borrower_id, borrower, expected_return_date, status
        FROM devices
        WHERE status = '借出'
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
        AND expected_return_date < NOW()
        ORDER BY expected_return_date
        LIMIT 10
    """)
    overdue = cursor.fetchall()
    print(f"   找到 {len(overdue)} 个逾期设备")
    for d in overdue:
        overdue_hours = (datetime.now() - d['expected_return_date']).total_seconds() / 3600
        print(f"   ID:{d['id']} | {d['name']} | 借用人:{d['borrower']} | 应还时间:{d['expected_return_date']} | 逾期约:{overdue_hours:.1f}小时")
    print()

    # 6. 检查时间对比
    print("6. 时间对比检查:")
    cursor.execute("SELECT NOW() as now_time")
    now_result = cursor.fetchone()
    print(f"   数据库当前时间: {now_result['now_time']}")
    print(f"   Python当前时间: {datetime.now()}")
    print()

    # 7. 查看所有借用设备的预期归还时间（不管是否逾期）
    print("7. 所有借用设备的预期归还时间（前20个）:")
    cursor.execute("""
        SELECT id, name, borrower, expected_return_date,
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
        print(f"   {d['name']} (借用人:{d['borrower']}): {d['expected_return_date']} [{d['overdue_status']}]")

print()
print("=" * 60)
print("总结:")
print("- 数据库中存储的状态值是中文 '借出'")
print("- 使用 'BORROWED' 查询会返回空结果")
print("- db_store.py 中的查询是正确的（使用 '借出'）")
print("- debug_overdue.py 有bug（使用 'BORROWED'）")
print("=" * 60)
