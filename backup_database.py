#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库备份脚本
"""

import os
import sys
import subprocess
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import config

def backup_database():
    """备份数据库"""
    # 获取数据库配置
    db_name = config.MYSQL_DATABASE
    
    # 创建备份目录
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database_backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    # 生成备份文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'{db_name}_{timestamp}.sql')
    
    print("=" * 60)
    print("💾 数据库备份")
    print("=" * 60)
    print(f"\n数据库类型: MySQL")
    print(f"数据库名: {db_name}")
    print(f"备份文件: {backup_file}")
    
    try:
        # 使用 mysqldump 备份
        cmd = [
            'mysqldump',
            '-h', config.MYSQL_HOST,
            '-P', str(config.MYSQL_PORT),
            '-u', config.MYSQL_USER,
            f"--password={config.MYSQL_PASSWORD}",
            '--databases', db_name,
            '--result-file', backup_file,
            '--single-transaction',
            '--routines',
            '--triggers'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # 获取文件大小
            file_size = os.path.getsize(backup_file)
            file_size_mb = file_size / (1024 * 1024)
            
            print(f"\n✅ 备份成功！")
            print(f"   文件大小: {file_size_mb:.2f} MB")
            print(f"   保存位置: {backup_file}")
            
            # 同时更新最新备份
            latest_backup = os.path.join(backup_dir, f'{db_name}.sql')
            with open(backup_file, 'rb') as src:
                with open(latest_backup, 'wb') as dst:
                    dst.write(src.read())
            print(f"   最新备份: {latest_backup}")
            
        else:
            print(f"\n❌ 备份失败！")
            print(f"错误信息: {result.stderr}")
            
    except FileNotFoundError:
        print("\n❌ 未找到 mysqldump 命令！")
        print("请确保 MySQL 的 bin 目录已添加到系统 PATH 中。")
    except Exception as e:
        print(f"\n❌ 备份出错: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    backup_database()
