# -*- coding: utf-8 -*-
"""
数据库操作模块
仅支持MySQL数据库
使用连接池优化性能
"""
import os
import threading
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, Admin, Notification, Announcement, UserLike, Reservation, UserPoints, PointsRecord, Bounty, ShopItem, UserInventory, AdminOperationLog
from .models import DeviceStatus, DeviceType, OperationType, ReservationStatus, PointsTransactionType, BountyStatus, ShopItemType, ShopItemSource

# 导入配置
from .config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

# 全局线程锁，用于写操作同步（细粒度锁，按表分锁）
_db_locks = {
    'devices': threading.Lock(),
    'users': threading.Lock(),
    'records': threading.Lock(),
    'reservations': threading.Lock(),
    'points': threading.Lock(),
    'default': threading.Lock()
}

# 数据库初始化标志，确保只执行一次
_db_initialized = False
_db_init_lock = threading.Lock()

# 导入pymysql
import pymysql
from pymysql.cursors import DictCursor
# 让pymysql兼容MySQLdb接口
pymysql.install_as_MySQLdb()

# 导入连接池
from dbutils.pooled_db import PooledDB

# 创建连接池（应用启动时初始化）
_db_pool = None

def init_db_pool():
    """初始化数据库连接池"""
    global _db_pool
    if _db_pool is None:
        _db_pool = PooledDB(
            creator=pymysql,
            maxconnections=100,     # 最大连接数（支持100并发）
            mincached=10,           # 最小空闲连接
            maxcached=20,           # 最大空闲连接
            maxshared=0,            # 最大共享连接数（0表示不共享）
            blocking=True,          # 连接池满时阻塞等待
            maxusage=None,          # 连接最大使用次数（None表示无限制）
            setsession=[],          # 会话设置
            ping=1,                 # 检查连接是否有效（1表示每次获取时检查）
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False,
            use_unicode=True
        )
        print("✓ 数据库连接池已初始化")
    return _db_pool

def get_db_pool():
    """获取连接池实例"""
    global _db_pool
    if _db_pool is None:
        return init_db_pool()
    return _db_pool


def get_mysql_connection():
    """获取MySQL连接（从连接池）"""
    pool = get_db_pool()
    return pool.connection()


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器（从连接池）"""
    conn = None
    try:
        conn = get_mysql_connection()
        yield conn
    finally:
        if conn:
            conn.close()  # 连接池的close实际上是归还连接到池


@contextmanager
def get_db_transaction(table_name='default'):
    """获取数据库事务上下文管理器（带细粒度锁保护）"""
    lock = _db_locks.get(table_name, _db_locks['default'])
    with lock:
        conn = get_mysql_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e


def row_to_dict(row) -> Dict[str, Any]:
    """将数据库行转换为字典"""
    return row


def safe_str(val):
    """安全字符串转换"""
    if val is None:
        return ''
    return str(val)


def parse_datetime(val) -> Optional[datetime]:
    """解析日期时间"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        # 处理带微秒的格式
        for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
            try:
                return datetime.strptime(val, fmt)
            except:
                continue
    return None


def format_datetime(val) -> Optional[str]:
    """将datetime格式化为数据库字符串"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, str):
        return val
    return None


def escape_percent(val):
    """转义字符串中的 % 字符，防止 pymysql 格式化错误"""
    if val is None:
        return None
    if isinstance(val, str):
        # 将 % 替换为 %% 以正确转义
        return val.replace('%', '%%')
    return val


def init_database():
    """初始化数据库，创建必要的表（只执行一次）"""
    global _db_initialized

    with _db_init_lock:
        if _db_initialized:
            return

        # MySQL表已经通过init_mysql.py创建
        # 检查并添加 borrower_id 列（如果不存在）
        _migrate_mysql_add_borrower_id()
        # 检查并添加 avatar 列（如果不存在）
        _migrate_mysql_add_avatar()
        # 检查并添加 signature 列（如果不存在）
        _migrate_mysql_add_signature()
        # 检查并添加 phone 列（如果不存在）
        _migrate_mysql_add_phone()
        # 检查并添加 asset_number 和 purchase_amount 列（如果不存在）
        _migrate_mysql_add_asset_fields()
        # 检查并添加 custodian_id 列（如果不存在）
        _migrate_mysql_add_custodian_id()
        # 检查并添加 previous_status 列（如果不存在）
        _migrate_mysql_add_previous_status()
        # 创建 reservations 表
        _migrate_mysql_create_reservations()
        # 创建邮件发送记录表
        _migrate_mysql_create_email_logs()
        # 创建积分相关表
        _migrate_mysql_create_points_tables()
        # 创建悬赏表
        _migrate_mysql_create_bounties_table()
        # 创建积分商城相关表
        _migrate_mysql_create_shop_tables()
        # 添加用户装扮字段
        _migrate_mysql_add_user_equip_fields()
        # 添加用户鼠标皮肤字段
        _migrate_mysql_add_user_cursor_field()
        # 创建每日转盘相关表
        _migrate_mysql_create_wheel_tables()
        # 检查并添加 operation_logs 表的 source 列
        _migrate_mysql_add_operation_log_source()
        # 创建后台管理操作日志表
        _migrate_mysql_create_admin_operation_logs_table()

        _db_initialized = True
        print("✓ 数据库初始化完成")


def _migrate_mysql_add_borrower_id():
    """MySQL: 检查并添加 borrower_id 列"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT borrower_id FROM devices LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE devices ADD COLUMN borrower_id VARCHAR(64)")
                conn.commit()
                print("✓ MySQL: 已添加 borrower_id 列到 devices 表")
    except Exception as e:
        print(f"⚠ MySQL 迁移警告: {e}")


def _migrate_mysql_add_avatar():
    """MySQL: 检查并添加 avatar 列到 users 表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT avatar FROM users LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE users ADD COLUMN avatar VARCHAR(500) DEFAULT ''")
                conn.commit()
                print("✓ MySQL: 已添加 avatar 列到 users 表")
    except Exception as e:
        print(f"⚠ MySQL avatar 迁移警告: {e}")


def _migrate_mysql_add_signature():
    """MySQL: 检查并添加 signature 列到 users 表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT signature FROM users LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE users ADD COLUMN signature VARCHAR(255) DEFAULT ''")
                conn.commit()
                print("✓ MySQL: 已添加 signature 列到 users 表")
    except Exception as e:
        print(f"⚠ MySQL signature 迁移警告: {e}")


def _migrate_mysql_add_phone():
    """MySQL: 检查并添加 phone 列到 users 表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT phone FROM users LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT ''")
                conn.commit()
                print("✓ MySQL: 已添加 phone 列到 users 表")
    except Exception as e:
        print(f"⚠ MySQL phone 迁移警告: {e}")


def _migrate_mysql_add_asset_fields():
    """MySQL: 检查并添加 asset_number 和 purchase_amount 列到 devices 表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT asset_number FROM devices LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE devices ADD COLUMN asset_number VARCHAR(100)")
                conn.commit()
                print("✓ MySQL: 已添加 asset_number 列到 devices 表")

            try:
                cursor.execute("SELECT purchase_amount FROM devices LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE devices ADD COLUMN purchase_amount DECIMAL(10,2) DEFAULT 0")
                conn.commit()
                print("✓ MySQL: 已添加 purchase_amount 列到 devices 表")
    except Exception as e:
        print(f"⚠ MySQL asset fields 迁移警告: {e}")


def _migrate_mysql_add_custodian_id():
    """MySQL: 检查并添加 custodian_id 列到 devices 表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT custodian_id FROM devices LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE devices ADD COLUMN custodian_id VARCHAR(64)")
                conn.commit()
                print("✓ MySQL: 已添加 custodian_id 列到 devices 表")
    except Exception as e:
        print(f"⚠ MySQL custodian_id 迁移警告: {e}")


def _migrate_mysql_add_previous_status():
    """MySQL: 检查并添加 previous_status 列到 devices 表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT previous_status FROM devices LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE devices ADD COLUMN previous_status VARCHAR(32)")
                conn.commit()
                print("✓ MySQL: 已添加 previous_status 列到 devices 表")
    except Exception as e:
        print(f"⚠ MySQL previous_status 迁移警告: {e}")


