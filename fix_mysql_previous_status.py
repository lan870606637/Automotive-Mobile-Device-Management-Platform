# -*- coding: utf-8 -*-
"""
修复 MySQL 数据库 devices 表缺少 previous_status 字段的问题
"""
import pymysql
import sys
import os

# 加载环境变量
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

def fix_previous_status():
    """添加 previous_status 字段到 devices 表"""
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
        
        # 检查字段是否已存在
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'devices' 
            AND COLUMN_NAME = 'previous_status'
        """, (MYSQL_DATABASE,))
        
        if cursor.fetchone():
            print("✓ previous_status 字段已存在，无需修复")
        else:
            # 添加字段
            cursor.execute("ALTER TABLE devices ADD COLUMN previous_status VARCHAR(32)")
            conn.commit()
            print("✓ 成功添加 previous_status 字段到 devices 表")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("修复 MySQL 数据库 previous_status 字段")
    print("=" * 50)
    print(f"数据库: {MYSQL_DATABASE}")
    print(f"主机: {MYSQL_HOST}:{MYSQL_PORT}")
    print("=" * 50)
    print()
    
    if fix_previous_status():
        print()
        print("修复完成！")
    else:
        print()
        print("修复失败，请检查错误信息")
        sys.exit(1)
