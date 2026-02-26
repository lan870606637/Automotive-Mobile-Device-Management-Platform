# -*- coding: utf-8 -*-
"""
清空所有设备的借用信息
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_store import DatabaseStore
from common.models import DeviceStatus

def clear_all_borrower_info():
    """清空所有设备的借用信息"""
    print("=" * 60)
    print("清空设备借用信息")
    print("=" * 60)
    
    db = DatabaseStore()
    devices = db.get_all_devices()
    
    cleared_count = 0
    for device in devices:
        # 清空借用信息
        device.borrower = ""
        device.borrower_id = ""
        device.phone = ""
        device.borrow_time = None
        device.expected_return_date = None
        device.location = ""
        device.reason = ""
        device.entry_source = ""
        device.admin_operator = ""
        
        # 如果设备状态是借出，重置为在库
        if device.status == DeviceStatus.BORROWED:
            device.status = DeviceStatus.IN_STOCK
            print(f"  重置设备状态: {device.name} -> 在库")
        
        db.save_device(device)
        cleared_count += 1
    
    print(f"\n✓ 已清空 {cleared_count} 个设备的借用信息")
    print("=" * 60)

if __name__ == "__main__":
    clear_all_borrower_info()
