# -*- coding: utf-8 -*-
"""
重置MySQL数据库（删除所有表并重新创建）
"""
import pymysql
import sys

MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = input('请输入MySQL root密码: ')
MYSQL_DATABASE = 'device_management'

def reset_database():
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
        
        # 禁用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 获取所有表
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        # 删除所有表
        for table in tables:
            table_name = table[0]
            cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            print(f"✓ 删除表: {table_name}")
        
        # 启用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✓ 所有表已删除，可以重新运行 init_mysql.py")
        return True
        
    except Exception as e:
        print(f"✗ 重置失败: {e}")
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("MySQL数据库重置工具")
    print("=" * 50)
    print()
    print("警告: 这将删除所有数据！")
    print()
    
    confirm = input("确认删除所有表? (yes/no): ")
    if confirm.lower() == 'yes':
        reset_database()
    else:
        print("已取消")
