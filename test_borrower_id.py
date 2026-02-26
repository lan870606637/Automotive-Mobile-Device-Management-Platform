# -*- coding: utf-8 -*-
"""
测试 borrower_id 是否正确保存
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_store import DatabaseStore
from common.models import DeviceStatus

def test_borrower_id():
    db = DatabaseStore()
    
    # 获取所有设备
    devices = db.get_all_devices()
    
    print("=" * 60)
    print("检查设备 borrower_id 字段")
    print("=" * 60)
    
    borrowed_devices = []
    for device in devices:
        if device.status == DeviceStatus.BORROWED:
            borrowed_devices.append(device)
            print(f"\n设备: {device.name}")
            print(f"  状态: {device.status.value}")
            print(f"  borrower (名称): {device.borrower}")
            print(f"  borrower_id (ID): {device.borrower_id}")
    
    print("\n" + "=" * 60)
    print(f"总计: {len(borrowed_devices)} 个借出设备")
    print("=" * 60)
    
    # 检查用户
    print("\n" + "=" * 60)
    print("用户列表")
    print("=" * 60)
    users = db.get_all_users()
    for user in users:
        print(f"\n用户: {user.borrower_name}")
        print(f"  ID: {user.id}")
        print(f"  邮箱: {user.email}")

if __name__ == "__main__":
    test_borrower_id()