def _migrate_mysql_create_reservations():
    """MySQL: 创建 reservations 表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reservations (
                    id VARCHAR(64) PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL,
                    device_type VARCHAR(32) NOT NULL,
                    device_name VARCHAR(255) NOT NULL,
                    reserver_id VARCHAR(64) NOT NULL,
                    reserver_name VARCHAR(255) NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    custodian_approved TINYINT DEFAULT 0,
                    custodian_approved_at DATETIME,
                    borrower_approved TINYINT DEFAULT 0,
                    borrower_approved_at DATETIME,
                    custodian_notified TINYINT DEFAULT 0,
                    borrower_notified TINYINT DEFAULT 0,
                    cancelled_by VARCHAR(64),
                    cancelled_at DATETIME,
                    cancel_reason VARCHAR(500),
                    rejected_by VARCHAR(64),
                    rejected_at DATETIME,
                    converted_to_borrow TINYINT DEFAULT 0,
                    converted_at DATETIME,
                    custodian_id VARCHAR(64),
                    current_borrower_id VARCHAR(64),
                    current_borrower_name VARCHAR(255),
                    reason VARCHAR(500),
                    INDEX idx_device (device_id, device_type),
                    INDEX idx_reserver (reserver_id),
                    INDEX idx_status (status),
                    INDEX idx_time (start_time, end_time)
                )
            ''')
            conn.commit()
            print("✓ MySQL: 已创建 reservations 表")
    except Exception as e:
        print(f"⚠ MySQL reservations 表迁移警告: {e}")


def _migrate_mysql_create_email_logs():
    """MySQL: 创建邮件发送记录表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_logs (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    user_email VARCHAR(255) NOT NULL,
                    email_type VARCHAR(32) NOT NULL,
                    related_id VARCHAR(64),
                    related_type VARCHAR(32),
                    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(16) DEFAULT 'sent',
                    content TEXT,
                    INDEX idx_user (user_id),
                    INDEX idx_type (email_type),
                    INDEX idx_sent_at (sent_at)
                )
            ''')
            conn.commit()
            print("✓ MySQL: 已创建 email_logs 表")
    except Exception as e:
        print(f"⚠ MySQL email_logs 表迁移警告: {e}")


class DatabaseStore:
    """数据库存储类"""
    
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        init_database()
    
    # ========== 设备相关操作 ==========
    
    def get_all_devices(self, device_type: str = None) -> List[Device]:
        """获取所有设备"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if device_type:
                cursor.execute(
                    "SELECT * FROM devices WHERE device_type = %s AND is_deleted = 0",
                    (device_type,)
                )
            else:
                cursor.execute("SELECT * FROM devices WHERE is_deleted = 0")
            
            rows = cursor.fetchall()
            return [Device.from_dict(row_to_dict(row)) for row in rows]
    
    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """根据ID获取设备"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM devices WHERE id = %s AND is_deleted = 0",
                (device_id,)
            )
            row = cursor.fetchone()
            if row:
                return Device.from_dict(row_to_dict(row))
            return None
    
    def save_device(self, device: Device) -> bool:
        """保存设备"""
        import traceback
        with get_db_transaction('devices') as conn:
            cursor = conn.cursor()

            # 检查设备是否存在
            cursor.execute(
                "SELECT id FROM devices WHERE id = %s",
                (device.id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                # 更新设备
                sql = """UPDATE devices SET
                    name = %s, device_type = %s, model = %s, cabinet_number = %s,
                    status = %s, remark = %s, jira_address = %s, borrower = %s,
                    borrower_id = %s, custodian_id = %s, phone = %s, borrow_time = %s, location = %s, reason = %s,
                    entry_source = %s, expected_return_date = %s, admin_operator = %s,
                    ship_time = %s, ship_remark = %s, ship_by = %s,
                    pre_ship_borrower = %s, pre_ship_borrow_time = %s,
                    pre_ship_expected_return_date = %s, lost_time = %s,
                    damage_reason = %s, damage_time = %s, previous_borrower = %s, previous_status = %s,
                    sn = %s, system_version = %s, imei = %s, carrier = %s,
                    software_version = %s, hardware_version = %s,
                    project_attribute = %s, connection_method = %s,
                    os_version = %s, os_platform = %s, product_name = %s,
                    screen_orientation = %s, screen_resolution = %s,
                    asset_number = %s, purchase_amount = %s, is_deleted = %s
                    WHERE id = %s
                """

                params = (
                    escape_percent(device.name),
                    device.device_type.value if device.device_type else None,
                    escape_percent(device.model),
                    escape_percent(device.cabinet_number),
                    device.status.value if device.status else None,
                    escape_percent(device.remark),
                    escape_percent(device.jira_address),
                    escape_percent(device.borrower),
                    device.borrower_id,
                    device.custodian_id,
                    escape_percent(device.phone),
                    format_datetime(device.borrow_time),
                    escape_percent(device.location),
                    escape_percent(device.reason),
                    escape_percent(device.entry_source),
                    format_datetime(device.expected_return_date),
                    escape_percent(device.admin_operator),
                    format_datetime(device.ship_time),
                    escape_percent(device.ship_remark),
                    escape_percent(device.ship_by),
                    escape_percent(device.pre_ship_borrower),
                    format_datetime(device.pre_ship_borrow_time),
                    format_datetime(device.pre_ship_expected_return_date),
                    format_datetime(device.lost_time),
                    escape_percent(device.damage_reason),
                    format_datetime(device.damage_time),
                    escape_percent(device.previous_borrower),
                    device.previous_status,
                    escape_percent(device.sn),
                    escape_percent(device.system_version),
                    escape_percent(device.imei),
                    escape_percent(device.carrier),
                    escape_percent(device.software_version),
                    escape_percent(device.hardware_version),
                    escape_percent(device.project_attribute),
                    escape_percent(device.connection_method),
                    escape_percent(device.os_version),
                    escape_percent(device.os_platform),
                    escape_percent(device.product_name),
                    escape_percent(device.screen_orientation),
                    escape_percent(device.screen_resolution),
                    escape_percent(device.asset_number),
                    device.purchase_amount,
                    1 if device.is_deleted else 0,
                    device.id
                )
                cursor.execute(sql, params)
            else:
                # 插入新设备
                sql = """INSERT INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, borrower, borrower_id, custodian_id, phone, borrow_time, location, reason,
                    entry_source, expected_return_date, admin_operator, ship_time,
                    ship_remark, ship_by, pre_ship_borrower, pre_ship_borrow_time,
                    pre_ship_expected_return_date, lost_time, damage_reason,
                    damage_time, previous_borrower, previous_status, sn, system_version, imei,
                    carrier, software_version, hardware_version, project_attribute,
                    connection_method, os_version, os_platform, product_name,
                    screen_orientation, screen_resolution, asset_number, purchase_amount, is_deleted
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                params = (
                    device.id,
                    escape_percent(device.name),
                    device.device_type.value if device.device_type else None,
                    escape_percent(device.model),
                    escape_percent(device.cabinet_number),
                    device.status.value if device.status else None,
                    escape_percent(device.remark),
                    escape_percent(device.jira_address),
                    escape_percent(device.borrower),
                    device.borrower_id,
                    device.custodian_id,
                    escape_percent(device.phone),
                    format_datetime(device.borrow_time),
                    escape_percent(device.location),
                    escape_percent(device.reason),
                    escape_percent(device.entry_source),
                    format_datetime(device.expected_return_date),
                    escape_percent(device.admin_operator),
                    format_datetime(device.ship_time),
                    escape_percent(device.ship_remark),
                    escape_percent(device.ship_by),
                    escape_percent(device.pre_ship_borrower),
                    format_datetime(device.pre_ship_borrow_time),
                    format_datetime(device.pre_ship_expected_return_date),
                    format_datetime(device.lost_time),
                    escape_percent(device.damage_reason),
                    format_datetime(device.damage_time),
                    escape_percent(device.previous_borrower),
                    device.previous_status,
                    escape_percent(device.sn),
                    escape_percent(device.system_version),
                    escape_percent(device.imei),
                    escape_percent(device.carrier),
                    escape_percent(device.software_version),
                    escape_percent(device.hardware_version),
                    escape_percent(device.project_attribute),
                    escape_percent(device.connection_method),
                    escape_percent(device.os_version),
                    escape_percent(device.os_platform),
                    escape_percent(device.product_name),
                    escape_percent(device.screen_orientation),
                    escape_percent(device.screen_resolution),
                    escape_percent(device.asset_number),
                    device.purchase_amount,
                    1 if device.is_deleted else 0
                )

                # DEBUG: 打印调试信息
                print(f"[DEBUG] save_device - device.id: {device.id}")
                print(f"[DEBUG] save_device - device.name: {device.name}")
                print(f"[DEBUG] save_device - device.remark: {device.remark}")
                print(f"[DEBUG] save_device - device.model: {device.model}")
                print(f"[DEBUG] save_device - params count: {len(params)}")

                try:
                    cursor.execute(sql, params)
                except Exception as e:
                    print(f"[DEBUG] save_device - SQL execute error: {e}")
                    print(f"[DEBUG] save_device - traceback: {traceback.format_exc()}")
                    raise
            
            return True
    
    def delete_device(self, device_id: str) -> bool:
        """软删除设备"""
        with get_db_transaction('devices') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE devices SET is_deleted = 1 WHERE id = %s",
                (device_id,)
            )
            return True

    # ========== 优化的统计查询方法 ==========

    def get_device_statistics(self) -> Dict[str, Any]:
        """获取设备统计信息（使用SQL聚合查询优化）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 总体统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status IN ('在库', '保管中', '流通', '无柜号') THEN 1 ELSE 0 END) as available,
                    SUM(CASE WHEN status = '借出' THEN 1 ELSE 0 END) as borrowed,
                    SUM(CASE WHEN status = '损坏' THEN 1 ELSE 0 END) as damaged,
                    SUM(CASE WHEN status = '丢失' THEN 1 ELSE 0 END) as lost,
                    SUM(CASE WHEN status = '在库' THEN 1 ELSE 0 END) as in_stock,
                    SUM(CASE WHEN status = '保管中' THEN 1 ELSE 0 END) as in_custody,
                    SUM(CASE WHEN status = '无柜号' THEN 1 ELSE 0 END) as no_cabinet,
                    SUM(CASE WHEN status = '流通' THEN 1 ELSE 0 END) as circulating,
                    SUM(CASE WHEN status = '报废' THEN 1 ELSE 0 END) as scrapped,
                    SUM(CASE WHEN status = '已发货' THEN 1 ELSE 0 END) as shipped,
                    SUM(CASE WHEN status = '封存' THEN 1 ELSE 0 END) as sealed
                FROM devices 
                WHERE is_deleted = 0
            """)
            overall_stats = cursor.fetchone()

            # 设备类型统计
            cursor.execute("""
                SELECT 
                    device_type,
                    COUNT(*) as count
                FROM devices 
                WHERE is_deleted = 0
                GROUP BY device_type
            """)
            type_stats = {row['device_type']: row['count'] for row in cursor.fetchall()}

            return {
                'total': overall_stats['total'] or 0,
                'available': overall_stats['available'] or 0,
                'borrowed': overall_stats['borrowed'] or 0,
                'damaged': overall_stats['damaged'] or 0,
                'lost': overall_stats['lost'] or 0,
                'in_stock': overall_stats['in_stock'] or 0,
                'in_custody': overall_stats['in_custody'] or 0,
                'no_cabinet': overall_stats['no_cabinet'] or 0,
                'circulating': overall_stats['circulating'] or 0,
                'scrapped': overall_stats['scrapped'] or 0,
                'shipped': overall_stats['shipped'] or 0,
                'sealed': overall_stats['sealed'] or 0,
                'by_type': type_stats
            }

    def get_overdue_devices(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取逾期设备列表（使用SQL优化查询）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT
                    id,
                    name as device_name,
                    device_type,
                    borrower,
                    borrow_time,
                    expected_return_date,
                    phone,
                    TIMESTAMPDIFF(HOUR, expected_return_date, NOW()) as overdue_hours,
                    TIMESTAMPDIFF(DAY, expected_return_date, NOW()) as overdue_days
                FROM devices
                WHERE status = '借出'
                AND is_deleted = 0
                AND expected_return_date IS NOT NULL
                AND expected_return_date < NOW()
                ORDER BY expected_return_date ASC
            """
            if limit:
                sql += f" LIMIT {limit}"

            cursor.execute(sql)
            rows = cursor.fetchall()

            overdue_devices = []
            for row in rows:
                overdue_devices.append({
                    'id': row['id'],
                    'device_name': row['device_name'],
                    'device_type': row['device_type'],
                    'borrower': row['borrower'] or '未知',
                    'borrow_time': row['borrow_time'].strftime('%Y-%m-%d') if row['borrow_time'] else '',
                    'expect_return_time': row['expected_return_date'].strftime('%Y-%m-%d') if row['expected_return_date'] else '',
                    'overdue_days': row['overdue_days'] or 0,
                    'overdue_hours': row['overdue_hours'] or 0,
                    'phone': row['phone']
                })

            return overdue_devices

    def get_overdue_count(self) -> int:
        """获取逾期设备数量（使用SQL优化查询）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM devices
                WHERE status = '借出'
                AND is_deleted = 0
                AND expected_return_date IS NOT NULL
                AND expected_return_date < NOW()
            """)
            row = cursor.fetchone()
            return row['count'] if row else 0

    def get_today_borrow_return_count(self) -> Dict[str, int]:
        """获取今日借出和归还数量"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN operation_type IN ('借出', '强制借出') THEN 1 ELSE 0 END) as borrow_count,
                    SUM(CASE WHEN operation_type IN ('归还', '强制归还') THEN 1 ELSE 0 END) as return_count
                FROM records 
                WHERE DATE(operation_time) = CURDATE()
            """)
            row = cursor.fetchone()
            return {
                'borrow': row['borrow_count'] or 0,
                'return': row['return_count'] or 0
            }

    def get_recent_records(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的记录（优化版）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    operation_type,
                    device_name,
                    device_type,
                    borrower,
                    operator,
                    operation_time,
                    remark
                FROM records 
                ORDER BY operation_time DESC
                LIMIT %s
            """, (limit,))

            rows = cursor.fetchall()
            records = []
            for row in rows:
                records.append({
                    'action_type': row['operation_type'],
                    'device_name': row['device_name'],
                    'device_type': row['device_type'],
                    'user_name': row['borrower'],
                    'operator': row['operator'],
                    'time': row['operation_time'].strftime('%Y-%m-%d %H:%M') if row['operation_time'] else '',
                    'remarks': row['remark']
                })
            return records

    # ========== 用户相关操作 ==========

    def get_all_users(self) -> List[User]:
        """获取所有用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE is_deleted = 0")
            rows = cursor.fetchall()
            return [User.from_dict(row_to_dict(row)) for row in rows]

    def get_users_paginated(self, page: int = 1, per_page: int = 20, search: str = None) -> Dict[str, Any]:
        """获取分页用户列表（优化版）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            where_clause = "WHERE is_deleted = 0"
            params = []
            if search:
                where_clause += " AND (borrower_name LIKE %s OR email LIKE %s)"
                search_pattern = f"%{search}%"
                params = [search_pattern, search_pattern]

            # 获取总数
            count_sql = f"SELECT COUNT(*) as total FROM users {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['total']

            # 获取分页数据
            offset = (page - 1) * per_page
            sql = f"""
                SELECT id, email, borrower_name, avatar, signature,
                       borrow_count, return_count, is_frozen, is_admin,
                       is_first_login, create_time, phone
                FROM users
                {where_clause}
                ORDER BY create_time DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, params + [per_page, offset])
            rows = cursor.fetchall()

            users_data = []
            for row in rows:
                users_data.append({
                    'id': row['id'],
                    'name': row['borrower_name'],
                    'email': row['email'],
                    'avatar': row['avatar'],
                    'signature': row['signature'],
                    'borrow_count': row['borrow_count'],
                    'return_count': row['return_count'],
                    'is_admin': bool(row['is_admin']),
                    'is_frozen': bool(row['is_frozen']),
                    'is_first_login': bool(row['is_first_login']),
                    'register_time': row['create_time'].strftime('%Y-%m-%d') if row['create_time'] else '-',
                    'phone': row['phone']
                })

            return {
                'users': users_data,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE id = %s AND is_deleted = 0",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return User.from_dict(row_to_dict(row))
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE email = %s AND is_deleted = 0",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return User.from_dict(row_to_dict(row))
            return None
    
    def save_user(self, user: User) -> bool:
        """保存用户"""
        with get_db_transaction('users') as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM users WHERE id = %s",
                (user.id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                sql = """UPDATE users SET
                    email = %s, password = %s, borrower_name = %s, avatar = %s, signature = %s,
                    borrow_count = %s, return_count = %s, is_frozen = %s, is_admin = %s, is_deleted = %s, is_first_login = %s,
                    current_title = %s, current_avatar_frame = %s, current_theme = %s, current_cursor = %s
                    WHERE id = %s
                """
                params = (
                    user.email, user.password, user.borrower_name, user.avatar, user.signature,
                    user.borrow_count, user.return_count,
                    1 if user.is_frozen else 0,
                    1 if user.is_admin else 0,
                    1 if user.is_deleted else 0,
                    1 if user.is_first_login else 0,
                    user.current_title,
                    user.current_avatar_frame,
                    user.current_theme,
                    user.current_cursor,
                    user.id
                )
                cursor.execute(sql, params)
            else:
                sql = """INSERT INTO users (
                    id, email, password, borrower_name, avatar, signature, borrow_count,
                    return_count, is_frozen, is_admin, is_deleted, is_first_login, create_time,
                    current_title, current_avatar_frame, current_theme, current_cursor
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s)
                """
                params = (
                    user.id, user.email, user.password,
                    user.borrower_name, user.avatar, user.signature, user.borrow_count, user.return_count,
                    1 if user.is_frozen else 0,
                    1 if user.is_admin else 0,
                    1 if user.is_first_login else 0,
                    user.current_title,
                    user.current_avatar_frame,
                    user.current_theme,
                    user.current_cursor
                )
                cursor.execute(sql, params)
            
            return True
    
    # ========== 记录相关操作 ==========
    
    def get_all_records(self, limit: int = None) -> List[Record]:
        """获取所有记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if limit:
                cursor.execute(
                    "SELECT * FROM records ORDER BY operation_time DESC LIMIT %s",
                    (limit,)
                )
            else:
                cursor.execute("SELECT * FROM records ORDER BY operation_time DESC")
            rows = cursor.fetchall()
            return [Record.from_dict(row_to_dict(row)) for row in rows]

    def get_records_by_device(self, device_id: str) -> List[Record]:
        """根据设备ID获取记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM records WHERE device_id = %s ORDER BY operation_time DESC",
                (device_id,)
            )
            rows = cursor.fetchall()
            return [Record.from_dict(row_to_dict(row)) for row in rows]
    
    def save_record(self, record: Record) -> bool:
        """保存记录"""
        with get_db_transaction('records') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO records (
                id, device_id, device_name, device_type, operation_type, operator,
                operation_time, borrower, phone, reason, entry_source, remark
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                record.id, record.device_id, record.device_name, record.device_type,
                record.operation_type.value if record.operation_type else None,
                record.operator, format_datetime(record.operation_time),
                record.borrower, record.phone, record.reason,
                record.entry_source, record.remark
            )
            cursor.execute(sql, params)
            return True
    
    # ========== 备注相关操作 ==========
    
    def get_remarks(self, device_id: str = None) -> List[UserRemark]:
        """获取备注"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if device_id:
                cursor.execute(
                    "SELECT * FROM user_remarks WHERE device_id = %s ORDER BY create_time DESC",
                    (device_id,)
                )
            else:
                cursor.execute("SELECT * FROM user_remarks ORDER BY create_time DESC")
            rows = cursor.fetchall()
            return [UserRemark.from_dict(row_to_dict(row)) for row in rows]
    
    def get_remarks_by_device(self, device_id: str) -> List[UserRemark]:
        """根据设备ID获取备注"""
        return self.get_remarks(device_id)
    
    def get_all_remarks(self) -> List[UserRemark]:
        """获取所有备注"""
        return self.get_remarks()
    
    def save_remark(self, remark: UserRemark) -> bool:
        """保存备注"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_remarks (
                id, device_id, device_type, content, creator, create_time, is_inappropriate
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                remark.id, remark.device_id, remark.device_type,
                remark.content, remark.creator, format_datetime(remark.create_time),
                1 if remark.is_inappropriate else 0
            )
            cursor.execute(sql, params)
            return True
    
    # ========== 管理员相关操作 ==========
    
    def get_admin_by_username(self, username: str) -> Optional[Admin]:
        """根据用户名获取管理员"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM admins WHERE username = %s",
                (username,)
            )
            row = cursor.fetchone()
            if row:
                return Admin.from_dict(row_to_dict(row))
            return None
    
    # ========== 通知相关操作 ==========
    
    def get_notifications_by_user(self, user_id: str) -> List[Notification]:
        """获取用户通知"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notifications WHERE user_id = %s ORDER BY create_time DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [Notification.from_dict(row_to_dict(row)) for row in rows]
    
    def save_notification(self, notification: Notification) -> bool:
        """保存通知"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO notifications (
                id, user_id, user_name, title, content, device_name, device_id,
                is_read, create_time, notification_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                notification.id, notification.user_id, notification.user_name,
                notification.title, notification.content, notification.device_name,
                notification.device_id, 1 if notification.is_read else 0,
                format_datetime(notification.create_time), notification.notification_type
            )
            cursor.execute(sql, params)
            return True

    def mark_notification_as_read(self, notification_id: str) -> bool:
        """将通知标记为已读"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = "UPDATE notifications SET is_read = 1 WHERE id = %s"
            params = (notification_id,)
            cursor.execute(sql, params)
            return True
    
    # ========== 公告相关操作 ==========
    
    def get_all_announcements(self, active_only: bool = False) -> List[Announcement]:
        """获取所有公告"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute(
                    "SELECT * FROM announcements WHERE is_active = 1 ORDER BY sort_order DESC, create_time DESC"
                )
            else:
                cursor.execute("SELECT * FROM announcements ORDER BY sort_order DESC, create_time DESC")
            rows = cursor.fetchall()
            return [Announcement.from_dict(row_to_dict(row)) for row in rows]
    
    # ========== 操作日志相关操作 ==========

    def add_operation_log(self, operation: str, device_name: str, operator: str, source: str = "admin") -> bool:
        """添加操作日志"""
        with get_db_transaction('records') as conn:
            cursor = conn.cursor()
            import uuid
            sql = """INSERT INTO operation_logs (
                id, operation_time, operator, operation_content, device_info, source
            ) VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, %s)
            """
            params = (str(uuid.uuid4()), operator, operation, device_name, source)
            cursor.execute(sql, params)
            return True

    def get_all_operation_logs(self) -> List[OperationLog]:
        """获取所有操作日志"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM operation_logs ORDER BY operation_time DESC")
            rows = cursor.fetchall()
            return [OperationLog.from_dict(row_to_dict(row)) for row in rows]
    
    def save_operation_log(self, log: OperationLog) -> bool:
        """保存操作日志"""
        with get_db_transaction('records') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO operation_logs (
                id, operation_time, operator, operation_content, device_info, source
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            params = (
                log.id,
                format_datetime(log.operation_time),
                log.operator,
                log.operation_content,
                log.device_info,
                log.source
            )
            cursor.execute(sql, params)
            return True

    # ========== 后台管理操作日志相关操作 ==========

    def save_admin_operation_log(self, log: AdminOperationLog) -> bool:
        """保存后台管理操作日志"""
        with get_db_transaction('records') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO admin_operation_logs (
                id, operation_time, admin_id, admin_name, action_type, action_name,
                target_type, target_id, target_name, description, ip_address,
                user_agent, request_method, request_path, request_params, result, error_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                log.id,
                format_datetime(log.operation_time),
                log.admin_id,
                log.admin_name,
                log.action_type,
                log.action_name,
                log.target_type,
                log.target_id,
                log.target_name,
                log.description,
                log.ip_address,
                log.user_agent,
                log.request_method,
                log.request_path,
                log.request_params,
                log.result,
                log.error_message
            )
            cursor.execute(sql, params)
            return True

    def get_admin_operation_logs(self, limit: int = 100, offset: int = 0,
                                  admin_id: str = None, action_type: str = None,
                                  target_type: str = None, result: str = None,
                                  start_time: datetime = None, end_time: datetime = None) -> List[AdminOperationLog]:
        """获取后台管理操作日志列表"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            conditions = []
            params = []

            if admin_id:
                conditions.append("admin_id = %s")
                params.append(admin_id)
            if action_type:
                conditions.append("action_type = %s")
                params.append(action_type)
            if target_type:
                conditions.append("target_type = %s")
                params.append(target_type)
            if result:
                conditions.append("result = %s")
                params.append(result)
            if start_time:
                conditions.append("operation_time >= %s")
                params.append(format_datetime(start_time))
            if end_time:
                conditions.append("operation_time <= %s")
                params.append(format_datetime(end_time))

            # 构建SQL
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            sql = f"""
                SELECT * FROM admin_operation_logs
                {where_clause}
                ORDER BY operation_time DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [AdminOperationLog.from_dict(row_to_dict(row)) for row in rows]

    def get_admin_operation_logs_count(self, admin_id: str = None, action_type: str = None,
                                        target_type: str = None, result: str = None,
                                        start_time: datetime = None, end_time: datetime = None) -> int:
        """获取后台管理操作日志总数"""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            conditions = []
            params = []

            if admin_id:
                conditions.append("admin_id = %s")
                params.append(admin_id)
            if action_type:
                conditions.append("action_type = %s")
                params.append(action_type)
            if target_type:
                conditions.append("target_type = %s")
                params.append(target_type)
            if result:
                conditions.append("result = %s")
                params.append(result)
            if start_time:
                conditions.append("operation_time >= %s")
                params.append(format_datetime(start_time))
            if end_time:
                conditions.append("operation_time <= %s")
                params.append(format_datetime(end_time))

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            sql = f"SELECT COUNT(*) as count FROM admin_operation_logs {where_clause}"
            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            return row['count']

    def clear_admin_operation_logs(self, days: int = 90) -> int:
        """清理指定天数之前的后台管理操作日志"""
        from datetime import timedelta
        with get_db_transaction('records') as conn:
            cursor = conn.cursor()
            cutoff_date = datetime.now() - timedelta(days=days)

            sql = """
                DELETE FROM admin_operation_logs
                WHERE operation_time < %s
            """
            cursor.execute(sql, (format_datetime(cutoff_date),))
            return cursor.rowcount

    # ========== 查看记录相关操作 ==========
    
    def get_view_records_by_device(self, device_id: str, limit: int = 20) -> list:
        """根据设备ID获取查看记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM view_records WHERE device_id = %s ORDER BY view_time DESC LIMIT %s",
                (device_id, limit)
            )
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]

    def save_view_record(self, device_id: str, device_type: str, viewer: str) -> bool:
        """添加查看记录"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            import uuid
            sql = """INSERT INTO view_records (
                id, device_id, device_type, viewer, view_time
            ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            """
            params = (str(uuid.uuid4()), device_id, device_type, viewer)
            cursor.execute(sql, params)
            return True
    
    def add_view_record(self, device_id: str, viewer: str) -> bool:
        """添加查看记录（兼容旧接口）"""
        return self.save_view_record(device_id, '', viewer)
    
    # ========== 用户点赞相关操作 ==========
    
    def get_user_likes_to_user(self, user_id: str) -> List[UserLike]:
        """获取用户收到的点赞"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_likes WHERE to_user_id = %s",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [UserLike.from_dict(row_to_dict(row)) for row in rows]
    
    def get_user_likes_by_user(self, from_user_id: str) -> List[UserLike]:
        """获取用户发出的点赞"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_likes WHERE from_user_id = %s",
                (from_user_id,)
            )
            rows = cursor.fetchall()
            return [UserLike.from_dict(row_to_dict(row)) for row in rows]
    
    def save_user_like(self, like: UserLike) -> bool:
        """保存用户点赞"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_likes (
                id, from_user_id, to_user_id, create_date, create_time
            ) VALUES (%s, %s, %s, %s, %s)
            """
            params = (
                like.id, like.from_user_id, like.to_user_id,
                like.create_date, format_datetime(like.create_time)
            )
            cursor.execute(sql, params)
            return True
    
    # ========== 预约相关操作 ==========
    
    def get_reservation_by_id(self, reservation_id: str) -> Optional[Reservation]:
        """根据ID获取预约"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reservations WHERE id = %s",
                (reservation_id,)
            )
            row = cursor.fetchone()
            if row:
                return Reservation.from_dict(row_to_dict(row))
            return None
    
    def get_reservations_by_device(self, device_id: str, device_type: str = None, 
                                   status: str = None, active_only: bool = False) -> List[Reservation]:
        """获取设备的预约列表"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM reservations WHERE device_id = %s"
            params = [device_id]
            
            if device_type:
                sql += " AND device_type = %s"
                params.append(device_type)
            
            if status:
                if isinstance(status, list):
                    placeholders = ','.join(['%s'] * len(status))
                    sql += f" AND status IN ({placeholders})"
                    params.extend(status)
                else:
                    sql += " AND status = %s"
                    params.append(status)
            
            if active_only:
                # 只获取未结束的有效预约（排除已取消、已拒绝、已过期、已转借用的预约）
                sql += " AND end_time > %s AND status NOT IN ('已取消', '已拒绝', '已过期', '已转借用')"
                params.append(format_datetime(datetime.now()))
            
            sql += " ORDER BY start_time ASC"
            
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]

    # ========== 邮件发送记录相关操作 ==========

    def save_email_log(self, user_id: str, user_email: str, email_type: str,
                       related_id: str = None, related_type: str = None,
                       status: str = 'sent', content: str = None) -> bool:
        """保存邮件发送记录"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            email_id = str(uuid.uuid4())
            sent_at = format_datetime(datetime.now())
            
            cursor.execute(
                """INSERT INTO email_logs 
                   (id, user_id, user_email, email_type, related_id, related_type, sent_at, status, content)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (email_id, user_id, user_email, email_type, related_id, related_type, sent_at, status, content)
            )
            return True

    def get_email_logs_by_user(self, user_id: str, email_type: str = None, 
                                limit: int = None) -> List[Dict[str, Any]]:
        """获取用户的邮件发送记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if email_type:
                cursor.execute(
                    """SELECT * FROM email_logs 
                       WHERE user_id = %s AND email_type = %s 
                       ORDER BY sent_at DESC""",
                    (user_id, email_type)
                )
            else:
                cursor.execute(
                    """SELECT * FROM email_logs 
                       WHERE user_id = %s 
                       ORDER BY sent_at DESC""",
                    (user_id,)
                )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                row_dict = row_to_dict(row)
                if limit and len(results) >= limit:
                    break
                results.append(row_dict)
            return results

    def get_last_email_sent_time(self, user_id: str, email_type: str, 
                                  related_id: str = None) -> Optional[datetime]:
        """获取指定类型邮件的最后发送时间"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if related_id:
                cursor.execute(
                    """SELECT sent_at FROM email_logs 
                       WHERE user_id = %s AND email_type = %s AND related_id = %s
                       ORDER BY sent_at DESC LIMIT 1""",
                    (user_id, email_type, related_id)
                )
            else:
                cursor.execute(
                    """SELECT sent_at FROM email_logs 
                       WHERE user_id = %s AND email_type = %s
                       ORDER BY sent_at DESC LIMIT 1""",
                    (user_id, email_type)
                )
            row = cursor.fetchone()
            if row:
                return parse_datetime(row['sent_at'])
            return None

    def has_email_sent_within_hours(self, user_id: str, email_type: str, 
                                     hours: int, related_id: str = None) -> bool:
        """检查指定类型邮件是否在指定小时内已发送"""
        last_sent = self.get_last_email_sent_time(user_id, email_type, related_id)
        if not last_sent:
            return False
        time_diff = datetime.now() - last_sent
        return time_diff.total_seconds() < hours * 3600

    def has_email_sent_today(self, user_id: str, email_type: str, 
                              related_id: str = None) -> bool:
        """检查指定类型邮件今天是否已发送"""
        last_sent = self.get_last_email_sent_time(user_id, email_type, related_id)
        if not last_sent:
            return False
        return last_sent.date() == datetime.now().date()
    
    def get_reservations_by_reserver(self, reserver_id: str, status: str = None) -> List[Reservation]:
        """获取预约人的预约列表"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM reservations WHERE reserver_id = %s"
            params = [reserver_id]
            
            if status:
                sql += " AND status = %s"
                params.append(status)
            
            sql += " ORDER BY created_at DESC"
            
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    def get_reservations_by_custodian(self, custodian_id: str, pending_only: bool = False) -> List[Reservation]:
        """获取保管人需要处理的预约"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if pending_only:
                sql = """SELECT * FROM reservations 
                        WHERE custodian_id = %s 
                        AND status IN ('待保管人确认', '待2人确认')
                        AND custodian_approved = 0"""
            else:
                sql = "SELECT * FROM reservations WHERE custodian_id = %s"
            
            cursor.execute(sql, (custodian_id,))
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    def get_reservations_by_borrower(self, borrower_id: str, pending_only: bool = False) -> List[Reservation]:
        """获取借用人需要处理的预约"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if pending_only:
                sql = """SELECT * FROM reservations 
                        WHERE current_borrower_id = %s 
                        AND status IN ('待借用人确认', '待2人确认')
                        AND borrower_approved = 0"""
            else:
                sql = "SELECT * FROM reservations WHERE current_borrower_id = %s"
            
            cursor.execute(sql, (borrower_id,))
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    def save_reservation(self, reservation: Reservation) -> bool:
        """保存预约"""
        with get_db_transaction('reservations') as conn:
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute(
                "SELECT id FROM reservations WHERE id = %s",
                (reservation.id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                # 更新
                sql = """UPDATE reservations SET
                    device_id = %s, device_type = %s, device_name = %s,
                    reserver_id = %s, reserver_name = %s,
                    start_time = %s, end_time = %s, status = %s,
                    updated_at = %s,
                    custodian_approved = %s, custodian_approved_at = %s,
                    borrower_approved = %s, borrower_approved_at = %s,
                    custodian_notified = %s, borrower_notified = %s,
                    cancelled_by = %s, cancelled_at = %s, cancel_reason = %s,
                    rejected_by = %s, rejected_at = %s,
                    converted_to_borrow = %s, converted_at = %s,
                    custodian_id = %s, current_borrower_id = %s, current_borrower_name = %s,
                    reason = %s
                    WHERE id = %s
                """
                params = (
                    reservation.device_id, reservation.device_type, reservation.device_name,
                    reservation.reserver_id, reservation.reserver_name,
                    format_datetime(reservation.start_time), format_datetime(reservation.end_time), reservation.status,
                    format_datetime(datetime.now()),
                    1 if reservation.custodian_approved else 0, format_datetime(reservation.custodian_approved_at),
                    1 if reservation.borrower_approved else 0, format_datetime(reservation.borrower_approved_at),
                    1 if reservation.custodian_notified else 0, 1 if reservation.borrower_notified else 0,
                    reservation.cancelled_by, format_datetime(reservation.cancelled_at), reservation.cancel_reason,
                    reservation.rejected_by, format_datetime(reservation.rejected_at),
                    1 if reservation.converted_to_borrow else 0, format_datetime(reservation.converted_at),
                    reservation.custodian_id, reservation.current_borrower_id, reservation.current_borrower_name,
                    reservation.reason, reservation.id
                )
            else:
                # 插入
                sql = """INSERT INTO reservations (
                    id, device_id, device_type, device_name,
                    reserver_id, reserver_name,
                    start_time, end_time, status,
                    created_at, updated_at,
                    custodian_approved, custodian_approved_at,
                    borrower_approved, borrower_approved_at,
                    custodian_notified, borrower_notified,
                    cancelled_by, cancelled_at, cancel_reason,
                    rejected_by, rejected_at,
                    converted_to_borrow, converted_at,
                    custodian_id, current_borrower_id, current_borrower_name,
                    reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    reservation.id, reservation.device_id, reservation.device_type, reservation.device_name,
                    reservation.reserver_id, reservation.reserver_name,
                    format_datetime(reservation.start_time), format_datetime(reservation.end_time), reservation.status,
                    format_datetime(reservation.created_at), format_datetime(reservation.updated_at),
                    1 if reservation.custodian_approved else 0, format_datetime(reservation.custodian_approved_at),
                    1 if reservation.borrower_approved else 0, format_datetime(reservation.borrower_approved_at),
                    1 if reservation.custodian_notified else 0, 1 if reservation.borrower_notified else 0,
                    reservation.cancelled_by, format_datetime(reservation.cancelled_at), reservation.cancel_reason,
                    reservation.rejected_by, format_datetime(reservation.rejected_at),
                    1 if reservation.converted_to_borrow else 0, format_datetime(reservation.converted_at),
                    reservation.custodian_id, reservation.current_borrower_id, reservation.current_borrower_name,
                    reservation.reason
                )
            
            cursor.execute(sql, params)
            return True
    
    def delete_reservation(self, reservation_id: str) -> bool:
        """删除预约"""
        with get_db_transaction('reservations') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM reservations WHERE id = %s",
                (reservation_id,)
            )
            return cursor.rowcount > 0
    
    def get_pending_reservations_to_convert(self) -> List[Reservation]:
        """获取需要转为借用的已同意预约（定时任务用）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = format_datetime(datetime.now())
            cursor.execute(
                """SELECT * FROM reservations 
                   WHERE status = '已同意' 
                   AND start_time <= %s 
                   AND converted_to_borrow = 0""",
                (now,)
            )
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    def get_reservations_to_cleanup(self, cutoff_date: datetime) -> List[Reservation]:
        """获取需要清理的旧预约记录（已结束超过指定时间的）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cutoff = format_datetime(cutoff_date)
            cursor.execute(
                """SELECT * FROM reservations 
                   WHERE end_time <= %s 
                   AND status IN ('已取消', '已拒绝', '已过期', '已转借用')""",
                (cutoff,)
            )
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]

    def get_expired_pending_reservations(self) -> List[Reservation]:
        """获取已过期的待确认预约（定时任务用）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = format_datetime(datetime.now())
            cursor.execute(
                """SELECT * FROM reservations 
                   WHERE status IN ('待保管人确认', '待借用人确认', '待2人确认')
                   AND start_time <= %s""",
                (now,)
            )
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    def get_reservations_by_status(self, status: str) -> List[Reservation]:
        """根据状态获取预约列表"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reservations WHERE status = %s",
                (status,)
            )
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    # ========== 积分相关操作 ==========
    
    def get_user_points(self, user_id: str) -> Optional[UserPoints]:
        """获取用户积分"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_points WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return UserPoints.from_dict(row_to_dict(row))
            return None
    
    def save_user_points(self, user_points: UserPoints) -> bool:
        """保存用户积分"""
        with get_db_transaction('points') as conn:
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute(
                "SELECT id FROM user_points WHERE user_id = %s",
                (user_points.user_id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                sql = """UPDATE user_points SET
                    points = %s, total_earned = %s, total_spent = %s, update_time = %s
                    WHERE user_id = %s
                """
                params = (
                    user_points.points, user_points.total_earned, user_points.total_spent,
                    format_datetime(datetime.now()), user_points.user_id
                )
            else:
                sql = """INSERT INTO user_points (
                    id, user_id, points, total_earned, total_spent, update_time
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                params = (
                    user_points.id, user_points.user_id, user_points.points,
                    user_points.total_earned, user_points.total_spent, format_datetime(datetime.now())
                )
            
            cursor.execute(sql, params)
            return True
    
    def add_points_record(self, record: PointsRecord) -> bool:
        """添加积分记录"""
        with get_db_transaction('points') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO points_records (
                id, user_id, transaction_type, points_change, points_after,
                description, related_id, create_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                record.id, record.user_id,
                record.transaction_type.value if record.transaction_type else None,
                record.points_change, record.points_after,
                record.description, record.related_id, format_datetime(record.create_time)
            )
            cursor.execute(sql, params)
            return True
    
    def get_points_records(self, user_id: str, limit: int = None) -> List[PointsRecord]:
        """获取用户积分记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if limit:
                cursor.execute(
                    "SELECT * FROM points_records WHERE user_id = %s ORDER BY create_time DESC LIMIT %s",
                    (user_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM points_records WHERE user_id = %s ORDER BY create_time DESC",
                    (user_id,)
                )
            rows = cursor.fetchall()
            return [PointsRecord.from_dict(row_to_dict(row)) for row in rows]
    
    def get_all_user_points(self) -> List[UserPoints]:
        """获取所有用户积分（用于排行榜）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_points ORDER BY points DESC")
            rows = cursor.fetchall()
            return [UserPoints.from_dict(row_to_dict(row)) for row in rows]

    def get_points_rankings_optimized(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取积分排行榜（SQL优化版本）
        使用JOIN和SQL排序替代Python内存排序，大幅提升性能
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.id as user_id,
                    u.borrower_name,
                    u.avatar,
                    u.signature,
                    u.is_frozen,
                    u.is_deleted,
                    COALESCE(up.points, 0) as points,
                    COALESCE(up.total_earned, 0) as total_earned,
                    COALESCE(up.total_spent, 0) as total_spent
                FROM users u
                LEFT JOIN user_points up ON u.id = up.user_id
                WHERE u.is_frozen = 0 AND u.is_deleted = 0
                ORDER BY up.total_earned DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]

    def get_user_points_rank_optimized(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户积分排名（SQL优化版本）
        使用窗口函数计算排名，避免加载所有数据
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 获取用户排名和总分
            cursor.execute("""
                SELECT 
                    user_rank,
                    total_earned,
                    points,
                    total_users
                FROM (
                    SELECT 
                        u.id,
                        COALESCE(up.total_earned, 0) as total_earned,
                        COALESCE(up.points, 0) as points,
                        RANK() OVER (ORDER BY up.total_earned DESC) as user_rank,
                        COUNT(*) OVER () as total_users
                    FROM users u
                    LEFT JOIN user_points up ON u.id = up.user_id
                    WHERE u.is_frozen = 0 AND u.is_deleted = 0
                ) ranked
                WHERE id = %s
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                result = row_to_dict(row)
                return {
                    'rank': result.get('user_rank'),
                    'points': result.get('total_earned', 0),
                    'current_points': result.get('points', 0),
                    'total_earned': result.get('total_earned', 0),
                    'total_users': result.get('total_users', 0)
                }
            return {'rank': None, 'points': 0, 'total_earned': 0, 'total_users': 0}
    
    # ========== 悬赏相关操作 ==========
    
    def get_bounty_by_id(self, bounty_id: str) -> Optional[Bounty]:
        """根据ID获取悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bounties WHERE id = %s",
                (bounty_id,)
            )
            row = cursor.fetchone()
            if row:
                return Bounty.from_dict(row_to_dict(row))
            return None
    
    def get_all_bounties(self, status: str = None, limit: int = None) -> List[Bounty]:
        """获取所有悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM bounties"
            params = []
            
            if status:
                sql += " WHERE status = %s"
                params.append(status)
            
            sql += " ORDER BY create_time DESC"
            
            if limit:
                sql += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(sql, tuple(params) if params else ())
            rows = cursor.fetchall()
            return [Bounty.from_dict(row_to_dict(row)) for row in rows]
    
    def get_bounties_by_publisher(self, publisher_id: str) -> List[Bounty]:
        """获取用户发布的悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bounties WHERE publisher_id = %s ORDER BY create_time DESC",
                (publisher_id,)
            )
            rows = cursor.fetchall()
            return [Bounty.from_dict(row_to_dict(row)) for row in rows]
    
    def get_bounties_by_claimer(self, claimer_id: str) -> List[Bounty]:
        """获取用户认领的悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bounties WHERE claimer_id = %s ORDER BY create_time DESC",
                (claimer_id,)
            )
            rows = cursor.fetchall()
            return [Bounty.from_dict(row_to_dict(row)) for row in rows]
    
    def save_bounty(self, bounty: Bounty) -> bool:
        """保存悬赏"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute(
                "SELECT id FROM bounties WHERE id = %s",
                (bounty.id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                sql = """UPDATE bounties SET
                    title = %s, description = %s, publisher_id = %s, publisher_name = %s,
                    reward_points = %s, status = %s, device_name = %s, device_id = %s,
                    device_previous_status = %s, claim_time = %s, complete_time = %s,
                    expire_time = %s, claimer_id = %s, claimer_name = %s, finder_description = %s,
                    is_active = %s
                    WHERE id = %s
                """
                params = (
                    bounty.title, bounty.description, bounty.publisher_id, bounty.publisher_name,
                    bounty.reward_points,
                    bounty.status.value if bounty.status else None,
                    bounty.device_name, bounty.device_id, bounty.device_previous_status,
                    format_datetime(bounty.claim_time), format_datetime(bounty.complete_time),
                    format_datetime(bounty.expire_time),
                    bounty.claimer_id, bounty.claimer_name, bounty.finder_description,
                    bounty.is_active,
                    bounty.id
                )
            else:
                sql = """INSERT INTO bounties (
                    id, title, description, publisher_id, publisher_name, reward_points,
                    status, device_name, device_id, device_previous_status, create_time,
                    claim_time, complete_time, expire_time, claimer_id, claimer_name, finder_description,
                    is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    bounty.id, bounty.title, bounty.description, bounty.publisher_id,
                    bounty.publisher_name, bounty.reward_points,
                    bounty.status.value if bounty.status else None,
                    bounty.device_name, bounty.device_id, bounty.device_previous_status,
                    format_datetime(bounty.create_time),
                    format_datetime(bounty.claim_time), format_datetime(bounty.complete_time),
                    format_datetime(bounty.expire_time),
                    bounty.claimer_id, bounty.claimer_name, bounty.finder_description,
                    bounty.is_active
                )
            
            cursor.execute(sql, params)
            return True
    
    def delete_bounty(self, bounty_id: str) -> bool:
        """删除悬赏"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM bounties WHERE id = %s",
                (bounty_id,)
            )
            return cursor.rowcount > 0

    def get_expired_bounties(self) -> List[Bounty]:
        """获取所有已过期的待认领悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "SELECT * FROM bounties WHERE status = '待认领' AND expire_time < %s",
                (now,)
            )
            rows = cursor.fetchall()
            return [Bounty.from_dict(row_to_dict(row)) for row in rows]

    def auto_cancel_expired_bounties(self) -> List[Bounty]:
        """自动取消所有已过期的悬赏，返回被取消的悬赏列表"""
        expired_bounties = self.get_expired_bounties()
        cancelled_bounties = []

        for bounty in expired_bounties:
            # 更新状态为已取消
            bounty.status = BountyStatus.CANCELLED
            self.save_bounty(bounty)
            cancelled_bounties.append(bounty)

        return cancelled_bounties

    # ========== 积分商城相关操作 ==========
    
    def get_shop_item_by_id(self, item_id: str) -> Optional[ShopItem]:
        """根据ID获取商品"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM shop_items WHERE id = %s",
                (item_id,)
            )
            row = cursor.fetchone()
            if row:
                return ShopItem.from_dict(row_to_dict(row))
            return None
    
    def get_all_shop_items(self, item_type: str = None, only_active: bool = True) -> List[ShopItem]:
        """获取所有商品"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM shop_items WHERE 1=1"
            params = []
            
            if only_active:
                sql += " AND is_active = 1"
            
            if item_type:
                sql += " AND item_type = %s"
                params.append(item_type)
            
            sql += " ORDER BY sort_order ASC, create_time ASC"
            
            cursor.execute(sql, tuple(params) if params else ())
            rows = cursor.fetchall()
            return [ShopItem.from_dict(row_to_dict(row)) for row in rows]
    
    def save_shop_item(self, item: ShopItem) -> bool:
        """保存商品"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM shop_items WHERE id = %s",
                (item.id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                sql = """UPDATE shop_items SET
                    name = %s, description = %s, item_type = %s, price = %s,
                    icon = %s, color = %s, is_active = %s, sort_order = %s
                    WHERE id = %s
                """
                params = (
                    item.name, item.description,
                    item.item_type.value if item.item_type else None,
                    item.price, item.icon, item.color,
                    1 if item.is_active else 0, item.sort_order, item.id
                )
            else:
                sql = """INSERT INTO shop_items (
                    id, name, description, item_type, price, icon, color, is_active, sort_order, create_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    item.id, item.name, item.description,
                    item.item_type.value if item.item_type else None,
                    item.price, item.icon, item.color,
                    1 if item.is_active else 0, item.sort_order,
                    format_datetime(item.create_time)
                )
            
            cursor.execute(sql, params)
            return True
    
    def delete_shop_item(self, item_id: str) -> bool:
        """删除商品"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM shop_items WHERE id = %s",
                (item_id,)
            )
            return True
    
    # ========== 用户背包相关操作 ==========
    
    def get_user_inventory(self, user_id: str, item_type: str = None) -> List[UserInventory]:
        """获取用户背包物品"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM user_inventory WHERE user_id = %s"
            params = [user_id]
            
            if item_type:
                sql += " AND item_type = %s"
                params.append(item_type)
            
            sql += " ORDER BY acquire_time DESC"
            
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [UserInventory.from_dict(row_to_dict(row)) for row in rows]
    
    def get_inventory_item_by_id(self, inventory_id: str) -> Optional[UserInventory]:
        """根据ID获取背包物品"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_inventory WHERE id = %s",
                (inventory_id,)
            )
            row = cursor.fetchone()
            if row:
                return UserInventory.from_dict(row_to_dict(row))
            return None
    
    def add_to_inventory(self, item: UserInventory) -> bool:
        """添加物品到背包"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_inventory (
                id, user_id, item_id, item_type, item_name, item_icon, item_color,
                source, is_used, acquire_time, use_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                item.id, item.user_id, item.item_id,
                item.item_type.value if item.item_type else None,
                item.item_name, item.item_icon, item.item_color,
                item.source.value if item.source else None,
                1 if item.is_used else 0,
                format_datetime(item.acquire_time),
                format_datetime(item.use_time)
            )
            cursor.execute(sql, params)
            return True
    
    def update_inventory_item_status(self, inventory_id: str, is_used: bool, use_time: datetime = None) -> bool:
        """更新背包物品使用状态"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = """UPDATE user_inventory SET
                is_used = %s, use_time = %s
                WHERE id = %s
            """
            params = (
                1 if is_used else 0,
                format_datetime(use_time),
                inventory_id
            )
            cursor.execute(sql, params)
            return True
    
    def has_item_in_inventory(self, user_id: str, item_id: str) -> bool:
        """检查用户是否已拥有某物品"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM user_inventory WHERE user_id = %s AND item_id = %s LIMIT 1",
                (user_id, item_id)
            )
            return cursor.fetchone() is not None

    # ========== 每日转盘相关操作 ==========

    def add_wheel_record(self, user_id: str, prize_id: str, prize_name: str, prize_points: int, cost: int) -> bool:
        """添加转盘抽奖记录"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO wheel_records (
                id, user_id, prize_id, prize_name, prize_points, cost, create_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                str(uuid.uuid4()),
                user_id,
                prize_id,
                prize_name,
                prize_points,
                cost,
                format_datetime(datetime.now())
            )
            cursor.execute(sql, params)
            return True

    def get_wheel_records_by_date(self, user_id: str, date_str: str) -> List[Dict[str, Any]]:
        """获取用户指定日期的抽奖记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # date_str 格式: YYYY-MM-DD
            cursor.execute(
                """SELECT * FROM wheel_records 
                   WHERE user_id = %s AND DATE(create_time) = %s 
                   ORDER BY create_time ASC""",
                (user_id, date_str)
            )
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]

    def get_wheel_records_by_user(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的抽奖记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM wheel_records 
                   WHERE user_id = %s 
                   ORDER BY create_time DESC 
                   LIMIT %s""",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]

    def add_hidden_title(self, user_id: str, title_id: str, title_name: str, title_color: str) -> bool:
        """添加用户隐藏称号"""
        with get_db_transaction('default') as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_hidden_titles (
                id, user_id, title_id, title_name, title_color, acquire_time
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            params = (
                str(uuid.uuid4()),
                user_id,
                title_id,
                title_name,
                title_color,
                format_datetime(datetime.now())
            )
            cursor.execute(sql, params)
            return True

    def has_hidden_title(self, user_id: str, title_id: str) -> bool:
        """检查用户是否已有某隐藏称号"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id FROM user_hidden_titles 
                   WHERE user_id = %s AND title_id = %s LIMIT 1""",
                (user_id, title_id)
            )
            return cursor.fetchone() is not None

    def get_user_hidden_titles(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所有隐藏称号"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM user_hidden_titles 
                   WHERE user_id = %s 
                   ORDER BY acquire_time DESC""",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]


# ========== 数据库迁移函数 ==========

def _migrate_mysql_create_points_tables():
    """MySQL: 创建积分相关表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 创建用户积分表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_points (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL UNIQUE,
                    points INT DEFAULT 0,
                    total_earned INT DEFAULT 0,
                    total_spent INT DEFAULT 0,
                    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    INDEX idx_user_id (user_id)
                )
            ''')
            
            # 创建积分记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS points_records (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    transaction_type VARCHAR(32) NOT NULL,
                    points_change INT NOT NULL,
                    points_after INT NOT NULL,
                    description VARCHAR(500),
                    related_id VARCHAR(64),
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_create_time (create_time)
                )
            ''')
            
            conn.commit()
            print("✓ MySQL: 已创建积分相关表")
    except Exception as e:
        print(f"⚠ MySQL 积分表迁移警告: {e}")


def _migrate_mysql_create_shop_tables():
    """MySQL: 创建积分商城相关表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 创建商品表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description VARCHAR(500),
                    item_type VARCHAR(32) NOT NULL,
                    price INT NOT NULL,
                    icon VARCHAR(100),
                    color VARCHAR(50),
                    is_active TINYINT DEFAULT 1,
                    sort_order INT DEFAULT 0,
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_item_type (item_type),
                    INDEX idx_is_active (is_active)
                )
            ''')
            
            # 创建用户背包表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_inventory (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    item_id VARCHAR(64) NOT NULL,
                    item_type VARCHAR(32) NOT NULL,
                    item_name VARCHAR(255) NOT NULL,
                    item_icon VARCHAR(100),
                    item_color VARCHAR(50),
                    source VARCHAR(32) DEFAULT '积分商城',
                    is_used TINYINT DEFAULT 0,
                    acquire_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    use_time DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_item_id (item_id)
                )
            ''')
            
            conn.commit()
            print("✓ MySQL: 已创建积分商城相关表")
    except Exception as e:
        print(f"⚠ MySQL 积分商城表迁移警告: {e}")


def _migrate_mysql_add_user_equip_fields():
    """MySQL: 添加用户装扮字段"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT current_title FROM users LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE users ADD COLUMN current_title VARCHAR(64) DEFAULT ''")
                conn.commit()
                print("✓ MySQL: 已添加 current_title 列到 users 表")

            try:
                cursor.execute("SELECT current_avatar_frame FROM users LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE users ADD COLUMN current_avatar_frame VARCHAR(64) DEFAULT ''")
                conn.commit()
                print("✓ MySQL: 已添加 current_avatar_frame 列到 users 表")

            try:
                cursor.execute("SELECT current_theme FROM users LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE users ADD COLUMN current_theme VARCHAR(64) DEFAULT ''")
                conn.commit()
                print("✓ MySQL: 已添加 current_theme 列到 users 表")
    except Exception as e:
        print(f"⚠ MySQL 用户装扮字段迁移警告: {e}")


def _migrate_mysql_add_user_cursor_field():
    """MySQL: 添加用户鼠标皮肤字段"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT current_cursor FROM users LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE users ADD COLUMN current_cursor VARCHAR(64) DEFAULT ''")
                conn.commit()
                print("✓ MySQL: 已添加 current_cursor 列到 users 表")
    except Exception as e:
        print(f"⚠ MySQL 用户鼠标皮肤字段迁移警告: {e}")


def _migrate_mysql_create_bounties_table():
    """MySQL: 创建悬赏表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bounties (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    publisher_id VARCHAR(64) NOT NULL,
                    publisher_name VARCHAR(255) NOT NULL,
                    reward_points INT NOT NULL,
                    status VARCHAR(32) DEFAULT '待认领',
                    device_name VARCHAR(255),
                    device_id VARCHAR(64),
                    device_previous_status VARCHAR(32),
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    claim_time DATETIME,
                    complete_time DATETIME,
                    claimer_id VARCHAR(64),
                    claimer_name VARCHAR(255),
                    finder_description TEXT,
                    FOREIGN KEY (publisher_id) REFERENCES users(id),
                    INDEX idx_status (status),
                    INDEX idx_publisher (publisher_id),
                    INDEX idx_claimer (claimer_id)
                )
            ''')

            conn.commit()
            print("✓ MySQL: 已创建悬赏表")

            # 检查并添加 device_id 列
            try:
                cursor.execute("SELECT device_id FROM bounties LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE bounties ADD COLUMN device_id VARCHAR(64)")
                conn.commit()
                print("✓ MySQL: 已添加 device_id 列到 bounties 表")

            # 检查并添加 device_previous_status 列
            try:
                cursor.execute("SELECT device_previous_status FROM bounties LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE bounties ADD COLUMN device_previous_status VARCHAR(32)")
                conn.commit()
                print("✓ MySQL: 已添加 device_previous_status 列到 bounties 表")

            # 检查并添加 expire_time 列
            try:
                cursor.execute("SELECT expire_time FROM bounties LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE bounties ADD COLUMN expire_time DATETIME")
                conn.commit()
                print("✓ MySQL: 已添加 expire_time 列到 bounties 表")

            # 检查并添加 is_active 列
            try:
                cursor.execute("SELECT is_active FROM bounties LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE bounties ADD COLUMN is_active TINYINT DEFAULT 1")
                conn.commit()
                print("✓ MySQL: 已添加 is_active 列到 bounties 表")
    except Exception as e:
        print(f"⚠ MySQL 悬赏表迁移警告: {e}")


