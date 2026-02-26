# -*- coding: utf-8 -*-
"""
检查当前使用的数据库类型
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import DB_TYPE

IS_MYSQL = (DB_TYPE == 'mysql')

print("=" * 60)
print("数据库配置检查")
print("=" * 60)

print(f"\nDB_TYPE: {DB_TYPE}")
print(f"IS_MYSQL: {IS_MYSQL}")

if DB_TYPE == 'mysql':
    from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_DATABASE
    print(f"\nMySQL 配置:")
    print(f"  主机: {MYSQL_HOST}")
    print(f"  端口: {MYSQL_PORT}")
    print(f"  用户: {MYSQL_USER}")
    print(f"  数据库: {MYSQL_DATABASE}")
else:
    from common.config import SQLITE_DB_PATH
    print(f"\nSQLite 配置:")
    print(f"  路径: {SQLITE_DB_PATH}")
    print(f"  文件存在: {os.path.exists(SQLITE_DB_PATH)}")

print("\n" + "=" * 60)
