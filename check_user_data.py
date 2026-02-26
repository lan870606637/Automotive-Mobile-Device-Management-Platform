# -*- coding: utf-8 -*-
"""
检查用户数据完整性
识别有问题的旧数据
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import api_client
from common.models import DeviceStatus

print("=" * 70)
print("检查用户数据完整性")
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
        # 状态是借出，但没有借用人信息
        problem_borrowed.append({
            'device': device,
            'issue': '无借用人信息',
            'type': 'critical'
        })
    elif has_borrower_name and not has_borrower_id:
        # 有借用人名称但没有ID - 可能是旧数据
        user = user_name_map.get(device.borrower)
        if user:
            problem_borrowed.append({
                'device': device,
                'issue': f'有borrower名称但无borrower_id (可修复: 用户{user.borrower_name}存在)',
                'type': 'fixable',
                'user': user
            })
        else:
            problem_borrowed.append({
                'device': device,
                'issue': f'borrower名称"{device.borrower}"对应的用户不存在',
                'type': 'orphan'
            })
    elif not has_borrower_name and has_borrower_id:
        # 有ID但没有名称
        user = user_id_map.get(device.borrower_id)
        if user:
            problem_borrowed.append({
                'device': device,
                'issue': f'有borrower_id但无borrower名称 (可修复: 用户{user.borrower_name}存在)',
                'type': 'fixable',
                'user': user
            })
        else:
            problem_borrowed.append({
                'device': device,
                'issue': f'borrower_id对应的用户不存在',
                'type': 'orphan'
            })

print(f"   有问题设备: {len(problem_borrowed)} 个")
if problem_borrowed:
    for pb in problem_borrowed[:10]:  # 只显示前10个
        d = pb['device']
        print(f"   - {d.name}: {pb['issue']}")
    if len(problem_borrowed) > 10:
        print(f"   ... 还有 {len(problem_borrowed) - 10} 个")

# ==================== 检查2: 保管设备的 custodian_id 问题 ====================
print(f"\n{'='*70}")
print("【检查2】保管设备的 custodian_id 问题")
print("=" * 70)

# 手机、手机卡、其它设备使用 cabinet_number 作为保管人
custody_device_types = ['手机', '手机卡', '其它设备']
custody_devices = [d for d in all_devices if d.device_type.value in custody_device_types]
print(f"   需要保管人的设备: {len(custody_devices)} 个 (手机/手机卡/其它设备)")

problem_custody = []
for device in custody_devices:
    has_cabinet = bool(device.cabinet_number)
    has_custodian_id = bool(device.custodian_id)
    
    if not has_cabinet and not has_custodian_id:
        # 无保管人信息 - 可能是无柜号状态
        if device.status != DeviceStatus.NO_CABINET:
            problem_custody.append({
                'device': device,
                'issue': '无保管人信息且状态不是无柜号',
                'type': 'warning'
            })
    elif has_cabinet and not has_custodian_id:
        # 有cabinet_number但没有custodian_id - 这是正常情况，但可以修复
        user = user_name_map.get(device.cabinet_number)
        if user:
            problem_custody.append({
                'device': device,
                'issue': f'有cabinet_number但无custodian_id (可修复: 用户{user.borrower_name}存在)',
                'type': 'fixable',
                'user': user
            })
        # 如果cabinet_number不是用户名（如"流通"、"封存"、柜号"A01"等），则不算问题
        elif device.cabinet_number in ['流通', '封存'] or '-' in device.cabinet_number or device.cabinet_number.isdigit():
            pass  # 这是正常的柜号格式
        else:
            problem_custody.append({
                'device': device,
                'issue': f'cabinet_number"{device.cabinet_number}"可能对应用户但用户不存在',
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
    # 检查 borrower_id 是否指向已删除用户
    if device.borrower_id and device.borrower_id in deleted_user_ids:
        orphan_devices.append({
            'device': device,
            'issue': f'借用人已删除 (borrower_id: {device.borrower_id[:8]}...)',
            'type': 'borrower_deleted'
        })
    # 检查 custodian_id 是否指向已删除用户
    elif device.custodian_id and device.custodian_id in deleted_user_ids:
        orphan_devices.append({
            'device': device,
            'issue': f'保管人已删除 (custodian_id: {device.custodian_id[:8]}...)',
            'type': 'custodian_deleted'
        })
    # 检查 borrower 名称是否指向已删除用户
    elif device.borrower and device.borrower in deleted_user_names:
        orphan_devices.append({
            'device': device,
            'issue': f'借用人"{device.borrower}"已删除',
            'type': 'borrower_name_deleted'
        })

print(f"   关联已删除用户的设备: {len(orphan_devices)} 个")
if orphan_devices:
    for od in orphan_devices[:10]:
        d = od['device']
        print(f"   - {d.name}: {od['issue']}")
    if len(orphan_devices) > 10:
        print(f"   ... 还有 {len(orphan_devices) - 10} 个")

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
        if custodian:
            print(f"   - 保管: {len(custodian)} 个")

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
    print("\n   建议:")
    fixable_count = sum(1 for p in problem_borrowed if p['type'] == 'fixable')
    fixable_count += sum(1 for p in problem_custody if p['type'] == 'fixable')
    if fixable_count > 0:
        print(f"   - 有 {fixable_count} 个设备可以通过修复脚本自动修复")
    if len(orphan_devices) > 0:
        print(f"   - 有 {len(orphan_devices)} 个设备关联了已删除用户，需要清理")

print("\n" + "=" * 70)
