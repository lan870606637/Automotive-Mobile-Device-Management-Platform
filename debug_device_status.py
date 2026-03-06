# -*- coding: utf-8 -*-
"""
调试特定设备状态
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

print("=" * 70)
print("调试设备: oppo Find X5 Pro")
print("=" * 70)
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # 1. 查找这个设备
    print("1. 查找 oppo Find X5 Pro 设备:")
    cursor.execute("""
        SELECT 
            id, name, status, borrower, borrower_id, 
            expected_return_date, borrow_time, is_deleted
        FROM devices 
        WHERE name LIKE '%oppo%Find%X5%Pro%'
        OR name LIKE '%Find%X5%Pro%'
    """)
    devices = cursor.fetchall()
    
    if not devices:
        print("   未找到设备，尝试模糊搜索...")
        cursor.execute("""
            SELECT 
                id, name, status, borrower, borrower_id, 
                expected_return_date, borrow_time, is_deleted
            FROM devices 
            WHERE name LIKE '%oppo%'
            OR name LIKE '%Find%'
            OR name LIKE '%X5%'
            LIMIT 10
        """)
        devices = cursor.fetchall()
    
    for d in devices:
        print(f"   ID: {d['id']}")
        print(f"   名称: {d['name']}")
        print(f"   状态: {d['status']}")
        print(f"   借用人: {d['borrower']}")
        print(f"   借用人ID: {d['borrower_id']}")
        print(f"   预期归还: {d['expected_return_date']}")
        print(f"   借出时间: {d['borrow_time']}")
        print(f"   是否删除: {d['is_deleted']}")
        print()
        
        # 检查是否逾期
        if d['expected_return_date']:
            expected = d['expected_return_date']
            if isinstance(expected, str):
                expected = datetime.strptime(expected, '%Y-%m-%d %H:%M:%S')
            
            now = datetime.now()
            if expected < now:
                overdue_hours = int((now - expected).total_seconds() / 3600)
                print(f"   ⚠️ 已逾期 {overdue_hours} 小时")
            else:
                print(f"   ✓ 未逾期")
        print()
    
    # 2. 检查后台管理的逾期查询条件
    print("2. 后台管理的逾期查询条件检查:")
    print("   查询条件: status='借出' AND expected_return_date < NOW()")

    if devices:
        device = devices[0]
        cursor.execute("""
            SELECT
                name,
                expected_return_date,
                NOW() as now_time,
                CASE
                    WHEN expected_return_date < NOW() THEN '符合逾期条件'
                    ELSE '不符合逾期条件'
                END as is_overdue
            FROM devices
            WHERE id = %s
        """, (device['id'],))
        result = cursor.fetchone()
        if result:
            print(f"   设备: {result['name']}")
            print(f"   预期归还: {result['expected_return_date']}")
            print(f"   当前时间: {result['now_time']}")
            print(f"   结果: {result['is_overdue']}")
    print()

    # 3. 检查所有借出状态的设备
    print("3. 所有借出状态的设备:")
    cursor.execute("""
        SELECT
            name,
            expected_return_date,
            CASE
                WHEN expected_return_date < NOW() THEN '已逾期'
                ELSE '未逾期'
            END as status
        FROM devices
        WHERE status = '借出'
        AND is_deleted = 0
        ORDER BY expected_return_date
    """)
    all_borrowed = cursor.fetchall()
    for d in all_borrowed:
        print(f"   {d['name']}: {d['expected_return_date']} [{d['status']}]")

print()
print("=" * 70)
