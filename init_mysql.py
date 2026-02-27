# -*- coding: utf-8 -*-
"""
MySQL数据库初始化脚本
用于创建数据库和表结构（与SQLite结构一致）
"""
import pymysql
import sys

# MySQL连接配置
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = input('请输入MySQL root密码: ')
MYSQL_DATABASE = 'device_management'

def create_database():
    """创建数据库"""
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        # 创建数据库
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✓ 数据库 '{MYSQL_DATABASE}' 创建成功")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 创建数据库失败: {e}")
        return False

def create_tables():
    """创建数据表（与SQLite结构一致）"""
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        # 设备表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                device_type VARCHAR(50) NOT NULL,
                model VARCHAR(255),
                cabinet_number VARCHAR(100),
                status VARCHAR(50) NOT NULL,
                remark TEXT,
                jira_address VARCHAR(255),
                is_deleted INT DEFAULT 0,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                borrower VARCHAR(255),
                borrower_id VARCHAR(64),
                phone VARCHAR(20),
                borrow_time TIMESTAMP NULL,
                location VARCHAR(255),
                reason TEXT,
                entry_source VARCHAR(50),
                expected_return_date TIMESTAMP NULL,
                admin_operator VARCHAR(100),
                ship_time TIMESTAMP NULL,
                ship_remark TEXT,
                ship_by VARCHAR(100),
                pre_ship_borrower VARCHAR(255),
                pre_ship_borrow_time TIMESTAMP NULL,
                pre_ship_expected_return_date TIMESTAMP NULL,
                lost_time TIMESTAMP NULL,
                damage_reason TEXT,
                damage_time TIMESTAMP NULL,
                previous_borrower VARCHAR(255),
                sn VARCHAR(100),
                system_version VARCHAR(100),
                imei VARCHAR(100),
                carrier VARCHAR(100),
                software_version VARCHAR(100),
                hardware_version VARCHAR(100),
                project_attribute VARCHAR(255),
                connection_method VARCHAR(500),
                os_version VARCHAR(100),
                os_platform VARCHAR(100),
                product_name VARCHAR(255),
                screen_orientation VARCHAR(50),
                screen_resolution VARCHAR(50),
                INDEX idx_status (status),
                INDEX idx_borrower (borrower),
                INDEX idx_device_type (device_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ devices 表创建成功")
        
        # 记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id VARCHAR(64) PRIMARY KEY,
                device_id VARCHAR(64) NOT NULL,
                device_name VARCHAR(255),
                device_type VARCHAR(50),
                operation_type VARCHAR(50) NOT NULL,
                operator VARCHAR(100),
                operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                borrower VARCHAR(255),
                phone VARCHAR(20),
                reason TEXT,
                entry_source VARCHAR(50),
                remark TEXT,
                INDEX idx_device_id (device_id),
                INDEX idx_operation_time (operation_time),
                INDEX idx_borrower (borrower)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ records 表创建成功")
        
        # 备注表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_remarks (
                id VARCHAR(64) PRIMARY KEY,
                device_id VARCHAR(64) NOT NULL,
                device_type VARCHAR(50),
                content TEXT NOT NULL,
                creator VARCHAR(100),
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_inappropriate INT DEFAULT 0,
                INDEX idx_device_id (device_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ user_remarks 表创建成功")
        
        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(64) PRIMARY KEY,
                email VARCHAR(255) UNIQUE,
                password VARCHAR(255) NOT NULL DEFAULT '123456',
                borrower_name VARCHAR(100),
                avatar VARCHAR(500) DEFAULT '',
                borrow_count INT DEFAULT 0,
                return_count INT DEFAULT 0,
                is_frozen INT DEFAULT 0,
                is_admin INT DEFAULT 0,
                is_deleted INT DEFAULT 0,
                is_first_login INT DEFAULT 1,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_email (email),
                INDEX idx_borrower_name (borrower_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ users 表创建成功")
        
        # 操作日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id VARCHAR(64) PRIMARY KEY,
                operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                operator VARCHAR(100),
                operation_content TEXT,
                device_info TEXT,
                INDEX idx_operation_time (operation_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ operation_logs 表创建成功")
        
        # 查看记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS view_records (
                id VARCHAR(64) PRIMARY KEY,
                device_id VARCHAR(64) NOT NULL,
                device_type VARCHAR(50),
                viewer VARCHAR(100),
                view_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_device_id (device_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ view_records 表创建成功")
        
        # 管理员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id VARCHAR(64) PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ admins 表创建成功")
        
        # 通知表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                user_name VARCHAR(100),
                title VARCHAR(255),
                content TEXT,
                device_name VARCHAR(255),
                device_id VARCHAR(64),
                is_read INT DEFAULT 0,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notification_type VARCHAR(50),
                INDEX idx_user_id (user_id),
                INDEX idx_is_read (is_read)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ notifications 表创建成功")
        
        # 公告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id VARCHAR(64) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                announcement_type VARCHAR(50),
                is_active INT DEFAULT 1,
                sort_order INT DEFAULT 0,
                creator VARCHAR(100),
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                force_show_version INT DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ announcements 表创建成功")
        
        # 用户点赞表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_likes (
                id VARCHAR(64) PRIMARY KEY,
                from_user_id VARCHAR(64) NOT NULL,
                to_user_id VARCHAR(64) NOT NULL,
                create_date VARCHAR(20),
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_like (from_user_id, to_user_id, create_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        print("✓ user_likes 表创建成功")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 创建表失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 50)
    print("MySQL数据库初始化工具")
    print("=" * 50)
    print()
    
    # 创建数据库
    if not create_database():
        sys.exit(1)
    
    # 创建表
    if not create_tables():
        sys.exit(1)
    
    print()
    print("=" * 50)
    print("数据库初始化完成！")
    print("=" * 50)
    print()
    print("接下来请:")
    print("1. 复制 .env.example 为 .env")
    print("2. 修改 .env 中的数据库配置:")
    print("   DB_TYPE=mysql")
    print("   MYSQL_PASSWORD=你的密码")
    print("3. 运行 python migrate_to_mysql.py 迁移数据")
    print()

if __name__ == '__main__':
    main()
