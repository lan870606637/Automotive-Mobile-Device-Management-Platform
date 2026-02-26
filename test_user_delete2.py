# -*- coding: utf-8 -*-
"""
测试用户删除流程 - 调试版本
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
    print("测试用户删除流程 - 调试版本")
    print("=" * 60)
    
    db = DatabaseStore()
    api = APIClient()
    
    print(f"\n数据库实例 ID: {id(db)}")
    print(f"APIClient._db ID: {id(api._db)}")
    
    # 1. 创建一个测试用户
    print("\n1. 创建测试用户...")
    try:
        user = api.create_user(
            borrower_name="测试用户2",
            email="test2@example.com",
            password="123456",
            is_admin=False
        )
        print(f"   ✓ 用户创建成功")
        print(f"     - ID: {user.id}")
        print(f"     - 名称: {user.borrower_name}")
    except Exception as e:
        print(f"   ✗ 创建用户失败: {e}")
        return
    
    # 2. 验证用户是否能在数据库中找到
    print("\n2. 验证用户是否能在数据库中找到...")
    all_users = db.get_all_users()
    print(f"   - 数据库中共有 {len(all_users)} 个用户")
    found_user = None
    for u in all_users:
        if u.borrower_name == "测试用户2":
            found_user = u
            print(f"   ✓ 找到用户: {u.borrower_name}, ID: {u.id}")
            break
    
    if not found_user:
        print("   ✗ 未找到用户！")
        return
    
    # 3. 获取一个可借用的设备
    print("\n3. 查找可借用设备...")
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
    
    # 4. 直接测试 borrow_device 中的用户查找逻辑
    print("\n4. 测试用户查找逻辑...")
    borrower_name = "测试用户2"
    borrower_id = ""
    for u in db.get_all_users():
        if u.borrower_name == borrower_name:
            borrower_id = u.id
            print(f"   ✓ 找到用户ID: {borrower_id}")
            break
    
    if not borrower_id:
        print("   ✗ 未找到用户ID！")
        return
    
    # 5. 借用设备
    print("\n5. 借用设备...")
    try:
        api.borrow_device(
            device_id=available_device.id,
            borrower=found_user.borrower_name,  # 使用用户名称
            days=7,
            remarks="测试借用"
        )
        print(f"   ✓ 设备借用成功")
    except Exception as e:
        print(f"   ✗ 借用设备失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 6. 验证设备借用信息
    print("\n6. 验证设备借用信息...")
    device = db.get_device_by_id(available_device.id)
    print(f"   - 设备状态: {device.status.value}")
    print(f"   - borrower (名称): {device.borrower}")
    print(f"   - borrower_id (ID): {device.borrower_id}")
    
    if not device.borrower_id:
        print("   ✗ borrower_id 为空！")
    else:
        print(f"   ✓ borrower_id 正确: {device.borrower_id}")
    
    # 7. 检查用户借用设备列表
    print("\n7. 检查用户借用设备列表...")
    borrowed_devices = api.get_user_borrowed_devices_by_id(found_user.id)
    print(f"   - 找到 {len(borrowed_devices)} 个借用设备")
    
    # 8. 尝试删除用户
    print("\n8. 尝试删除用户...")
    success, message = api.delete_user(found_user.id)
    if success:
        print(f"   ✗ 删除成功（不应该成功）: {message}")
    else:
        print(f"   ✓ 删除被阻止: {message}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_user_delete()
