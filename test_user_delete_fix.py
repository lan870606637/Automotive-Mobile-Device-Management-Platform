# -*- coding: utf-8 -*-
"""
测试用户删除修复
验证删除用户时是否正确检查借用设备和保管设备
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import api_client
from common.models import DeviceStatus, Phone
from datetime import datetime

print("=" * 60)
print("测试用户删除修复")
print("=" * 60)

# 1. 获取所有用户
print("\n1. 获取所有用户...")
users = api_client.get_all_users()
active_users = [u for u in users if not u.is_deleted]
print(f"   共有 {len(active_users)} 个有效用户")

if not active_users:
    print("   没有有效用户，测试结束")
    sys.exit(0)

# 2. 获取所有设备
print("\n2. 获取所有设备...")
all_devices = api_client.get_all_devices()
print(f"   共有 {len(all_devices)} 个设备")

# 3. 检查每个用户的借用设备和保管设备
print("\n3. 检查每个用户的设备关联情况...")
for user in active_users:
    borrowed = api_client.get_user_borrowed_devices_by_id(user.id)
    custodian = api_client.get_user_custodian_devices_by_id(user.id)
    
    if borrowed or custodian:
        print(f"\n   用户: {user.borrower_name} (ID: {user.id[:8]}...)")
        if borrowed:
            print(f"   - 借用设备: {len(borrowed)} 个")
            for d in borrowed:
                print(f"     • {d.name} (borrower={d.borrower}, borrower_id={d.borrower_id[:8] if d.borrower_id else '空'})")
        if custodian:
            print(f"   - 保管设备: {len(custodian)} 个")
            for d in custodian:
                print(f"     • {d.name} (cabinet_number={d.cabinet_number}, custodian_id={d.custodian_id[:8] if d.custodian_id else '空'})")

# 4. 测试删除一个有设备的用户
print("\n4. 测试删除用户...")

# 找一个有借用设备的用户
test_user = None
for user in active_users:
    borrowed = api_client.get_user_borrowed_devices_by_id(user.id)
    if borrowed:
        test_user = user
        break

# 如果没有借用设备的用户，找有保管设备的用户
if not test_user:
    for user in active_users:
        custodian = api_client.get_user_custodian_devices_by_id(user.id)
        if custodian:
            test_user = user
            break

if test_user:
    print(f"\n   测试用户: {test_user.borrower_name}")
    
    borrowed = api_client.get_user_borrowed_devices_by_id(test_user.id)
    custodian = api_client.get_user_custodian_devices_by_id(test_user.id)
    
    print(f"   - 借用设备: {len(borrowed)} 个")
    print(f"   - 保管设备: {len(custodian)} 个")
    
    # 尝试删除
    print(f"\n   尝试删除用户...")
    success, message = api_client.delete_user(test_user.id)
    print(f"   结果: {'成功' if success else '失败'}")
    print(f"   消息: {message}")
    
    if not success and (borrowed or custodian):
        print("\n   ✓ 正确阻止了删除操作！")
    elif success and not borrowed and not custodian:
        print("\n   ✓ 用户没有设备，删除成功")
    else:
        print("\n   ✗ 删除逻辑可能有问题")
else:
    print("   没有找到有设备的用户")

# 5. 找一个没有设备的用户测试删除
print("\n5. 测试删除没有设备的用户...")
clean_user = None
for user in active_users:
    borrowed = api_client.get_user_borrowed_devices_by_id(user.id)
    custodian = api_client.get_user_custodian_devices_by_id(user.id)
    if not borrowed and not custodian:
        clean_user = user
        break

if clean_user:
    print(f"\n   测试用户: {clean_user.borrower_name}")
    print(f"   尝试删除用户...")
    success, message = api_client.delete_user(clean_user.id)
    print(f"   结果: {'成功' if success else '失败'}")
    print(f"   消息: {message}")
    
    if success:
        print("\n   ✓ 正确删除了没有设备的用户！")
    else:
        print("\n   ✗ 删除失败，可能有其他问题")
else:
    print("   没有找到没有设备的用户")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
