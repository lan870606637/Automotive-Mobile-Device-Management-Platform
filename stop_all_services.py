#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
停止所有服务 (Memurai + Celery)
"""
import os
import sys
import time
import subprocess
from pathlib import Path

# 配置
MEMURAI_EXE = "memurai.exe"


def print_header():
    """打印标题"""
    print("=" * 50)
    print("   停止所有服务 (Memurai + Celery)")
    print("=" * 50)
    print()


def stop_celery_worker():
    """停止 Celery Worker"""
    print("[1/3] 停止 Celery Worker...")
    
    try:
        # 查找并终止 celery worker 进程
        result = subprocess.run(
            ["taskkill", "/F", "/FI", "WINDOWTITLE eq Celery Worker*"],
            capture_output=True,
            text=True
        )
        
        # 也尝试通过进程名终止
        subprocess.run(
            ["taskkill", "/F", "/IM", "celery.exe"],
            capture_output=True
        )
        
        print("       Celery Worker 已停止")
        return True
    except Exception as e:
        print(f"       停止时出错: {e}")
        return False


def stop_celery_beat():
    """停止 Celery Beat"""
    print("[2/3] 停止 Celery Beat...")
    
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/FI", "WINDOWTITLE eq Celery Beat*"],
            capture_output=True,
            text=True
        )
        print("       Celery Beat 已停止")
        return True
    except Exception as e:
        print(f"       停止时出错: {e}")
        return False


def stop_memurai():
    """停止 Memurai"""
    print("[3/3] 停止 Memurai...")
    
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", MEMURAI_EXE],
            capture_output=True,
            text=True
        )
        
        if "成功" in result.stdout or "SUCCESS" in result.stdout:
            print("       Memurai 已停止")
        else:
            print("       Memurai 进程已终止或之前未运行")
        
        return True
    except Exception as e:
        print(f"       停止时出错: {e}")
        return False


def print_footer():
    """打印页脚"""
    print()
    print("=" * 50)
    print("   所有服务已停止！")
    print("=" * 50)
    print()


def main():
    """主函数"""
    print_header()
    
    # 停止服务（按相反顺序）
    stop_celery_worker()
    time.sleep(1)
    
    stop_celery_beat()
    time.sleep(1)
    
    stop_memurai()
    time.sleep(1)
    
    print_footer()
    
    # 等待用户按键
    input("按 Enter 键退出...")


if __name__ == "__main__":
    main()
