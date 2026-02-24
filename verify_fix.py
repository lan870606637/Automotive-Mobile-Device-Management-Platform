# -*- coding: utf-8 -*-
"""
验证修复结果：检查lan的统计是否一致
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import APIClient

def verify_stats():
    """验证统计结果"""
    print("=" * 80)
    print("验证修复结果 - lan的借用次数统计")
    print("=" * 80)
    
    api_client = APIClient()
    api_client.reload_data()
    
    # 获取所有记录
    all_records = api_client.get_records()
    
    # 新的统计逻辑（只统计接收方）
    def is_borrow_record_new(record, user_name):
        op_type = record.operation_type.value
        borrower_str = record.borrower or ''
        
        if '借出' in op_type:
            # 借出记录，检查borrower是否是当前用户
            if '——>' in borrower_str:
                parts = borrower_str.split('——>')
                if len(parts) > 1:
                    to_user = parts[1].strip()
                    if to_user == user_name:
                        return True
            elif borrower_str.strip() == user_name:
                return True
        
        elif op_type == '转借':
            # 转借记录，只统计接收方（转入方）
            if '——>' in borrower_str:
                parts = borrower_str.split('——>')
                if len(parts) > 1:
                    to_user = parts[1].strip()
                    if to_user == user_name:
                        return True
        
        return False
    
    # 统计lan的借用次数
    lan_borrow_count = 0
    for record in all_records:
        if is_borrow_record_new(record, 'lan'):
            lan_borrow_count += 1
    
    print(f"\nlan的借用次数（新逻辑）: {lan_borrow_count} 次")
    
    # 从用户模型获取
    all_users = api_client.get_all_users()
    lan_user = None
    for u in all_users:
        if u.borrower_name == 'lan':
            lan_user = u
            break
    
    if lan_user:
        print(f"lan的借用次数（用户模型）: {lan_user.borrow_count} 次")
        print(f"lan的归还次数（用户模型）: {lan_user.return_count} 次")
        
        if lan_borrow_count == lan_user.borrow_count:
            print("\n✅ 统计一致！修复成功！")
        else:
            print(f"\n❌ 统计不一致！差异: {lan_borrow_count - lan_user.borrow_count} 次")
            print("\n需要运行 sync_user_stats.py 同步数据")
    else:
        print("\n❌ 未找到用户 'lan'")

if __name__ == '__main__':
    try:
        verify_stats()
    except Exception as e:
        print(f"\n验证过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
