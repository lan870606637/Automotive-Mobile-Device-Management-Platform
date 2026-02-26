# -*- coding: utf-8 -*-
"""
清理所有用户数据和设备借用信息
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_store import DatabaseStore, get_db_transaction, get_db_connection, IS_MYSQL
from common.config import DB_TYPE

def reset_all_data():
    """清理所有用户数据和设备借用信息"""
    print("=" * 60)
    print("开始清理数据...")
    print("=" * 60)
    
    db = DatabaseStore()
    
    # 1. 删除所有用户
    print("\n1. 删除所有用户...")
    users = db.get_all_users()
    deleted_count = 0
    for user in users:
        # 物理删除用户
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            if IS_MYSQL:
                cursor.execute("DELETE FROM users WHERE id = %s", (user.id,))
            else:
                cursor.execute("DELETE FROM users WHERE id = ?", (user.id,))
            deleted_count += 1
    print(f"   ✓ 已删除 {deleted_count} 个用户")
    
    # 2. 清空所有设备的借用信息
    print("\n2. 清空设备借用信息...")
    devices = db.get_all_devices()
    cleared_count = 0
    for device in devices:
        device.borrower = ""
        device.borrower_id = ""
        device.phone = ""
        device.borrow_time = None
        device.expected_return_date = None
        device.location = ""
        device.reason = ""
        device.entry_source = ""
        device.admin_operator = ""
        # 重置状态为在库
        from common.models import DeviceStatus
        if device.status == DeviceStatus.BORROWED:
            device.status = DeviceStatus.IN_STOCK
        db.save_device(device)
        cleared_count += 1
    print(f"   ✓ 已清空 {cleared_count} 个设备的借用信息")
    
    # 3. 清空借用记录
    print("\n3. 清空借用记录...")
    with get_db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM records")
        print(f"   ✓ 已清空所有借用记录")
    
    # 4. 清空操作日志
    print("\n4. 清空操作日志...")
    with get_db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM operation_logs")
        print(f"   ✓ 已清空所有操作日志")
    
    print("\n" + "=" * 60)
    print("数据清理完成！")
    print("=" * 60)
    print(f"\n清理 summary:")
    print(f"  - 删除用户: {deleted_count} 个")
    print(f"  - 清空设备: {cleared_count} 个")
    print(f"  - 数据库类型: {DB_TYPE}")
    print("\n现在您可以重新添加用户和借还设备了。")

if __name__ == "__main__":
    confirm = input("警告：这将删除所有用户数据和借用记录！\n确定要继续吗？(yes/no): ")
    if confirm.lower() == "yes":
        reset_all_data()
    else:
        print("操作已取消。")
