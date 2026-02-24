# -*- coding: utf-8 -*-
"""
同步用户统计数据脚本
将历史记录中的借用/归还次数同步到用户模型的 borrow_count 和 return_count 字段
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.api_client import APIClient
from common.models import OperationType

def extract_user_from_borrower(borrower_str, op_type=''):
    """从 borrower 字段中提取用户名
    
    处理以下格式:
    - 直接用户名: "张三"
    - 转借格式: "张三——>李四"
    - 被转借格式: "被转借：张三——>李四"
    
    过滤掉:
    - 保管人代还: "保管人代还：xxx"
    - nan值
    """
    if not borrower_str:
        return None
    
    borrower_str = str(borrower_str).strip()
    
    # 过滤特殊格式
    if borrower_str.startswith('保管人代还：'):
        return None
    if borrower_str.lower() == 'nan' or borrower_str == '':
        return None
    
    # 处理转借格式 - 对于转借操作，返回接收方
    if '——>' in borrower_str:
        parts = borrower_str.split('——>')
        if len(parts) > 1:
            # 返回接收方（转入方）
            to_user = parts[1].strip()
            # 清理前缀
            to_user = to_user.replace('被转借：', '').replace('转借：', '').replace('转给自己：', '').replace('未找到退回：', '').strip()
            if to_user and to_user.lower() != 'nan':
                return to_user
            return None
    
    # 处理普通格式 - 清理可能的前缀
    clean_borrower = borrower_str.replace('被转借：', '').replace('转借：', '').replace('转给自己：', '').replace('未找到退回：', '').strip()
    if clean_borrower and clean_borrower.lower() != 'nan':
        return clean_borrower
    return None

def sync_user_stats():
    """同步用户统计数据"""
    print("=" * 60)
    print("开始同步用户统计数据")
    print("=" * 60)
    
    # 初始化 API 客户端
    api_client = APIClient()
    api_client.reload_data()
    
    # 获取所有记录
    all_records = api_client.get_records()
    print(f"\n总共有 {len(all_records)} 条记录需要处理")
    
    # 统计每个用户的借用和归还次数
    user_borrow_counts = {}  # 用户借用次数
    user_return_counts = {}  # 用户归还次数
    
    # 用于调试的计数器
    borrow_records = 0
    return_records = 0
    transfer_records = 0
    
    for record in all_records:
        op_type = record.operation_type.value
        borrower_str = record.borrower or ''
        
        # 处理借出记录
        if '借出' in op_type:
            borrow_records += 1
            user = extract_user_from_borrower(borrower_str)
            if user:
                user_borrow_counts[user] = user_borrow_counts.get(user, 0) + 1
                print(f"  借出记录 [{record.device_name}]: {user} -> 借用次数 +1")
        
        # 处理归还记录
        elif '归还' in op_type:
            return_records += 1
            user = extract_user_from_borrower(borrower_str)
            if user:
                user_return_counts[user] = user_return_counts.get(user, 0) + 1
                print(f"  归还记录 [{record.device_name}]: {user} -> 归还次数 +1")
        
        # 处理转借记录（转给自己或别人转给我）
        elif op_type == '转借':
            transfer_records += 1
            user = extract_user_from_borrower(borrower_str)
            if user:
                user_borrow_counts[user] = user_borrow_counts.get(user, 0) + 1
                print(f"  转借记录 [{record.device_name}]: {user} 接收设备 -> 借用次数 +1 (原borrower: {borrower_str})")
    
    print("\n" + "=" * 60)
    print("记录统计")
    print("=" * 60)
    print(f"  借出记录: {borrow_records} 条")
    print(f"  归还记录: {return_records} 条")
    print(f"  转借记录: {transfer_records} 条")
    print(f"  涉及借用人: {len(user_borrow_counts)} 人")
    print(f"  涉及归还人: {len(user_return_counts)} 人")
    
    print("\n" + "=" * 60)
    print("用户统计详情")
    print("=" * 60)
    
    # 获取所有用户
    all_users = api_client.get_all_users()
    
    # 更新每个用户的统计
    updated_count = 0
    for user in all_users:
        user_name = user.borrower_name
        old_borrow = user.borrow_count
        old_return = user.return_count
        
        # 从统计中获取新的次数
        new_borrow = user_borrow_counts.get(user_name, 0)
        new_return = user_return_counts.get(user_name, 0)
        
        # 如果有变化，更新用户数据
        if old_borrow != new_borrow or old_return != new_return:
            user.borrow_count = new_borrow
            user.return_count = new_return
            updated_count += 1
            print(f"\n用户: {user_name}")
            print(f"  借用次数: {old_borrow} -> {new_borrow}")
            print(f"  归还次数: {old_return} -> {new_return}")
    
    # 保存数据
    api_client._save_data()
    
    print("\n" + "=" * 60)
    print(f"同步完成！共更新了 {updated_count} 个用户的统计数据")
    print("=" * 60)
    
    # 显示汇总
    print("\n汇总信息:")
    print(f"  处理记录数: {len(all_records)}")
    print(f"  借出记录数: {borrow_records}")
    print(f"  归还记录数: {return_records}")
    print(f"  转借记录数: {transfer_records}")
    print(f"  涉及借用人: {len(user_borrow_counts)}")
    print(f"  涉及归还人: {len(user_return_counts)}")
    print(f"  更新用户数: {updated_count}")
    
    # 显示借用次数前10名
    if user_borrow_counts:
        print("\n借用次数前10名:")
        sorted_borrow = sorted(user_borrow_counts.items(), key=lambda x: x[1], reverse=True)
        for i, (name, count) in enumerate(sorted_borrow[:10], 1):
            print(f"  {i}. {name}: {count}次")
    
    # 显示归还次数前10名
    if user_return_counts:
        print("\n归还次数前10名:")
        sorted_return = sorted(user_return_counts.items(), key=lambda x: x[1], reverse=True)
        for i, (name, count) in enumerate(sorted_return[:10], 1):
            print(f"  {i}. {name}: {count}次")
    
    # 显示没有统计的用户（用于调试）
    users_with_stats = set(user_borrow_counts.keys()) | set(user_return_counts.keys())
    users_without_stats = [u.borrower_name for u in all_users if u.borrower_name not in users_with_stats]
    if users_without_stats:
        print(f"\n没有借用/归还记录的用户 ({len(users_without_stats)} 个):")
        for name in users_without_stats[:10]:
            print(f"  - {name}")
        if len(users_without_stats) > 10:
            print(f"  ... 还有 {len(users_without_stats) - 10} 个用户")

if __name__ == '__main__':
    try:
        sync_user_stats()
    except Exception as e:
        print(f"\n同步过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
