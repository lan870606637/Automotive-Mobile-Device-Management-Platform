# -*- coding: utf-8 -*-
"""
数据库操作模块
支持SQLite和MySQL两种数据库
"""
import os
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, Admin, Notification, Announcement, UserLike, Reservation
from .models import DeviceStatus, DeviceType, OperationType, ReservationStatus

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
        # 检查并添加 asset_number 和 purchase_amount 列（如果不存在）
        _migrate_mysql_add_asset_fields()
        # 检查并添加 custodian_id 列（如果不存在）
        _migrate_mysql_add_custodian_id()
        # 创建 reservations 表
        _migrate_mysql_create_reservations()
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

        # 检查并添加 asset_number 和 purchase_amount 列
        _migrate_sqlite_add_asset_fields(cursor)

        # 检查并添加 custodian_id 列
        _migrate_sqlite_add_custodian_id(cursor)

        # 创建 reservations 表
        _migrate_sqlite_create_reservations(cursor)

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
                    damage_reason = %s, damage_time = %s, previous_borrower = %s,
                    sn = %s, system_version = %s, imei = %s, carrier = %s,
                    software_version = %s, hardware_version = %s,
                    project_attribute = %s, connection_method = %s,
                    os_version = %s, os_platform = %s, product_name = %s,
                    screen_orientation = %s, screen_resolution = %s,
                    asset_number = %s, purchase_amount = %s
                    WHERE id = %s
                """ if IS_MYSQL else """UPDATE devices SET
                    name = ?, device_type = ?, model = ?, cabinet_number = ?,
                    status = ?, remark = ?, jira_address = ?, borrower = ?,
                    borrower_id = ?, custodian_id = ?, phone = ?, borrow_time = ?, location = ?, reason = ?,
                    entry_source = ?, expected_return_date = ?, admin_operator = ?,
                    ship_time = ?, ship_remark = ?, ship_by = ?,
                    pre_ship_borrower = ?, pre_ship_borrow_time = ?,
                    pre_ship_expected_return_date = ?, lost_time = ?,
                    damage_reason = ?, damage_time = ?, previous_borrower = ?,
                    sn = ?, system_version = ?, imei = ?, carrier = ?,
                    software_version = ?, hardware_version = ?,
                    project_attribute = ?, connection_method = ?,
                    os_version = ?, os_platform = ?, product_name = ?,
                    screen_orientation = ?, screen_resolution = ?,
                    asset_number = ?, purchase_amount = ?
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
                    format_datetime(device.damage_time), device.previous_borrower,
                    device.sn, device.system_version, device.imei, device.carrier,
                    device.software_version, device.hardware_version,
                    device.project_attribute, device.connection_method,
                    device.os_version, device.os_platform, device.product_name,
                    device.screen_orientation, device.screen_resolution,
                    device.asset_number, device.purchase_amount,
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
                    damage_time, previous_borrower, sn, system_version, imei,
                    carrier, software_version, hardware_version, project_attribute,
                    connection_method, os_version, os_platform, product_name,
                    screen_orientation, screen_resolution, asset_number, purchase_amount
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """ if IS_MYSQL else """INSERT INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, borrower, borrower_id, custodian_id, phone, borrow_time, location, reason,
                    entry_source, expected_return_date, admin_operator, ship_time,
                    ship_remark, ship_by, pre_ship_borrower, pre_ship_borrow_time,
                    pre_ship_expected_return_date, lost_time, damage_reason,
                    damage_time, previous_borrower, sn, system_version, imei,
                    carrier, software_version, hardware_version, project_attribute,
                    connection_method, os_version, os_platform, product_name,
                    screen_orientation, screen_resolution, asset_number, purchase_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    format_datetime(device.damage_time), device.previous_borrower,
                    device.sn, device.system_version, device.imei, device.carrier,
                    device.software_version, device.hardware_version,
                    device.project_attribute, device.connection_method,
                    device.os_version, device.os_platform, device.product_name,
                    device.screen_orientation, device.screen_resolution,
                    device.asset_number, device.purchase_amount
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
                    email = %s, password = %s, borrower_name = %s, avatar = %s,
                    borrow_count = %s, return_count = %s, is_frozen = %s, is_admin = %s, is_deleted = %s, is_first_login = %s
                    WHERE id = %s
                """ if IS_MYSQL else """UPDATE users SET
                    email = ?, password = ?, borrower_name = ?, avatar = ?,
                    borrow_count = ?, return_count = ?, is_frozen = ?, is_admin = ?, is_deleted = ?, is_first_login = ?
                    WHERE id = ?
                """
                params = (
                    user.email, user.password, user.borrower_name, user.avatar,
                    user.borrow_count, user.return_count,
                    1 if user.is_frozen else 0,
                    1 if user.is_admin else 0,
                    1 if user.is_deleted else 0,
                    1 if user.is_first_login else 0,
                    user.id
                )
                cursor.execute(sql, params)
            else:
                sql = """INSERT INTO users (
                    id, email, password, borrower_name, avatar, borrow_count,
                    return_count, is_frozen, is_admin, is_deleted, is_first_login, create_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, CURRENT_TIMESTAMP)
                """ if IS_MYSQL else """INSERT INTO users (
                    id, email, password, borrower_name, avatar, borrow_count,
                    return_count, is_frozen, is_admin, is_deleted, is_first_login, create_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
                """
                params = (
                    user.id, user.email, user.password,
                    user.borrower_name, user.avatar, user.borrow_count, user.return_count,
                    1 if user.is_frozen else 0,
                    1 if user.is_admin else 0,
                    1 if user.is_first_login else 0
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
                # 只获取未结束的有效预约
                sql += " AND end_time > %s AND status NOT IN ('已取消', '已拒绝', '已过期')" if IS_MYSQL else " AND end_time > ? AND status NOT IN ('已取消', '已拒绝', '已过期')"
                params.append(format_datetime(datetime.now()))
            
            sql += " ORDER BY start_time ASC"
            
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [Reservation.from_dict(row_to_dict(row)) for row in rows]
    
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
