# -*- coding: utf-8 -*-
"""
立即测试发送逾期邮件
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("立即测试发送逾期邮件")
print("=" * 70)
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 导入必要的模块
from common.api_client import APIClient
from common.db_store import DatabaseStore
from common.models import DeviceStatus

# 创建 APIClient 实例
print("初始化 APIClient...")
api_client = APIClient()
print("✓ APIClient 初始化完成")
print()

# 直接调用发送逾期邮件的方法
print("调用 send_overdue_email_reminders()...")
print("-" * 70)
try:
    api_client.send_overdue_email_reminders()
    print("-" * 70)
    print("✓ 方法执行完成")
except Exception as e:
    print("-" * 70)
    print(f"✗ 执行失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("检查邮件发送日志...")
print("=" * 70)

# 检查最近发送的邮件
from common.db_store import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM email_logs
        WHERE email_type = 'overdue_daily'
        ORDER BY sent_at DESC
        LIMIT 5
    """)
    logs = cursor.fetchall()
    
    if logs:
        print(f"最近 {len(logs)} 条逾期邮件发送记录:")
        for log in logs:
            print(f"   时间: {log['sent_at']} | 用户: {log['user_email']} | 状态: {log['status']} | 设备: {log['related_id']}")
    else:
        print("   没有逾期邮件发送记录")

print()
print("=" * 70)
