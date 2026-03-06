# -*- coding: utf-8 -*-
"""
检查沈晋元的用户记录
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

def main():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 查找沈晋元的所有用户记录
        print("=" * 60)
        print("查找沈晋元的用户记录")
        print("=" * 60)
        
        cursor.execute("""
            SELECT id, borrower_name, email
            FROM users 
            WHERE borrower_name LIKE '%沈晋元%'
        """)
        users = cursor.fetchall()
        print(f"\n找到 {len(users)} 个用户记录 (按姓名搜索 '沈晋元'):")
        for u in users:
            print(f"  ID: {u['id']}")
            print(f"  姓名: {u['borrower_name']}")
            print(f"  邮箱: {u['email']}")
            print()
        
        # 查找邮箱包含 lan 的用户
        cursor.execute("""
            SELECT id, borrower_name, email
            FROM users 
            WHERE email LIKE '%lan%'
        """)
        users = cursor.fetchall()
        print(f"\n找到 {len(users)} 个用户记录 (按邮箱搜索包含 'lan'):")
        for u in users:
            print(f"  ID: {u['id']}")
            print(f"  姓名: {u['borrower_name']}")
            print(f"  邮箱: {u['email']}")
            print()
        
        # 查看沈晋元借用的设备
        print("=" * 60)
        print("沈晋元借用的设备")
        print("=" * 60)
        
        cursor.execute("""
            SELECT 
                d.id,
                d.name,
                d.borrower,
                d.borrower_id,
                d.expected_return_date,
                d.status,
                u.borrower_name as user_name,
                u.email as user_email
            FROM devices d
            LEFT JOIN users u ON d.borrower = u.borrower_name
            WHERE d.borrower LIKE '%沈晋元%'
            AND d.status = '借出'
        """)
        devices = cursor.fetchall()
        
        print(f"\n找到 {len(devices)} 个借出设备:")
        for d in devices:
            print(f"  设备: {d['name']}")
            print(f"  设备表borrower: {d['borrower']}")
            print(f"  设备表borrower_id: {d['borrower_id']}")
            print(f"  关联用户姓名: {d['user_name']}")
            print(f"  关联用户邮箱: {d['user_email']}")
            print()

if __name__ == '__main__':
    main()
