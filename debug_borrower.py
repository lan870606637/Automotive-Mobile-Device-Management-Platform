# -*- coding: utf-8 -*-
"""
调试借用人ID问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

print("=" * 70)
print("调试借用人ID问题")
print("=" * 70)
print()

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # 1. 检查逾期设备的借用人信息（只要过了预期归还时间就算逾期）
    print("1. 逾期设备的借用人信息:")
    cursor.execute("""
        SELECT
            d.id,
            d.name,
            d.borrower,
            d.borrower_id,
            d.expected_return_date
        FROM devices d
        WHERE d.status = '借出'
        AND d.is_deleted = 0
        AND d.expected_return_date IS NOT NULL
        AND d.expected_return_date < NOW()
        ORDER BY d.expected_return_date
    """)
    devices = cursor.fetchall()
    
    print(f"   找到 {len(devices)} 个逾期设备")
    for d in devices:
        print(f"   设备: {d['name']}")
        print(f"      borrower: {d['borrower']}")
        print(f"      borrower_id: {d['borrower_id']}")
        print(f"      expected_return_date: {d['expected_return_date']}")
        print()
    
    # 2. 检查JOIN查询的结果（只要过了预期归还时间就算逾期）
    print("2. JOIN查询的结果:")
    cursor.execute("""
        SELECT
            d.id,
            d.name,
            d.borrower,
            d.borrower_id,
            u.id as user_id,
            u.borrower_name,
            u.email
        FROM devices d
        LEFT JOIN users u ON d.borrower_id = u.id
        WHERE d.status = '借出'
        AND d.is_deleted = 0
        AND d.expected_return_date IS NOT NULL
        AND d.expected_return_date < NOW()
        ORDER BY d.expected_return_date
    """)
    results = cursor.fetchall()
    
    print(f"   JOIN结果数量: {len(results)}")
    for r in results:
        print(f"   设备: {r['name']}")
        print(f"      d.borrower_id: {r['borrower_id']}")
        print(f"      u.id: {r['user_id']}")
        print(f"      u.email: {r['email']}")
        print()

print("=" * 70)
