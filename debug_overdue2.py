# -*- coding: utf-8 -*-
"""
调试逾期设备查询问题 - 对比不同查询条件
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

print("=" * 70)
print("调试逾期设备查询 - 对比不同查询条件")
print("=" * 70)
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # 1. 查看所有借用中的设备（不管有没有预期归还时间）
    print("1. 所有借用中的设备:")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM devices 
        WHERE status = 'BORROWED' AND is_deleted = 0
    """)
    result = cursor.fetchone()
    print(f"   总数: {result['count']}")
    print()
    
    # 2. 借用中且有预期归还时间的设备
    print("2. 借用中且有预期归还时间的设备:")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM devices 
        WHERE status = 'BORROWED' 
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
    """)
    result = cursor.fetchone()
    print(f"   总数: {result['count']}")
    print()
    
    # 3. 我的脚本查询条件: expected_return_date < NOW()
    print("3. 脚本查询条件 (expected_return_date < NOW()):")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM devices 
        WHERE status = 'BORROWED' 
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
        AND expected_return_date < NOW()
    """)
    result = cursor.fetchone()
    print(f"   逾期数量: {result['count']}")
    print()
    
    # 4. 后台管理查询条件: expected_return_date < NOW()
    print("4. 后台管理查询条件 (expected_return_date < NOW()):")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM devices
        WHERE status = 'BORROWED'
        AND is_deleted = 0
        AND expected_return_date IS NOT NULL
        AND expected_return_date < NOW()
    """)
    result = cursor.fetchone()
    print(f"   逾期数量: {result['count']}")
    print()
    
    # 5. 查看具体的借用中设备详情
    print("5. 借用中设备的预期归还时间详情:")
    cursor.execute("""
        SELECT
            id,
            name,
            borrower,
            expected_return_date,
            status,
            NOW() as now_time,
            CASE
                WHEN expected_return_date IS NULL THEN '无预期归还时间'
                WHEN expected_return_date < NOW() THEN '已逾期'
                ELSE '未逾期'
            END as overdue_status
        FROM devices
        WHERE status = 'BORROWED'
        AND is_deleted = 0
        ORDER BY expected_return_date
        LIMIT 20
    """)
    devices = cursor.fetchall()
    if devices:
        for d in devices:
            print(f"   {d['name']} | 借用人:{d['borrower']} | 应还:{d['expected_return_date']} | 状态:{d['overdue_status']}")
    else:
        print("   没有借用中的设备")
    print()
    
    # 6. 检查数据库当前时间
    print("6. 数据库时间检查:")
    cursor.execute("SELECT NOW() as db_time, @@time_zone as timezone")
    result = cursor.fetchone()
    print(f"   数据库当前时间: {result['db_time']}")
    print(f"   数据库时区: {result['timezone']}")
    print(f"   Python当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

print()
print("=" * 70)
print("结论:")
print("  - 后台管理和脚本都使用: expected_return_date < NOW()")
print("  - 只要过了预期归还时间就算逾期")
print("=" * 70)
