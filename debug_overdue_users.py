# -*- coding: utf-8 -*-
"""
调试逾期设备用户分组问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def debug_overdue_devices():
    """调试逾期设备"""
    print("=" * 60)
    print("调试逾期设备用户分组")
    print("=" * 60)
    print()
    
    from common.db_store import get_db_connection
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 查询逾期设备（只要过了预期归还时间就算逾期）
        cursor.execute("""
            SELECT
                d.id,
                d.name,
                d.device_type,
                d.borrower_id,
                d.expected_return_date,
                d.borrower,
                u.borrower_name,
                u.email,
                u.id as user_table_id
            FROM devices d
            LEFT JOIN users u ON d.borrower = u.borrower_name
            WHERE d.status = '借出'
            AND d.is_deleted = 0
            AND d.expected_return_date IS NOT NULL
            AND d.expected_return_date < NOW()
            ORDER BY d.borrower, d.expected_return_date
        """)
        overdue_devices = cursor.fetchall()
        
        print(f"发现 {len(overdue_devices)} 个逾期设备:\n")
        
        for device in overdue_devices:
            print(f"设备: {device['name']}")
            print(f"  - d.borrower (设备表借用人): {device['borrower']}")
            print(f"  - d.borrower_id (设备表借用人ID): {device['borrower_id']}")
            print(f