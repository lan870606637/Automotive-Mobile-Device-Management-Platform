# -*- coding: utf-8 -*-
"""
测试 purchase_amount 字段处理
"""

# 测试各种情况
test_cases = [
    {},  # 空字典
    {'purchase_amount': ''},  # 空字符串
    {'purchase_amount': None},  # None
    {'purchase_amount': 0},  # 整数 0
    {'purchase_amount': 100.5},  # 浮点数
    {'purchase_amount': '100.5'},  # 字符串数字
]

for data in test_cases:
    try:
        # 原始代码逻辑
        purchase_amount = float(data.get('purchase_amount', 0)) if data.get('purchase_amount') else 0.0
        print(f"✓ 数据 {data} -> {purchase_amount}")
    except Exception as e:
        print(f"✗ 数据 {data} -> 错误: {e}")
