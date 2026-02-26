# -*- coding: utf-8 -*-
"""
修复用户数据
1. 为保管设备设置 custodian_id
2. 清理有问题的测试数据
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import api_client
from common.models import DeviceStatus
from common.db_store import DatabaseStore

print("=" * 70)
print("修复用户数据")
print("=" * 70)

# 获取所有数据
users = api_client.get_all_users()
all_devices = api_client.get_all_devices()
active_users = [u for u in users if not u.is_deleted]

user_name_map = {u.borrower_name: u for u in users if u.borrower_name}
user_id_map = {u.id: u for u in users}

db = DatabaseStore()

# ==================== 修复1: 设置 custodian_id ====================
print("\n【修复1】为保管设备设置 custodian_id")
print("-" * 70)

custody_device_types = ['手机', '手机卡', '其它设备']
fixed_custodian_count = 0

for device in all_devices:
    if device.device_type.value not in custody_device_types:
        continue
    
    # 如果有 cabinet_number 但没有 custodian_id
    if device.cabinet_number and not device.custodian_id:
        user = user_name_map.get(device.cabinet_number)
        if user:
            print(f"   修复: {device.name} -> custodian_id = {user.borrower_name}")
            device.custodian_id = user.id
            db.save_device(device)
            fixed_custodian_count += 1

print(f"   共修复 {fixed_custodian_count} 个设备的 custodian_id")

# ==================== 修复2: 设置 borrower_id（借出设备）====================
print("\n【修复2】为借出设备设置 borrower_id")
print("-" * 70)

fixed_borrower_count = 0

for device in all_devices:
    if device.status == DeviceStatus.BORROWED:
        # 如果有 borrower 名称但没有 borrower_id
        if device.borrower and not device.borrower_id:
            user = user_name_map.get(device.borrower)
            if user:
                print(f"   修复: {device.name} -> borrower_id = {user.borrower_name}")
                device.borrower_id = user.id
                db.save_device(device)
                fixed_borrower_count += 1

print(f"   共修复 {fixed_borrower_count} 个借出设备的 borrower_id")

# ==================== 修复3: 清理无效数据 ====================
print("\n【修复3】清理无效数据")
print("-" * 70)

cleaned_count = 0

for device in all_devices:
    needs_save = False
    
    # 清理无效的 borrower_id（指向不存在的用户）
    if device.borrower_id and device.borrower_id not in user_id_map:
        print(f"   清理: {device.name} 的无效 borrower_id")
        device.borrower_id = ""
        needs_save = True
    
    # 清理无效的 custodian_id（指向不存在的用户）
    if device.custodian_id and device.custodian_id not in user_id_map:
        print(f"   清理: {device.name} 的无效 custodian_id")
        device.custodian_id = ""
        needs_save = True
    
    # 如果设备状态不是借出，但还有借用信息，清理它
    if device.status != DeviceStatus.BORROWED:
        if device.borrower or device.borrower_id:
            print(f"   清理: {device.name} 的非借出状态借用信息")
            device.borrower = ""
            device.borrower_id = ""
            device.borrow_time = None
            device.expected_return_date = None
            needs_save = True
    
    if needs_save:
        db.save_device(device)
        cleaned_count += 1

print(f"   共清理 {cleaned_count} 个设备的无效数据")

# ==================== 修复4: 处理异常 cabinet_number ====================
print("\n【修复4】处理异常的 cabinet_number")
print("-" * 70)

# 定义有效的柜号模式（数字、带-的柜号、流通、封存）
valid_cabinet_patterns = ['流通', '封存', '无柜号']

cabinet_fixed_count = 0

for device in all_devices:
    if device.device_type.value not in custody_device_types:
        continue
    
    cabinet = device.cabinet_number
    if not cabinet:
        continue
    
    # 检查是否是有效柜号格式
    is_valid = False
    
    # 检查是否是已知模式
    if cabinet in valid_cabinet_patterns:
        is_valid = True
    # 检查是否是数字格式（如 26-27）
    elif '-' in cabinet and all(part.isdigit() for part in cabinet.split('-')):
        is_valid = True
    # 检查是否对应有效用户
    elif cabinet in user_name_map:
        is_valid = True
    
    if not is_valid:
        # 异常数据，设置为无柜号
        print(f"   修复: {device.name} 的 cabinet_number '{cabinet}' -> '无柜号'")
        device.cabinet_number = "无柜号"
        device.custodian_id = ""
        device.status = DeviceStatus.NO_CABINET
        db.save_device(device)
        cabinet_fixed_count += 1

print(f"   共修复 {cabinet_fixed_count} 个设备的异常 cabinet_number")

# ==================== 总结 ====================
print("\n" + "=" * 70)
print("【修复总结】")
print("=" * 70)
print(f"   设置 custodian_id: {fixed_custodian_count} 个")
print(f"   设置 borrower_id: {fixed_borrower_count} 个")
print(f"   清理无效数据: {cleaned_count} 个")
print(f"   修复异常 cabinet_number: {cabinet_fixed_count} 个")
print(f"   总计修复: {fixed_custodian_count + fixed_borrower_count + cleaned_count + cabinet_fixed_count} 个")

# 重新检查数据
print("\n" + "=" * 70)
print("【重新检查数据】")
print("=" * 70)

# 重新加载数据
api_client.reload_data()
all_devices = api_client.get_all_devices()

# 检查是否还有问题
problem_count = 0
for device in all_devices:
    if device.device_type.value in custody_device_types:
        if device.cabinet_number and device.cabinet_number not in user_name_map:
            if device.cabinet_number not in valid_cabinet_patterns and '-' not in device.cabinet_number:
                problem_count += 1

if problem_count == 0:
    print("   ✓ 数据修复完成，没有明显问题！")
else:
    print(f"   还有 {problem_count} 个设备可能需要检查")

print("\n" + "=" * 70)
