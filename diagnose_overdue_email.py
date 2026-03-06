# -*- coding: utf-8 -*-
"""
诊断逾期邮件发送问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def diagnose_overdue_email():
    """诊断逾期邮件发送问题"""
    print("=" * 60)
    print("逾期邮件发送诊断工具")
    print("=" * 60)
    print(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        from common.db_store import get_db_connection, DatabaseStore
        from common.models import DeviceStatus
        
        db = DatabaseStore()
        
        # 1. 检查逾期设备
        print("【1】检查逾期设备...")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    d.id,
                    d.name,
                    d.device_type,
                    d.borrower_id,
                    d.expected_return_date,
                    d.borrower,
                    d.status,
                    d.borrow_time,
                    u.borrower_name,
                    u.email
                FROM devices d
                LEFT JOIN users u ON d.borrower = u.borrower_name
                WHERE d.status = '借出'
                AND d.is_deleted = 0
                AND d.expected_return_date IS NOT NULL
                AND d.expected_return_date < NOW()
                ORDER BY d.expected_return_date
            """)
            overdue_devices = cursor.fetchall()
        
        if not overdue_devices:
            print("   ✗ 没有发现逾期设备")
            print("\n诊断结果: 没有逾期设备，无需发送邮件")
            return
        
        print(f"   ✓ 发现 {len(overdue_devices)} 个逾期设备")
        print()
        
        # 2. 检查每个逾期设备的情况
        print("【2】检查每个逾期设备的邮件发送条件...")
        print()
        
        for device in overdue_devices:
            print(f"   设备: {device['name']} (ID: {device['id']})")
            print(f"   - 借用人: {device['borrower_name']} (ID: {device['borrower_id']})")
            print(f"   - 邮箱: {device['email'] or '未设置'}")
            print(f"   - 预计归还: {device['expected_return_date']}")
            
            # 计算逾期时间
            expected_date = device['expected_return_date']
            if isinstance(expected_date, str):
                expected_date = datetime.strptime(expected_date, '%Y-%m-%d %H:%M:%S')
            
            overdue_duration = datetime.now() - expected_date
            overdue_hours = overdue_duration.total_seconds() / 3600
            overdue_days = overdue_duration.days
            
            print(f"   - 逾期时间: {overdue_days}天 {overdue_hours % 24:.1f}小时")
            
            # 检查借用时长
            borrow_time = device['borrow_time']
            if borrow_time:
                if isinstance(borrow_time, str):
                    borrow_time = datetime.strptime(borrow_time, '%Y-%m-%d %H:%M:%S')
                borrow_duration = expected_date - borrow_time
                borrow_duration_hours = borrow_duration.total_seconds() / 3600
                print(f"   - 借用时长: {borrow_duration_hours:.1f}小时")
            
            # 3. 检查邮件发送历史
            print()
            print("   【3】检查邮件发送历史...")
            
            if not device['borrower_id']:
                print("   ✗ 错误: 设备没有borrower_id")
                print()
                continue
            
            # 检查 overdue_daily 类型的邮件
            last_sent = db.get_last_email_sent_time(
                device['borrower_id'], 'overdue_daily', device['id']
            )
            
            if last_sent:
                print(f"   ✓ 已发送过逾期提醒邮件")
                print(f"   - 上次发送时间: {last_sent.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 检查今天是否已发送
                sent_today = db.has_email_sent_today(
                    device['borrower_id'], 'overdue_daily', device['id']
                )
                if sent_today:
                    print(f"   ✗ 今天已经发送过，不会重复发送")
                else:
                    # 检查是否是24小时整数倍
                    hours_mod = overdue_hours % 24
                    if hours_mod <= 0.5 or hours_mod >= 23.5:
                        print(f"   ✓ 满足24小时周期条件，应该发送邮件")
                    else:
                        print(f"   ✗ 不满足24小时周期条件 (余数: {hours_mod:.1f}小时)")
                        print(f"      将在 {(24 - hours_mod):.1f}小时后发送")
            else:
                print(f"   ✗ 从未发送过逾期提醒邮件")
                print(f"   ✓ 按照新逻辑，这是首次逾期，应该立即发送邮件")
                
                # 检查用户邮箱
                if not device['email']:
                    print(f"   ✗ 错误: 用户没有设置邮箱地址，无法发送邮件")
                else:
                    print(f"   ✓ 用户邮箱正常，可以发送邮件")
            
            print()
            print("-" * 50)
            print()
        
        # 4. 检查邮件配置
        print("【4】检查邮件配置...")
        from common.email_sender import SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
        
        print(f"   - SMTP服务器: {SMTP_SERVER}")
        print(f"   - SMTP端口: {SMTP_PORT}")
        print(f"   - 发件人: {SMTP_USERNAME}")
        print(f"   - 密码: {'已设置' if SMTP_PASSWORD else '未设置'}")
        
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            print("   ✗ 错误: 邮件配置不完整")
        else:
            print("   ✓ 邮件配置正常")
        
        print()
        print("=" * 60)
        print("诊断完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ 诊断过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    diagnose_overdue_email()
