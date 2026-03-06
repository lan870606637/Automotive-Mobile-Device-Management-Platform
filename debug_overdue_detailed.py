# -*- coding: utf-8 -*-
"""
详细调试逾期邮件发送逻辑
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("详细调试逾期邮件发送逻辑")
print("=" * 70)
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

from common.api_client import APIClient
from common.models import DeviceStatus

# 创建 APIClient 实例
api_client = APIClient()
print("✓ APIClient 初始化完成")
print()

# 获取所有设备
print("获取所有设备...")
all_devices = api_client.get_all_devices()
print(f"✓ 共获取 {len(all_devices)} 个设备")
print()

now = datetime.now()
target_device_id = '0086a800-ffa7-4a29-a643-54bf52eba70c'

print("=" * 70)
print("逐个检查设备:")
print("=" * 70)

for device in all_devices:
    # 只检查目标设备
    if device.id != target_device_id:
        continue
    
    print(f"\n设备: {device.name}")
    print(f"  ID: {device.id}")
    print(f"  状态: {device.status}")
    print(f"  状态类型: {type(device.status)}")
    print(f"  状态值: {device.status.value if hasattr(device.status, 'value') else device.status}")
    print(f"  借用人ID: {device.borrower_id}")
    print(f"  预期归还: {device.expected_return_date}")
    print(f"  借出时间: {device.borrow_time}")
    
    # 检查条件1: 状态是 BORROWED
    is_borrowed = device.status == DeviceStatus.BORROWED
    print(f"\n  条件检查:")
    print(f"    1. status == DeviceStatus.BORROWED: {is_borrowed}")
    
    # 检查条件2: 有预期归还时间
    has_return_date = device.expected_return_date is not None
    print(f"    2. expected_return_date is not None: {has_return_date}")
    
    # 检查条件3: 有借用人ID
    has_borrower_id = device.borrower_id is not None and device.borrower_id != ''
    print(f"    3. borrower_id: {has_borrower_id} (值: '{device.borrower_id}')")
    
    if not (is_borrowed and has_return_date and has_borrower_id):
        print(f"\n  ✗ 基本条件不满足，跳过")
        continue
    
    # 获取用户信息
    user = api_client._db.get_user_by_id(device.borrower_id)
    print(f"\n  用户信息:")
    if user:
        print(f"    用户ID: {user.id}")
        print(f"    姓名: {user.borrower_name}")
        print(f"    邮箱: {user.email}")
    else:
        print(f"    ✗ 用户不存在!")
        continue
    
    if not user.email:
        print(f"    ✗ 用户没有邮箱，跳过")
        continue
    
    # 计算借用时长
    if device.borrow_time:
        borrow_duration = device.expected_return_date - device.borrow_time
        borrow_duration_hours = borrow_duration.total_seconds() / 3600
    else:
        borrow_duration_hours = 24
    
    print(f"\n  借用时长: {borrow_duration_hours:.2f} 小时")
    
    # 计算距离逾期的时间差
    time_until_overdue = device.expected_return_date - now
    minutes_until_overdue = time_until_overdue.total_seconds() / 60
    
    # 计算已逾期的时间
    if now > device.expected_return_date:
        overdue_duration = now - device.expected_return_date
        overdue_hours = overdue_duration.total_seconds() / 3600
    else:
        overdue_hours = 0
    
    print(f"  距离逾期: {minutes_until_overdue:.1f} 分钟 (负数表示已逾期)")
    print(f"  已逾期: {overdue_hours:.2f} 小时")
    
    # 判断发送逻辑
    print(f"\n  发送逻辑判断:")
    should_send = False
    email_type = None
    
    if borrow_duration_hours < 1:
        print(f"    借用时长 < 1小时，检查10分钟提醒窗口")
        if 5 <= minutes_until_overdue <= 10:
            print(f"    ✓ 在10分钟窗口内")
            # 检查是否已发送
            if not api_client._db.has_email_sent_within_hours(user.id, 'overdue_10min', 1, device.id):
                should_send = True
                email_type = 'overdue_10min'
                print(f"    ✓ 1小时内未发送过，应该发送")
            else:
                print(f"    ✗ 1小时内已发送过")
        else:
            print(f"    ✗ 不在10分钟窗口内")
    else:
        print(f"    借用时长 >= 1小时")
        
        # 逾期前1小时提醒
        if 55 <= minutes_until_overdue <= 60:
            print(f"    在1小时提醒窗口内 (55-60分钟)")
            if not api_client._db.has_email_sent_within_hours(user.id, 'overdue_1hour', 2, device.id):
                should_send = True
                email_type = 'overdue_1hour'
                print(f"    ✓ 2小时内未发送过，应该发送")
            else:
                print(f"    ✗ 2小时内已发送过")
        
        # 逾期前10分钟提醒
        elif 5 <= minutes_until_overdue <= 10:
            print(f"    在10分钟提醒窗口内 (5-10分钟)")
            if not api_client._db.has_email_sent_within_hours(user.id, 'overdue_10min', 1, device.id):
                should_send = True
                email_type = 'overdue_10min'
                print(f"    ✓ 1小时内未发送过，应该发送")
            else:
                print(f"    ✗ 1小时内已发送过")
        
        # 逾期后提醒
        elif overdue_hours > 0:
            print(f"    设备已逾期，进入逾期后提醒逻辑")
            last_sent = api_client._db.get_last_email_sent_time(user.id, 'overdue_daily', device.id)
            
            if not last_sent:
                should_send = True
                email_type = 'overdue_daily'
                print(f"    ✓ 首次逾期，应该立即发送")
            else:
                print(f"    非首次逾期，上次发送: {last_sent}")
                hours_mod = overdue_hours % 24
                print(f"    逾期小时数 % 24 = {hours_mod:.2f}")
                
                if hours_mod <= 0.5 or hours_mod >= 23.5:
                    print(f"    ✓ 满足24小时周期条件")
                    if not api_client._db.has_email_sent_today(user.id, 'overdue_daily', device.id):
                        should_send = True
                        email_type = 'overdue_daily'
                        print(f"    ✓ 今天未发送过，应该发送")
                    else:
                        print(f"    ✗ 今天已发送过")
                else:
                    print(f"    ✗ 不满足24小时周期条件，将在 {24-hours_mod:.1f} 小时后发送")
        else:
            print(f"    不在任何提醒窗口内")
    
    print(f"\n  最终判断: {'✓ 应该发送' if should_send else '✗ 不发送'}")
    if email_type:
        print(f"  邮件类型: {email_type}")

print("\n" + "=" * 70)
print("检查完成")
print("=" * 70)
