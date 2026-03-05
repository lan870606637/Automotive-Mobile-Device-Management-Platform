# -*- coding: utf-8 -*-
"""
积分相关异步任务
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from celery import shared_task
from datetime import datetime, timedelta


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_daily_rankings_async(self):
    """
    异步处理每日排行榜
    计算排行榜并发放奖励
    """
    try:
        from common.api_client import api_client
        from common.points_service import points_service
        from common.models import PointsTransactionType

        print("开始处理每日排行榜...")

        # 获取排行榜
        rankings = points_service.get_points_rankings(limit=10)

        # 为前十名发放奖励
        for rank_data in rankings:
            rank = rank_data['rank']
            user_id = rank_data['user_id']

            # 获取奖励积分
            reward_points = points_service.RANKING_REWARDS.get(rank, 0)

            if reward_points > 0:
                # 发放奖励
                result = points_service.add_points(
                    user_id=user_id,
                    points=reward_points,
                    transaction_type=PointsTransactionType.RANKING_REWARD,
                    description=f'每日排行榜第{rank}名奖励',
                    related_id=''
                )

                if result.get('success'):
                    print(f"✓ 用户 {user_id} 获得排行榜第{rank}名奖励: {reward_points}积分")
                else:
                    print(f"✗ 用户 {user_id} 排行榜奖励发放失败: {result.get('message')}")

        print("每日排行榜处理完成")
        return {'success': True, 'message': '排行榜处理完成', 'processed': len(rankings)}

    except Exception as e:
        print(f"✗ 处理排行榜时发生错误: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def add_points_async(self, user_id: str, points: int, transaction_type: str,
                     description: str = "", related_id: str = ""):
    """
    异步添加积分
    :param user_id: 用户ID
    :param points: 积分（正数为增加，负数为扣除）
    :param transaction_type: 交易类型
    :param description: 描述
    :param related_id: 相关记录ID
    """
    try:
        from common.points_service import points_service
        from common.models import PointsTransactionType

        # 转换交易类型
        trans_type = PointsTransactionType(transaction_type)

        result = points_service.add_points(
            user_id=user_id,
            points=points,
            transaction_type=trans_type,
            description=description,
            related_id=related_id
        )

        return result

    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_first_login_reward_async(self, user_id: str):
    """
    异步处理首次登录奖励
    :param user_id: 用户ID
    """
    try:
        from common.points_service import points_service

        result = points_service.first_login_reward(user_id)
        return result

    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_daily_login_reward_async(self, user_id: str):
    """
    异步处理每日登录奖励
    :param user_id: 用户ID
    """
    try:
        from common.points_service import points_service

        result = points_service.daily_login_reward(user_id)
        return result

    except Exception as e:
        raise self.retry(exc=e)
