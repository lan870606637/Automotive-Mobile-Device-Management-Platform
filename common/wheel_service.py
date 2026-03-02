# -*- coding: utf-8 -*-
"""
每日转盘抽奖服务模块
处理转盘抽奖逻辑、奖品发放、抽奖记录等
"""
import uuid
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .models import PointsTransactionType, ShopItemType, ShopItemSource
from .db_store import DatabaseStore
from .points_service import points_service
from .hidden_titles import get_random_hidden_title, get_hidden_title_by_id


@dataclass
class WheelPrize:
    """转盘奖品"""
    id: str
    name: str
    points: int  # 积分值，0表示非积分奖品（如称号）
    probability: float  # 概率（百分比）
    color: str  # 转盘扇区颜色
    icon: str  # 图标
    is_title: bool = False  # 是否是称号奖品


# 转盘奖品配置（13种奖品）
WHEEL_PRIZES = [
    WheelPrize("prize_5", "5积分", 5, 50.0, "#52c41a", "💚"),
    WheelPrize("prize_10", "10积分", 10, 20.0, "#95de64", "💚"),
    WheelPrize("prize_20", "20积分", 20, 10.0, "#1890ff", "💙"),
    WheelPrize("prize_30", "30积分", 30, 5.0, "#69c0ff", "💙"),
    WheelPrize("prize_40", "40积分", 40, 3.0, "#722ed1", "💜"),
    WheelPrize("prize_50", "50积分", 50, 2.0, "#b37feb", "💜"),
    WheelPrize("prize_100", "100积分", 100, 1.0, "#fa8c16", "🧡"),
    WheelPrize("prize_200", "200积分", 200, 0.05, "#ff7a45", "🧡"),
    WheelPrize("prize_300", "300积分", 300, 0.04, "#ff4d4f", "❤️"),
    WheelPrize("prize_400", "400积分", 400, 0.03, "#ff7875", "❤️"),
    WheelPrize("prize_500", "500积分", 500, 0.02, "#ffd700", "⭐"),
    WheelPrize("prize_1000", "1000积分", 1000, 0.01, "#ffd700", "👑"),
    WheelPrize("prize_title", "隐藏称号", 0, 8.85, "#eb2f96", "🎁", is_title=True),
]

# 抽奖次数价格配置
SPIN_PRICES = {
    1: 0,    # 第1次免费
    2: 100,  # 第2次及以后都是100积分
}


def get_spin_price(spin_count: int) -> int:
    """获取第N次抽奖的价格"""
    if spin_count <= 1:
        return 0
    else:
        return 100  # 第2次及以后都是100积分


