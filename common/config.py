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

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'excel_templates')

# 端口配置
USER_SERVICE_PORT = 5000
ADMIN_SERVICE_PORT = 5001

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
