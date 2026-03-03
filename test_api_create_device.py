# -*- coding: utf-8 -*-
"""
测试通过 API 创建设备
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入 admin_service app
from admin_service.app import app

with app.test_client() as client:
    # 先登录
    login_data = {
        'username': 'admin',
        'password': 'admin123'
    }
    response = client.post('/api/admin/login', json=login_data)
    print(f"登录响应: {response.status_code}")
    login_result = response.get_json()
    print(f"登录数据: {login_result}")
    
    if login_result and login_result.get('success'):
        # 创建设备
        device_data = {
            'device_type': '手机',
            'device_name': '测试手机设备2',
            'model': 'iPhone 15 Pro',
            'cabinet': '',
            'status': '在库',
            'remarks': '测试备注',
            'asset_number': '',
            'purchase_amount': 0,
            'sn': 'SN789012',
            'imei': 'IMEI789012',
            'system_version': 'iOS 17.1',
            'carrier': '中国联通'
        }
        
        response = client.post('/api/devices', json=device_data)
        print(f"\n创建设备响应: {response.status_code}")
        print(f"响应数据: {response.get_json()}")
    else:
        print("登录失败，无法测试创建设备")
