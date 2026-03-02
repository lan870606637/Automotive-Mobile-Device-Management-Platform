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

    # 主题皮肤列表
    themes = [
        {"name": "深海蓝", "description": "深邃海洋风格，沉稳专业", "price": 500, "icon": "ocean-blue"},
        {"name": "樱花粉", "description": "浪漫樱花风格，温柔甜美", "price": 500, "icon": "sakura-pink"},
        {"name": "森林绿", "description": "自然森林风格，清新活力", "price": 500, "icon": "forest-green"},
        {"name": "暗夜紫", "description": "神秘暗夜风格，酷炫科技", "price": 600, "icon": "dark-purple"},
        {"name": "暖阳橙", "description": "温暖阳光风格，活力热情", "price": 500, "icon": "warm-orange"},
    ]

    # 鼠标皮肤列表 - 20个精美设计（适合男生女生）
    cursor_skins = [
        # 可爱萌系（适合女生）
        {"name": "樱花猫爪", "description": "粉嫩樱花色猫爪，萌化少女心", "price": 300, "icon": "cat-paw-pink", "color": "#FFB6C1"},
        {"name": "彩虹独角兽", "description": "梦幻独角兽角，七彩流光", "price": 400, "icon": "unicorn-rainbow", "color": "#FF69B4"},
        {"name": "软萌兔耳", "description": "白色兔耳朵，可爱俏皮", "price": 350, "icon": "bunny-ears", "color": "#FFF0F5"},
        {"name": "魔法星星", "description": "闪烁的魔法星星，梦幻唯美", "price": 320, "icon": "magic-star", "color": "#DDA0DD"},
        {"name": "糖果爱心", "description": "甜蜜糖果色爱心，甜到心里", "price": 280, "icon": "candy-heart", "color": "#FF1493"},
        {"name": "云朵棉花糖", "description": "软绵绵的云朵，治愈系", "price": 300, "icon": "cloud-cotton", "color": "#E6E6FA"},
        {"name": "蝴蝶飞舞", "description": "彩色蝴蝶翅膀，翩翩起舞", "price": 380, "icon": "butterfly-wing", "color": "#DA70D6"},
        {"name": "珍珠贝壳", "description": "海洋珍珠贝壳，优雅高贵", "price": 420, "icon": "pearl-shell", "color": "#FFE4E1"},
        # 酷炫科技（适合男生）
        {"name": "赛博光剑", "description": "霓虹光剑，未来科技感", "price": 450, "icon": "cyber-lightsaber", "color": "#00FFFF"},
        {"name": "机械齿轮", "description": "精密机械齿轮，工业美学", "price": 400, "icon": "mechanical-gear", "color": "#708090"},
        {"name": "电竞之刃", "description": "锋利电竞风格，战斗气息", "price": 500, "icon": "gaming-blade", "color": "#DC143C"},
        {"name": "量子核心", "description": "旋转量子核心，能量澎湃", "price": 480, "icon": "quantum-core", "color": "#4169E1"},
        {"name": "龙鳞护甲", "description": "古老龙鳞纹理，霸气外露", "price": 550, "icon": "dragon-scale", "color": "#8B0000"},
        {"name": "黑曜石锋", "description": "黑曜石切割面，冷峻锋利", "price": 420, "icon": "obsidian-edge", "color": "#2F4F4F"},
        # 中性风格（男女通用）
        {"name": "极简几何", "description": "简约几何线条，现代极简", "price": 250, "icon": "minimal-geo", "color": "#333333"},
        {"name": "流光溢彩", "description": "渐变流光效果，炫彩夺目", "price": 380, "icon": "gradient-flow", "color": "#FF6347"},
        {"name": "水墨丹青", "description": "中国风水墨，古典雅致", "price": 450, "icon": "ink-wash", "color": "#2F4F4F"},
        {"name": "星空轨迹", "description": "流星划过夜空，浪漫神秘", "price": 400, "icon": "star-trail", "color": "#191970"},
        {"name": "水晶棱镜", "description": "透明水晶折射，纯净剔透", "price": 350, "icon": "crystal-prism", "color": "#87CEEB"},
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

    # 添加主题皮肤
    print("\n🎨 添加/更新主题皮肤...")
    for i, theme_data in enumerate(themes):
        item_id = f"theme_{i+1:03d}"
        item = ShopItem(
            id=item_id,
            name=theme_data["name"],
            description=theme_data["description"],
            item_type=ShopItemType.THEME,
            price=theme_data["price"],
            icon=theme_data["icon"],
            sort_order=i
        )
        db.save_shop_item(item)
        if item_id in existing_ids:
            updated_count += 1
            print(f"  🔄 {theme_data['name']} - {theme_data['price']}积分 (更新)")
        else:
            added_count += 1
            print(f"  ✓ {theme_data['name']} - {theme_data['price']}积分 (新增)")

    # 添加鼠标皮肤
    print("\n🖱️ 添加/更新鼠标皮肤...")
    for i, cursor_data in enumerate(cursor_skins):
        item_id = f"cursor_{i+1:03d}"
        item = ShopItem(
            id=item_id,
            name=cursor_data["name"],
            description=cursor_data["description"],
            item_type=ShopItemType.CURSOR,
            price=cursor_data["price"],
            icon=cursor_data["icon"],
            color=cursor_data["color"],
            sort_order=i
        )
        db.save_shop_item(item)
        if item_id in existing_ids:
            updated_count += 1
            print(f"  🔄 {cursor_data['name']} - {cursor_data['price']}积分 (更新)")
        else:
            added_count += 1
            print(f"  ✓ {cursor_data['name']} - {cursor_data['price']}积分 (新增)")

    print("\n" + "=" * 60)
    print(f"✅ 完成！新增 {added_count} 个，更新 {updated_count} 个")
    print(f"   共 {len(titles)} 个称号，{len(avatar_frames)} 个头像边框，{len(themes)} 个主题皮肤，{len(cursor_skins)} 个鼠标皮肤")
    print("=" * 60)

if __name__ == "__main__":
    init_shop_items()