class WheelService:
    """转盘服务类"""
    
    def __init__(self, db_store: DatabaseStore = None):
        self.db = db_store or DatabaseStore()
    
    def get_user_daily_spin_count(self, user_id: str) -> int:
        """获取用户今日已抽奖次数"""
        today = datetime.now().strftime('%Y-%m-%d')
        records = self.db.get_wheel_records_by_date(user_id, today)
        return len(records)
    
    def get_next_spin_price(self, user_id: str) -> int:
        """获取用户下一次抽奖的价格"""
        spin_count = self.get_user_daily_spin_count(user_id)
        return get_spin_price(spin_count + 1)
    
    def can_spin(self, user_id: str) -> tuple:
        """检查用户是否可以抽奖，返回(是否可以, 原因, 价格)"""
        spin_count = self.get_user_daily_spin_count(user_id)
        price = get_spin_price(spin_count + 1)
        
        # 检查积分是否足够
        if price > 0:
            user_points = points_service.get_or_create_user_points(user_id)
            if user_points.points < price:
                return False, f"积分不足，需要{price}积分", price
        
        return True, "可以抽奖", price
    
    def spin(self, user_id: str) -> Dict[str, Any]:
        """
        执行抽奖
        返回: {
            'success': bool,
            'prize': {...},
            'message': str,
            'points_after': int,
            'is_new_title': bool  # 如果是称号，是否是新获得的
        }
        """
        # 检查是否可以抽奖
        can_spin, reason, price = self.can_spin(user_id)
        if not can_spin:
            return {'success': False, 'message': reason}
        
        # 扣除积分（如果不是免费）
        if price > 0:
            result = points_service.add_points(
                user_id=user_id,
                points=-price,
                transaction_type=PointsTransactionType.SHOP_BUY,
                description=f'每日转盘第{self.get_user_daily_spin_count(user_id) + 1}次抽奖'
            )
            if not result.get('success'):
                return {'success': False, 'message': '积分扣除失败'}
        
        # 抽奖
        prize = self._draw_prize()
        
        # 处理奖品
        is_new_title = False
        title_data = None
        
        if prize.is_title:
            # 获得隐藏称号
            title_result = self._award_hidden_title(user_id)
            is_new_title = title_result.get('is_new', False)
            title_data = title_result.get('title')
        else:
            # 获得积分
            points_service.add_points(
                user_id=user_id,
                points=prize.points,
                transaction_type=PointsTransactionType.RANKING_REWARD,
                description=f'每日转盘获得{prize.points}积分'
            )
        
        # 记录抽奖
        self._record_spin(user_id, prize, price)
        
        # 获取当前积分
        user_points = points_service.get_or_create_user_points(user_id)
        
        return {
            'success': True,
            'prize': {
                'id': prize.id,
                'name': prize.name,
                'points': prize.points,
                'color': prize.color,
                'icon': prize.icon,
                'is_title': prize.is_title,
                'title_data': title_data
            },
            'message': f'恭喜获得 {prize.name}！' if not prize.is_title else f'恭喜获得称号 [{title_data["name"]}]！',
            'points_after': user_points.points,
            'is_new_title': is_new_title,
            'spin_count': self.get_user_daily_spin_count(user_id),
            'next_price': get_spin_price(self.get_user_daily_spin_count(user_id) + 1)
        }
    
    def _draw_prize(self) -> WheelPrize:
        """根据概率抽取奖品"""
        # 构建概率权重列表
        prizes = WHEEL_PRIZES
        weights = [p.probability for p in prizes]
        
        # 使用random.choices进行加权随机选择
        selected = random.choices(prizes, weights=weights, k=1)[0]
        return selected
    
    def _award_hidden_title(self, user_id: str) -> Dict[str, Any]:
        """颁发隐藏称号"""
        # 获取随机隐藏称号
        title = get_random_hidden_title()
        if not title:
            # 如果出错，给100积分作为补偿
            points_service.add_points(
                user_id=user_id,
                points=50,
                transaction_type=PointsTransactionType.RANKING_REWARD,
                description='每日转盘称号获取失败补偿'
            )
            return {'is_new': False, 'title': {'name': '补偿50积分', 'id': 'compensation', 'color': '#8c8c8c'}, 'compensation': 50}
        
        # 检查用户是否已有此称号
        existing = self.db.has_hidden_title(user_id, title['id'])
        
        if not existing:
            # 添加到用户隐藏称号库
            self.db.add_hidden_title(user_id, title['id'], title['name'], title['color'])
            
            # 同时添加到用户背包
            from .models import UserInventory
            inventory_item = UserInventory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                item_id=title['id'],
                item_type=ShopItemType.TITLE,
                item_name=title['name'],
                item_icon='hidden_title',
                item_color=title['color'],
                source=ShopItemSource.RANDOM
            )
            self.db.add_to_inventory(inventory_item)
        else:
            # 重复称号，给予50积分补偿
            points_service.add_points(
                user_id=user_id,
                points=50,
                transaction_type=PointsTransactionType.RANKING_REWARD,
                description=f'每日转盘重复称号[{title["name"]}]补偿'
            )
        
        return {
            'is_new': not existing,
            'title': title,
            'compensation': 50 if existing else 0
        }
    
    def _record_spin(self, user_id: str, prize: WheelPrize, cost: int):
        """记录抽奖"""
        self.db.add_wheel_record(
            user_id=user_id,
            prize_id=prize.id,
            prize_name=prize.name,
            prize_points=prize.points,
            cost=cost
        )
    
    def get_wheel_status(self, user_id: str) -> Dict[str, Any]:
        """获取转盘状态信息"""
        spin_count = self.get_user_daily_spin_count(user_id)
        next_price = get_spin_price(spin_count + 1)
        user_points = points_service.get_or_create_user_points(user_id)
        
        return {
            'today_spin_count': spin_count,
            'next_spin_price': next_price,
            'can_spin': user_points.points >= next_price,
            'current_points': user_points.points,
            'prizes': [
                {
                    'id': p.id,
                    'name': p.name,
                    'points': p.points,
                    'color': p.color,
                    'icon': p.icon,
                    'is_title': p.is_title,
                    'probability': p.probability
                }
                for p in WHEEL_PRIZES
            ]
        }
    
    def get_user_hidden_titles(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户已获得的所有隐藏称号"""
        return self.db.get_user_hidden_titles(user_id)


# 全局转盘服务实例
wheel_service = WheelService()
