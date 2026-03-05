# -*- coding: utf-8 -*-
"""
Celery 异步任务配置
"""
import os
from celery import Celery
from kombu import Exchange, Queue

# Redis 配置
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
REDIS_DB = os.environ.get('REDIS_DB', '0')

# Broker 和 Backend 配置
BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
BACKEND_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

# 创建 Celery 应用
celery_app = Celery(
    'device_management',
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=[
        'common.tasks.email_tasks',
        'common.tasks.points_tasks',
        'common.tasks.maintenance_tasks',
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,

    # 任务执行设置
    task_track_started=True,
    task_time_limit=3600,  # 任务硬超时时间（秒）
    task_soft_time_limit=3000,  # 任务软超时时间（秒）

    # 结果后端设置
    result_backend=BACKEND_URL,
    result_expires=3600,  # 结果过期时间（秒）
    result_extended=True,

    # Worker 设置
    worker_prefetch_multiplier=4,  # 每个worker预取的任务数
    worker_max_tasks_per_child=1000,  # 每个worker进程执行的最大任务数

    # 队列配置
    task_default_queue='default',
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('email', Exchange('email'), routing_key='email'),
        Queue('points', Exchange('points'), routing_key='points'),
        Queue('maintenance', Exchange('maintenance'), routing_key='maintenance'),
    ),
    task_routes={
        'common.tasks.email_tasks.*': {'queue': 'email'},
        'common.tasks.points_tasks.*': {'queue': 'points'},
        'common.tasks.maintenance_tasks.*': {'queue': 'maintenance'},
    },

    # 任务重试设置
    task_default_retry_delay=60,  # 默认重试延迟（秒）
    task_max_retries=3,  # 最大重试次数

    # 并发设置
    worker_concurrency=4,  # worker并发数
)


def init_celery():
    """初始化 Celery 配置"""
    print(f"✓ Celery 配置已加载")
    print(f"  - Broker: {BROKER_URL}")
    print(f"  - Backend: {BACKEND_URL}")
    return celery_app


if __name__ == '__main__':
    init_celery()
