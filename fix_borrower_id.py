# -*- coding: utf-8 -*-
"""
修复设备表中borrower_id为空的记录
根据borrower（姓名）字段关联用户表，填充borrower_id
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def fix_borrower_id():
    """修复borrower_id为空的记录"""
    print("=" * 60)
    print("修复设备表 borrower_id 为空的问题")
    print("=" * 60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        from common.db_store import get_db_connection, DatabaseStore
        
        db = DatabaseStore()
        
        # 1. 查找所有borrower_id为空但borrower有值的设备
        print("【1】查找需要修复的设备...")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    d.id,
                    d.name,
                    d.borrower,
                    d.borrower_id,
                    d.status
                FROM devices d
                WHERE d.borrower IS NOT NULL 
                AND d.borrower != ''
                AND (d.borrower_id IS NULL OR d.borrower_id = '')
                AND d.is_deleted = 0
            """)
            devices_to_fix = cursor.fetchall()
        
        if not devices_to_fix:
            print("   ✓ 没有需要修复的设备")
            print("\n所有设备的borrower_id都已正确设置")
            return
        
        print(f"   发现 {len(devices_to_fix)} 个设备需要修复")
        print()
        
        # 2. 获取所有用户，建立姓名到ID的映射
        print("【2】获取用户映射...")
        users = db.get_all_users()
        borrower_name_to_id = {}
        for user in users:
            if user.borrower_name:
                borrower_name_to_id[user.borrower_name] = user.id
        print(f"   已加载 {len(borrower_name_to_id)} 个用户映射")
        print()
        
        # 3. 修复设备
        print("【3】开始修复设备...")
        fixed_count = 0
        failed_count = 0
        failed_devices = []
        
        for device in devices_to_fix:
            borrower_name = device['borrower']
            device_id = device['id']
            device_name = device['name']
            
            if borrower_name in borrower_name_to_id:
                borrower_id = borrower_name_to_id[borrower_name]
                
                # 更新设备
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE devices SET borrower_id = %s WHERE id = %s",
                        (borrower_id, device_id)
                    )
                    conn.commit()
                
                print(f"   ✓ {device_name} -> {borrower_name} ({borrower_id})")
                fixed_count += 1
            else:
                print(f"   ✗ {device_name} -> 找不到用户: {borrower_name}")
                failed_count += 1
                failed_devices.append({
                    'id': device_id,
                    'name': device_name,
                    'borrower': borrower_name
                })
        
        print()
        print("=" * 60)
        print("修复结果")
        print("=" * 60)
        print(f"   成功修复: {fixed_count} 个设备")
        print(f"   修复失败: {failed_count} 个设备")
        
        if failed_devices:
            print()
            print("以下设备修复失败（找不到对应的用户）：")
            for d in failed_devices:
                print(f"   - {d['name']} (借用人: {d['borrower']})")
        
        print()
        print("=" * 60)
        print("修复完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ 修复过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    fix_borrower_id()
