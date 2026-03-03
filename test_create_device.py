# -*- coding: utf-8 -*-
"""
测试创建设备
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import api_client
from common.models import DeviceType

print("测试创建设备...")

try:
    # 创建测试设备
    device = api_client.create_device(
        device_type=DeviceType.PHONE,
        device_name="测试手机设备",
        model="iPhone 15",
        cabinet="",
        status="在库",
        remarks="测试备注",
        asset_number="",
        purchase_amount=0.0,
        sn="SN123456",
        imei="IMEI123456",
        system_version="iOS 17",
        carrier="中国移动"
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
