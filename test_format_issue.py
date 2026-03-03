# -*- coding: utf-8 -*-
"""
测试 format string 问题 - 模拟创建设备时的 SQL 执行
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

        # 测试包含 % 字符的设备名称
        test_device_name = "测试设备 %s 名称"  # 包含 %s 的设备名称！
        test_cabinet = "A01 %s"  # 包含 %s 的柜号！

        print(f"\n测试设备名称: {test_device_name}")
        print(f"测试柜号: {test_cabinet}")

        # 测试 save_device 的 SQL 语句
        sql = """INSERT INTO devices (
            id, name, device_type, model, cabinet_number, status, remark,
            jira_address, borrower, borrower_id, custodian_id, phone, borrow_time, location, reason,
            entry_source, expected_return_date, admin_operator, ship_time,
            ship_remark, ship_by, pre_ship_borrower, pre_ship_borrow_time,
            pre_ship_expected_return_date, lost_time, damage_reason,
            damage_time, previous_borrower, previous_status, sn, system_version, imei,
            carrier, software_version, hardware_version, project_attribute,
            connection_method, os_version, os_platform, product_name,
            screen_orientation, screen_resolution, asset_number, purchase_amount, is_deleted
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        import uuid
        from datetime import datetime

        params = (
            str(uuid.uuid4()),  # id
            test_device_name,   # name - 包含 %s!
            '手机',             # device_type
            'Test Model',       # model
            test_cabinet,       # cabinet_number - 包含 %s!
            '在库',             # status
            '',                 # remark
            '',                 # jira_address
            '',                 # borrower
            '',                 # borrower_id
            '',                 # custodian_id
            '',                 # phone
            None,               # borrow_time
            '',                 # location
            '',                 # reason
            '',                 # entry_source
            None,               # expected_return_date
            '',                 # admin_operator
            None,               # ship_time
            '',                 # ship_remark
            '',                 # ship_by
            '',                 # pre_ship_borrower
            None,               # pre_ship_borrow_time
            None,               # pre_ship_expected_return_date
            None,               # lost_time
            '',                 # damage_reason
            None,               # damage_time
            '',                 # previous_borrower
            '',                 # previous_status
            '',                 # sn
            '',                 # system_version
            '',                 # imei
            '',                 # carrier
            '',                 # software_version
            '',                 # hardware_version
            '',                 # project_attribute
            '',                 # connection_method
            '',                 # os_version
            '',                 # os_platform
            '',                 # product_name
            '',                 # screen_orientation
            '',                 # screen_resolution
            '',                 # asset_number
            0.0,                # purchase_amount
            0                   # is_deleted
        )

        print(f"\nSQL 占位符数量: {sql.count('%s')}")
        print(f"参数数量: {len(params)}")

        print(f"\n尝试执行 SQL...")
        cursor.execute(sql, params)
        conn.commit()

        print(f"✓ 成功插入包含 %s 字符的设备！")

        # 清理测试数据
        cursor.execute("DELETE FROM devices WHERE name LIKE '测试设备 %'")
        conn.commit()

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
