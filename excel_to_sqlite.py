# -*- coding: utf-8 -*-
"""
Excel数据导入SQLite数据库脚本
将Excel文件中的数据导入到SQLite数据库中
"""
import os
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = os.path.join(BASE_DIR, 'excel_templates')
DB_PATH = os.path.join(BASE_DIR, 'device_management.db')


def safe_str(val):
    """安全字符串转换,处理NaN和浮点数.0后缀问题"""
    if pd.isna(val) or str(val).lower() == 'nan':
        return ''
    val_str = str(val)
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str


def safe_int(val, default=0):
    """安全整数转换"""
    if pd.isna(val):
        return default
    try:
        return int(val)
    except:
        return default


def safe_float(val, default=0.0):
    """安全浮点数转换"""
    if pd.isna(val):
        return default
    try:
        return float(val)
    except:
        return default


def safe_datetime(val):
    """安全日期时间转换"""
    if pd.isna(val):
        return None
    try:
        if isinstance(val, str):
            # 尝试多种日期格式
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                try:
                    return datetime.strptime(val, fmt)
                except:
                    continue
            return None
        elif isinstance(val, pd.Timestamp):
            return val.to_pydatetime()
        return None
    except:
        return None


def init_database():
    """初始化数据库，创建所有表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建设备表（车机、仪表、手机、手机卡、其它设备共用）
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
    
    # 创建记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            device_name TEXT,
            device_type TEXT,
            operation_type TEXT NOT NULL,
            operator TEXT NOT NULL,
            operation_time TIMESTAMP NOT NULL,
            borrower TEXT,
            phone TEXT,
            reason TEXT,
            entry_source TEXT,
            remark TEXT
        )
    ''')
    
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
    
    # 创建查看记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS view_records (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            device_type TEXT,
            viewer TEXT,
            view_time TIMESTAMP
        )
    ''')
    
    # 创建管理员表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            create_time TIMESTAMP
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
    conn.close()
    print("数据库初始化完成！")


def import_car_machines():
    """导入车机数据"""
    filepath = os.path.join(EXCEL_DIR, '车机表.xlsx')
    if not os.path.exists(filepath):
        print("车机表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('设备ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, is_deleted, create_time, borrower, phone,
                    borrow_time, location, reason, entry_source, expected_return_date,
                    lost_time, damage_reason, damage_time, previous_borrower,
                    software_version, hardware_version, project_attribute,
                    connection_method, os_version, os_platform, product_name,
                    screen_orientation, screen_resolution, ship_time, ship_remark,
                    ship_by, pre_ship_borrower, pre_ship_borrow_time, pre_ship_expected_return_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备名')),
                '车机',
                safe_str(row.get('型号')),
                safe_str(row.get('柜号')),
                safe_str(row.get('状态')),
                safe_str(row.get('备注')),
                safe_str(row.get('JIRA地址')),
                1 if safe_str(row.get('是否删除')) == '是' else 0,
                safe_datetime(row.get('创建时间')),
                safe_str(row.get('借用人')),
                safe_str(row.get('手机号')),
                safe_datetime(row.get('借用时间')),
                safe_str(row.get('借用地点')),
                safe_str(row.get('借用原因')),
                safe_str(row.get('录入者')),
                safe_datetime(row.get('预计归还日期')),
                safe_datetime(row.get('丢失时间')),
                safe_str(row.get('损坏原因')),
                safe_datetime(row.get('损坏时间')),
                safe_str(row.get('上一个借用人')),
                safe_str(row.get('软件版本')),
                safe_str(row.get('芯片型号')),
                safe_str(row.get('项目属性')),
                safe_str(row.get('连接方式')),
                safe_str(row.get('系统版本')),
                safe_str(row.get('系统平台')),
                safe_str(row.get('产品名称')),
                safe_str(row.get('屏幕方向')),
                safe_str(row.get('车机分辨率')),
                safe_datetime(row.get('寄出时间')),
                safe_str(row.get('寄出备注')),
                safe_str(row.get('寄出人')),
                safe_str(row.get('寄出前借用人')),
                safe_datetime(row.get('寄出前借用时间')),
                safe_datetime(row.get('寄出前预计归还'))
            ))
            count += 1
        except Exception as e:
            print(f"导入车机记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条车机记录")


def import_instruments():
    """导入仪表数据"""
    filepath = os.path.join(EXCEL_DIR, '仪表表.xlsx')
    if not os.path.exists(filepath):
        print("仪表表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('设备ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, is_deleted, create_time, borrower, phone,
                    borrow_time, location, reason, entry_source, expected_return_date,
                    lost_time, damage_reason, damage_time, previous_borrower,
                    software_version, hardware_version, project_attribute,
                    connection_method, os_version, os_platform, product_name,
                    screen_orientation, screen_resolution, ship_time, ship_remark,
                    ship_by, pre_ship_borrower, pre_ship_borrow_time, pre_ship_expected_return_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备名')),
                '仪表',
                safe_str(row.get('型号')),
                safe_str(row.get('柜号')),
                safe_str(row.get('状态')),
                safe_str(row.get('备注')),
                safe_str(row.get('JIRA地址')),
                1 if safe_str(row.get('是否删除')) == '是' else 0,
                safe_datetime(row.get('创建时间')),
                safe_str(row.get('借用人')),
                safe_str(row.get('手机号')),
                safe_datetime(row.get('借用时间')),
                safe_str(row.get('借用地点')),
                safe_str(row.get('借用原因')),
                safe_str(row.get('录入者')),
                safe_datetime(row.get('预计归还日期')),
                safe_datetime(row.get('丢失时间')),
                safe_str(row.get('损坏原因')),
                safe_datetime(row.get('损坏时间')),
                safe_str(row.get('上一个借用人')),
                safe_str(row.get('软件版本')),
                safe_str(row.get('芯片型号')),
                safe_str(row.get('项目属性')),
                safe_str(row.get('连接方式')),
                safe_str(row.get('系统版本')),
                safe_str(row.get('系统平台')),
                safe_str(row.get('产品名称')),
                safe_str(row.get('屏幕方向')),
                safe_str(row.get('车机分辨率')),
                safe_datetime(row.get('寄出时间')),
                safe_str(row.get('寄出备注')),
                safe_str(row.get('寄出人')),
                safe_str(row.get('寄出前借用人')),
                safe_datetime(row.get('寄出前借用时间')),
                safe_datetime(row.get('寄出前预计归还'))
            ))
            count += 1
        except Exception as e:
            print(f"导入仪表记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条仪表记录")


def import_phones():
    """导入手机数据"""
    filepath = os.path.join(EXCEL_DIR, '手机表.xlsx')
    if not os.path.exists(filepath):
        print("手机表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('设备ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, is_deleted, create_time, borrower, phone,
                    borrow_time, location, reason, entry_source, expected_return_date,
                    lost_time, damage_reason, damage_time, previous_borrower,
                    sn, system_version, imei, carrier, ship_time, ship_remark,
                    ship_by, pre_ship_borrower, pre_ship_borrow_time, pre_ship_expected_return_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备名')),
                '手机',
                safe_str(row.get('型号')),
                safe_str(row.get('保管人')),
                safe_str(row.get('状态')),
                safe_str(row.get('备注')),
                safe_str(row.get('JIRA地址')),
                1 if safe_str(row.get('是否删除')) == '是' else 0,
                safe_datetime(row.get('创建时间')),
                safe_str(row.get('借用人')),
                safe_str(row.get('手机号')),
                safe_datetime(row.get('借用时间')),
                safe_str(row.get('借用地点')),
                safe_str(row.get('借用原因')),
                safe_str(row.get('录入者')),
                safe_datetime(row.get('预计归还日期')),
                safe_datetime(row.get('丢失时间')),
                safe_str(row.get('损坏原因')),
                safe_datetime(row.get('损坏时间')),
                safe_str(row.get('上一个借用人')),
                safe_str(row.get('SN码')),
                safe_str(row.get('系统版本')),
                safe_str(row.get('IMEI')),
                safe_str(row.get('运营商')),
                safe_datetime(row.get('寄出时间')),
                safe_str(row.get('寄出备注')),
                safe_str(row.get('寄出人')),
                safe_str(row.get('寄出前借用人')),
                safe_datetime(row.get('寄出前借用时间')),
                safe_datetime(row.get('寄出前预计归还'))
            ))
            count += 1
        except Exception as e:
            print(f"导入手机记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条手机记录")


def import_sim_cards():
    """导入手机卡数据"""
    filepath = os.path.join(EXCEL_DIR, '手机卡表.xlsx')
    if not os.path.exists(filepath):
        print("手机卡表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('设备ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, is_deleted, create_time, borrower, phone,
                    borrow_time, location, reason, entry_source, expected_return_date,
                    lost_time, damage_reason, damage_time, previous_borrower,
                    software_version, hardware_version, ship_time, ship_remark,
                    ship_by, pre_ship_borrower, pre_ship_borrow_time, pre_ship_expected_return_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备名')),
                '手机卡',
                safe_str(row.get('号码')),
                safe_str(row.get('保管人')),
                safe_str(row.get('状态')),
                safe_str(row.get('备注')),
                safe_str(row.get('JIRA地址')),
                1 if safe_str(row.get('是否删除')) == '是' else 0,
                safe_datetime(row.get('创建时间')),
                safe_str(row.get('借用人')),
                safe_str(row.get('手机号')),
                safe_datetime(row.get('借用时间')),
                safe_str(row.get('借用地点')),
                safe_str(row.get('借用原因')),
                safe_str(row.get('录入者')),
                safe_datetime(row.get('预计归还日期')),
                safe_datetime(row.get('丢失时间')),
                safe_str(row.get('损坏原因')),
                safe_datetime(row.get('损坏时间')),
                safe_str(row.get('上一个借用人')),
                safe_str(row.get('软件版本')),
                safe_str(row.get('芯片型号')),
                safe_datetime(row.get('寄出时间')),
                safe_str(row.get('寄出备注')),
                safe_str(row.get('寄出人')),
                safe_str(row.get('寄出前借用人')),
                safe_datetime(row.get('寄出前借用时间')),
                safe_datetime(row.get('寄出前预计归还'))
            ))
            count += 1
        except Exception as e:
            print(f"导入手机卡记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条手机卡记录")


def import_other_devices():
    """导入其它设备数据"""
    filepath = os.path.join(EXCEL_DIR, '其它设备表.xlsx')
    if not os.path.exists(filepath):
        print("其它设备表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('设备ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO devices (
                    id, name, device_type, model, cabinet_number, status, remark,
                    jira_address, is_deleted, create_time, borrower, phone,
                    borrow_time, location, reason, entry_source, expected_return_date,
                    lost_time, damage_reason, damage_time, previous_borrower,
                    software_version, hardware_version, ship_time, ship_remark,
                    ship_by, pre_ship_borrower, pre_ship_borrow_time, pre_ship_expected_return_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备名')),
                '其它设备',
                safe_str(row.get('型号')),
                safe_str(row.get('保管人')),
                safe_str(row.get('状态')),
                safe_str(row.get('备注')),
                safe_str(row.get('JIRA地址')),
                1 if safe_str(row.get('是否删除')) == '是' else 0,
                safe_datetime(row.get('创建时间')),
                safe_str(row.get('借用人')),
                safe_str(row.get('手机号')),
                safe_datetime(row.get('借用时间')),
                safe_str(row.get('借用地点')),
                safe_str(row.get('借用原因')),
                safe_str(row.get('录入者')),
                safe_datetime(row.get('预计归还日期')),
                safe_datetime(row.get('丢失时间')),
                safe_str(row.get('损坏原因')),
                safe_datetime(row.get('损坏时间')),
                safe_str(row.get('上一个借用人')),
                safe_str(row.get('软件版本')),
                safe_str(row.get('芯片型号')),
                safe_datetime(row.get('寄出时间')),
                safe_str(row.get('寄出备注')),
                safe_str(row.get('寄出人')),
                safe_str(row.get('寄出前借用人')),
                safe_datetime(row.get('寄出前借用时间')),
                safe_datetime(row.get('寄出前预计归还'))
            ))
            count += 1
        except Exception as e:
            print(f"导入其它设备记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条其它设备记录")


def import_records():
    """导入记录数据"""
    filepath = os.path.join(EXCEL_DIR, '记录表.xlsx')
    if not os.path.exists(filepath):
        print("记录表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('记录ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO records (
                    id, device_id, device_name, device_type, operation_type,
                    operator, operation_time, borrower, phone, reason, entry_source, remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('记录ID')),
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备名')),
                safe_str(row.get('设备类型')),
                safe_str(row.get('操作类型')),
                safe_str(row.get('操作人')),
                safe_datetime(row.get('操作时间')),
                safe_str(row.get('借用人')),
                safe_str(row.get('手机号')),
                safe_str(row.get('原因')),
                safe_str(row.get('录入者')),
                safe_str(row.get('备注'))
            ))
            count += 1
        except Exception as e:
            print(f"导入记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条记录")


def import_user_remarks():
    """导入用户备注数据"""
    filepath = os.path.join(EXCEL_DIR, '用户备注表.xlsx')
    if not os.path.exists(filepath):
        print("用户备注表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('备注ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO user_remarks (
                    id, device_id, device_type, content, creator, create_time, is_inappropriate
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('备注ID')),
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备类型')),
                safe_str(row.get('备注内容')),
                safe_str(row.get('创建人')),
                safe_datetime(row.get('创建时间')),
                1 if safe_str(row.get('是否不当')) == '是' else 0
            ))
            count += 1
        except Exception as e:
            print(f"导入用户备注失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条用户备注")


def import_users():
    """导入用户数据"""
    filepath = os.path.join(EXCEL_DIR, '用户表.xlsx')
    if not os.path.exists(filepath):
        print("用户表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('用户ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (
                    id, wechat_name, phone, password, borrower_name,
                    borrow_count, return_count, is_frozen, is_admin, create_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('用户ID')),
                safe_str(row.get('微信名')),
                safe_str(row.get('手机号')),
                safe_str(row.get('密码', '123456')),
                safe_str(row.get('借用人')),
                safe_int(row.get('借用次数')),
                safe_int(row.get('归还次数')),
                1 if safe_str(row.get('状态')) == '已冻结' else 0,
                1 if safe_str(row.get('是否管理员')) == '是' else 0,
                safe_datetime(row.get('注册时间'))
            ))
            count += 1
        except Exception as e:
            print(f"导入用户失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条用户记录")


def import_operation_logs():
    """导入操作日志数据"""
    filepath = os.path.join(EXCEL_DIR, '操作日志表.xlsx')
    if not os.path.exists(filepath):
        print("操作日志表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('日志ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO operation_logs (
                    id, operation_time, operator, operation_content, device_info
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('日志ID')),
                safe_datetime(row.get('操作时间')),
                safe_str(row.get('操作人')),
                safe_str(row.get('操作内容')),
                safe_str(row.get('设备信息'))
            ))
            count += 1
        except Exception as e:
            print(f"导入操作日志失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条操作日志")


def import_view_records():
    """导入查看记录数据"""
    filepath = os.path.join(EXCEL_DIR, '查看记录表.xlsx')
    if not os.path.exists(filepath):
        print("查看记录表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('记录ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO view_records (
                    id, device_id, device_type, viewer, view_time
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('记录ID')),
                safe_str(row.get('设备ID')),
                safe_str(row.get('设备类型')),
                safe_str(row.get('查看人')),
                safe_datetime(row.get('查看时间'))
            ))
            count += 1
        except Exception as e:
            print(f"导入查看记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条查看记录")


def import_admins():
    """导入管理员数据"""
    filepath = os.path.join(EXCEL_DIR, '管理员表.xlsx')
    if not os.path.exists(filepath):
        print("管理员表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('管理员ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO admins (
                    id, username, password, create_time
                ) VALUES (?, ?, ?, ?)
            ''', (
                safe_str(row.get('管理员ID')),
                safe_str(row.get('账号')),
                safe_str(row.get('密码')),
                safe_datetime(row.get('创建时间'))
            ))
            count += 1
        except Exception as e:
            print(f"导入管理员失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条管理员记录")


def import_notifications():
    """导入通知数据"""
    filepath = os.path.join(EXCEL_DIR, '通知表.xlsx')
    if not os.path.exists(filepath):
        print("通知表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('通知ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO notifications (
                    id, user_id, user_name, title, content, device_name,
                    device_id, is_read, create_time, notification_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('通知ID')),
                safe_str(row.get('用户ID')),
                safe_str(row.get('用户名')),
                safe_str(row.get('标题')),
                safe_str(row.get('内容')),
                safe_str(row.get('设备名')),
                safe_str(row.get('设备ID')),
                1 if safe_str(row.get('是否已读')) == '是' else 0,
                safe_datetime(row.get('创建时间')),
                safe_str(row.get('通知类型', 'info'))
            ))
            count += 1
        except Exception as e:
            print(f"导入通知失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条通知")


def import_announcements():
    """导入公告数据"""
    filepath = os.path.join(EXCEL_DIR, '公告表.xlsx')
    if not os.path.exists(filepath):
        print("公告表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        if pd.isna(row.get('公告ID')):
            continue
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO announcements (
                    id, title, content, announcement_type, is_active,
                    sort_order, creator, create_time, update_time, force_show_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('公告ID')),
                safe_str(row.get('标题')),
                safe_str(row.get('内容')),
                safe_str(row.get('公告类型', 'normal')),
                1 if safe_str(row.get('是否上架')) == '是' else 0,
                safe_int(row.get('排序')),
                safe_str(row.get('创建人')),
                safe_datetime(row.get('创建时间')),
                safe_datetime(row.get('更新时间')),
                safe_int(row.get('强制显示版本'))
            ))
            count += 1
        except Exception as e:
            print(f"导入公告失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条公告")


def import_user_likes():
    """导入用户点赞数据"""
    filepath = os.path.join(EXCEL_DIR, '用户点赞表.xlsx')
    if not os.path.exists(filepath):
        print("用户点赞表.xlsx 不存在，跳过")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df = pd.read_excel(filepath)
    count = 0
    
    for _, row in df.iterrows():
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO user_likes (
                    id, from_user_id, to_user_id, create_date, create_time
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                safe_str(row.get('点赞ID')),
                safe_str(row.get('点赞用户ID')),
                safe_str(row.get('被点赞用户ID')),
                safe_str(row.get('点赞日期')),
                safe_datetime(row.get('点赞时间'))
            ))
            count += 1
        except Exception as e:
            print(f"导入点赞记录失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功导入 {count} 条点赞记录")


def verify_import():
    """验证导入结果"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = [
        ('devices', '设备'),
        ('records', '记录'),
        ('user_remarks', '用户备注'),
        ('users', '用户'),
        ('operation_logs', '操作日志'),
        ('view_records', '查看记录'),
        ('admins', '管理员'),
        ('notifications', '通知'),
        ('announcements', '公告'),
        ('user_likes', '用户点赞')
    ]
    
    print("\n" + "="*60)
    print("导入验证结果")
    print("="*60)
    
    for table, name in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{name}表: {count} 条记录")
    
    # 按设备类型统计
    print("\n设备类型统计:")
    cursor.execute("SELECT device_type, COUNT(*) FROM devices GROUP BY device_type")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} 条")
    
    conn.close()


def main():
    """主函数"""
    print("="*60)
    print("Excel数据导入SQLite数据库")
    print("="*60)
    
    # 初始化数据库
    init_database()
    
    print("\n开始导入数据...")
    print("-"*60)
    
    # 导入设备数据
    import_car_machines()
    import_instruments()
    import_phones()
    import_sim_cards()
    import_other_devices()
    
    # 导入其他数据
    import_records()
    import_user_remarks()
    import_users()
    import_operation_logs()
    import_view_records()
    import_admins()
    import_notifications()
    import_announcements()
    import_user_likes()
    
    print("-"*60)
    
    # 验证导入结果
    verify_import()
    
    print("\n" + "="*60)
    print(f"数据导入完成！数据库文件: {DB_PATH}")
    print("="*60)


if __name__ == '__main__':
    main()
