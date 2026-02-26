# -*- coding: utf-8 -*-
"""
数据迁移脚本：从SQLite迁移到MySQL
"""
import sqlite3
import pymysql
import sys
from datetime import datetime

# 配置
SQLITE_DB_PATH = 'device_management.db'
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = input('请输入MySQL root密码: ')
MYSQL_DATABASE = 'device_management'


def get_sqlite_connection():
    """获取SQLite连接"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_mysql_connection():
    """获取MySQL连接"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset='utf8mb4'
    )


def get_table_columns(sqlite_cursor, table_name):
    """获取SQLite表的列名"""
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = sqlite_cursor.fetchall()
    return [col[1] for col in columns]


def migrate_table(sqlite_cursor, mysql_cursor, table_name, batch_size=100):
    """迁移单张表"""
    print(f"  正在迁移 {table_name}...", end=' ')
    
    # 获取SQLite表的列名
    columns = get_table_columns(sqlite_cursor, table_name)
    
    if not columns:
        print(f"0条记录(无列)")
        return 0
    
    # 获取SQLite数据
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"0条记录")
        return 0
    
    # 构建INSERT语句（使用INSERT IGNORE跳过重复数据）
    placeholders = ', '.join(['%s'] * len(columns))
    column_names = ', '.join([f'`{col}`' for col in columns])
    insert_sql = f"INSERT IGNORE INTO `{table_name}` ({column_names}) VALUES ({placeholders})"
    
    # 批量插入
    count = 0
    batch = []
    
    for row in rows:
        values = []
        for col in columns:
            val = row[col]
            # 处理布尔值
            if isinstance(val, bool):
                val = 1 if val else 0
            values.append(val)
        batch.append(values)
        
        if len(batch) >= batch_size:
            mysql_cursor.executemany(insert_sql, batch)
            count += len(batch)
            batch = []
    
    # 插入剩余数据
    if batch:
        mysql_cursor.executemany(insert_sql, batch)
        count += len(batch)
    
    print(f"{count}条记录")
    return count


def main():
    print("=" * 60)
    print("SQLite 到 MySQL 数据迁移工具")
    print("=" * 60)
    print()
    
    # 检查SQLite数据库是否存在
    import os
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"✗ 找不到SQLite数据库: {SQLITE_DB_PATH}")
        sys.exit(1)
    
    # 连接数据库
    print("[1/3] 连接数据库...")
    try:
        sqlite_conn = get_sqlite_connection()
        sqlite_cursor = sqlite_conn.cursor()
        print("      ✓ SQLite连接成功")
    except Exception as e:
        print(f"      ✗ SQLite连接失败: {e}")
        sys.exit(1)
    
    try:
        mysql_conn = get_mysql_connection()
        mysql_cursor = mysql_conn.cursor()
        print("      ✓ MySQL连接成功")
    except Exception as e:
        print(f"      ✗ MySQL连接失败: {e}")
        sys.exit(1)
    
    print()
    print("[2/3] 开始迁移数据...")
    
    # 获取所有表（排除user_likes，因为有重复数据问题）
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_tables = [row[0] for row in sqlite_cursor.fetchall()]
    tables = [t for t in all_tables if t != 'user_likes']  # 跳过user_likes表
    
    total_records = 0
    
    for table_name in tables:
        try:
            count = migrate_table(sqlite_cursor, mysql_cursor, table_name)
            total_records += count
        except Exception as e:
            print(f"\n      ✗ 迁移 {table_name} 失败: {e}")
            import traceback
            traceback.print_exc()
            mysql_conn.rollback()
            sqlite_conn.close()
            mysql_conn.close()
            sys.exit(1)
    
    # 提交事务
    mysql_conn.commit()
    
    print()
    print("[3/3] 关闭连接...")
    sqlite_conn.close()
    mysql_conn.close()
    print("      ✓ 连接已关闭")
    
    print()
    print("=" * 60)
    print("数据迁移完成！")
    print("=" * 60)
    print()
    print(f"总计迁移: {total_records} 条记录")
    print()
    print("接下来可以:")
    print("1. 启动服务测试: python start_services.py")
    print("2. 检查数据是否完整")
    print("3. 确认无误后可以删除SQLite数据库备份")
    print()


if __name__ == '__main__':
    main()
