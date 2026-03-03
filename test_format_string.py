# -*- coding: utf-8 -*-
"""
测试 format string 问题
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config import DB_TYPE, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

print(f"数据库类型: {DB_TYPE}")
print(f"MySQL 配置: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")

# 测试 save_device 的 SQL 语句
if DB_TYPE == 'mysql':
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
    
    # 计算 %s 的数量
    count = sql.count('%s')
    print(f"INSERT 语句中 %s 占位符数量: {count}")
    
    # 模拟参数
    params = (
        'id', 'name', 'device_type', 'model', 'cabinet', 'status', 'remark',
        'jira', 'borrower', 'borrower_id', 'custodian_id', 'phone', None, 'location', 'reason',
        'entry_source', None, 'admin_operator', None,
        'ship_remark', 'ship_by', 'pre_ship_borrower', None,
        None, None, 'damage_reason',
        None, 'previous_borrower', 'previous_status', 'sn', 'system_version', 'imei',
        'carrier', 'software_version', 'hardware_version',
        'project_attribute', 'connection_method',
        'os_version', 'os_platform', 'product_name',
        'screen_orientation', 'screen_resolution',
        'asset_number', 0.0,
        0
    )
    
    print(f"参数数量: {len(params)}")
    
    if count == len(params):
        print("✓ INSERT 语句参数数量匹配")
    else:
        print(f"✗ INSERT 语句参数数量不匹配: {count} != {len(params)}")

# 测试 save_operation_log 的 SQL 语句
sql2 = """INSERT INTO operation_logs (
    id, operation_time, operator, operation_content, device_info, source
) VALUES (%s, %s, %s, %s, %s, %s)
"""

count2 = sql2.count('%s')
print(f"\noperation_logs INSERT 语句中 %s 占位符数量: {count2}")

params2 = ('id', None, 'operator', 'operation_content', 'device_info', 'source')
print(f"参数数量: {len(params2)}")

if count2 == len(params2):
    print("✓ operation_logs INSERT 语句参数数量匹配")
else:
    print(f"✗ operation_logs INSERT 语句参数数量不匹配: {count2} != {len(params2)}")

# 检查是否有可能是 % 字符在字符串中导致的问题
test_content = "测试 % 字符"
print(f"\n测试字符串: {test_content}")
print(f"包含 % 字符: {'%' in test_content}")

# 尝试执行格式化
try:
    result = "Content: %s" % test_content
    print(f"格式化结果: {result}")
except Exception as e:
    print(f"格式化错误: {e}")
