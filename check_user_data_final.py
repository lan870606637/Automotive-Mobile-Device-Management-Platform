# -*- coding: utf-8 -*-
"""
检查用户数据完整性 - 最终验证
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import api_client
from common.models import DeviceStatus

print("=" * 70)
print("检查用户数据完整性 - 最终验证")
print("=" * 70)

# 获取所有数据
users = api_client.get_all_users()
all_devices = api_client.get_all_devices()

active_users = [u for u in users if not u.is_deleted]
deleted_users = [u for u in users if u.is_deleted]

print(f"\n【用户统计】")
print(f"   有效用户: {len(active_users)} 个")
print(f"   已删除用户: {len(deleted_users)} 个")
print(f"   设备总数: {len(all_devices)} 个")

# 创建用户ID和名称的映射
user_id_map = {u.id: u for u in users}
user_name_map = {u.borrower_name: u for u in users if u.borrower_name}

# ==================== 检查1: 借出设备的 borrower_id 问题 ====================
print(f"\n{'='*70}")
print("【检查1】借出设备的 borrower_id 问题")
print("=" * 70)

borrowed_devices = [d for d in all_devices if d.status == DeviceStatus.BORROWED]
print(f"   借出状态设备: {len(borrowed_devices)} 个")

problem_borrowed = []
for device in borrowed_devices:
    has_borrower_name = bool(device.borrower)
    has_borrower_id = bool(device.borrower_id)
    
    if not has_borrower_name and not has_borrower_id:
        problem_borrowed.append({
            'device': device,
            'issue': '无借用人信息',
            'type': 'critical'
        })
    elif has_borrower_name and not has_borrower_id:
        user = user_name_map.get(device.borrower)
        if not user:
            problem_borrowed.append({
                'device': device,
                'issue': f'borrower名称"{device.borrower}"对应的用户不存在',
                'type': 'orphan'
            })
    elif not has_borrower_name and has_borrower_id:
        user = user_id_map.get(device.borrower_id)
        if not user:
            problem_borrowed.append({
                'device': device,
                'issue': f'borrower_id对应的用户不存在',
                'type': 'orphan'
            })

print(f"   有问题设备: {len(problem_borrowed)} 个")
if problem_borrowed:
    for pb in problem_borrowed:
        d = pb['device']
        print(f"   - {d.name}: {pb['issue']}")

# ==================== 检查2: 保管设备的 custodian_id 问题 ====================
print(f"\n{'='*70}")
print("【检查2】保管设备的 custodian_id 问题")
print("=" * 70)

custody_device_types = ['手机', '手机卡', '其它设备']
custody_devices = [d for d in all_devices if d.device_type.value in custody_device_types]
print(f"   需要保管人的设备: {len(custody_devices)} 个 (手机/手机卡/其它设备)")

problem_custody = []
valid_cabinet_patterns = ['流通', '封存', '无柜号']

for device in custody_devices:
    has_cabinet = bool(device.cabinet_number)
    has_custodian_id = bool(device.custodian_id)
    
    # 跳过无柜号状态的设备
    if device.status == DeviceStatus.NO_CABINET:
        continue
    
    if not has_cabinet and not has_custodian_id:
        # 无保管人信息且不是无柜号状态
        problem_custody.append({
            'device': device,
            'issue': '无保管人信息且状态不是无柜号',
            'type': 'warning'
        })
    elif has_cabinet and has_cabinet not in valid_cabinet_patterns:
        # 检查 cabinet_number 是否是有效的柜号格式
        is_valid_cabinet = '-' in device.cabinet_number and all(part.isdigit() for part in device.cabinet_number.split('-'))
        is_valid_user = device.cabinet_number in user_name_map
        
        if not is_valid_cabinet and not is_valid_user:
            problem_custody.append({
                'device': device,
                'issue': f'cabinet_number"{device.cabinet_number}"不是有效柜号格式且用户不存在',
                'type': 'orphan'
            })

print(f"   有问题设备: {len(problem_custody)} 个")
if problem_custody:
    for pc in problem_custody[:10]:
        d = pc['device']
        print(f"   - {d.name} ({d.device_type.value}): {pc['issue']}")
    if len(problem_custody) > 10:
        print(f"   ... 还有 {len(problem_custody) - 10} 个")

# ==================== 检查3: 已删除用户但还有设备关联 ====================
print(f"\n{'='*70}")
print("【检查3】已删除用户的设备关联")
print("=" * 70)

deleted_user_ids = {u.id for u in deleted_users}
deleted_user_names = {u.borrower_name for u in deleted_users if u.borrower_name}

orphan_devices = []
for device in all_devices:
    if device.borrower_id and device.borrower_id in deleted_user_ids:
        orphan_devices.append({
            'device': device,
            'issue': f'借用人已删除 (borrower_id: {device.borrower_id[:8]}...)',
            'type': 'borrower_deleted'
        })
    elif device.custodian_id and device.custodian_id in deleted_user_ids:
        orphan_devices.append({
            'device': device,
            'issue': f'保管人已删除 (custodian_id: {device.custodian_id[:8]}...)',
            'type': 'custodian_deleted'
        })
    elif device.borrower and device.borrower in deleted_user_names:
        orphan_devices.append({
            'device': device,
            'issue': f'借用人"{device.borrower}"已删除',
            'type': 'borrower_name_deleted'
        })

print(f"   关联已删除用户的设备: {len(orphan_devices)} 个")
if orphan_devices:
    for od in orphan_devices:
        d = od['device']
        print(f"   - {d.name}: {od['issue']}")

# ==================== 检查4: 用户借用/保管统计 ====================
print(f"\n{'='*70}")
print("【检查4】用户设备关联统计")
print("=" * 70)

for user in active_users:
    borrowed = api_client.get_user_borrowed_devices_by_id(user.id)
    custodian = api_client.get_user_custodian_devices_by_id(user.id)
    
    if borrowed or custodian:
        print(f"\n   用户: {user.borrower_name}")
        if borrowed:
            print(f"   - 借用: {len(borrowed)} 个")
            for d in borrowed:
                print(f"     • {d.name}")
        if custodian:
            print(f"   - 保管: {len(custodian)} 个")
            for d in custodian:
                print(f"     • {d.name}")

# ==================== 总结 ====================
print(f"\n{'='*70}")
print("【总结】")
print("=" * 70)

total_issues = len(problem_borrowed) + len(problem_custody) + len(orphan_devices)
print(f"   总问题数: {total_issues}")
print(f"   - 借出设备问题: {len(problem_borrowed)}")
print(f"   - 保管设备问题: {len(problem_custody)}")
print(f"   - 关联已删除用户: {len(orphan_devices)}")

if total_issues == 0:
    print("\n   ✓ 数据状态良好，没有发现问题！")
else:
    print("\n   ⚠ 还有部分问题需要处理")

print("\n" + "=" * 70)
