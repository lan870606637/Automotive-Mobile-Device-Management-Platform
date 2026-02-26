# -*- coding: utf-8 -*-
"""
数据库迁移脚本：修改用户表结构
- 将 phone 字段改为 email
- 删除 wechat_name 字段
- 添加 is_first_login 字段
"""
import os
import sys
import sqlite3

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import DB_TYPE, SQLITE_DB_PATH

def migrate_sqlite():
    """迁移SQLite数据库"""
    print("开始迁移SQLite数据库...")
    
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"数据库文件不存在: {SQLITE_DB_PATH}")
        return False
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. 检查users表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("users表不存在，无需迁移")
            return True
        
        # 2. 获取当前表结构
        cursor.execute("PRAGMA table_info(users)")
        columns = {col[1]: col for col in cursor.fetchall()}
        print(f"当前表列: {list(columns.keys())}")
        
        # 3. 创建新表（使用新的结构）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users_new (
                id TEXT PRIMARY KEY,
                email TEXT,
                password TEXT DEFAULT '123456',
                borrower_name TEXT,
                borrow_count INTEGER DEFAULT 0,
                return_count INTEGER DEFAULT 0,
                is_frozen INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                is_first_login INTEGER DEFAULT 1,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 4. 迁移数据
        # 检查旧字段是否存在
        has_phone = 'phone' in columns
        has_wechat_name = 'wechat_name' in columns
        
        if has_phone:
            # 如果有phone字段，将其作为email迁移
            cursor.execute('''
                INSERT INTO users_new (
                    id, email, password, borrower_name, borrow_count, 
                    return_count, is_frozen, is_admin, is_deleted, is_first_login, create_time
                )
                SELECT 
                    id, 
                    CASE 
                        WHEN phone IS NOT NULL AND phone != '' THEN phone || '@legacy.com'
                        ELSE id || '@legacy.com'
                    END as email,
                    COALESCE(password, '123456'),
                    COALESCE(borrower_name, ''),
                    COALESCE(borrow_count, 0),
                    COALESCE(return_count, 0),
                    COALESCE(is_frozen, 0),
                    COALESCE(is_admin, 0),
                    COALESCE(is_deleted, 0),
                    0 as is_first_login,
                    COALESCE(create_time, CURRENT_TIMESTAMP)
                FROM users
                WHERE is_deleted = 0
            ''')
        else:
            # 如果没有phone字段，使用id生成email
            cursor.execute('''
                INSERT INTO users_new (
                    id, email, password, borrower_name, borrow_count, 
                    return_count, is_frozen, is_admin, is_deleted, is_first_login, create_time
                )
                SELECT 
                    id, 
                    id || '@legacy.com' as email,
                    COALESCE(password, '123456'),
                    COALESCE(borrower_name, ''),
                    COALESCE(borrow_count, 0),
                    COALESCE(return_count, 0),
                    COALESCE(is_frozen, 0),
                    COALESCE(is_admin, 0),
                    COALESCE(is_deleted, 0),
                    0 as is_first_login,
                    COALESCE(create_time, CURRENT_TIMESTAMP)
                FROM users
                WHERE is_deleted = 0
            ''')
        
        # 5. 删除旧表，重命名新表
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_new RENAME TO users")
        
        # 6. 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_borrower_name ON users(borrower_name)")
        
        conn.commit()
        print("SQLite数据库迁移成功！")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def migrate_mysql():
    """迁移MySQL数据库"""
    print("开始迁移MySQL数据库...")
    
    try:
        import pymysql
        from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
        
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        # 1. 检查users表是否存在
        cursor.execute("SHOW TABLES LIKE 'users'")
        if not cursor.fetchone():
            print("users表不存在，无需迁移")
            return True
        
        # 2. 获取当前表结构
        cursor.execute("SHOW COLUMNS FROM users")
        columns = {col[0]: col for col in cursor.fetchall()}
        print(f"当前表列: {list(columns.keys())}")
        
        # 3. 添加新字段（如果不存在）
        if 'is_first_login' not in columns:
            print("添加 is_first_login 字段...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_first_login TINYINT(1) DEFAULT 1")
        
        if 'email' not in columns:
            print("添加 email 字段...")
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
            
            # 将phone数据迁移到email
            if 'phone' in columns:
                print("将 phone 数据迁移到 email...")
                cursor.execute("UPDATE users SET email = CONCAT(phone, '@legacy.com') WHERE phone IS NOT NULL AND phone != ''")
                cursor.execute("UPDATE users SET email = CONCAT(id, '@legacy.com') WHERE email IS NULL OR email = ''")
        
        # 4. 删除旧字段（如果存在）
        if 'wechat_name' in columns:
            print("删除 wechat_name 字段...")
            cursor.execute("ALTER TABLE users DROP COLUMN wechat_name")
        
        if 'phone' in columns:
            print("删除 phone 字段...")
            cursor.execute("ALTER TABLE users DROP COLUMN phone")
        
        # 5. 设置已存在用户的is_first_login为0（因为他们已经使用过系统）
        cursor.execute("UPDATE users SET is_first_login = 0 WHERE is_first_login IS NULL")
        
        # 6. 创建索引
        cursor.execute("CREATE INDEX idx_users_email ON users(email)")
        
        conn.commit()
        print("MySQL数据库迁移成功！")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def main():
    """主函数"""
    print("=" * 50)
    print("用户表结构迁移工具")
    print("=" * 50)
    print()
    
    if DB_TYPE == 'mysql':
        success = migrate_mysql()
    else:
        success = migrate_sqlite()
    
    print()
    if success:
        print("✅ 迁移完成！")
    else:
        print("❌ 迁移失败！")
        sys.exit(1)

if __name__ == '__main__':
    main()
