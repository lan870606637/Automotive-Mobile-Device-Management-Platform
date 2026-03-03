# -*- coding: utf-8 -*-
"""
测试完整的设备创建流程
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import api_client
from common.models import DeviceType

# 设置当前管理员
api_client.set_current_admin('测试管理员')

print("测试创建设备（带 % 字符）...")

try:
    # 创建测试设备（设备名称包含 % 字符）
    device = api_client.create_device(
        device_type=DeviceType.PHONE,
        device_name="测试%手机%设备",  # 包含 % 字符
        model="iPhone 15%Pro",  # 包含 % 字符
        cabinet="柜号%A01",  # 包含 % 字符
        status="在库",
        remarks="测试%备注",  # 包含 % 字符
        asset_number="资产%编号",  # 包含 % 字符
        purchase_amount=100.5,
        sn="SN%123456",  # 包含 % 字符
        imei="IMEI%789012",  # 包含 % 字符
        system_version="iOS%17",  # 包含 % 字符
        carrier="中国%移动"  # 包含 % 字符
    )
    print(f"✓ 设备创建成功: {device.id}")
    print(f"  名称: {device.name}")
    print(f"  型号: {device.model}")
    print(f"  SN: {device.sn}")
    print(f"  IMEI: {device.imei}")
except Exception as e:
    print(f"✗ 设备创建失败: {e}")
    import traceback
    traceback.print_exc()
