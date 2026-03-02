# -*- coding: utf-8 -*-
"""
数据库操作模块
支持SQLite和MySQL两种数据库
"""
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, Admin, Notification, Announcement, UserLike, Reservation, UserPoints, PointsRecord, Bounty, ShopItem, UserInventory
from .models import DeviceStatus, DeviceType, OperationType, ReservationStatus, PointsTransactionType, BountyStatus, ShopItemType, ShopItemSource

# 导入配置
from .config import DB_TYPE, SQLITE_DB_PATH, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

# 全局线程锁，用于写操作同步
db_write_lock = threading.Lock()

# 数据库类型标志
IS_MYSQL = (DB_TYPE == 'mysql')

# 如果是MySQL，导入pymysql
if IS_MYSQL:
    import pymysql
    from pymysql.cursors import DictCursor
    # 让pymysql兼容MySQLdb接口
    pymysql.install_as_MySQLdb()
    
    # 使用简单的连接缓存（pymysql没有内置连接池）
    _connection_cache = {}
    
    def get_mysql_connection():
        """获取MySQL连接（带简单缓存）"""
        import threading
        tid = threading.current_thread().ident
        
        if tid in _connection_cache:
            conn = _connection_cache[tid]
            try:
                # 测试连接是否有效
                conn.ping(reconnect=True)
                return conn
            except:
                # 连接已失效，创建新连接
                pass
        
        # 创建新连接
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False
        )
        _connection_cache[tid] = conn
        return conn


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    conn = None
    try:
        if IS_MYSQL:
            # MySQL: 创建新连接，不缓存
            conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                charset='utf8mb4',
                cursorclass=DictCursor,
                autocommit=False
            )
        else:
            conn = sqlite3.connect(SQLITE_DB_PATH, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # 启用WAL模式，提高并发性能
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            conn.execute('PRAGMA temp_store=MEMORY')
        
        yield conn
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_transaction():
    """获取数据库事务上下文管理器（带锁保护）"""
    with db_write_lock:
        if IS_MYSQL:
            # 使用连接缓存
            conn = get_mysql_connection()
        else:
            conn = sqlite3.connect(SQLITE_DB_PATH, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
        
        try:
            if not IS_MYSQL:
                conn.execute('BEGIN EXCLUSIVE')
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            if not IS_MYSQL:
                conn.close()


def row_to_dict(row) -> Dict[str, Any]:
    """将数据库行转换为字典"""
    if IS_MYSQL:
        return row
    else:
        return {key: row[key] for key in row.keys()}


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


def init_database():
    """初始化数据库，创建必要的表（MySQL下不需要，表已预先创建）"""
    if IS_MYSQL:
        # MySQL表已经通过init_mysql.py创建
        # 检查并添加 borrower_id 列（如果不存在）
        _migrate_mysql_add_borrower_id()
        # 检查并添加 avatar 列（如果不存在）
        _migrate_mysql_add_avatar()
        # 检查并添加 signature 列（如果不存在）
        _migrate_mysql_add_signature()
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
        return

    # SQLite初始化逻辑...
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 创建设备表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                model TEXT,
                cabinet_number TEXT,
                status TEXT NOT NULL,
                remark TEXT,
                jira_address TEXT,
                is_deleted INTEGER DEFAULT 0,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                borrower TEXT,
                borrower_id TEXT,
                custodian_id TEXT,
                phone TEXT,
                borrow_time TIMESTAMP,
                location TEXT,
                reason TEXT,
                entry_source TEXT,
                expected_return_date TIMESTAMP,
                admin_operator TEXT,
                ship_time TIMESTAMP,
                ship_remark TEXT,
                ship_by TEXT,
                pre_ship_borrower TEXT,
                pre_ship_borrow_time TIMESTAMP,
                pre_ship_expected_return_date TIMESTAMP,
                lost_time TIMESTAMP,
                damage_reason TEXT,
                damage_time TIMESTAMP,
                previous_borrower TEXT,
                sn TEXT,
                system_version TEXT,
                imei TEXT,
                carrier TEXT,
                software_version TEXT,
                hardware_version TEXT,
                project_attribute TEXT,
                connection_method TEXT,
                os_version TEXT,
                os_platform TEXT,
                product_name TEXT,
                screen_orientation TEXT,
                screen_resolution TEXT,
                asset_number TEXT,
                purchase_amount REAL DEFAULT 0
            )
        ''')

        # 检查并添加 borrower_id 列（如果表已存在但缺少该列）
        _migrate_sqlite_add_borrower_id(cursor)

        # 检查并添加 avatar 列到 users 表（如果表已存在但缺少该列）
        _migrate_sqlite_add_avatar(cursor)

        # 检查并添加 signature 列到 users 表（如果表已存在但缺少该列）
        _migrate_sqlite_add_signature(cursor)

        # 检查并添加 asset_number 和 purchase_amount 列
        _migrate_sqlite_add_asset_fields(cursor)

        # 检查并添加 custodian_id 列
        _migrate_sqlite_add_custodian_id(cursor)

        # 检查并添加 previous_status 列
        _migrate_sqlite_add_previous_status(cursor)

        # 创建 reservations 表
        _migrate_sqlite_create_reservations(cursor)

        # 创建邮件发送记录表
        _migrate_sqlite_create_email_logs(cursor)

        # 创建积分相关表
        _migrate_sqlite_create_points_tables(cursor)

        # 创建悬赏表
        _migrate_sqlite_create_bounties_table(cursor)
        
        # 创建积分商城相关表
        _migrate_sqlite_create_shop_tables(cursor)
        
        # 添加用户装扮字段
        _migrate_sqlite_add_user_equip_fields(cursor)
        
        # 添加用户鼠标皮肤字段
        _migrate_sqlite_add_user_cursor_field(cursor)
        
        # 创建每日转盘相关表
        _migrate_sqlite_create_wheel_tables(cursor)

        # 创建其他表...
        # (省略其他表的创建代码，保持原有逻辑)

        conn.commit()

def _migrate_sqlite_add_borrower_id(cursor):
    """SQLite: 检查并添加 borrower_id 列"""
    try:
        cursor.execute("SELECT borrower_id FROM devices LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE devices ADD COLUMN borrower_id TEXT")
        print("✓ SQLite: 已添加 borrower_id 列到 devices 表")

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


def _migrate_sqlite_add_avatar(cursor):
    """SQLite: 检查并添加 avatar 列到 users 表"""
    try:
        cursor.execute("SELECT avatar FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''")
        print("✓ SQLite: 已添加 avatar 列到 users 表")


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


def _migrate_sqlite_add_signature(cursor):
    """SQLite: 检查并添加 signature 列到 users 表"""
    try:
        cursor.execute("SELECT signature FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE users ADD COLUMN signature TEXT DEFAULT ''")
        print("✓ SQLite: 已添加 signature 列到 users 表")


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


def _migrate_sqlite_add_asset_fields(cursor):
    """SQLite: 检查并添加 asset_number 和 purchase_amount 列到 devices 表"""
    try:
        cursor.execute("SELECT asset_number FROM devices LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE devices ADD COLUMN asset_number TEXT")
        print("✓ SQLite: 已添加 asset_number 列到 devices 表")

    try:
        cursor.execute("SELECT purchase_amount FROM devices LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE devices ADD COLUMN purchase_amount REAL DEFAULT 0")
        print("✓ SQLite: 已添加 purchase_amount 列到 devices 表")


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


def _migrate_sqlite_add_custodian_id(cursor):
    """SQLite: 检查并添加 custodian_id 列到 devices 表"""
    try:
        cursor.execute("SELECT custodian_id FROM devices LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE devices ADD COLUMN custodian_id TEXT")
        print("✓ SQLite: 已添加 custodian_id 列到 devices 表")


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


def _migrate_sqlite_add_previous_status(cursor):
    """SQLite: 检查并添加 previous_status 列到 devices 表"""
    try:
        cursor.execute("SELECT previous_status FROM devices LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE devices ADD COLUMN previous_status TEXT")
        print("✓ SQLite: 已添加 previous_status 列到 devices 表")


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


def _migrate_sqlite_create_reservations(cursor):
    """SQLite: 创建 reservations 表"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            device_type TEXT NOT NULL,
            device_name TEXT NOT NULL,
            reserver_id TEXT NOT NULL,
            reserver_name TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            custodian_approved INTEGER DEFAULT 0,
            custodian_approved_at TIMESTAMP,
            borrower_approved INTEGER DEFAULT 0,
            borrower_approved_at TIMESTAMP,
            custodian_notified INTEGER DEFAULT 0,
            borrower_notified INTEGER DEFAULT 0,
            cancelled_by TEXT,
            cancelled_at TIMESTAMP,
            cancel_reason TEXT,
            rejected_by TEXT,
            rejected_at TIMESTAMP,
            converted_to_borrow INTEGER DEFAULT 0,
            converted_at TIMESTAMP,
            custodian_id TEXT,
            current_borrower_id TEXT,
            current_borrower_name TEXT,
            reason TEXT
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reservations_device ON reservations(device_id, device_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reservations_reserver ON reservations(reserver_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reservations_time ON reservations(start_time, end_time)')
    print("✓ SQLite: 已创建 reservations 表")


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


def _migrate_sqlite_create_email_logs(cursor):
    """SQLite: 创建邮件发送记录表"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_email TEXT NOT NULL,
            email_type TEXT NOT NULL,
            related_id TEXT,
            related_type TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'sent',
            content TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_logs_user ON email_logs(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_logs_type ON email_logs(email_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at ON email_logs(sent_at)')
    print("✓ SQLite: 已创建 email_logs 表")


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
                    "SELECT * FROM devices WHERE device_type = %s AND is_deleted = 0" if IS_MYSQL else 
                    "SELECT * FROM devices WHERE device_type = ? AND is_deleted = 0",
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
                "SELECT * FROM devices WHERE id = %s AND is_deleted = 0" if IS_MYSQL else
                "SELECT * FROM devices WHERE id = ? AND is_deleted = 0",
                (device_id,)
            )
            row = cursor.fetchone()
            if row:
                return Device.from_dict(row_to_dict(row))
            return None
    
    def save_device(self, device: Device) -> bool:
        """保存设备"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            
            # 检查设备是否存在
            cursor.execute(
                "SELECT id FROM devices WHERE id = %s" if IS_MYSQL else
                "SELECT id FROM devices WHERE id = ?",
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
                """ if IS_MYSQL else """UPDATE devices SET
                    name = ?, device_type = ?, model = ?, cabinet_number = ?,
                    status = ?, remark = ?, jira_address = ?, borrower = ?,
                    borrower_id = ?, custodian_id = ?, phone = ?, borrow_time = ?, location = ?, reason = ?,
                    entry_source = ?, expected_return_date = ?, admin_operator = ?,
                    ship_time = ?, ship_remark = ?, ship_by = ?,
                    pre_ship_borrower = ?, pre_ship_borrow_time = ?,
                    pre_ship_expected_return_date = ?, lost_time = ?,
                    damage_reason = ?, damage_time = ?, previous_borrower = ?, previous_status = ?,
                    sn = ?, system_version = ?, imei = ?, carrier = ?,
                    software_version = ?, hardware_version = ?,
                    project_attribute = ?, connection_method = ?,
                    os_version = ?, os_platform = ?, product_name = ?,
                    screen_orientation = ?, screen_resolution = ?,
                    asset_number = ?, purchase_amount = ?, is_deleted = ?
                    WHERE id = ?
                """

                params = (
                    device.name, device.device_type.value if device.device_type else None, device.model, device.cabinet_number,
                    device.status.value if device.status else None, device.remark, device.jira_address,
                    device.borrower, device.borrower_id, device.custodian_id, device.phone, format_datetime(device.borrow_time),
                    device.location, device.reason, device.entry_source,
                    format_datetime(device.expected_return_date), device.admin_operator,
                    format_datetime(device.ship_time), device.ship_remark, device.ship_by,
                    device.pre_ship_borrower, format_datetime(device.pre_ship_borrow_time),
                    format_datetime(device.pre_ship_expected_return_date),
                    format_datetime(device.lost_time), device.damage_reason,
                    format_datetime(device.damage_time), device.previous_borrower, device.previous_status,
                    device.sn, device.system_version, device.imei, device.carrier,
                    device.software_version, device.hardware_version,
                    device.project_attribute, device.connection_method,
                    device.os_version, device.os_platform, device.product_name,
                    device.screen_orientation, device.screen_resolution,
                    device.asset_number, device.purchase_amount,
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
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """ if IS_MYSQL else """INSERT INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, borrower, borrower_id, custodian_id, phone, borrow_time, location, reason,
                    entry_source, expected_return_date, admin_operator, ship_time,
                    ship_remark, ship_by, pre_ship_borrower, pre_ship_borrow_time,
                    pre_ship_expected_return_date, lost_time, damage_reason,
                    damage_time, previous_borrower, previous_status, sn, system_version, imei,
                    carrier, software_version, hardware_version, project_attribute,
                    connection_method, os_version, os_platform, product_name,
                    screen_orientation, screen_resolution, asset_number, purchase_amount, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                params = (
                    device.id, device.name, device.device_type.value if device.device_type else None, device.model,
                    device.cabinet_number, device.status.value if device.status else None,
                    device.remark, device.jira_address, device.borrower, device.borrower_id, device.custodian_id, device.phone,
                    format_datetime(device.borrow_time), device.location, device.reason,
                    device.entry_source, format_datetime(device.expected_return_date),
                    device.admin_operator, format_datetime(device.ship_time),
                    device.ship_remark, device.ship_by, device.pre_ship_borrower,
                    format_datetime(device.pre_ship_borrow_time),
                    format_datetime(device.pre_ship_expected_return_date),
                    format_datetime(device.lost_time), device.damage_reason,
                    format_datetime(device.damage_time), device.previous_borrower, device.previous_status,
                    device.sn, device.system_version, device.imei, device.carrier,
                    device.software_version, device.hardware_version,
                    device.project_attribute, device.connection_method,
                    device.os_version, device.os_platform, device.product_name,
                    device.screen_orientation, device.screen_resolution,
                    device.asset_number, device.purchase_amount,
                    1 if device.is_deleted else 0
                )
                cursor.execute(sql, params)
            
            return True
    
    def delete_device(self, device_id: str) -> bool:
        """软删除设备"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE devices SET is_deleted = 1 WHERE id = %s" if IS_MYSQL else
                "UPDATE devices SET is_deleted = 1 WHERE id = ?",
                (device_id,)
            )
            return True
    
    # ========== 用户相关操作 ==========
    
    def get_all_users(self) -> List[User]:
        """获取所有用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE is_deleted = 0")
            rows = cursor.fetchall()
            return [User.from_dict(row_to_dict(row)) for row in rows]
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE id = %s AND is_deleted = 0" if IS_MYSQL else
                "SELECT * FROM users WHERE id = ? AND is_deleted = 0",
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
                "SELECT * FROM users WHERE email = %s AND is_deleted = 0" if IS_MYSQL else
                "SELECT * FROM users WHERE email = ? AND is_deleted = 0",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return User.from_dict(row_to_dict(row))
            return None
    
    def save_user(self, user: User) -> bool:
        """保存用户"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM users WHERE id = %s" if IS_MYSQL else
                "SELECT id FROM users WHERE id = ?",
                (user.id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                sql = """UPDATE users SET
                    email = %s, password = %s, borrower_name = %s, avatar = %s, signature = %s,
                    borrow_count = %s, return_count = %s, is_frozen = %s, is_admin = %s, is_deleted = %s, is_first_login = %s,
                    current_title = %s, current_avatar_frame = %s, current_theme = %s, current_cursor = %s
                    WHERE id = %s
                """ if IS_MYSQL else """UPDATE users SET
                    email = ?, password = ?, borrower_name = ?, avatar = ?, signature = ?,
                    borrow_count = ?, return_count = ?, is_frozen = ?, is_admin = ?, is_deleted = ?, is_first_login = ?,
                    current_title = ?, current_avatar_frame = ?, current_theme = ?, current_cursor = ?
                    WHERE id = ?
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
                """ if IS_MYSQL else """INSERT INTO users (
                    id, email, password, borrower_name, avatar, signature, borrow_count,
                    return_count, is_frozen, is_admin, is_deleted, is_first_login, create_time,
                    current_title, current_avatar_frame, current_theme, current_cursor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
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
                    "SELECT * FROM records ORDER BY operation_time DESC LIMIT %s" if IS_MYSQL else
                    "SELECT * FROM records ORDER BY operation_time DESC LIMIT ?",
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
                "SELECT * FROM records WHERE device_id = %s ORDER BY operation_time DESC" if IS_MYSQL else
                "SELECT * FROM records WHERE device_id = ? ORDER BY operation_time DESC",
                (device_id,)
            )
            rows = cursor.fetchall()
            return [Record.from_dict(row_to_dict(row)) for row in rows]
    
    def save_record(self, record: Record) -> bool:
        """保存记录"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO records (
                id, device_id, device_name, device_type, operation_type, operator,
                operation_time, borrower, phone, reason, entry_source, remark
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO records (
                id, device_id, device_name, device_type, operation_type, operator,
                operation_time, borrower, phone, reason, entry_source, remark
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    "SELECT * FROM user_remarks WHERE device_id = %s ORDER BY create_time DESC" if IS_MYSQL else
                    "SELECT * FROM user_remarks WHERE device_id = ? ORDER BY create_time DESC",
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_remarks (
                id, device_id, device_type, content, creator, create_time, is_inappropriate
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO user_remarks (
                id, device_id, device_type, content, creator, create_time, is_inappropriate
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
                "SELECT * FROM admins WHERE username = %s" if IS_MYSQL else
                "SELECT * FROM admins WHERE username = ?",
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
                "SELECT * FROM notifications WHERE user_id = %s ORDER BY create_time DESC" if IS_MYSQL else
                "SELECT * FROM notifications WHERE user_id = ? ORDER BY create_time DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [Notification.from_dict(row_to_dict(row)) for row in rows]
    
    def save_notification(self, notification: Notification) -> bool:
        """保存通知"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO notifications (
                id, user_id, user_name, title, content, device_name, device_id,
                is_read, create_time, notification_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO notifications (
                id, user_id, user_name, title, content, device_name, device_id,
                is_read, create_time, notification_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = "UPDATE notifications SET is_read = 1 WHERE id = %s" if IS_MYSQL else "UPDATE notifications SET is_read = 1 WHERE id = ?"
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
                    "SELECT * FROM announcements WHERE is_active = 1 ORDER BY sort_order DESC, create_time DESC" if IS_MYSQL else
                    "SELECT * FROM announcements WHERE is_active = 1 ORDER BY sort_order DESC, create_time DESC"
                )
            else:
                cursor.execute("SELECT * FROM announcements ORDER BY sort_order DESC, create_time DESC")
            rows = cursor.fetchall()
            return [Announcement.from_dict(row_to_dict(row)) for row in rows]
    
    # ========== 操作日志相关操作 ==========

    def add_operation_log(self, operation: str, device_name: str, operator: str) -> bool:
        """添加操作日志"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            import uuid
            sql = """INSERT INTO operation_logs (
                id, operation_time, operator, operation_content, device_info
            ) VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO operation_logs (
                id, operation_time, operator, operation_content, device_info
            ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            """
            params = (str(uuid.uuid4()), operator, operation, device_name)
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO operation_logs (
                id, operation_time, operator, operation_content, device_info
            ) VALUES (%s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO operation_logs (
                id, operation_time, operator, operation_content, device_info
            ) VALUES (?, ?, ?, ?, ?)
            """
            params = (
                log.id,
                format_datetime(log.operation_time),
                log.operator,
                log.operation_content,
                log.device_info
            )
            cursor.execute(sql, params)
            return True
    
    # ========== 查看记录相关操作 ==========
    
    def get_view_records_by_device(self, device_id: str, limit: int = 20) -> list:
        """根据设备ID获取查看记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM view_records WHERE device_id = %s ORDER BY view_time DESC LIMIT %s" if IS_MYSQL else
                "SELECT * FROM view_records WHERE device_id = ? ORDER BY view_time DESC LIMIT ?",
                (device_id, limit)
            )
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]

    def save_view_record(self, device_id: str, device_type: str, viewer: str) -> bool:
        """添加查看记录"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            import uuid
            sql = """INSERT INTO view_records (
                id, device_id, device_type, viewer, view_time
            ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            """ if IS_MYSQL else """INSERT INTO view_records (
                id, device_id, device_type, viewer, view_time
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                "SELECT * FROM user_likes WHERE to_user_id = %s" if IS_MYSQL else
                "SELECT * FROM user_likes WHERE to_user_id = ?",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [UserLike.from_dict(row_to_dict(row)) for row in rows]
    
    def get_user_likes_by_user(self, from_user_id: str) -> List[UserLike]:
        """获取用户发出的点赞"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_likes WHERE from_user_id = %s" if IS_MYSQL else
                "SELECT * FROM user_likes WHERE from_user_id = ?",
                (from_user_id,)
            )
            rows = cursor.fetchall()
            return [UserLike.from_dict(row_to_dict(row)) for row in rows]
    
    def save_user_like(self, like: UserLike) -> bool:
        """保存用户点赞"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_likes (
                id, from_user_id, to_user_id, create_date, create_time
            ) VALUES (%s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO user_likes (
                id, from_user_id, to_user_id, create_date, create_time
            ) VALUES (?, ?, ?, ?, ?)
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
                "SELECT * FROM reservations WHERE id = %s" if IS_MYSQL else
                "SELECT * FROM reservations WHERE id = ?",
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
            
            sql = "SELECT * FROM reservations WHERE device_id = %s" if IS_MYSQL else "SELECT * FROM reservations WHERE device_id = ?"
            params = [device_id]
            
            if device_type:
                sql += " AND device_type = %s" if IS_MYSQL else " AND device_type = ?"
                params.append(device_type)
            
            if status:
                if isinstance(status, list):
                    placeholders = ','.join(['%s' if IS_MYSQL else '?'] * len(status))
                    sql += f" AND status IN ({placeholders})"
                    params.extend(status)
                else:
                    sql += " AND status = %s" if IS_MYSQL else " AND status = ?"
                    params.append(status)
            
            if active_only:
                # 只获取未结束的有效预约（排除已取消、已拒绝、已过期、已转借用的预约）
                sql += " AND end_time > %s AND status NOT IN ('已取消', '已拒绝', '已过期', '已转借用')" if IS_MYSQL else " AND end_time > ? AND status NOT IN ('已取消', '已拒绝', '已过期', '已转借用')"
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            email_id = str(uuid.uuid4())
            sent_at = format_datetime(datetime.now())
            
            cursor.execute(
                """INSERT INTO email_logs 
                   (id, user_id, user_email, email_type, related_id, related_type, sent_at, status, content)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""" if IS_MYSQL else
                """INSERT INTO email_logs 
                   (id, user_id, user_email, email_type, related_id, related_type, sent_at, status, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                       ORDER BY sent_at DESC""" if IS_MYSQL else
                    """SELECT * FROM email_logs 
                       WHERE user_id = ? AND email_type = ? 
                       ORDER BY sent_at DESC""",
                    (user_id, email_type)
                )
            else:
                cursor.execute(
                    """SELECT * FROM email_logs 
                       WHERE user_id = %s 
                       ORDER BY sent_at DESC""" if IS_MYSQL else
                    """SELECT * FROM email_logs 
                       WHERE user_id = ? 
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
                       ORDER BY sent_at DESC LIMIT 1""" if IS_MYSQL else
                    """SELECT sent_at FROM email_logs 
                       WHERE user_id = ? AND email_type = ? AND related_id = ?
                       ORDER BY sent_at DESC LIMIT 1""",
                    (user_id, email_type, related_id)
                )
            else:
                cursor.execute(
                    """SELECT sent_at FROM email_logs 
                       WHERE user_id = %s AND email_type = %s
                       ORDER BY sent_at DESC LIMIT 1""" if IS_MYSQL else
                    """SELECT sent_at FROM email_logs 
                       WHERE user_id = ? AND email_type = ?
                       ORDER BY sent_at DESC LIMIT 1""",
                    (user_id, email_type)
                )
            row = cursor.fetchone()
            if row:
                return parse_datetime(row['sent_at'] if IS_MYSQL else row[0])
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
            
            sql = "SELECT * FROM reservations WHERE reserver_id = %s" if IS_MYSQL else "SELECT * FROM reservations WHERE reserver_id = ?"
            params = [reserver_id]
            
            if status:
                sql += " AND status = %s" if IS_MYSQL else " AND status = ?"
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
                        AND custodian_approved = 0""" if IS_MYSQL else """SELECT * FROM reservations 
                        WHERE custodian_id = ? 
                        AND status IN ('待保管人确认', '待2人确认')
                        AND custodian_approved = 0"""
            else:
                sql = "SELECT * FROM reservations WHERE custodian_id = %s" if IS_MYSQL else "SELECT * FROM reservations WHERE custodian_id = ?"
            
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
                        AND borrower_approved = 0""" if IS_MYSQL else """SELECT * FROM reservations 
                        WHERE current_borrower_id = ? 
                        AND status IN ('待借用人确认', '待2人确认')
                        AND borrower_approved = 0"""
            else:
                sql = "SELECT * FROM reservations WHERE current_borrower_id = %s" if IS_MYSQL else "SELECT * FROM reservations WHERE current_borrower_id = ?"
            
            cursor.execute(sql, (borrower_id,))
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    def save_reservation(self, reservation: Reservation) -> bool:
        """保存预约"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute(
                "SELECT id FROM reservations WHERE id = %s" if IS_MYSQL else
                "SELECT id FROM reservations WHERE id = ?",
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
                """ if IS_MYSQL else """UPDATE reservations SET
                    device_id = ?, device_type = ?, device_name = ?,
                    reserver_id = ?, reserver_name = ?,
                    start_time = ?, end_time = ?, status = ?,
                    updated_at = ?,
                    custodian_approved = ?, custodian_approved_at = ?,
                    borrower_approved = ?, borrower_approved_at = ?,
                    custodian_notified = ?, borrower_notified = ?,
                    cancelled_by = ?, cancelled_at = ?, cancel_reason = ?,
                    rejected_by = ?, rejected_at = ?,
                    converted_to_borrow = ?, converted_at = ?,
                    custodian_id = ?, current_borrower_id = ?, current_borrower_name = ?,
                    reason = ?
                    WHERE id = ?
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
                """ if IS_MYSQL else """INSERT INTO reservations (
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM reservations WHERE id = %s" if IS_MYSQL else
                "DELETE FROM reservations WHERE id = ?",
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
                   AND converted_to_borrow = 0""" if IS_MYSQL else
                """SELECT * FROM reservations 
                   WHERE status = '已同意' 
                   AND start_time <= ? 
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
                   AND status IN ('已取消', '已拒绝', '已过期', '已转借用')""" if IS_MYSQL else
                """SELECT * FROM reservations 
                   WHERE end_time <= ? 
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
                   AND start_time <= %s""" if IS_MYSQL else
                """SELECT * FROM reservations 
                   WHERE status IN ('待保管人确认', '待借用人确认', '待2人确认')
                   AND start_time <= ?""",
                (now,)
            )
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
    def get_reservations_by_status(self, status: str) -> List[Reservation]:
        """根据状态获取预约列表"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reservations WHERE status = %s" if IS_MYSQL else
                "SELECT * FROM reservations WHERE status = ?",
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
                "SELECT * FROM user_points WHERE user_id = %s" if IS_MYSQL else
                "SELECT * FROM user_points WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return UserPoints.from_dict(row_to_dict(row))
            return None
    
    def save_user_points(self, user_points: UserPoints) -> bool:
        """保存用户积分"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute(
                "SELECT id FROM user_points WHERE user_id = %s" if IS_MYSQL else
                "SELECT id FROM user_points WHERE user_id = ?",
                (user_points.user_id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                sql = """UPDATE user_points SET
                    points = %s, total_earned = %s, total_spent = %s, update_time = %s
                    WHERE user_id = %s
                """ if IS_MYSQL else """UPDATE user_points SET
                    points = ?, total_earned = ?, total_spent = ?, update_time = ?
                    WHERE user_id = ?
                """
                params = (
                    user_points.points, user_points.total_earned, user_points.total_spent,
                    format_datetime(datetime.now()), user_points.user_id
                )
            else:
                sql = """INSERT INTO user_points (
                    id, user_id, points, total_earned, total_spent, update_time
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """ if IS_MYSQL else """INSERT INTO user_points (
                    id, user_id, points, total_earned, total_spent, update_time
                ) VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (
                    user_points.id, user_points.user_id, user_points.points,
                    user_points.total_earned, user_points.total_spent, format_datetime(datetime.now())
                )
            
            cursor.execute(sql, params)
            return True
    
    def add_points_record(self, record: PointsRecord) -> bool:
        """添加积分记录"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO points_records (
                id, user_id, transaction_type, points_change, points_after,
                description, related_id, create_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO points_records (
                id, user_id, transaction_type, points_change, points_after,
                description, related_id, create_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                    "SELECT * FROM points_records WHERE user_id = %s ORDER BY create_time DESC LIMIT %s" if IS_MYSQL else
                    "SELECT * FROM points_records WHERE user_id = ? ORDER BY create_time DESC LIMIT ?",
                    (user_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM points_records WHERE user_id = %s ORDER BY create_time DESC" if IS_MYSQL else
                    "SELECT * FROM points_records WHERE user_id = ? ORDER BY create_time DESC",
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
    
    # ========== 悬赏相关操作 ==========
    
    def get_bounty_by_id(self, bounty_id: str) -> Optional[Bounty]:
        """根据ID获取悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bounties WHERE id = %s" if IS_MYSQL else
                "SELECT * FROM bounties WHERE id = ?",
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
                sql += " WHERE status = %s" if IS_MYSQL else " WHERE status = ?"
                params.append(status)
            
            sql += " ORDER BY create_time DESC"
            
            if limit:
                sql += " LIMIT %s" if IS_MYSQL else " LIMIT ?"
                params.append(limit)
            
            cursor.execute(sql, tuple(params) if params else ())
            rows = cursor.fetchall()
            return [Bounty.from_dict(row_to_dict(row)) for row in rows]
    
    def get_bounties_by_publisher(self, publisher_id: str) -> List[Bounty]:
        """获取用户发布的悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bounties WHERE publisher_id = %s ORDER BY create_time DESC" if IS_MYSQL else
                "SELECT * FROM bounties WHERE publisher_id = ? ORDER BY create_time DESC",
                (publisher_id,)
            )
            rows = cursor.fetchall()
            return [Bounty.from_dict(row_to_dict(row)) for row in rows]
    
    def get_bounties_by_claimer(self, claimer_id: str) -> List[Bounty]:
        """获取用户认领的悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bounties WHERE claimer_id = %s ORDER BY create_time DESC" if IS_MYSQL else
                "SELECT * FROM bounties WHERE claimer_id = ? ORDER BY create_time DESC",
                (claimer_id,)
            )
            rows = cursor.fetchall()
            return [Bounty.from_dict(row_to_dict(row)) for row in rows]
    
    def save_bounty(self, bounty: Bounty) -> bool:
        """保存悬赏"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute(
                "SELECT id FROM bounties WHERE id = %s" if IS_MYSQL else
                "SELECT id FROM bounties WHERE id = ?",
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
                """ if IS_MYSQL else """UPDATE bounties SET
                    title = ?, description = ?, publisher_id = ?, publisher_name = ?,
                    reward_points = ?, status = ?, device_name = ?, device_id = ?,
                    device_previous_status = ?, claim_time = ?, complete_time = ?,
                    expire_time = ?, claimer_id = ?, claimer_name = ?, finder_description = ?,
                    is_active = ?
                    WHERE id = ?
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
                """ if IS_MYSQL else """INSERT INTO bounties (
                    id, title, description, publisher_id, publisher_name, reward_points,
                    status, device_name, device_id, device_previous_status, create_time,
                    claim_time, complete_time, expire_time, claimer_id, claimer_name, finder_description,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM bounties WHERE id = %s" if IS_MYSQL else
                "DELETE FROM bounties WHERE id = ?",
                (bounty_id,)
            )
            return cursor.rowcount > 0

    def get_expired_bounties(self) -> List[Bounty]:
        """获取所有已过期的待认领悬赏"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "SELECT * FROM bounties WHERE status = '待认领' AND expire_time < %s" if IS_MYSQL else
                "SELECT * FROM bounties WHERE status = '待认领' AND expire_time < ?",
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
                "SELECT * FROM shop_items WHERE id = %s" if IS_MYSQL else
                "SELECT * FROM shop_items WHERE id = ?",
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
                sql += " AND item_type = %s" if IS_MYSQL else " AND item_type = ?"
                params.append(item_type)
            
            sql += " ORDER BY sort_order ASC, create_time ASC"
            
            cursor.execute(sql, tuple(params) if params else ())
            rows = cursor.fetchall()
            return [ShopItem.from_dict(row_to_dict(row)) for row in rows]
    
    def save_shop_item(self, item: ShopItem) -> bool:
        """保存商品"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id FROM shop_items WHERE id = %s" if IS_MYSQL else
                "SELECT id FROM shop_items WHERE id = ?",
                (item.id,)
            )
            exists = cursor.fetchone()
            
            if exists:
                sql = """UPDATE shop_items SET
                    name = %s, description = %s, item_type = %s, price = %s,
                    icon = %s, color = %s, is_active = %s, sort_order = %s
                    WHERE id = %s
                """ if IS_MYSQL else """UPDATE shop_items SET
                    name = ?, description = ?, item_type = ?, price = ?,
                    icon = ?, color = ?, is_active = ?, sort_order = ?
                    WHERE id = ?
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
                """ if IS_MYSQL else """INSERT INTO shop_items (
                    id, name, description, item_type, price, icon, color, is_active, sort_order, create_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM shop_items WHERE id = %s" if IS_MYSQL else
                "DELETE FROM shop_items WHERE id = ?",
                (item_id,)
            )
            return True
    
    # ========== 用户背包相关操作 ==========
    
    def get_user_inventory(self, user_id: str, item_type: str = None) -> List[UserInventory]:
        """获取用户背包物品"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM user_inventory WHERE user_id = %s" if IS_MYSQL else "SELECT * FROM user_inventory WHERE user_id = ?"
            params = [user_id]
            
            if item_type:
                sql += " AND item_type = %s" if IS_MYSQL else " AND item_type = ?"
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
                "SELECT * FROM user_inventory WHERE id = %s" if IS_MYSQL else
                "SELECT * FROM user_inventory WHERE id = ?",
                (inventory_id,)
            )
            row = cursor.fetchone()
            if row:
                return UserInventory.from_dict(row_to_dict(row))
            return None
    
    def add_to_inventory(self, item: UserInventory) -> bool:
        """添加物品到背包"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_inventory (
                id, user_id, item_id, item_type, item_name, item_icon, item_color,
                source, is_used, acquire_time, use_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO user_inventory (
                id, user_id, item_id, item_type, item_name, item_icon, item_color,
                source, is_used, acquire_time, use_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """UPDATE user_inventory SET
                is_used = %s, use_time = %s
                WHERE id = %s
            """ if IS_MYSQL else """UPDATE user_inventory SET
                is_used = ?, use_time = ?
                WHERE id = ?
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
                "SELECT id FROM user_inventory WHERE user_id = %s AND item_id = %s LIMIT 1" if IS_MYSQL else
                "SELECT id FROM user_inventory WHERE user_id = ? AND item_id = ? LIMIT 1",
                (user_id, item_id)
            )
            return cursor.fetchone() is not None

    # ========== 每日转盘相关操作 ==========

    def add_wheel_record(self, user_id: str, prize_id: str, prize_name: str, prize_points: int, cost: int) -> bool:
        """添加转盘抽奖记录"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO wheel_records (
                id, user_id, prize_id, prize_name, prize_points, cost, create_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO wheel_records (
                id, user_id, prize_id, prize_name, prize_points, cost, create_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
            if IS_MYSQL:
                cursor.execute(
                    """SELECT * FROM wheel_records 
                       WHERE user_id = %s AND DATE(create_time) = %s 
                       ORDER BY create_time ASC""",
                    (user_id, date_str)
                )
            else:
                cursor.execute(
                    """SELECT * FROM wheel_records 
                       WHERE user_id = ? AND date(create_time) = ? 
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
                   LIMIT %s""" if IS_MYSQL else
                """SELECT * FROM wheel_records 
                   WHERE user_id = ? 
                   ORDER BY create_time DESC 
                   LIMIT ?""",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]

    def add_hidden_title(self, user_id: str, title_id: str, title_name: str, title_color: str) -> bool:
        """添加用户隐藏称号"""
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            sql = """INSERT INTO user_hidden_titles (
                id, user_id, title_id, title_name, title_color, acquire_time
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """ if IS_MYSQL else """INSERT INTO user_hidden_titles (
                id, user_id, title_id, title_name, title_color, acquire_time
            ) VALUES (?, ?, ?, ?, ?, ?)
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
                   WHERE user_id = %s AND title_id = %s LIMIT 1""" if IS_MYSQL else
                """SELECT id FROM user_hidden_titles 
                   WHERE user_id = ? AND title_id = ? LIMIT 1""",
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
                   ORDER BY acquire_time DESC""" if IS_MYSQL else
                """SELECT * FROM user_hidden_titles 
                   WHERE user_id = ? 
                   ORDER BY acquire_time DESC""",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]


# ========== 数据库迁移函数 ==========

def _migrate_sqlite_create_points_tables(cursor):
    """SQLite: 创建积分相关表"""
    # 创建用户积分表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_points (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE,
            points INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 创建积分记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS points_records (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            points_change INTEGER NOT NULL,
            points_after INTEGER NOT NULL,
            description TEXT,
            related_id TEXT,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_points_user ON user_points(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_points_records_user ON points_records(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_points_records_time ON points_records(create_time)')
    print("✓ SQLite: 已创建积分相关表")


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


def _migrate_sqlite_create_shop_tables(cursor):
    """SQLite: 创建积分商城相关表"""
    # 创建商品表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            item_type TEXT NOT NULL,
            price INTEGER NOT NULL,
            icon TEXT,
            color TEXT,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建用户背包表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_inventory (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_icon TEXT,
            item_color TEXT,
            source TEXT DEFAULT '积分商城',
            is_used INTEGER DEFAULT 0,
            acquire_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            use_time TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_shop_items_type ON shop_items(item_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_shop_items_active ON shop_items(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_inventory_user ON user_inventory(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_inventory_item ON user_inventory(item_id)')
    print("✓ SQLite: 已创建积分商城相关表")


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


def _migrate_sqlite_add_user_equip_fields(cursor):
    """SQLite: 添加用户装扮字段"""
    try:
        cursor.execute("SELECT current_title FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN current_title TEXT DEFAULT ''")
        print("✓ SQLite: 已添加 current_title 列到 users 表")

    try:
        cursor.execute("SELECT current_avatar_frame FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN current_avatar_frame TEXT DEFAULT ''")
        print("✓ SQLite: 已添加 current_avatar_frame 列到 users 表")

    try:
        cursor.execute("SELECT current_theme FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN current_theme TEXT DEFAULT ''")
        print("✓ SQLite: 已添加 current_theme 列到 users 表")


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


def _migrate_sqlite_add_user_cursor_field(cursor):
    """SQLite: 添加用户鼠标皮肤字段"""
    try:
        cursor.execute("SELECT current_cursor FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN current_cursor TEXT DEFAULT ''")
        print("✓ SQLite: 已添加 current_cursor 列到 users 表")


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


def _migrate_sqlite_create_bounties_table(cursor):
    """SQLite: 创建悬赏表"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bounties (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            publisher_id TEXT NOT NULL,
            publisher_name TEXT NOT NULL,
            reward_points INTEGER NOT NULL,
            status TEXT DEFAULT '待认领',
            device_name TEXT,
            device_id TEXT,
            device_previous_status TEXT,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            claim_time TIMESTAMP,
            complete_time TIMESTAMP,
            claimer_id TEXT,
            claimer_name TEXT,
            finder_description TEXT,
            FOREIGN KEY (publisher_id) REFERENCES users(id)
        )
    ''')

    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bounties_status ON bounties(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bounties_publisher ON bounties(publisher_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bounties_claimer ON bounties(claimer_id)')
    print("✓ SQLite: 已创建悬赏表")

    # 检查并添加 device_id 列
    try:
        cursor.execute("SELECT device_id FROM bounties LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE bounties ADD COLUMN device_id TEXT")
        print("✓ SQLite: 已添加 device_id 列到 bounties 表")

    # 检查并添加 device_previous_status 列
    try:
        cursor.execute("SELECT device_previous_status FROM bounties LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE bounties ADD COLUMN device_previous_status TEXT")
        print("✓ SQLite: 已添加 device_previous_status 列到 bounties 表")

    # 检查并添加 expire_time 列
    try:
        cursor.execute("SELECT expire_time FROM bounties LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE bounties ADD COLUMN expire_time TIMESTAMP")
        print("✓ SQLite: 已添加 expire_time 列到 bounties 表")

    # 检查并添加 is_active 列
    try:
        cursor.execute("SELECT is_active FROM bounties LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE bounties ADD COLUMN is_active INTEGER DEFAULT 1")
        print("✓ SQLite: 已添加 is_active 列到 bounties 表")


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


def _migrate_sqlite_create_wheel_tables(cursor):
    """SQLite: 创建每日转盘相关表"""
    # 创建转盘抽奖记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wheel_records (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            prize_id TEXT NOT NULL,
            prize_name TEXT NOT NULL,
            prize_points INTEGER DEFAULT 0,
            cost INTEGER DEFAULT 0,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 创建用户隐藏称号表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_hidden_titles (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title_id TEXT NOT NULL,
            title_name TEXT NOT NULL,
            title_color TEXT DEFAULT '#1890ff',
            acquire_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_wheel_records_user ON wheel_records(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_wheel_records_time ON wheel_records(create_time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_hidden_titles_user ON user_hidden_titles(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_hidden_titles_title ON user_hidden_titles(title_id)')
    print("✓ SQLite: 已创建每日转盘相关表")


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
