# -*- coding: utf-8 -*-
"""
检查邮件发送日志
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from common.db_store import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM email_logs
        WHERE user_email = 'lan.shen@carbit.com.cn'
        ORDER BY sent_at DESC
        LIMIT 5
    ''')
    logs = cursor.fetchall()
    print('沈晋元的邮件发送记录:')
    for log in logs:
        print(f'  {log["sent_at"]} | {log["email_type"]} | {log["status"]} | 设备: {log["related_id"]}')
