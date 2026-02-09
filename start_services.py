# -*- coding: utf-8 -*-
"""
统一启动脚本 - 同时启动用户服务和管理服务
"""
import sys
import os
import subprocess
import time
import signal
from threading import Thread

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 进程列表
processes = []


def start_user_service():
    """启动用户服务"""
    print("=" * 50)
    print("正在启动用户服务 (端口: 5000)...")
    print("=" * 50)
    
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    proc = subprocess.Popen(
        [sys.executable, 'user_service/app.py'],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env
    )
    processes.append(proc)
    return proc


def start_admin_service():
    """启动管理服务"""
    print("=" * 50)
    print("正在启动管理服务 (端口: 5001)...")
    print("=" * 50)
    
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    proc = subprocess.Popen(
        [sys.executable, 'admin_service/app.py'],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env
    )
    processes.append(proc)
    return proc


def signal_handler(sig, frame):
    """信号处理函数 - 优雅地关闭所有服务"""
    print("\n" + "=" * 50)
    print("正在关闭所有服务...")
    print("=" * 50)
    
    for proc in processes:
        if proc.poll() is None:  # 如果进程还在运行
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    
    print("所有服务已关闭")
    sys.exit(0)


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     车机与手机设备管理系统 - 统一启动脚本                     ║
║                                                              ║
║     用户服务: http://localhost:5000                          ║
║     管理服务: http://localhost:5001                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 注册信号处理函数
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动用户服务
    user_proc = start_user_service()
    time.sleep(2)  # 等待服务启动
    
    # 启动管理服务
    admin_proc = start_admin_service()
    time.sleep(2)  # 等待服务启动
    
    print("\n" + "=" * 50)
    print("所有服务已启动!")
    print("=" * 50)
    print("\n访问地址:")
    print("  用户服务: http://localhost:5000")
    print("  管理服务: http://localhost:5001")
    print("\n按 Ctrl+C 停止所有服务")
    print("=" * 50 + "\n")
    
    try:
        # 等待所有进程结束
        while True:
            # 检查进程状态
            user_status = user_proc.poll()
            admin_status = admin_proc.poll()
            
            if user_status is not None:
                print(f"用户服务已退出 (返回码: {user_status})")
                break
            
            if admin_status is not None:
                print(f"管理服务已退出 (返回码: {admin_status})")
                break
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == '__main__':
    main()
