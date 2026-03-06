# -*- coding: utf-8 -*-
"""
诊断特定设备的逾期邮件发送情况
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

from common.db_store import DatabaseStore, get_db_connection

device_id = '0086a800-ffa7-4a29-a643-54bf52eba70c'
device_name = 'realme X2 IMEI：867092048374671'

print("=" * 70)
print(f"诊断设备: {device_name}")
print(f"设备ID: {device_id}")
print("=" * 70)
print()

db = DatabaseStore()

# 1. 获取设备信息
print("1. 设备基本信息:")
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.*, u.id as user_id, u.email, u.borrower_name
        FROM devices d
        LEFT JOIN users u ON d.borrower_id = u.id
        WHERE d.id = %s
    """, (device_id,))
    device = cursor.fetchone()
    
    if not device:
        print("   ✗ 设备不存在!")
        sys.exit(1)
    
    print(f"   设备名称: {device['name']}")
    print(f"   状态: {device['status']}")
    print(f"   借用人: {device['borrower']}")
    print(f"   借用人ID: {device['borrower_id']}")
    print(f"   预期归还时间: {device['expected_return_date']}")
    print(f"   借出时间: {device['borrow_time']}")
    print()
    
    user_id = device['user_id']
    user_email = device['email']
    borrower_name = device['borrower_name']
    expected_return = device['expected_return_date']
    
    if not expected_return:
        print("   ✗ 设备没有预期归还时间，不会发送逾期提醒")
        sys.exit(1)
    
    if device['status'] != '借出':
        print(f"   ✗ 设备状态不是'借出'（当前是'{device['status']}'），不会发送逾期提醒")
        sys.exit(1)

# 2. 计算逾期信息
now = datetime.now()
print("2. 逾期计算:")
print(f"   当前时间: {now}")
print(f"   预期归还: {expected_return}")

if now <= expected_return:
    print("   ✗ 设备尚未逾期")
    sys.exit(1)

overdue_duration = now - expected_return
overdue_hours = overdue_duration.total_seconds() / 3600
overdue_days = overdue_duration.days
print(f"   已逾期: {overdue_hours:.1f} 小时 ({overdue_days} 天)")
print()

# 3. 检查用户邮箱
print("3. 用户邮箱检查:")
print(f"   用户ID: {user_id}")
print(f"   借用人: {borrower_name}")
print(f"   邮箱: {user_email}")
if not user_email:
    print("   ✗ 用户没有邮箱，无法发送邮件提醒")
else:
    print("   ✓ 用户有邮箱，可以发送邮件")
print()

# 4. 检查邮件发送历史
print("4. 邮件发送历史检查:")
last_sent = db.get_last_email_sent_time(user_id, 'overdue_daily', device_id)
if last_sent:
    print(f"   上次发送时间: {last_sent}")
    hours_since_last = (now - last_sent).total_seconds() / 3600
    print(f"   距离上次发送: {hours_since_last:.1f} 小时")
    
    sent_today = db.has_email_sent_today(user_id, 'overdue_daily', device_id)
    print(f"   今天是否已发送: {'是' if sent_today else '否'}")
else:
    print("   从未发送过逾期提醒邮件")
print()

# 5. 检查发送条件
print("5. 发送条件检查:")

# 计算借用时长
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT borrow_time FROM devices WHERE id = %s", (device_id,))
    result = cursor.fetchone()
    borrow_time = result['borrow_time']

if borrow_time:
    borrow_duration = expected_return - borrow_time
    borrow_duration_hours = borrow_duration.total_seconds() / 3600
else:
    borrow_duration_hours = 24

print(f"   借用时长: {borrow_duration_hours:.1f} 小时")

# 计算距离逾期的时间差（负数表示已逾期）
time_until_overdue = expected_return - now
minutes_until_overdue = time_until_overdue.total_seconds() / 60

print(f"   距离逾期: {minutes_until_overdue:.1f} 分钟 (负数表示已逾期)")
print()

# 6. 判断是否应该发送
print("6. 发送判断逻辑:")
should_send = False
reason = ""

if overdue_hours > 0:
    # 逾期后提醒
    print("   设备已逾期，进入逾期后提醒逻辑")
    
    if not last_sent:
        should_send = True
        reason = "首次逾期，应该立即发送"
        print("   ✓ 首次逾期，应该发送邮件")
    else:
        print(f"   非首次逾期，检查24小时周期条件")
        hours_mod = overdue_hours % 24
        print(f"   逾期小时数 % 24 = {hours_mod:.1f} 小时")
        
        if hours_mod <= 0.5 or hours_mod >= 23.5:
            print(f"   ✓ 满足24小时周期条件 (在边界范围内)")
            sent_today = db.has_email_sent_today(user_id, 'overdue_daily', device_id)
            if not sent_today:
                should_send = True
                reason = "满足24小时周期且今天未发送"
                print(f"   ✓ 今天未发送过，应该发送邮件")
            else:
                print(f"   ✗ 今天已经发送过，不再发送")
        else:
            print(f"   ✗ 不满足24小时周期条件")
            print(f"      将在 {24 - hours_mod:.1f} 小时后发送")
else:
    # 逾期前提醒
    print("   设备尚未逾期，检查逾期前提醒条件")
    
    if borrow_duration_hours < 1:
        # 借用时间小于1小时，只在逾期前10分钟发送
        if 5 <= minutes_until_overdue <= 10:
            sent_within_hours = db.has_email_sent_within_hours(user_id, 'overdue_10min', 1, device_id)
            if not sent_within_hours:
                should_send = True
                reason = "借用时间<1小时，逾期前10分钟提醒"
                print("   ✓ 满足10分钟提醒条件")
            else:
                print("   ✗ 1小时内已发送过10分钟提醒")
        else:
            print(f"   ✗ 不在10分钟提醒窗口内 (当前距离逾期 {minutes_until_overdue:.1f} 分钟)")
    else:
        # 借用时间大于等于1小时
        # 逾期前1小时提醒
        if 55 <= minutes_until_overdue <= 60:
            sent_within_hours = db.has_email_sent_within_hours(user_id, 'overdue_1hour', 2, device_id)
            if not sent_within_hours:
                should_send = True
                reason = "逾期前1小时提醒"
                print("   ✓ 满足1小时提醒条件")
            else:
                print("   ✗ 2小时内已发送过1小时提醒")
        # 逾期前10分钟提醒
        elif 5 <= minutes_until_overdue <= 10:
            sent_within_hours = db.has_email_sent_within_hours(user_id, 'overdue_10min', 1, device_id)
            if not sent_within_hours:
                should_send = True
                reason = "逾期前10分钟提醒"
                print("   ✓ 满足10分钟提醒条件")
            else:
                print("   ✗ 1小时内已发送过10分钟提醒")
        else:
            print(f"   ✗ 不在任何提醒窗口内")

print()
print("=" * 70)
if should_send:
    print(f"结论: ✓ 应该发送邮件")
    print(f"原因: {reason}")
else:
    print(f"结论: ✗ 不应该发送邮件")
print("=" * 70)
