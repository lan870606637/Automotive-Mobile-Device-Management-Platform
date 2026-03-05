# -*- coding: utf-8 -*-
"""
检查邮件配置状态
"""
import os

def check_email_config():
    """检查邮件配置"""
    print("=" * 60)
    print("邮件配置检查")
    print("=" * 60)
    print()
    
    configs = {
        'SMTP_SERVER': os.getenv('SMTP_SERVER', 'smtp.company.com'),
        'SMTP_PORT': os.getenv('SMTP_PORT', '587'),
        'SMTP_USERNAME': os.getenv('SMTP_USERNAME', ''),
        'SMTP_PASSWORD': '已设置' if os.getenv('SMTP_PASSWORD') else '未设置',
        'SMTP_FROM_NAME': os.getenv('SMTP_FROM_NAME', '设备管理系统'),
        'SMTP_FROM_EMAIL': os.getenv('SMTP_FROM_EMAIL', 'noreply@company.com'),
    }
    
    is_configured = True
    
    for key, value in configs.items():
        if key == 'SMTP_PASSWORD':
            status = '✓' if value == '已设置' else '✗'
            if value == '未设置':
                is_configured = False
        elif key in ['SMTP_USERNAME'] and not value:
            status = '✗'
            is_configured = False
        else:
            status = '✓'
        print(f"[{status}] {key}: {value}")