def _migrate_mysql_create_wheel_tables():
    """MySQL: 创建每日转盘相关表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 创建转盘抽奖记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wheel_records (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    prize_id VARCHAR(64) NOT NULL,
                    prize_name VARCHAR(255) NOT NULL,
                    prize_points INT DEFAULT 0,
                    cost INT DEFAULT 0,
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_create_time (create_time)
                )
            ''')
            
            # 创建用户隐藏称号表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_hidden_titles (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    title_id VARCHAR(64) NOT NULL,
                    title_name VARCHAR(255) NOT NULL,
                    title_color VARCHAR(50) DEFAULT '#1890ff',
                    acquire_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_title_id (title_id)
                )
            ''')
            
            conn.commit()
            print("✓ MySQL: 已创建每日转盘相关表")
    except Exception as e:
        print(f"⚠ MySQL 每日转盘表迁移警告: {e}")


def _migrate_mysql_add_operation_log_source():
    """MySQL: 检查并添加 operation_logs 表的 source 列"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT source FROM operation_logs LIMIT 1")
            except Exception:
                # 列不存在，添加它
                cursor.execute("ALTER TABLE operation_logs ADD COLUMN source VARCHAR(20) DEFAULT 'admin'")
                cursor.execute("CREATE INDEX idx_source ON operation_logs(source)")
                conn.commit()
                print("✓ MySQL: 已添加 source 列到 operation_logs 表")
    except Exception as e:
        print(f"⚠ MySQL operation_logs source 列迁移警告: {e}")


def _migrate_mysql_create_admin_operation_logs_table():
    """MySQL: 创建后台管理操作日志表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_operation_logs (
                    id VARCHAR(64) PRIMARY KEY,
                    operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    admin_id VARCHAR(64) NOT NULL,
                    admin_name VARCHAR(100) NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    action_name VARCHAR(100) NOT NULL,
                    target_type VARCHAR(50) NOT NULL,
                    target_id VARCHAR(64),
                    target_name VARCHAR(200),
                    description TEXT,
                    ip_address VARCHAR(50),
                    user_agent TEXT,
                    request_method VARCHAR(10),
                    request_path VARCHAR(500),
                    request_params TEXT,
                    result VARCHAR(20) DEFAULT 'SUCCESS',
                    error_message TEXT,
                    INDEX idx_admin_id (admin_id),
                    INDEX idx_operation_time (operation_time),
                    INDEX idx_action_type (action_type),
                    INDEX idx_target_type (target_type),
                    INDEX idx_result (result)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            conn.commit()
            print("✓ MySQL: 已创建 admin_operation_logs 表")
    except Exception as e:
        print(f"⚠ MySQL 创建 admin_operation_logs 表警告: {e}")
