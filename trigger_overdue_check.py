# -*- coding: utf-8 -*-
"""
手动触发逾期设备检查并发送邮件提醒
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def check_overdue_devices():
    """检查逾期设备并发送邮件"""
    print("=" * 60)
    print("手动触发逾期设备检查")
    print("=" * 60)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        from common.db_store import get_db_connection, DatabaseStore
        from common.email_sender import email_sender
        
        db = DatabaseStore()
        
        # 获取逾期设备（按用户分组）- 使用中文状态值'借出'
        # 只要过了预期归还时间就算逾期
        # 注意：使用 borrower（姓名）而不是 borrower_id 来关联用户
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
                    u.borrower_name,
                    u.email
                FROM devices d
                LEFT JOIN users u ON d.borrower = u.borrower_name
                WHERE d.status = '借出'
                AND d.is_deleted = 0
                AND d.expected_return_date IS NOT NULL
                AND d.expected_return_date < NOW()
                ORDER BY d.borrower, d.expected_return_date
            """)
            overdue_devices = cursor.fetchall()
        
        if not overdue_devices:
            print("✓ 没有发现逾期设备")
            return
        
        print(f"发现 {len(overdue_devices)} 个逾期设备")
        print()
        
        # 按用户分组
        user_devices = {}
        for device in overdue_devices:
            user_id = device['borrower_id']
            if user_id not in user_devices:
                user_devices[user_id] = {
                    'username': device['borrower_name'],
                    'email': device['email'],
                    'devices': []
                }
            
            # 计算逾期天数
            expected_date = device['expected_return_date']
            if isinstance(expected_date, str):
                expected_date = datetime.strptime(expected_date, '%Y-%m-%d %H:%M:%S')
            
            days_overdue = (datetime.now() - expected_date).days
            if days_overdue < 1:
                days_overdue = 1
            
            user_devices[user_id]['devices'].append({
                'name': device['name'],
                'device_type': device['device_type'],
                'days_overdue': days_overdue
            })
        
        # 发送邮件提醒
        sent_count = 0
        failed_count = 0
        
        for user_id, user_info in user_devices.items():
            print(f"正在处理用户: {user_info['username']} ({user_info['email']})")
            
            if not user_info['email']:
                print(f"  ✗ 用户没有邮箱地址，跳过")
                failed_count += 1
                continue
            
            try:
                # 使用 EmailSender 发送逾期提醒
                result = email_sender.send_overdue_reminder(
                    to_email=user_info['email'],
                    borrower_name=user_info['username'],
                    devices=user_info['devices'],
                    reminder_type='daily'
                )
                
                if result:
                    print(f"  ✓ 邮件发送成功")
                    sent_count += 1
                    
                    # 记录邮件日志
                    try:
                        for device in user_info['devices']:
                            db.save_email_log(
                                user_id=user_id,
                                user_email=user_info['email'],
                                email_type='overdue_reminder',
                                related_id=device['name'],
                                related_type='device',
                                status='sent'
                            )
                    except Exception as e:
                        print(f"  ⚠ 记录邮件日志失败: {e}")
                else:
                    print(f"  ✗ 邮件发送失败")
                    failed_count += 1
                    
            except Exception as e:
                print(f"  ✗ 发送邮件时出错: {e}")
                failed_count += 1
            
            print()
        
        print("=" * 60)
        print("处理结果:")
        print(f"  逾期设备总数: {len(overdue_devices)}")
        print(f"  涉及用户数: {len(user_devices)}")
        print(f"  邮件发送成功: {sent_count}")
        print(f"  邮件发送失败: {failed_count}")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ 检查逾期设备时发生错误: {e}")
        import traceback
        traceback.print_exc()


def test_email_send():
    """测试邮件发送功能"""
    print("=" * 60)
    print("测试邮件发送功能")
    print("=" * 60)
    print()
    
    try:
        from common.email_sender import email_sender
        
        # 测试邮箱（可以修改为你的邮箱）
        test_email = input("请输入测试邮箱地址 (直接回车使用默认邮箱): ").strip()
        
        if not test_email:
            # 从数据库获取第一个有邮箱的用户
            from common.db_store import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT email, borrower_name FROM users WHERE email IS NOT NULL AND email != '' LIMIT 1")
                user = cursor.fetchone()
                if user:
                    test_email = user['email']
                    print(f"使用数据库中的用户邮箱: {test_email} ({user['borrower_name']})")
                else:
                    print("✗ 数据库中没有找到有邮箱的用户")
                    return
        
        print(f"正在发送测试邮件到: {test_email}")
        print()
        
        result = email_sender.send_email(
            to_email=test_email,
            subject="【设备管理系统】邮件发送测试",
            html_content="""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #1890ff;">邮件发送测试</h2>
                    <p>这是一封测试邮件。</p>
                    <p>如果您收到此邮件，说明邮件发送功能正常工作。</p>
                    <p style="margin-top: 30px; color: #666; font-size: 12px;">
                        发送时间: {send_time}
                    </p>
                </div>
            </body>
            </html>
            """.format(send_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        
        if result:
            print("✓ 测试邮件发送成功！")
            print(f"  收件人: {test_email}")
        else:
            print("✗ 测试邮件发送失败")
            
    except Exception as e:
        print(f"✗ 发送测试邮件时出错: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print()
    print("=" * 60)
    print("逾期设备检查工具")
    print("=" * 60)
    print()
    print("请选择操作:")
    print("  1. 检查逾期设备并发送邮件提醒")
    print("  2. 测试邮件发送功能")
    print("  3. 退出")
    print()
    
    choice = input("请输入选项 (1/2/3): ").strip()
    
    if choice == '1':
        print()
        check_overdue_devices()
    elif choice == '2':
        print()
        test_email_send()
    elif choice == '3':
        print("退出程序")
        return
    else:
        print("无效的选项")
        return
    
    print()
    input("按 Enter 键退出...")


if __name__ == '__main__':
    main()
