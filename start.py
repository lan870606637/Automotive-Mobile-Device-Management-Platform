# -*- coding: utf-8 -*-
"""
统一启动脚本 - 支持快速模式和完整模式
用法: python start.py [quick|full]
  quick - 快速启动（带端口号，无需管理员权限）
  full  - 完整启动（带Nginx，不带端口号，需要管理员权限）
"""
import sys
import os
import subprocess
import time
import signal
import socket
import argparse
from threading import Thread
from pathlib import Path

# 添加项目根目录到路径
PROJECT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_DIR))

# 配置
NGINX_PATH = PROJECT_DIR / "nginx"
NGINX_EXE = NGINX_PATH / "nginx.exe"
HOSTS_FILE = Path("C:/Windows/System32/drivers/etc/hosts")
LOGS_DIR = PROJECT_DIR / "logs"

# 确保日志目录存在
LOGS_DIR.mkdir(exist_ok=True)

# 进程列表
processes = []


def print_header():
    """打印标题"""
    print("=" * 60)
    print("   车机与手机设备管理系统 - 统一启动脚本")
    print("=" * 60)
    print()


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_admin():
    """检查是否以管理员权限运行"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def check_nginx():
    """检查Nginx是否存在"""
    if not NGINX_EXE.exists():
        print("[错误] 找不到 Nginx!")
        print(f"       请下载 Nginx 并解压到: {NGINX_PATH}")
        print("       下载地址: http://nginx.org/en/download.html")
        return False
    return True


def check_hosts_configured():
    """检查hosts文件是否已配置域名"""
    try:
        with open(HOSTS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            return 'device.carbit.com.cn' in content
    except:
        return False


def setup_hosts():
    """配置hosts文件"""
    print("[配置] 正在配置域名...")
    try:
        hosts_entries = """
