#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL数据库备份脚本
"""
import os
import subprocess
import sys
from datetime import datetime
from common.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

def backup_mysql():
    """备份MySQL数据库到SQL文件"""
    
    # 创建备份目录
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # 生成备份文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'{MYSQL_DATABASE}_{timestamp}.sql')
    
    print(f"开始备份数据库: {MYSQL_DATABASE}")
    print(f"备份文件: {backup_file}")
    
    # 构建mysqldump命令
    # 使用MYSQL_PWD环境变量传递密码，避免密码暴露在命令行
    env = os.environ.copy()
    env['MYSQL_PWD'] = MYSQL_PASSWORD
    
    cmd = [
        'mysqldump',
        '--host', MYSQL_HOST,
        '--port', str(MYSQL_PORT),
        '--user', MYSQL_USER,
        '--single-transaction',  # 保证一致性
        '--routines',  # 包含存储过程
        '--triggers',  # 包含触发器
        '--events',    # 包含事件
        MYSQL_DATABASE
    ]
    
    try:
        # 执行备份
        with open(backup_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
        
        if result.returncode != 0:
            print(f"备份失败: {result.stderr}")
            # 删除失败的备份文件
            if os.path.exists(backup_file):
                os.remove(backup_file)
            return None
        
        # 获取文件大小
        file_size = os.path.getsize(backup_file)
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"✅ 备份成功!")
        print(f"   文件: {backup_file}")
        print(f"   大小: {file_size_mb:.2f} MB")
        
        return backup_file
        
    except FileNotFoundError:
        print("错误: 找不到 mysqldump 命令")
        print("请确保 MySQL 已安装并添加到系统 PATH")
        return None
    except Exception as e:
        print(f"备份出错: {e}")
        # 删除失败的备份文件
        if os.path.exists(backup_file):
            os.remove(backup_file)
        return None

def backup_to_github(backup_file):
    """将备份文件上传到GitHub"""
    import shutil
    
    if not backup_file or not os.path.exists(backup_file):
        print("备份文件不存在")
        return False
    
    # 复制备份文件到项目根目录，方便Git提交
    project_root = os.path.dirname(os.path.abspath(__file__))
    backup_filename = os.path.basename(backup_file)
    dest_file = os.path.join(project_root, 'database_backup.sql')
    
    # 复制最新的备份为固定名称
    shutil.copy2(backup_file, dest_file)
    print(f"✅ 已复制备份到: {dest_file}")
    
    # 同时保留带时间戳的版本
    timestamp_dest = os.path.join(project_root, backup_filename)
    shutil.copy2(backup_file, timestamp_dest)
    print(f"✅ 已保留时间戳版本: {timestamp_dest}")
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("MySQL数据库备份工具")
    print("=" * 60)
    
    # 执行备份
    backup_file = backup_mysql()
    
    if backup_file:
        # 复制到项目目录
        backup_to_github(backup_file)
        print("\n✅ 备份完成!")
        print(f"备份文件已保存到项目目录")
        sys.exit(0)
    else:
        print("\n❌ 备份失败!")
        sys.exit(1)
