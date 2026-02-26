# -*- coding: utf-8 -*-
"""
测试删除用户逻辑
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import APIClient
from common.db_store import DatabaseStore
from common.models import DeviceStatus

def test_delete_user():
    """测试删除用户"""
    print("=" * 60)
    print("测试删除用户逻辑")
    print("=" * 60)
    
    api = APIClient()
    db = DatabaseStore()
    
    # 1. 获取所有用户
    print("\n1. 获取所有用户...")
    users = db.get_all_users()
    print(f"   共有 {len(users)} 个用户")
    
    # 2. 获取所有借出设备
    print("\n2. 获取所有借出设备...")
    devices = db.get_all_devices()
    borrowed_devices = [d for d in devices if d.status == DeviceStatus.BORROWED]
    print(f"   共有 {len(borrowed_devices)} 个借出设备:")
    for d in borrowed_devices:
        print(f"     - {d.name}: borrower={d.borrower}, borrower_id={d.borrower_id[:8] if d.borrower_id else '(空)'}")
    
    # 3. 检查每个有借用设备的用户
    print("\n3. 检查有借用设备的用户...")
    for device in borrowed_devices:
        if device.borrower_id:
            user = db.get_user_by_id(device.borrower_id)
            if user:
                print(f"\n   设备: {device.name}")
                print(f"   借用人: {user.borrower_name} (ID: {user.id[:8]}...)")
                
                # 尝试删除该用户
                print(f"   尝试删除用户...")
                success, message = api.delete_user(user.id)
                print(f"   结果: success={success}, message={message}")
            else:
                print(f"   ✗ 未找到用户: {device.borrower_id}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_delete_user()
