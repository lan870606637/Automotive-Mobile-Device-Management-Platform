# -*- coding: utf-8 -*-
"""
缓存管理器
提供内存缓存机制，避免频繁的数据库查询
"""
import time
import threading
from typing import Any, Optional, Callable
from functools import wraps


class CacheManager:
    """缓存管理器（单例模式）"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_cache()
        return cls._instance

    def _init_cache(self):
        """初始化缓存"""
        self._cache = {}
        self._cache_lock = threading.RLock()
        self._default_ttl = 60  # 默认缓存时间60秒

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        :param key: 缓存键
        :return: 缓存值，如果不存在或已过期则返回None
        """
        with self._cache_lock:
            if key not in self._cache:
                return None

            item = self._cache[key]
            if item['expire_time'] < time.time():
                # 缓存已过期，删除
                del self._cache[key]
                return None

            return item['value']

    def set(self, key: str, value: Any, ttl: int = None):
        """
        设置缓存值
        :param key: 缓存键
        :param value: 缓存值
        :param ttl: 过期时间（秒），默认60秒
        """
        if ttl is None:
            ttl = self._default_ttl

        with self._cache_lock:
            self._cache[key] = {
                'value': value,
                'expire_time': time.time() + ttl,
                'create_time': time.time()
            }

    def delete(self, key: str):
        """
        删除缓存
        :param key: 缓存键
        """
        with self._cache_lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """清空所有缓存"""
        with self._cache_lock:
            self._cache.clear()

    def clear_pattern(self, pattern: str):
        """
        清空匹配模式的缓存
        :param pattern: 匹配模式（简单的字符串包含匹配）
        """
        with self._cache_lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        with self._cache_lock:
            total = len(self._cache)
            expired = sum(1 for item in self._cache.values() if item['expire_time'] < time.time())
            return {
                'total_keys': total,
                'expired_keys': expired,
                'valid_keys': total - expired
            }

    def cached(self, ttl: int = 60, key_prefix: str = None):
        """
        缓存装饰器
        :param ttl: 缓存过期时间（秒）
        :param key_prefix: 缓存键前缀
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = key_prefix or func.__name__
                if args:
                    cache_key += f":{str(args)}"
                if kwargs:
                    cache_key += f":{str(sorted(kwargs.items()))}"

                # 尝试从缓存获取
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # 执行函数
                result = func(*args, **kwargs)

                # 缓存结果
                self.set(cache_key, result, ttl)

                return result
            return wrapper
        return decorator


# 全局缓存实例
cache_manager = CacheManager()


class DataCache:
    """数据缓存类 - 专门用于缓存业务数据"""

    # 分级缓存TTL配置（秒）
    CACHE_TTL = {
        'devices': 180,      # 设备列表：3分钟（数据变化较频繁）
        'users': 300,        # 用户列表：5分钟（数据变化较少）
        'records': 60,       # 记录列表：1分钟（数据变化频繁）
        'statistics': 300,   # 统计数据：5分钟（计算成本高）
        'device_single': 120, # 单个设备：2分钟
    }

    def __init__(self):
        self.cache = cache_manager
        self._data_versions = {}
        self._version_lock = threading.Lock()

    def _get_version_key(self, data_type: str) -> str:
        """获取版本键"""
        return f"version:{data_type}"

    def _increment_version(self, data_type: str):
        """增加数据版本号"""
        with self._version_lock:
            version_key = self._get_version_key(data_type)
            current_version = self._data_versions.get(version_key, 0)
            self._data_versions[version_key] = current_version + 1

    def get_data_version(self, data_type: str) -> int:
        """获取数据版本号"""
        version_key = self._get_version_key(data_type)
        return self._data_versions.get(version_key, 0)

    def get_cached_devices(self, device_type: str = None, force_refresh: bool = False) -> list:
        """
        获取缓存的设备列表
        :param device_type: 设备类型过滤
        :param force_refresh: 强制刷新缓存
        :return: 设备列表
        """
        cache_key = f"devices:{device_type or 'all'}"

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # 从数据库加载
        from common.db_store import DatabaseStore
        db = DatabaseStore()
        devices = db.get_all_devices(device_type)

        # 转换为字典列表以便缓存
        devices_data = [device.to_dict() if hasattr(device, 'to_dict') else device for device in devices]

        # 缓存3分钟（使用分级缓存TTL）
        self.cache.set(cache_key, devices_data, ttl=self.CACHE_TTL['devices'])

        return devices_data

    def invalidate_devices_cache(self, device_type: str = None):
        """
        使设备缓存失效
        :param device_type: 特定设备类型，None表示所有设备缓存
        """
        if device_type:
            self.cache.delete(f"devices:{device_type}")
        else:
            self.cache.clear_pattern("devices:")
        self._increment_version('devices')

    def get_cached_users(self, force_refresh: bool = False) -> list:
        """
        获取缓存的用户列表
        :param force_refresh: 强制刷新缓存
        :return: 用户列表
        """
        cache_key = "users:all"

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # 从数据库加载
        from common.db_store import DatabaseStore
        db = DatabaseStore()
        users = db.get_all_users()

        # 转换为字典列表
        users_data = [user.to_dict() if hasattr(user, 'to_dict') else user for user in users]

        # 缓存5分钟（使用分级缓存TTL）
        self.cache.set(cache_key, users_data, ttl=self.CACHE_TTL['users'])

        return users_data

    def invalidate_users_cache(self):
        """使用户缓存失效"""
        self.cache.delete("users:all")
        self.cache.clear_pattern("users:page:")
        self._increment_version('users')

    def get_cached_users_paginated(self, page: int = 1, per_page: int = 20, search: str = None, force_refresh: bool = False) -> dict:
        """
        获取缓存的分页用户列表
        :param page: 页码
        :param per_page: 每页数量
        :param search: 搜索关键词
        :param force_refresh: 强制刷新缓存
        :return: 分页用户数据
        """
        cache_key = f"users:page:{page}:{per_page}:{search or 'all'}"

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # 从数据库加载
        from common.db_store import DatabaseStore
        db = DatabaseStore()
        result = db.get_users_paginated(page=page, per_page=per_page, search=search)

        # 缓存1分钟（使用分级缓存TTL）
        self.cache.set(cache_key, result, ttl=self.CACHE_TTL['records'])

        return result

    def get_cached_records(self, limit: int = None, force_refresh: bool = False) -> list:
        """
        获取缓存的记录列表
        :param limit: 限制数量
        :param force_refresh: 强制刷新缓存
        :return: 记录列表
        """
        cache_key = f"records:{limit or 'all'}"

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # 从数据库加载
        from common.db_store import DatabaseStore
        db = DatabaseStore()
        records = db.get_all_records(limit)

        # 转换为字典列表
        records_data = [record.to_dict() if hasattr(record, 'to_dict') else record for record in records]

        # 缓存1分钟（使用分级缓存TTL）
        self.cache.set(cache_key, records_data, ttl=self.CACHE_TTL['records'])

        return records_data

    def invalidate_records_cache(self):
        """使记录缓存失效"""
        self.cache.clear_pattern("records:")
        self._increment_version('records')

    def get_device_by_id_cached(self, device_id: str, force_refresh: bool = False) -> Optional[dict]:
        """
        获取缓存的单个设备
        :param device_id: 设备ID
        :param force_refresh: 强制刷新缓存
        :return: 设备数据
        """
        cache_key = f"device:{device_id}"

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # 从数据库加载
        from common.db_store import DatabaseStore
        db = DatabaseStore()
        device = db.get_device_by_id(device_id)

        if device:
            device_data = device.to_dict() if hasattr(device, 'to_dict') else device
            # 缓存2分钟（使用分级缓存TTL）
            self.cache.set(cache_key, device_data, ttl=self.CACHE_TTL['device_single'])
            return device_data

        return None

    def invalidate_device_cache(self, device_id: str):
        """
        使单个设备缓存失效
        :param device_id: 设备ID
        """
        self.cache.delete(f"device:{device_id}")
        self.invalidate_devices_cache()

    def clear_all_cache(self):
        """清空所有缓存"""
        self.cache.clear()
        with self._version_lock:
            self._data_versions.clear()


# 全局数据缓存实例
data_cache = DataCache()


def cached(ttl: int = 60, key_prefix: str = None):
    """
    缓存装饰器快捷方式
    :param ttl: 缓存过期时间（秒）
    :param key_prefix: 缓存键前缀
    """
    return cache_manager.cached(ttl=ttl, key_prefix=key_prefix)
