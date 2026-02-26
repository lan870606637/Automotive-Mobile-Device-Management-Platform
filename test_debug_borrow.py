# -*- coding: utf-8 -*-
"""
调试借用设备时的 borrower_id
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_store import DatabaseStore
from common.models import DeviceStatus

def debug_borrow():
    """调试借用"""
    print("=" * 60)
    print("调试借用设备")
    print("=" * 60)
    
    db = DatabaseStore()
    
    # 1. 获取用户
    print("\n1. 获取用户...")
    users = db.get_all_users()
    print(f"   共有 {len(users)} 个用户")
    
    target_user = None
    for u in users:
        print(f"   - {u.borrower_name}: {u.id}")
        if u.borrower_name == "测试用户2":
            target_user = u
    
    if not target_user:
        print("   ✗ 未找到测试用户2")
        return
    
    print(f"   ✓ 找到用户: {target_user.borrower_name}, ID: {target_user.id}")
    
    # 2. 模拟 borrow_device 中的查找逻辑
    print("\n2. 模拟查找逻辑...")
    borrower_name = "测试用户2"
    borrower_id = ""
    
    print(f"   查找条件: borrower_name = '{borrower_name}'")
    for u in db.get_all_users():
        print(f"   检查用户: '{u.borrower_name}' == '{borrower_name}' ? {u.borrower_name == borrower_name}")
        if u.borrower_name == borrower_name:
            borrower_id = u.id
            print(f"   ✓ 找到ID: {borrower_id}")
            break
    
    if not borrower_id:
        print("   ✗ 未找到 borrower_id")
        return
    
    # 3. 获取设备并设置 borrower_id
    print("\n3. 获取设备...")
    devices = db.get_all_devices()
    target_device = None
    for d in devices:
        if d.status == DeviceStatus.IN_STOCK:
            target_device = d
            break
    
    if not target_device:
        print("   ✗ 没有可借用的设备")
        return
    
    print(f"   ✓ 找到设备: {target_device.name}")
    
    # 4. 设置借用信息
    print("\n4. 设置借用信息...")
    target_device.borrower = target_user.borrower_name
    target_device.borrower_id = target_user.id
    target_device.status = DeviceStatus.BORROWED
    
    print(f"   - borrower: {target_device.borrower}")
    print(f"   - borrower_id: {target_device.borrower_id}")
    print(f"   - status: {target_device.status}")
    
    # 5. 保存设备
    print("\n5. 保存设备...")
    db.save_device(target_device)
    print("   ✓ 设备已保存")
    
    # 6. 重新读取设备验证
    print("\n6. 重新读取设备验证...")
    device = db.get_device_by_id(target_device.id)
    print(f"   - borrower: {device.borrower}")
    print(f"   - borrower_id: {device.borrower_id}")
    
    if device.borrower_id:
        print("   ✓ borrower_id 保存成功！")
    else:
        print("   ✗ borrower_id 为空！")

if __name__ == "__main__":
    debug_borrow()
