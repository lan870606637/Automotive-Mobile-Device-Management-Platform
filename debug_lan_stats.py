# -*- coding: utf-8 -*-
"""
调试脚本：分析lan的借用记录统计差异
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import APIClient

def analyze_lan_records():
    """分析lan的记录"""
    print("=" * 80)
    print("分析 lan 的借用记录")
    print("=" * 80)
    
    api_client = APIClient()
    api_client.reload_data()
    
    # 获取所有记录
    all_records = api_client.get_records()
    
    # 方法1：按照同步脚本的逻辑统计（用于排行榜）
    print("\n【方法1】按照同步脚本逻辑统计（用于排行榜）：")
    print("-" * 80)
    
    def extract_user_from_borrower(borrower_str):
        if not borrower_str:
            return None
        borrower_str = str(borrower_str).strip()
        if borrower_str.startswith('保管人代还：'):
            return None
        if borrower_str.lower() == 'nan' or borrower_str == '':
            return None
        if '——>' in borrower_str:
            parts = borrower_str.split('——>')
            if len(parts) > 1:
                to_user = parts[1].strip()
                to_user = to_user.replace('被转借：', '').replace('转借：', '').replace('转给自己：', '').replace('未找到退回：', '').strip()
                if to_user and to_user.lower() != 'nan':
                    return to_user
                return None
        clean_borrower = borrower_str.replace('被转借：', '').replace('转借：', '').replace('转给自己：', '').replace('未找到退回：', '').strip()
        if clean_borrower and clean_borrower.lower() != 'nan':
            return clean_borrower
        return None
    
    method1_count = 0
    for record in all_records:
        op_type = record.operation_type.value
        borrower_str = record.borrower or ''
        
        if '借出' in op_type:
            user = extract_user_from_borrower(borrower_str)
            if user == 'lan':
                method1_count += 1
                print(f"  借出: {record.device_name} (borrower: {borrower_str})")
        
        elif op_type == '转借':
            user = extract_user_from_borrower(borrower_str)
            if user == 'lan':
                method1_count += 1
                print(f"  转借: {record.device_name} (borrower: {borrower_str})")
    
    print(f"\n方法1统计结果: {method1_count} 次")
    
    # 方法2：按照我的借用记录页面逻辑统计
    print("\n【方法2】按照我的借用记录页面逻辑统计：")
    print("-" * 80)
    
    # 获取当前用户信息
    current_user_name = 'lan'
    
    def is_borrow_record(record):
        op_type = record.operation_type.value
        if '借出' in op_type:
            return True
        if op_type == '转借':
            # 检查是否是转给我自己的记录（operator是我 或 borrower字段中包含我作为接收方）
            if record.operator == current_user_name:
                return True
            # 解析borrower字段，检查我是否是接收方
            if '——>' in record.borrower:
                parts = record.borrower.split('——>')
                if len(parts) > 1:
                    to_user = parts[1].strip()
                    if to_user == current_user_name:
                        return True
        return False
    
    method2_count = 0
    for record in all_records:
        if is_borrow_record(record):
            # 检查这条记录是否与lan相关
            op_type = record.operation_type.value
            borrower_str = record.borrower or ''
            
            # 检查是否是lan的记录
            is_lan_record = False
            
            if '借出' in op_type:
                # 借出记录，检查borrower是否是lan
                if '——>' in borrower_str:
                    parts = borrower_str.split('——>')
                    to_user = parts[1].strip() if len(parts) > 1 else ''
                    if to_user == 'lan' or parts[0].strip() == 'lan':
                        is_lan_record = True
                elif borrower_str.strip() == 'lan':
                    is_lan_record = True
            
            elif op_type == '转借':
                # 转借记录，检查operator是否是lan或lan是否是接收方
                if record.operator == 'lan':
                    is_lan_record = True
                elif '——>' in borrower_str:
                    parts = borrower_str.split('——>')
                    to_user = parts[1].strip() if len(parts) > 1 else ''
                    if to_user == 'lan':
                        is_lan_record = True
            
            if is_lan_record:
                method2_count += 1
                print(f"  {op_type}: {record.device_name} (operator: {record.operator}, borrower: {borrower_str})")
    
    print(f"\n方法2统计结果: {method2_count} 次")
    
    # 方法3：简单统计所有包含lan的记录
    print("\n【方法3】简单统计所有borrower包含lan的记录：")
    print("-" * 80)
    
    method3_count = 0
    for record in all_records:
        op_type = record.operation_type.value
        borrower_str = record.borrower or ''
        
        if '借出' in op_type or op_type == '转借':
            if 'lan' in borrower_str:
                method3_count += 1
                print(f"  {op_type}: {record.device_name} (borrower: {borrower_str})")
    
    print(f"\n方法3统计结果: {method3_count} 次")
    
    # 显示差异分析
    print("\n" + "=" * 80)
    print("差异分析")
    print("=" * 80)
    print(f"方法1 (排行榜逻辑): {method1_count} 次")
    print(f"方法2 (我的记录逻辑): {method2_count} 次")
    print(f"方法3 (简单包含): {method3_count} 次")
    print(f"\n差异: {method2_count - method1_count} 次")
    
    # 找出差异记录
    print("\n【差异记录】方法2统计了但方法1没统计的记录：")
    print("-" * 80)
    
    for record in all_records:
        op_type = record.operation_type.value
        borrower_str = record.borrower or ''
        
        # 方法2判断
        is_method2 = False
        if '借出' in op_type:
            if '——>' in borrower_str:
                parts = borrower_str.split('——>')
                to_user = parts[1].strip() if len(parts) > 1 else ''
                if to_user == 'lan' or parts[0].strip() == 'lan':
                    is_method2 = True
            elif borrower_str.strip() == 'lan':
                is_method2 = True
        elif op_type == '转借':
            if record.operator == 'lan':
                is_method2 = True
            elif '——>' in borrower_str:
                parts = borrower_str.split('——>')
                to_user = parts[1].strip() if len(parts) > 1 else ''
                if to_user == 'lan':
                    is_method2 = True
        
        # 方法1判断
        is_method1 = False
        if '借出' in op_type:
            user = extract_user_from_borrower(borrower_str)
            if user == 'lan':
                is_method1 = True
        elif op_type == '转借':
            user = extract_user_from_borrower(borrower_str)
            if user == 'lan':
                is_method1 = True
        
        # 只显示方法2有但方法1没有的
        if is_method2 and not is_method1:
            print(f"  {op_type}: {record.device_name}")
            print(f"    operator: {record.operator}")
            print(f"    borrower: {borrower_str}")
            print()

if __name__ == '__main__':
    try:
        analyze_lan_records()
    except Exception as e:
        print(f"\n分析过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
