# -*- coding: utf-8 -*-
"""
测试 % 字符处理
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import DB_TYPE, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
import pymysql

print(f"数据库类型: {DB_TYPE}")

# 测试 % 字符在 SQL 参数中的处理
if DB_TYPE == 'mysql':
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
        
        # 测试包含 % 字符的数据
        test_content = "测试 % 字符"
        test_device_info = "设备 % 信息"
        
        sql = """INSERT INTO operation_logs (
            id, operation_time, operator, operation_content, device_info, source
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        import uuid
        from datetime import datetime
        
        params = (
            str(uuid.uuid4()),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'test_operator',
            test_content,
            test_device_info,
            'test'
        )
        
        print(f"SQL: {sql}")
        print(f"Params: {params}")
        
        cursor.execute(sql, params)
        conn.commit()
        
        print(f"✓ 成功插入包含 % 字符的数据")
        print(f"  operation_content: {test_content}")
        print(f"  device_info: {test_device_info}")
        
        # 清理测试数据
        cursor.execute("DELETE FROM operation_logs WHERE source = 'test'")
        conn.commit()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