# 设备管理系统本地开发环境
127.0.0.1       device.carbit.com.cn
127.0.0.1       admin.device.carbit.com.cn
127.0.0.1       mobile.device.carbit.com.cn
"""
        with open(HOSTS_FILE, 'a', encoding='utf-8') as f:
            f.write(hosts_entries)
        print("       域名配置完成")
        return True
    except Exception as e:
        print(f"[错误] 配置域名失败: {e}")
        print("       请手动以管理员身份运行 setup_domains.bat")
        return False


def start_service(service_name, app_path, port):
    """启动服务（后台运行，日志写入文件）"""
    print(f"[启动] {service_name} (端口: {port})...")

    env = os.environ.copy()
    env['PYTHONPATH'] = str(PROJECT_DIR)
    # 设置 UTF-8 编码，避免 Unicode 错误
    env['PYTHONIOENCODING'] = 'utf-8'

    # 日志文件路径
    log_file = LOGS_DIR / f"{Path(app_path).stem}.log"

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"Service started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*50}\n")

    proc = subprocess.Popen(
        [sys.executable, str(app_path)],
        cwd=str(PROJECT_DIR),
        env=env,
        stdout=open(log_file, 'a', encoding='utf-8'),
        stderr=subprocess.STDOUT
    )
    processes.append(proc)
    time.sleep(2)
    print(f"       {service_name} 已启动 (日志: logs/{log_file.name})")
    return proc


def start_nginx():
    """启动Nginx（后台运行）"""
    print("[启动] Nginx (端口: 80)...")
    
    proc = subprocess.Popen(
        [str(NGINX_EXE)],
        cwd=str(NGINX_PATH),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(proc)
    time.sleep(2)
    
    # 验证Nginx是否启动成功
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq nginx.exe'],
        capture_output=True,
        text=True
    )
    if 'nginx.exe' in result.stdout:
        print("       Nginx 已启动")
        return True
    else:
        print("[错误] Nginx 启动失败!")
        print("       请检查 nginx/logs/error.log 了解详情")
        return False


def stop_nginx():
    """停止Nginx"""
    subprocess.run(['taskkill', '/f', '/im', 'nginx.exe'], 
                   capture_output=True)


def signal_handler(sig, frame):
    """信号处理函数 - 优雅地关闭所有服务"""
    print("\n" + "=" * 60)
    print("正在关闭所有服务...")
    print("=" * 60)
    
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    
    stop_nginx()
    print("所有服务已关闭")
    sys.exit(0)


def print_access_urls(mode, local_ip):
    """打印访问地址"""
    print("\n" + "=" * 60)
    print("访问地址:")
    print("=" * 60)

    if mode == 'full':
        print("\n【域名访问】(推荐，无需端口号):")
        print("  用户端:   http://device.carbit.com.cn")
        print("  管理后台: http://admin.device.carbit.com.cn")
        print("  手机端:   http://mobile.device.carbit.com.cn")

    print("\n【本地访问】(带端口号):")
    print("  用户端:   http://localhost:5000")
    print("  管理后台: http://localhost:5001")
    print("  手机端:   http://localhost:5002")

    print(f"\n【局域网访问】(其他设备使用):")
    print(f"  用户端:   http://{local_ip}:5000")
    print(f"  管理后台: http://{local_ip}:5001")
    print(f"  手机端:   http://{local_ip}:5002")

    print("\n" + "=" * 60)
    print("日志文件:")
    print("=" * 60)
    print(f"  用户服务: logs/app.log")
    print(f"  管理服务: logs/app.log")
    print(f"  手机端服务: logs/app.log")
    if mode == 'full':
        print(f"  Nginx:    nginx/logs/error.log")

    print("\n" + "=" * 60)
    print("按 Ctrl+C 停止所有服务")
    print("=" * 60 + "\n")


def run_quick_mode():
    """快速模式 - 只启动Python服务"""
    print("\n[模式] 快速启动 (带端口号)\n")
    
    local_ip = get_local_ip()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动服务
    user_proc = start_service("用户服务", "user_service/app.py", 5000)
    admin_proc = start_service("管理服务", "admin_service/app.py", 5001)
    mobile_proc = start_service("手机端服务", "mobile_service/app.py", 5002)
    
    print("\n" + "=" * 60)
    print("所有服务已启动!")
    
    print_access_urls('quick', local_ip)
    
    # 等待进程结束
    try:
        while True:
            if user_proc.poll() is not None:
                print(f"用户服务已退出 (返回码: {user_proc.poll()})")
                break
            if admin_proc.poll() is not None:
                print(f"管理服务已退出 (返回码: {admin_proc.poll()})")
                break
            if mobile_proc.poll() is not None:
                print(f"手机端服务已退出 (返回码: {mobile_proc.poll()})")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


def run_full_mode():
    """完整模式 - 启动Python服务 + Nginx"""
    print("\n[模式] 完整启动 (带Nginx，不带端口号)\n")
    
    # 检查管理员权限
    if not is_admin():
        print("[错误] 请以管理员身份运行此脚本!")
        print("       Nginx 需要绑定 80 端口，需要管理员权限。")
        print("\n操作方法:")
        print("  1. 右键点击命令提示符/PowerShell")
        print("  2. 选择'以管理员身份运行'")
        print("  3. 运行: python start.py full")
        return
    
    # 检查Nginx
    if not check_nginx():
        return
    
    # 检查hosts配置
    if not check_hosts_configured():
        if not setup_hosts():
            return
    
    local_ip = get_local_ip()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 先停止可能已运行的Nginx
    stop_nginx()
    time.sleep(1)
    
    # 启动服务
    user_proc = start_service("用户服务", "user_service/app.py", 5000)
    admin_proc = start_service("管理服务", "admin_service/app.py", 5001)
    mobile_proc = start_service("手机端服务", "mobile_service/app.py", 5002)
    
    # 启动Nginx
    if not start_nginx():
        signal_handler(None, None)
        return
    
    print("\n" + "=" * 60)
    print("所有服务已启动!")
    
    print_access_urls('full', local_ip)
    
    # 等待进程结束
    try:
        while True:
            if user_proc.poll() is not None:
                print(f"用户服务已退出 (返回码: {user_proc.poll()})")
                break
            if admin_proc.poll() is not None:
                print(f"管理服务已退出 (返回码: {admin_proc.poll()})")
                break
            if mobile_proc.poll() is not None:
                print(f"手机端服务已退出 (返回码: {mobile_proc.poll()})")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


def main():
    """主函数"""
    print_header()
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='设备管理系统启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start.py        # 快速启动（默认）
  python start.py quick  # 快速启动（带端口号）
  python start.py full   # 完整启动（带Nginx，需要管理员权限）
        """
    )
    parser.add_argument(
        'mode',
        nargs='?',
        choices=['quick', 'full'],
        default='quick',
        help='启动模式: quick=快速启动(默认), full=完整启动带Nginx'
    )
    args = parser.parse_args()
    
    # 根据模式启动
    if args.mode == 'quick':
        run_quick_mode()
    else:
        run_full_mode()


if __name__ == '__main__':
    main()
