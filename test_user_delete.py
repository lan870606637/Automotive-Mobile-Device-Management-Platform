# -*- coding: utf-8 -*-
"""
测试用户删除流程 - 验证名下有设备的用户是否能被删除
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_store import DatabaseStore
from common.api_client import APIClient
from common.models import DeviceStatus

def test_user_delete():
    """测试用户删除"""
    print("=" * 60)
    print("测试用户删除流程")
    print("=" * 60)
    
    db = DatabaseStore()
    api = APIClient()
    
    # 1. 创建一个测试用户
    print("\n1. 创建测试用户...")
    try:
        user = api.create_user(
            borrower_name="测试用户",
            email="test@example.com",
            password="123456",
            is_admin=False
        )
        print(f"   ✓ 用户创建成功")
        print(f"     - ID: {user.id}")
        print(f"     - 名称: {user.borrower_name}")
        print(f"     - 邮箱: {user.email}")
    except Exception as e:
        print(f"   ✗ 创建用户失败: {e}")
        return
    
    # 2. 获取一个可借用的设备
    print("\n2. 查找可借用设备...")
    devices = db.get_all_devices()
    available_device = None
    for device in devices:
        if device.status == DeviceStatus.IN_STOCK:
            available_device = device
            break
    
    if not available_device:
        print("   ✗ 没有可借用的设备")
        return
    
    print(f"   ✓ 找到设备: {available_device.name}")
    
    # 3. 借用设备
    print("\n3. 借用设备...")
    try:
        api.borrow_device(
            device_id=available_device.id,
            borrower=user.borrower_name,
            days=7,
            remarks="测试借用"
        )
        print(f"   ✓ 设备借用成功")
    except Exception as e:
        print(f"   ✗ 借用设备失败: {e}")
        return
    
    # 4. 验证设备借用信息
    print("\n4. 验证设备借用信息...")
    device = db.get_device_by_id(available_device.id)
    print(f"   - 设备状态: {device.status.value}")
    print(f"   - borrower (名称): {device.borrower}")
    print(f"   - borrower_id (ID): {device.borrower_id}")
    
    # 5. 检查用户借用设备列表
    print("\n5. 检查用户借用设备列表...")
    borrowed_devices = api.get_user_borrowed_devices_by_id(user.id)
    print(f"   - 找到 {len(borrowed_devices)} 个借用设备")
    for d in borrowed_devices:
        print(f"     - {d.name}")
    
    # 6. 尝试删除用户（应该失败）
    print("\n6. 尝试删除用户（应该失败）...")
    success, message = api.delete_user(user.id)
    if success:
        print(f"   ✗ 删除成功（不应该成功）: {message}")
    else:
        print(f"   ✓ 删除被阻止: {message}")
    
    # 7. 归还设备
    print("\n7. 归还设备...")
    try:
        api.return_device(device.id)
        print(f"   ✓ 设备归还成功")
    except Exception as e:
        print(f"   ✗ 归还设备失败: {e}")
    
    # 8. 再次尝试删除用户（应该成功）
    print("\n8. 再次尝试删除用户（应该成功）...")
    success, message = api.delete_user(user.id)
    if success:
        print(f"   ✓ 删除成功: {message}")
    else:
        print(f"   ✗ 删除失败: {message}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_user_delete()
