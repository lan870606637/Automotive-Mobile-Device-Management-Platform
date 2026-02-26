# -*- coding: utf-8 -*-
"""
测试设备状态API返回
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import api_client

print("=" * 70)
print("测试设备状态API返回")
print("=" * 70)

# 获取所有设备
all_devices = api_client.get_all_devices()

print(f"\n设备总数: {len(all_devices)}")
print("\n前5个设备的状态信息:")

for i, device in enumerate(all_devices[:5]):
    print(f"\n{i+1}. {device.name}")
    print(f"   类型: {device.device_type.value}")
    print(f"   状态: {device.status.value}")
    print(f"   status类型: {type(device.status)}")

# 检查手机设备
print("\n" + "=" * 70)
print("手机设备列表:")
print("=" * 70)

phones = [d for d in all_devices if d.device_type.value == '手机']
print(f"手机设备数量: {len(phones)}")

for device in phones[:10]:
    print(f"   - {device.name}: 状态={device.status.value}")

print("\n" + "=" * 70)
