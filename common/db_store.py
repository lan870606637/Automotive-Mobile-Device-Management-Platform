# -*- coding: utf-8 -*-
"""
SQLite数据库操作模块
替代Excel数据存储，提供数据库读写操作
"""
import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, Admin, Notification, Announcement, UserLike
from .models import DeviceStatus, DeviceType, OperationType

# 数据库路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'device_management.db')


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """将数据库行转换为字典"""
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
    """初始化数据库，创建必要的表"""
    # 确保数据库目录存在
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 创建用户备注表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_remarks (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                device_type TEXT,
                content TEXT,
                creator TEXT,
                create_time TIMESTAMP,
                is_inappropriate INTEGER DEFAULT 0
            )
        ''')
        
        # 创建设备表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                model TEXT,
                cabinet_number TEXT,
                status TEXT DEFAULT '在库',
                remark TEXT,
                jira_address TEXT,
                is_deleted INTEGER DEFAULT 0,
                create_time TIMESTAMP,
                borrower TEXT,
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
                screen_resolution TEXT
            )
        ''')
        
        # 创建借还记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                device_id TEXT,
                device_name TEXT,
                device_type TEXT,
                operation_type TEXT,
                operator TEXT,
                operation_time TIMESTAMP,
                borrower TEXT,
                phone TEXT,
                reason TEXT,
                entry_source TEXT,
                remark TEXT
            )
        ''')
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                wechat_name TEXT,
                phone TEXT,
                password TEXT DEFAULT '123456',
                borrower_name TEXT,
                borrow_count INTEGER DEFAULT 0,
                return_count INTEGER DEFAULT 0,
                is_frozen INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                create_time TIMESTAMP
            )
        ''')
        
        # 创建查看记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS view_records (
                id TEXT PRIMARY KEY,
                device_id TEXT,
                device_type TEXT,
                viewer TEXT,
                view_time TIMESTAMP
            )
        ''')
        
        # 创建操作日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id TEXT PRIMARY KEY,
                operation_time TIMESTAMP,
                operator TEXT,
                operation_content TEXT,
                device_info TEXT
            )
        ''')
        
        # 创建通知表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                title TEXT,
                content TEXT,
                device_name TEXT,
                device_id TEXT,
                is_read INTEGER DEFAULT 0,
                create_time TIMESTAMP,
                notification_type TEXT DEFAULT 'info'
            )
        ''')
        
        # 创建公告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                announcement_type TEXT DEFAULT 'normal',
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                creator TEXT,
                create_time TIMESTAMP,
                update_time TIMESTAMP,
                force_show_version INTEGER DEFAULT 0
            )
        ''')
        
        # 创建用户点赞表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_likes (
                id TEXT PRIMARY KEY,
                from_user_id TEXT,
                to_user_id TEXT,
                create_date TEXT,
                create_time TIMESTAMP
            )
        ''')
        
        conn.commit()


class DatabaseStore:
    """SQLite数据存储类"""
    
    @staticmethod
    def _row_to_device(row: sqlite3.Row) -> Device:
        """将数据库行转换为Device对象"""
        device_type = row['device_type']
        
        # 根据设备类型创建对应的对象
        if device_type == '车机':
            device = CarMachine(
                id=row['id'],
                name=row['name'],
                model=safe_str(row['model']),
                cabinet_number=safe_str(row['cabinet_number']),
                status=DeviceStatus(row['status']) if row['status'] else DeviceStatus.IN_STOCK,
                remark=safe_str(row['remark']),
                jira_address=safe_str(row['jira_address']),
                is_deleted=bool(row['is_deleted']),
                create_time=parse_datetime(row['create_time']),
            )
        elif device_type == '仪表':
            device = Instrument(
                id=row['id'],
                name=row['name'],
                model=safe_str(row['model']),
                cabinet_number=safe_str(row['cabinet_number']),
                status=DeviceStatus(row['status']) if row['status'] else DeviceStatus.IN_STOCK,
                remark=safe_str(row['remark']),
                jira_address=safe_str(row['jira_address']),
                is_deleted=bool(row['is_deleted']),
                create_time=parse_datetime(row['create_time']),
            )
        elif device_type == '手机':
            device = Phone(
                id=row['id'],
                name=row['name'],
                model=safe_str(row['model']),
                cabinet_number=safe_str(row['cabinet_number']),
                status=DeviceStatus(row['status']) if row['status'] else DeviceStatus.IN_CUSTODY,
                remark=safe_str(row['remark']),
                jira_address=safe_str(row['jira_address']),
                is_deleted=bool(row['is_deleted']),
                create_time=parse_datetime(row['create_time']),
            )
        elif device_type == '手机卡':
            device = SimCard(
                id=row['id'],
                name=row['name'],
                model=safe_str(row['model']),
                cabinet_number=safe_str(row['cabinet_number']),
                status=DeviceStatus(row['status']) if row['status'] else DeviceStatus.IN_CUSTODY,
                remark=safe_str(row['remark']),
                jira_address=safe_str(row['jira_address']),
                is_deleted=bool(row['is_deleted']),
                create_time=parse_datetime(row['create_time']),
            )
        else:  # 其它设备
            device = OtherDevice(
                id=row['id'],
                name=row['name'],
                model=safe_str(row['model']),
                cabinet_number=safe_str(row['cabinet_number']),
                status=DeviceStatus(row['status']) if row['status'] else DeviceStatus.IN_CUSTODY,
                remark=safe_str(row['remark']),
                jira_address=safe_str(row['jira_address']),
                is_deleted=bool(row['is_deleted']),
                create_time=parse_datetime(row['create_time']),
            )
        
        # 通用字段
        device.borrower = safe_str(row['borrower'])
        device.phone = safe_str(row['phone'])
        device.borrow_time = parse_datetime(row['borrow_time'])
        device.location = safe_str(row['location'])
        device.reason = safe_str(row['reason'])
        device.entry_source = safe_str(row['entry_source'])
        device.expected_return_date = parse_datetime(row['expected_return_date'])
        device.admin_operator = safe_str(row['admin_operator'])
        device.ship_time = parse_datetime(row['ship_time'])
        device.ship_remark = safe_str(row['ship_remark'])
        device.ship_by = safe_str(row['ship_by'])
        device.pre_ship_borrower = safe_str(row['pre_ship_borrower'])
        device.pre_ship_borrow_time = parse_datetime(row['pre_ship_borrow_time'])
        device.pre_ship_expected_return_date = parse_datetime(row['pre_ship_expected_return_date'])
        device.lost_time = parse_datetime(row['lost_time'])
        device.damage_reason = safe_str(row['damage_reason'])
        device.damage_time = parse_datetime(row['damage_time'])
        device.previous_borrower = safe_str(row['previous_borrower'])
        
        # 特有字段
        device.sn = safe_str(row['sn'])
        device.system_version = safe_str(row['system_version'])
        device.imei = safe_str(row['imei'])
        device.carrier = safe_str(row['carrier'])
        device.software_version = safe_str(row['software_version'])
        device.hardware_version = safe_str(row['hardware_version'])
        device.project_attribute = safe_str(row['project_attribute'])
        device.connection_method = safe_str(row['connection_method'])
        device.os_version = safe_str(row['os_version'])
        device.os_platform = safe_str(row['os_platform'])
        device.product_name = safe_str(row['product_name'])
        device.screen_orientation = safe_str(row['screen_orientation'])
        device.screen_resolution = safe_str(row['screen_resolution'])
        
        return device
    
    @staticmethod
    def _device_to_tuple(device: Device) -> tuple:
        """将Device对象转换为数据库元组"""
        return (
            device.id,
            device.name,
            device.device_type.value,
            device.model,
            device.cabinet_number,
            device.status.value,
            device.remark,
            device.jira_address,
            1 if device.is_deleted else 0,
            format_datetime(device.create_time),
            device.borrower,
            device.phone,
            format_datetime(device.borrow_time),
            device.location,
            device.reason,
            device.entry_source,
            format_datetime(device.expected_return_date),
            device.admin_operator,
            format_datetime(device.ship_time),
            device.ship_remark,
            device.ship_by,
            device.pre_ship_borrower,
            format_datetime(device.pre_ship_borrow_time),
            format_datetime(device.pre_ship_expected_return_date),
            format_datetime(device.lost_time),
            device.damage_reason,
            format_datetime(device.damage_time),
            device.previous_borrower,
            device.sn,
            device.system_version,
            device.imei,
            device.carrier,
            device.software_version,
            device.hardware_version,
            device.project_attribute,
            device.connection_method,
            device.os_version,
            device.os_platform,
            device.product_name,
            device.screen_orientation,
            device.screen_resolution,
        )
    
    # ==================== 设备相关操作 ====================
    
    @staticmethod
    def get_all_devices(device_type: Optional[str] = None, include_deleted: bool = False) -> List[Device]:
        """获取所有设备"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if device_type:
                if include_deleted:
                    cursor.execute('SELECT * FROM devices WHERE device_type = ?', (device_type,))
                else:
                    cursor.execute('SELECT * FROM devices WHERE device_type = ? AND is_deleted = 0', (device_type,))
            else:
                if include_deleted:
                    cursor.execute('SELECT * FROM devices')
                else:
                    cursor.execute('SELECT * FROM devices WHERE is_deleted = 0')
            
            rows = cursor.fetchall()
            return [DatabaseStore._row_to_device(row) for row in rows]
    
    @staticmethod
    def get_device_by_id(device_id: str) -> Optional[Device]:
        """根据ID获取设备"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
            row = cursor.fetchone()
            if row:
                return DatabaseStore._row_to_device(row)
            return None
    
    @staticmethod
    def save_device(device: Device):
        """保存设备（新增或更新）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, is_deleted, create_time, borrower, phone,
                    borrow_time, location, reason, entry_source, expected_return_date,
                    admin_operator, ship_time, ship_remark, ship_by, pre_ship_borrower,
                    pre_ship_borrow_time, pre_ship_expected_return_date, lost_time,
                    damage_reason, damage_time, previous_borrower, sn, system_version,
                    imei, carrier, software_version, hardware_version, project_attribute,
                    connection_method, os_version, os_platform, product_name,
                    screen_orientation, screen_resolution
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', DatabaseStore._device_to_tuple(device))
            conn.commit()
    
    @staticmethod
    def delete_device(device_id: str, soft_delete: bool = True):
        """删除设备（软删除或硬删除）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if soft_delete:
                cursor.execute('UPDATE devices SET is_deleted = 1 WHERE id = ?', (device_id,))
            else:
                cursor.execute('DELETE FROM devices WHERE id = ?', (device_id,))
            conn.commit()
    
    @staticmethod
    def search_devices(keyword: str, device_type: Optional[str] = None) -> List[Device]:
        """搜索设备"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            sql = '''
                SELECT * FROM devices 
                WHERE is_deleted = 0 
                AND (name LIKE ? OR model LIKE ? OR cabinet_number LIKE ? OR borrower LIKE ?)
            '''
            params = [f'%{keyword}%'] * 4
            
            if device_type:
                sql += ' AND device_type = ?'
                params.append(device_type)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [DatabaseStore._row_to_device(row) for row in rows]
    
    # ==================== 记录相关操作 ====================
    
    @staticmethod
    def get_all_records() -> List[Record]:
        """获取所有记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM records ORDER BY operation_time DESC')
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                record = Record(
                    id=row['id'],
                    device_id=row['device_id'],
                    device_name=safe_str(row['device_name']),
                    device_type=safe_str(row['device_type']),
                    operation_type=OperationType(row['operation_type']),
                    operator=row['operator'],
                    operation_time=parse_datetime(row['operation_time']) or datetime.now(),
                    borrower=safe_str(row['borrower']),
                    phone=safe_str(row['phone']),
                    reason=safe_str(row['reason']),
                    entry_source=safe_str(row['entry_source']),
                    remark=safe_str(row['remark']),
                )
                records.append(record)
            return records
    
    @staticmethod
    def get_records_by_device(device_id: str) -> List[Record]:
        """获取设备的记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM records WHERE device_id = ? ORDER BY operation_time DESC', (device_id,))
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                record = Record(
                    id=row['id'],
                    device_id=row['device_id'],
                    device_name=safe_str(row['device_name']),
                    device_type=safe_str(row['device_type']),
                    operation_type=OperationType(row['operation_type']),
                    operator=row['operator'],
                    operation_time=parse_datetime(row['operation_time']) or datetime.now(),
                    borrower=safe_str(row['borrower']),
                    phone=safe_str(row['phone']),
                    reason=safe_str(row['reason']),
                    entry_source=safe_str(row['entry_source']),
                    remark=safe_str(row['remark']),
                )
                records.append(record)
            return records
    
    @staticmethod
    def save_record(record: Record):
        """保存记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO records (
                    id, device_id, device_name, device_type, operation_type,
                    operator, operation_time, borrower, phone, reason, entry_source, remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.id,
                record.device_id,
                record.device_name,
                record.device_type,
                record.operation_type.value,
                record.operator,
                format_datetime(record.operation_time),
                record.borrower,
                record.phone,
                record.reason,
                record.entry_source,
                record.remark,
            ))
            conn.commit()
    
    # ==================== 用户相关操作 ====================
    
    @staticmethod
    def get_all_users(include_deleted: bool = False) -> List[User]:
        """获取所有用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if include_deleted:
                cursor.execute('SELECT * FROM users')
            else:
                cursor.execute('SELECT * FROM users WHERE is_deleted = 0')
            
            rows = cursor.fetchall()
            users = []
            for row in rows:
                user = User(
                    id=row['id'],
                    wechat_name=safe_str(row['wechat_name']),
                    phone=safe_str(row['phone']),
                    password=safe_str(row['password']),
                    borrower_name=safe_str(row['borrower_name']),
                    borrow_count=row['borrow_count'] or 0,
                    return_count=row['return_count'] or 0,
                    is_frozen=bool(row['is_frozen']),
                    is_admin=bool(row['is_admin']),
                    is_deleted=bool(row['is_deleted']),
                    create_time=parse_datetime(row['create_time']),
                )
                users.append(user)
            return users
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return User(
                    id=row['id'],
                    wechat_name=safe_str(row['wechat_name']),
                    phone=safe_str(row['phone']),
                    password=safe_str(row['password']),
                    borrower_name=safe_str(row['borrower_name']),
                    borrow_count=row['borrow_count'] or 0,
                    return_count=row['return_count'] or 0,
                    is_frozen=bool(row['is_frozen']),
                    is_admin=bool(row['is_admin']),
                    is_deleted=bool(row['is_deleted']),
                    create_time=parse_datetime(row['create_time']),
                )
            return None
    
    @staticmethod
    def get_user_by_phone(phone: str) -> Optional[User]:
        """根据手机号获取用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE phone = ? AND is_deleted = 0', (phone,))
            row = cursor.fetchone()
            if row:
                return User(
                    id=row['id'],
                    wechat_name=safe_str(row['wechat_name']),
                    phone=safe_str(row['phone']),
                    password=safe_str(row['password']),
                    borrower_name=safe_str(row['borrower_name']),
                    borrow_count=row['borrow_count'] or 0,
                    return_count=row['return_count'] or 0,
                    is_frozen=bool(row['is_frozen']),
                    is_admin=bool(row['is_admin']),
                    is_deleted=bool(row['is_deleted']),
                    create_time=parse_datetime(row['create_time']),
                )
            return None
    
    @staticmethod
    def save_user(user: User):
        """保存用户"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (
                    id, wechat_name, phone, password, borrower_name,
                    borrow_count, return_count, is_frozen, is_admin, is_deleted, create_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user.id,
                user.wechat_name,
                user.phone,
                user.password,
                user.borrower_name,
                user.borrow_count,
                user.return_count,
                1 if user.is_frozen else 0,
                1 if user.is_admin else 0,
                1 if user.is_deleted else 0,
                format_datetime(user.create_time),
            ))
            conn.commit()
    
    # ==================== 管理员相关操作 ====================
    
    @staticmethod
    def get_all_admins() -> List[Admin]:
        """获取所有管理员"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM admins')
            rows = cursor.fetchall()
            
            admins = []
            for row in rows:
                admin = Admin(
                    id=row['id'],
                    username=row['username'],
                    password=row['password'],
                    create_time=parse_datetime(row['create_time']),
                )
                admins.append(admin)
            return admins
    
    @staticmethod
    def get_admin_by_username(username: str) -> Optional[Admin]:
        """根据用户名获取管理员"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM admins WHERE username = ?', (username,))
            row = cursor.fetchone()
            if row:
                return Admin(
                    id=row['id'],
                    username=row['username'],
                    password=row['password'],
                    create_time=parse_datetime(row['create_time']),
                )
            return None
    
    # ==================== 通知相关操作 ====================
    
    @staticmethod
    def get_notifications_by_user(user_id: str) -> List[Notification]:
        """获取用户的通知"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY create_time DESC', (user_id,))
            rows = cursor.fetchall()
            
            notifications = []
            for row in rows:
                notification = Notification(
                    id=row['id'],
                    user_id=row['user_id'],
                    user_name=safe_str(row['user_name']),
                    title=row['title'],
                    content=row['content'],
                    device_name=safe_str(row['device_name']),
                    device_id=safe_str(row['device_id']),
                    is_read=bool(row['is_read']),
                    create_time=parse_datetime(row['create_time']),
                    notification_type=safe_str(row['notification_type']),
                )
                notifications.append(notification)
            return notifications
    
    @staticmethod
    def save_notification(notification: Notification):
        """保存通知"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO notifications (
                    id, user_id, user_name, title, content, device_name,
                    device_id, is_read, create_time, notification_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                notification.id,
                notification.user_id,
                notification.user_name,
                notification.title,
                notification.content,
                notification.device_name,
                notification.device_id,
                1 if notification.is_read else 0,
                notification.create_time.strftime('%Y-%m-%d %H:%M:%S') if notification.create_time else None,
                notification.notification_type,
            ))
            conn.commit()
    
    @staticmethod
    def mark_notification_as_read(notification_id: str):
        """标记通知为已读"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))
            conn.commit()
    
    # ==================== 公告相关操作 ====================
    
    @staticmethod
    def get_all_announcements(active_only: bool = True) -> List[Announcement]:
        """获取所有公告"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if active_only:
                cursor.execute('SELECT * FROM announcements WHERE is_active = 1 ORDER BY sort_order ASC, create_time DESC')
            else:
                cursor.execute('SELECT * FROM announcements ORDER BY sort_order ASC, create_time DESC')
            
            rows = cursor.fetchall()
            
            announcements = []
            for row in rows:
                announcement = Announcement(
                    id=row['id'],
                    title=row['title'],
                    content=row['content'],
                    announcement_type=safe_str(row['announcement_type']),
                    is_active=bool(row['is_active']),
                    sort_order=row['sort_order'] or 0,
                    creator=safe_str(row['creator']),
                    create_time=parse_datetime(row['create_time']),
                    update_time=parse_datetime(row['update_time']),
                    force_show_version=row['force_show_version'] or 0,
                )
                announcements.append(announcement)
            return announcements
    
    @staticmethod
    def save_announcement(announcement: Announcement):
        """保存公告"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO announcements (
                    id, title, content, announcement_type, is_active,
                    sort_order, creator, create_time, update_time, force_show_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                announcement.id,
                announcement.title,
                announcement.content,
                announcement.announcement_type,
                1 if announcement.is_active else 0,
                announcement.sort_order,
                announcement.creator,
                format_datetime(announcement.create_time),
                format_datetime(announcement.update_time),
                announcement.force_show_version,
            ))
            conn.commit()
    
    # ==================== 操作日志相关操作 ====================
    
    @staticmethod
    def get_all_operation_logs() -> List[OperationLog]:
        """获取所有操作日志"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM operation_logs ORDER BY operation_time DESC')
            rows = cursor.fetchall()
            
            logs = []
            for row in rows:
                log = OperationLog(
                    id=row['id'],
                    operation_time=parse_datetime(row['operation_time']) or datetime.now(),
                    operator=row['operator'],
                    operation_content=safe_str(row['operation_content']),
                    device_info=safe_str(row['device_info']),
                )
                logs.append(log)
            return logs
    
    @staticmethod
    def save_operation_log(log: OperationLog):
        """保存操作日志"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO operation_logs (
                    id, operation_time, operator, operation_content, device_info
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                log.id,
                format_datetime(log.operation_time),
                log.operator,
                log.operation_content,
                log.device_info,
            ))
            conn.commit()
    
    # ==================== 用户备注相关操作 ====================
    
    @staticmethod
    def get_remarks_by_device(device_id: str) -> List[UserRemark]:
        """获取设备的备注"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_remarks WHERE device_id = ? ORDER BY create_time DESC', (device_id,))
            rows = cursor.fetchall()
            
            remarks = []
            for row in rows:
                remark = UserRemark(
                    id=row['id'],
                    device_id=row['device_id'],
                    device_type=safe_str(row['device_type']),
                    content=safe_str(row['content']),
                    creator=row['creator'],
                    create_time=parse_datetime(row['create_time']) or datetime.now(),
                    is_inappropriate=bool(row['is_inappropriate']),
                )
                remarks.append(remark)
            return remarks
    
    @staticmethod
    def save_remark(remark: UserRemark):
        """保存备注"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_remarks (
                    id, device_id, device_type, content, creator, create_time, is_inappropriate
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                remark.id,
                remark.device_id,
                remark.device_type,
                remark.content,
                remark.creator,
                format_datetime(remark.create_time),
                1 if remark.is_inappropriate else 0,
            ))
            conn.commit()

    @staticmethod
    def delete_remark(remark_id: str):
        """删除备注"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_remarks WHERE id = ?', (remark_id,))
            conn.commit()

    @staticmethod
    def mark_remark_inappropriate(remark_id: str, is_inappropriate: bool = True):
        """标记备注为不当内容"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE user_remarks SET is_inappropriate = ? WHERE id = ?',
                         (1 if is_inappropriate else 0, remark_id))
            conn.commit()
            return cursor.rowcount > 0

    # ==================== 查看记录相关操作 ====================
    
    @staticmethod
    def get_view_records_by_device(device_id: str) -> List[Dict]:
        """获取设备的查看记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM view_records WHERE device_id = ? ORDER BY view_time DESC', (device_id,))
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]
    
    @staticmethod
    def save_view_record(device_id: str, device_type: str, viewer: str):
        """保存查看记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            import uuid
            cursor.execute('''
                INSERT INTO view_records (id, device_id, device_type, viewer, view_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()),
                device_id,
                device_type,
                viewer,
                datetime.now(),
            ))
            conn.commit()
    
    # ==================== 用户点赞相关操作 ====================
    
    @staticmethod
    def get_user_likes_by_user(user_id: str) -> List[UserLike]:
        """获取用户的点赞记录（我赞别人的）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_likes WHERE from_user_id = ?', (user_id,))
            rows = cursor.fetchall()
            
            likes = []
            for row in rows:
                like = UserLike(
                    id=row['id'],
                    from_user_id=row['from_user_id'],
                    to_user_id=row['to_user_id'],
                    create_date=safe_str(row['create_date']),
                    create_time=parse_datetime(row['create_time']) or datetime.now(),
                )
                likes.append(like)
            return likes

    @staticmethod
    def get_user_likes_to_user(user_id: str) -> List[UserLike]:
        """获取用户被点赞的记录（别人赞我的）"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_likes WHERE to_user_id = ?', (user_id,))
            rows = cursor.fetchall()
            
            likes = []
            for row in rows:
                like = UserLike(
                    id=row['id'],
                    from_user_id=row['from_user_id'],
                    to_user_id=row['to_user_id'],
                    create_date=safe_str(row['create_date']),
                    create_time=parse_datetime(row['create_time']) or datetime.now(),
                )
                likes.append(like)
            return likes
    
    @staticmethod
    def save_user_like(like: UserLike):
        """保存点赞记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_likes (
                    id, from_user_id, to_user_id, create_date, create_time
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                like.id,
                like.from_user_id,
                like.to_user_id,
                like.create_date,
                format_datetime(like.create_time),
            ))
            conn.commit()

    # ==================== 获取所有数据（兼容方法）====================

    @staticmethod
    def get_all_remarks() -> List[UserRemark]:
        """获取所有备注"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_remarks ORDER BY create_time DESC')
            rows = cursor.fetchall()

            remarks = []
            for row in rows:
                remark = UserRemark(
                    id=row['id'],
                    device_id=row['device_id'],
                    device_type=safe_str(row['device_type']),
                    content=safe_str(row['content']),
                    creator=row['creator'],
                    create_time=parse_datetime(row['create_time']) or datetime.now(),
                    is_inappropriate=bool(row['is_inappropriate']),
                )
                remarks.append(remark)
            return remarks

    @staticmethod
    def get_all_view_records() -> List[Dict]:
        """获取所有查看记录"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM view_records ORDER BY view_time DESC')
            rows = cursor.fetchall()
            return [row_to_dict(row) for row in rows]

    @staticmethod
    def get_all_notifications() -> List[Notification]:
        """获取所有通知"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM notifications ORDER BY create_time DESC')
            rows = cursor.fetchall()

            notifications = []
            for row in rows:
                notification = Notification(
                    id=row['id'],
                    user_id=row['user_id'],
                    user_name=safe_str(row['user_name']),
                    title=row['title'],
                    content=row['content'],
                    device_name=safe_str(row['device_name']),
                    device_id=safe_str(row['device_id']),
                    is_read=bool(row['is_read']),
                    create_time=parse_datetime(row['create_time']),
                    notification_type=safe_str(row['notification_type']),
                )
                notifications.append(notification)
            return notifications

    @staticmethod
    def get_all_user_likes() -> List[UserLike]:
        """获取所有用户点赞"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_likes ORDER BY create_time DESC')
            rows = cursor.fetchall()

            likes = []
            for row in rows:
                like = UserLike(
                    id=row['id'],
                    from_user_id=row['from_user_id'],
                    to_user_id=row['to_user_id'],
                    create_date=safe_str(row['create_date']),
                    create_time=parse_datetime(row['create_time']) or datetime.now(),
                )
                likes.append(like)
            return likes
