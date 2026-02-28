# -*- coding: utf-8 -*-
"""
积分服务模块
处理积分的获取、消费、记录等操作
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from .models import UserPoints, PointsRecord, PointsTransactionType
from .db_store import DatabaseStore


class PointsService:
    """积分服务类"""
    
    # 积分规则配置
    POINTS_RULES = {
        'FIRST_LOGIN': 50,          # 首次登录
        'DAILY_LOGIN': 20,          # 每日登录
        'BORROW': 5,                # 借用设备
        'RETURN': 10,               # 归还设备
        'OVERDUE': -15,             # 逾期归还
        'CREATE_BOUNTY': -10,       # 发布悬赏（固定扣除）
        'COMPLETE_BOUNTY': 0,       # 完成悬赏（获得悬赏积分，动态计算）
        'LIKE': 1,                  # 点赞
        'SEARCH': 5,                # 首页搜索
        'REPORT_FOUND': 10,         # 我已找到
        'REPORT_FIXED': 10,         # 我已修好
        'REPORT_DAMAGED': 10,       # 损坏报备
        'REPORT_LOST': 10,          # 丢失报备
        'TRANSFER': 1,              # 转借
        'RENEW': 1,                 # 续期
        'RESERVE': 1,               # 预约
    }
    
    # 排行榜前十奖励
    RANKING_REWARDS = {
        1: 30,   # 第一名
        2: 20,   # 第二名
        3: 15,   # 第三名
        4: 10,   # 第四名
        5: 10,   # 第五名
        6: 10,   # 第六名
        7: 10,   # 第七名
        8: 10,   # 第八名
        9: 10,   # 第九名
        10: 10,  # 第十名
    }
    
    # 积分排行榜称号（前10名）
    POINTS_TITLES = [
        "👑 积分之神", "⚔️ 积分至尊", "🔥 积分霸主", "⚡ 积分狂魔", "💎 积分财神",
        "🌟 积分王者", "🏆 积分大师", "💰 积分达人", "🎯 积分猎手", "⭐ 积分先锋"
    ]
    
    def __init__(self, db_store: DatabaseStore = None):
        self.db = db_store or DatabaseStore()
    
    def get_or_create_user_points(self, user_id: str) -> UserPoints:
        """获取或创建用户积分记录"""
        user_points = self.db.get_user_points(user_id)
        if not user_points:
            user_points = UserPoints(
                id=str(uuid.uuid4()),
                user_id=user_id,
                points=0,
                total_earned=0,
                total_spent=0
            )
            self.db.save_user_points(user_points)
        return user_points
    
    def add_points(self, user_id: str, points: int, transaction_type: PointsTransactionType,
                   description: str = "", related_id: str = "") -> Dict[str, Any]:
        """
        增加/扣除用户积分
        :param user_id: 用户ID
        :param points: 积分变动（正数为增加，负数为扣除）
        :param transaction_type: 交易类型
        :param description: 描述
        :param related_id: 相关记录ID
        :return: 操作结果
        """
        # 获取或创建用户积分
        user_points = self.get_or_create_user_points(user_id)
        
        # 计算新积分
        new_points = user_points.points + points
        
        # 更新用户积分
        user_points.points = new_points
        if points > 0:
            user_points.total_earned += points
        else:
            user_points.total_spent += abs(points)
        user_points.update_time = datetime.now()
        
        # 保存用户积分
        self.db.save_user_points(user_points)
        
        # 创建积分记录
        record = PointsRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            transaction_type=transaction_type,
            points_change=points,
            points_after=new_points,
            description=description,
            related_id=related_id
        )
        self.db.add_points_record(record)
        
        return {
            'success': True,
            'points': new_points,
            'points_change': points,
            'message': f'{"获得" if points > 0 else "扣除"} {abs(points)} 积分'
        }
    
    def get_user_points(self, user_id: str) -> int:
        """获取用户当前积分"""
        user_points = self.db.get_user_points(user_id)
        return user_points.points if user_points else 0
    
    def get_user_points_detail(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户积分详情"""
        user_points = self.db.get_user_points(user_id)
        if not user_points:
            return None
        
        return {
            'points': user_points.points,
            'total_earned': user_points.total_earned,
            'total_spent': user_points.total_spent,
            'update_time': user_points.update_time.strftime('%Y-%m-%d %H:%M:%S') if user_points.update_time else ''
        }
    
    def get_points_records(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户积分记录"""
        records = self.db.get_points_records(user_id, limit)
        return [record.to_dict() for record in records]
    
    def get_points_rankings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取积分排行榜（按累计积分排序）"""
        from .api_client import api_client

        # 获取所有用户
        all_users = api_client._users

        # 获取所有已有积分的用户
        all_points = self.db.get_all_user_points()
        points_dict = {p.user_id: p for p in all_points}

        # 为所有用户创建积分数据（如果没有则初始化为0）
        all_user_points = []
        for user in all_users:
            if user.id in points_dict:
                all_user_points.append(points_dict[user.id])
            else:
                # 创建初始积分记录（不保存到数据库，仅用于显示）
                all_user_points.append(UserPoints(
                    id='',
                    user_id=user.id,
                    points=0,
                    total_earned=0,
                    total_spent=0
                ))

        # 按累计积分排序
        sorted_points = sorted(all_user_points, key=lambda x: x.total_earned, reverse=True)
        
        rankings = []
        for i, user_points in enumerate(sorted_points[:limit]):
            rank = i + 1  # 从上到下排序，没有并列
            
            # 获取用户信息
            user = None
            for u in api_client._users:
                if u.id == user_points.user_id:
                    user = u
                    break
            
            if user:
                # 前10名添加称号
                title = None
                if rank <= 10:
                    title = self.POINTS_TITLES[i] if i < len(self.POINTS_TITLES) else self.POINTS_TITLES[-1]
                
                rankings.append({
                    'rank': rank,
                    'user_id': user_points.user_id,
                    'user_name': user.borrower_name,
                    'points': user_points.total_earned,  # 显示累计积分
                    'current_points': user_points.points,  # 当前剩余积分（备用）
                    'total_earned': user_points.total_earned,
                    'avatar': user.avatar,
                    'title': title
                })
        
        return rankings
    
    def get_user_points_rank(self, user_id: str) -> Dict[str, Any]:
        """获取用户累计积分排名"""
        all_points = self.db.get_all_user_points()
        # 按累计积分排序
        sorted_points = sorted(all_points, key=lambda x: x.total_earned, reverse=True)

        user_points = self.db.get_user_points(user_id)
        if not user_points:
            return {'rank': None, 'points': 0, 'total_earned': 0}

        # 计算排名
        rank = 1
        for up in sorted_points:
            if up.user_id == user_id:
                break
            rank += 1

        return {
            'rank': rank,
            'points': user_points.total_earned,  # 返回累计积分用于显示
            'current_points': user_points.points,  # 当前剩余积分
            'total_earned': user_points.total_earned,
            'total_users': len(sorted_points)
        }
    
    # ========== 业务场景积分操作 ==========
    
    def first_login_reward(self, user_id: str) -> Dict[str, Any]:
        """首次登录奖励"""
        # 检查是否已经有首次登录积分记录
        records = self.db.get_points_records(user_id)
        
        for record in records:
            # 检查是否已经有首次登录记录
            trans_type = record.transaction_type
            if isinstance(trans_type, PointsTransactionType):
                if trans_type == PointsTransactionType.FIRST_LOGIN:
                    return {'success': False, 'message': '已经领取过首次登录奖励'}
            elif isinstance(trans_type, str):
                if trans_type == '首次登录':
                    return {'success': False, 'message': '已经领取过首次登录奖励'}
        
        # 没有首次登录记录，发放首次登录奖励
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['FIRST_LOGIN'],
            transaction_type=PointsTransactionType.FIRST_LOGIN,
            description='首次登录系统奖励'
        )
    
    def borrow_reward(self, user_id: str, device_name: str, device_id: str) -> Dict[str, Any]:
        """借用设备奖励"""
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['BORROW'],
            transaction_type=PointsTransactionType.BORROW,
            description=f'借用设备: {device_name}',
            related_id=device_id
        )
    
    def return_reward(self, user_id: str, device_name: str, device_id: str) -> Dict[str, Any]:
        """归还设备奖励"""
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['RETURN'],
            transaction_type=PointsTransactionType.RETURN,
            description=f'归还设备: {device_name}',
            related_id=device_id
        )
    
    def overdue_penalty(self, user_id: str, device_name: str, device_id: str) -> Dict[str, Any]:
        """逾期归还惩罚"""
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['OVERDUE'],
            transaction_type=PointsTransactionType.OVERDUE,
            description=f'逾期归还设备: {device_name}',
            related_id=device_id
        )
    
    def create_bounty_cost(self, user_id: str, bounty_title: str, bounty_id: str) -> Dict[str, Any]:
        """发布悬赏扣除积分"""
        # 检查积分是否足够
        user_points = self.get_or_create_user_points(user_id)
        if user_points.points < 10:
            return {'success': False, 'message': '积分不足，发布悬赏需要10积分'}
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['CREATE_BOUNTY'],
            transaction_type=PointsTransactionType.CREATE_BOUNTY,
            description=f'发布悬赏: {bounty_title}',
            related_id=bounty_id
        )
    
    def complete_bounty_reward(self, user_id: str, bounty_title: str, bounty_id: str, reward_points: int) -> Dict[str, Any]:
        """完成悬赏获得积分"""
        return self.add_points(
            user_id=user_id,
            points=reward_points,
            transaction_type=PointsTransactionType.COMPLETE_BOUNTY,
            description=f'完成悬赏: {bounty_title}',
            related_id=bounty_id
        )
    
    def receive_bounty_reward(self, user_id: str, bounty_title: str, bounty_id: str, reward_points: int) -> Dict[str, Any]:
        """获得悬赏奖励（发榜人确认后）"""
        return self.add_points(
            user_id=user_id,
            points=reward_points,
            transaction_type=PointsTransactionType.RECEIVE_BOUNTY,
            description=f'获得悬赏奖励: {bounty_title}',
            related_id=bounty_id
        )
    
    # ========== 新的积分获取方式 ==========
    
    def check_daily_login(self, user_id: str) -> bool:
        """检查今天是否已经登录过"""
        today = datetime.now().strftime('%Y-%m-%d')
        records = self.db.get_points_records(user_id)
        for record in records:
            # 检查是否是每日登录类型
            trans_type = record.transaction_type
            is_daily_login = False
            if isinstance(trans_type, PointsTransactionType):
                is_daily_login = (trans_type == PointsTransactionType.DAILY_LOGIN)
            elif isinstance(trans_type, str):
                is_daily_login = (trans_type == '每日登录')
            
            if is_daily_login:
                # 检查是否是今天
                record_date = None
                if record.create_time:
                    if isinstance(record.create_time, datetime):
                        record_date = record.create_time.strftime('%Y-%m-%d')
                    elif isinstance(record.create_time, str):
                        # 如果是字符串，取前10位
                        record_date = record.create_time[:10]
                if record_date == today:
                    return True
        return False
    
    def daily_login_reward(self, user_id: str) -> Dict[str, Any]:
        """每日登录奖励"""
        if self.check_daily_login(user_id):
            return {'success': False, 'message': '今天已经领取过登录奖励'}
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['DAILY_LOGIN'],
            transaction_type=PointsTransactionType.DAILY_LOGIN,
            description='每日登录奖励'
        )
    
    def ranking_reward(self, user_id: str, rank: int, ranking_type: str) -> Dict[str, Any]:
        """排行榜奖励"""
        if rank < 1 or rank > 10:
            return {'success': False, 'message': '排名不在奖励范围内'}
        
        # 检查今天是否已经获得过该排行榜奖励
        today = datetime.now().strftime('%Y-%m-%d')
        records = self.db.get_points_records(user_id)
        for record in records:
            # 检查是否是排行榜奖励类型
            trans_type = record.transaction_type
            is_ranking_reward = False
            if isinstance(trans_type, PointsTransactionType):
                is_ranking_reward = (trans_type == PointsTransactionType.RANKING_REWARD)
            elif isinstance(trans_type, str):
                is_ranking_reward = (trans_type == '排行榜奖励')
            
            if is_ranking_reward:
                # 检查是否是今天
                record_date = None
                if record.create_time:
                    if isinstance(record.create_time, datetime):
                        record_date = record.create_time.strftime('%Y-%m-%d')
                    elif isinstance(record.create_time, str):
                        record_date = record.create_time[:10]
                
                if record_date == today and ranking_type in record.description:
                    return {'success': False, 'message': '今天已经获得过该排行榜奖励'}
        
        points = self.RANKING_REWARDS.get(rank, 10)
        return self.add_points(
            user_id=user_id,
            points=points,
            transaction_type=PointsTransactionType.RANKING_REWARD,
            description=f'{ranking_type}第{rank}名奖励',
            related_id=str(rank)
        )
    
    def like_reward(self, user_id: str) -> Dict[str, Any]:
        """点赞奖励"""
        # 检查今天点赞次数
        today = datetime.now().strftime('%Y-%m-%d')
        records = self.db.get_points_records(user_id)
        like_count = 0
        for record in records:
            if record.transaction_type == PointsTransactionType.LIKE:
                if record.create_time and record.create_time.strftime('%Y-%m-%d') == today:
                    like_count += 1
        
        if like_count >= 5:
            return {'success': False, 'message': '今天点赞奖励次数已达上限（5次）'}
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['LIKE'],
            transaction_type=PointsTransactionType.LIKE,
            description=f'点赞奖励 ({like_count + 1}/5)'
        )
    
    def search_reward(self, user_id: str) -> Dict[str, Any]:
        """搜索奖励"""
        # 检查今天是否已经获得过搜索奖励
        today = datetime.now().strftime('%Y-%m-%d')
        records = self.db.get_points_records(user_id)
        for record in records:
            if record.transaction_type == PointsTransactionType.SEARCH:
                if record.create_time and record.create_time.strftime('%Y-%m-%d') == today:
                    return {'success': False, 'message': '今天已经获得过搜索奖励'}
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['SEARCH'],
            transaction_type=PointsTransactionType.SEARCH,
            description='首页搜索奖励'
        )
    
    def report_reward(self, user_id: str, report_type: str, device_name: str = '') -> Dict[str, Any]:
        """报备奖励（我已找到、我已修好、损坏报备、丢失报备）"""
        type_map = {
            'found': (PointsTransactionType.REPORT_FOUND, 'REPORT_FOUND', '我已找到'),
            'fixed': (PointsTransactionType.REPORT_FIXED, 'REPORT_FIXED', '我已修好'),
            'damaged': (PointsTransactionType.REPORT_DAMAGED, 'REPORT_DAMAGED', '损坏报备'),
            'lost': (PointsTransactionType.REPORT_LOST, 'REPORT_LOST', '丢失报备'),
        }
        
        if report_type not in type_map:
            return {'success': False, 'message': '未知的报备类型'}
        
        trans_type, rule_key, type_name = type_map[report_type]
        
        # 检查今天该类型报备是否已获得过奖励
        today = datetime.now().strftime('%Y-%m-%d')
        records = self.db.get_points_records(user_id)
        for record in records:
            if record.transaction_type == trans_type:
                if record.create_time and record.create_time.strftime('%Y-%m-%d') == today:
                    return {'success': False, 'message': f'今天已经获得过{type_name}奖励'}
        
        desc = f'{type_name}'
        if device_name:
            desc += f': {device_name}'
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES[rule_key],
            transaction_type=trans_type,
            description=desc
        )
    
    def transfer_reward(self, user_id: str, device_name: str = '') -> Dict[str, Any]:
        """转借奖励"""
        desc = '转借设备'
        if device_name:
            desc += f': {device_name}'
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['TRANSFER'],
            transaction_type=PointsTransactionType.TRANSFER,
            description=desc
        )
    
    def renew_reward(self, user_id: str, device_name: str = '') -> Dict[str, Any]:
        """续期奖励"""
        desc = '续期'
        if device_name:
            desc += f': {device_name}'
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['RENEW'],
            transaction_type=PointsTransactionType.RENEW,
            description=desc
        )
    
    def reserve_reward(self, user_id: str, device_name: str = '') -> Dict[str, Any]:
        """预约奖励"""
        desc = '预约设备'
        if device_name:
            desc += f': {device_name}'
        
        return self.add_points(
            user_id=user_id,
            points=self.POINTS_RULES['RESERVE'],
            transaction_type=PointsTransactionType.RESERVE,
            description=desc
        )


# 全局积分服务实例
points_service = PointsService()
