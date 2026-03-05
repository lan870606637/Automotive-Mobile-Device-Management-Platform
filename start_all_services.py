#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动所有服务 (Memurai + Celery)
"""
import os
import sys
import time
import subprocess
from pathlib import Path

# 配置
PROJECT_DIR = Path("D:/Automotive-Mobile-Device-Management-Platform")
MEMURAI_PATH = Path("C:/Program Files/Memurai")
MEMURAI_EXE = MEMURAI_PATH / "memurai.exe"
MEMURAI_CLI = MEMURAI_PATH / "memurai-cli.exe"


def print_header():
    """打印标题"""
    print("=" * 50)
    print("   启动所有服务 (Memurai + Celery)")
    print("=" * 50)
    print()


def is_memurai_running():
    """检查 Memurai 是否正在运行"""
    try:
        result = subprocess.run(
            [str(MEMURAI_CLI), "ping"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0 and "PONG" in result.stdout
    except:
        return False


def start_memurai():
    """启动 Memurai"""
    print("[1/4] 检查 Memurai 服务...")
    
    if is_memurai_running():
        print("       Memurai 已在运行")
        return True
    
    print("       启动 Memurai...")
    try:
        subprocess.Popen(
            [str(MEMURAI_EXE)],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        time.sleep(2)
        return True
    except Exception as e:
        print(f"       启动失败: {e}")
        return False


def wait_for_memurai():
    """等待 Memurai 就绪"""
    print("[2/4] 等待 Memurai 就绪...")
    
    max_attempts = 30
    for i in range(max_attempts):
        if is_memurai_running():
            print("       Memurai 已就绪 (PONG)")
            return True
        time.sleep(1)
    
    print("       等待超时，Memurai 可能未正常启动")
    return False


def start_celery_worker():
    """启动 Celery Worker"""
    print("[3/4] 启动 Celery Worker...")
    
    try:
        subprocess.Popen(
            [
                "celery",
                "-A", "common.celery_config",
                "worker",
                "--loglevel=info",
                "-Q", "default,email,points,maintenance"
            ],
            cwd=PROJECT_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        print("       Celery Worker 已启动")
        return True
    except Exception as e:
        print(f"       启动失败: {e}")
        return False


def start_celery_beat():
    """启动 Celery Beat"""
    print("[4/4] 启动 Celery Beat...")
    
    try:
        subprocess.Popen(
            [
                "celery",
                "-A", "common.celery_config",
                "beat",
                "--loglevel=info"
            ],
            cwd=PROJECT_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        print("       Celery Beat 已启动")
        return True
    except Exception as e:
        print(f"       启动失败: {e}")
        return False


def print_footer():
    """打印页脚"""
    print()
    print("=" * 50)
    print("   所有服务已启动！")
    print("=" * 50)
    print()
    print("服务列表:")
    print("  - Memurai (Redis): localhost:6379")
    print("  - Celery Worker:   处理异步任务")
    print("  - Celery Beat:     定时任务调度")
    print()


def main():
    """主函数"""
    print_header()
    
    # 检查路径是否存在
    if not MEMURAI_EXE.exists():
        print(f"错误: 找不到 Memurai: {MEMURAI_EXE}")
        sys.exit(1)
    
    if not PROJECT_DIR.exists():
        print(f"错误: 找不到项目目录: {PROJECT_DIR}")
        sys.exit(1)
    
    # 启动服务
    if not start_memurai():
        sys.exit(1)
    
    if not wait_for_memurai():
        sys.exit(1)
    
    if not start_celery_worker():
        sys.exit(1)
    
    if not start_celery_beat():
        sys.exit(1)
    
    print_footer()
    
    # 等待用户按键
    input("按 Enter 键退出...")


if __name__ == "__main__":
    main()
