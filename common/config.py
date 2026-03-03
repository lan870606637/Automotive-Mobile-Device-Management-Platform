# -*- coding: utf-8 -*-
"""
共享配置模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 服务器配置
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
SERVER_URL = os.getenv('SERVER_URL', '').rstrip('/')

# 域名配置
USER_DOMAIN = os.getenv('USER_DOMAIN', 'device.carbit.com.cn')
ADMIN_DOMAIN = os.getenv('ADMIN_DOMAIN', 'admin.device.carbit.com.cn')

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'excel_templates')

# 端口配置
USER_SERVICE_PORT = 5000
ADMIN_SERVICE_PORT = 5001
MOBILE_SERVICE_PORT = 5002

# 数据库配置（仅支持MySQL）
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'device_management')

# 数据库连接URL
SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4'

# Excel 文件路径
EXCEL_FILES = {
    'car_machines': os.path.join(DATA_DIR, '车机设备表.xlsx'),
    'phones': os.path.join(DATA_DIR, '手机设备表.xlsx'),
    'records': os.path.join(DATA_DIR, '借还记录表.xlsx'),
    'remarks': os.path.join(DATA_DIR, '用户备注表.xlsx'),
    'users': os.path.join(DATA_DIR, '用户表.xlsx'),
    'operation_logs': os.path.join(DATA_DIR, '操作日志表.xlsx'),
    'view_records': os.path.join(DATA_DIR, '查看记录表.xlsx'),
    'admins': os.path.join(DATA_DIR, '管理员表.xlsx'),
}
