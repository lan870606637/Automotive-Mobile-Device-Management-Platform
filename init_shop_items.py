#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化积分商城商品数据
生成随机的称号和头像边框
"""

import sys
import os
import uuid

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db_store import DatabaseStore
from common.models import ShopItem, ShopItemType

def init_shop_items():
    """初始化积分商城商品"""
    db = DatabaseStore()

    # 称号列表
    titles = [
        {"name": "初出茅庐", "description": "刚刚踏入设备管理世界的新人", "price": 50, "color": "#8c8c8c"},
        {"name": "设备学徒", "description": "正在学习设备管理的基础知识", "price": 100, "color": "#52c41a"},
        {"name": "借还达人", "description": "熟练借用和归还设备的老手", "price": 200, "color": "#1890ff"},
        {"name": "设备守护者", "description": "精心保管设备的守护者", "price": 300, "color": "#722ed1"},
        {"name": "积分猎人", "description": "热衷于赚取积分的活跃玩家", "price": 400, "color": "#fa8c16"},
        {"name": "悬赏专家", "description": "完成悬赏任务的高手", "price": 500, "color": "#eb2f96"},
        {"name": "排行榜常客", "description": "经常出现在排行榜上的名人", "price": 600, "color": "#f5222d"},
        {"name": "设备大师", "description": "设备管理领域的专家", "price": 800, "color": "#13c2c2"},
        {"name": "传奇借用人", "description": "传说中的设备借用者", "price": 1000, "color": "#faad14"},
        {"name": "至尊管理员", "description": "至高无上的设备管理者", "price": 1500, "color": "#cf1322"},
        {"name": "夜猫子", "description": "喜欢在深夜使用设备的夜猫子", "price": 300, "color": "#2f4554"},
        {"name": "早起鸟", "description": "每天最早来借设备的人", "price": 300, "color": "#fadb14"},
        {"name": "完美归还者", "description": "从不逾期归还的完美主义者", "price": 500, "color": "#237804"},
        {"name": "社交达人", "description": "喜欢点赞和互动的社交高手", "price": 350, "color": "#eb2f96"},
        {"name": "探索者", "description": "喜欢搜索和发现新设备的探索者", "price": 250, "color": "#096dd9"},
    ]

    # 头像边框列表
    avatar_frames = [
        {"name": "简约银框", "description": "低调简约的银色边框", "price": 100, "color": "#bfbfbf", "icon": "simple"},
        {"name": "活力绿框", "description": "充满活力的绿色边框", "price": 150, "color": "#52c41a", "icon": "simple"},
        {"name": "天空蓝框", "description": "如天空般清澈的蓝色边框", "price": 200, "color": "#1890ff", "icon": "simple"},
        {"name": "神秘紫框", "description": "神秘优雅的紫色边框", "price": 250, "color": "#722ed1", "icon": "simple"},
        {"name": "热情橙框", "description": "热情洋溢的橙色边框", "price": 300, "color": "#fa8c16", "icon": "simple"},
        {"name": "浪漫粉框", "description": "浪漫可爱的粉色边框", "price": 350, "color": "#eb2f96", "icon": "simple"},
        {"name": "热情红框", "description": "热情似火的红色边框", "price": 400, "color": "#f5222d", "icon": "simple"},
        {"name": "清新青框", "description": "清新自然的青色边框", "price": 450, "color": "#13c2c2", "icon": "simple"},
        {"name": "土豪金框", "description": "奢华尊贵的金色边框", "price": 600, "color": "#faad14", "icon": "simple"},
        {"name": "暗夜黑框", "description": "神秘深邃的黑色边框", "price": 500, "color": "#262626", "icon": "simple"},
        {"name": "彩虹框", "description": "七彩斑斓的彩虹边框", "price": 800, "color": "#ff4d4f", "icon": "simple"},
        {"name": "星空框", "description": "璀璨星空的梦幻边框", "price": 700, "color": "#1d39c4", "icon": "simple"},
        # 图案边框
        {"name": "龙纹金框", "description": "金龙环绕，尊贵霸气", "price": 1500, "color": "#ffd700", "icon": "dragon"},
        {"name": "烈焰马框", "description": "骏马奔腾，热情似火", "price": 1200, "color": "#ff6b35", "icon": "horse"},
        {"name": "玫瑰恋框", "description": "玫瑰环绕，浪漫永恒", "price": 1000, "color": "#e91e63", "icon": "rose"},
        {"name": "凤凰框", "description": "凤凰涅槃，浴火重生", "price": 1800, "color": "#ff5722", "icon": "phoenix"},
        {"name": "蝴蝶梦框", "description": "蝴蝶飞舞，梦幻唯美", "price": 900, "color": "#9c27b0", "icon": "butterfly"},
        {"name": "星辰框", "description": "星辰环绕，神秘浩瀚", "price": 1100, "color": "#3f51b5", "icon": "star"},
    ]

    print("=" * 60)
    print("🛒 初始化积分商城商品数据")
    print("=" * 60)

    # 获取现有商品
    existing_items = db.get_all_shop_items(only_active=False)
    existing_ids = {item.id for item in existing_items}

    added_count = 0
    updated_count = 0

    # 添加称号
    print("\n🏆 添加/更新称号...")
    for i, title_data in enumerate(titles):
        item_id = f"title_{i+1:03d}"
        item = ShopItem(
            id=item_id,
            name=title_data["name"],
            description=title_data["description"],
            item_type=ShopItemType.TITLE,
            price=title_data["price"],
            color=title_data["color"],
            sort_order=i
        )
        db.save_shop_item(item)
        if item_id in existing_ids:
            updated_count += 1
            print(f"  🔄 {title_data['name']} - {title_data['price']}积分 (更新)")
        else:
            added_count += 1
            print(f"  ✓ {title_data['name']} - {title_data['price']}积分 (新增)")

    # 添加头像边框
    print("\n🖼️ 添加/更新头像边框...")
    for i, frame_data in enumerate(avatar_frames):
        item_id = f"frame_{i+1:03d}"
        item = ShopItem(
            id=item_id,
            name=frame_data["name"],
            description=frame_data["description"],
            item_type=ShopItemType.AVATAR_FRAME,
            price=frame_data["price"],
            color=frame_data["color"],
            icon=frame_data.get("icon", "simple"),
            sort_order=i
        )
        db.save_shop_item(item)
        if item_id in existing_ids:
            updated_count += 1
            print(f"  🔄 {frame_data['name']} - {frame_data['price']}积分 (更新)")
        else:
            added_count += 1
            print(f"  ✓ {frame_data['name']} - {frame_data['price']}积分 (新增)")

    print("\n" + "=" * 60)
    print(f"✅ 完成！新增 {added_count} 个，更新 {updated_count} 个")
    print(f"   共 {len(titles)} 个称号，{len(avatar_frames)} 个头像边框")
    print("=" * 60)

if __name__ == "__main__":
    init_shop_items()
