# -*- coding: utf-8 -*-
"""
生产环境启动脚本 - 使用 Waitress WSGI 服务器
支持高并发，适合100+用户同时使用

用法: python start_production.py [quick|full]
  quick - 快速启动（带端口号，无需管理员权限）
  full  - 完整启动（带Nginx，不带端口号，需要管理员权限）

特点:
  - 使用 Waitress 替代 Flask 开发服务器
  - 支持多线程处理并发请求
  - 自动根据CPU核心数调整工作线程
  - 支持 graceful shutdown
"""
import sys
import os
import subprocess
import time
import signal
import socket
import argparse
import threading
from pathlib import Path

# 添加项目根目录到路径
PROJECT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_DIR))

# 尝试导入waitress
try:
    from waitress import serve
    WAITRESS_AVAILABLE = True
except ImportError:
    WAITRESS_AVAILABLE = False
    print("[警告] Waitress未安装，将使用Flask开发服务器")
    print("       建议安装: pip install waitress")

# 配置
NGINX_PATH = PROJECT_DIR / "nginx"
NGINX_EXE = NGINX_PATH / "nginx.exe"
HOSTS_FILE = Path("C:/Windows/System32/drivers/etc/hosts")
LOGS_DIR = PROJECT_DIR / "logs"

# 确保日志目录存在
LOGS_DIR.mkdir(exist_ok=True)

# 进程列表
processes = []
servers = []  # Waitress服务器列表


def print_header():
    """打印标题"""
    print("=" * 60)
    print("   车机与手机设备管理系统 - 生产环境启动脚本")
    print("   支持高并发 (100+用户)")
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


def get_cpu_count():
    """获取CPU核心数"""
    try:
        return os.cpu_count() or 4
    except:
        return 4


def start_service_waitress(service_name, app_module, app_var, port):
    """使用Waitress启动服务（生产环境）"""
    print(f"[启动] {service_name} (端口: {port})...")
    
    if not WAITRESS_AVAILABLE:
        # 降级到Flask开发服务器
        return start_service_flask(service_name, app_module, app_var, port)
    
    try:
        # 动态导入应用
        module_parts = app_module.split('.')
        module = __import__(app_module, fromlist=[app_var])
        app = getattr(module, app_var)
        
        # 计算线程数
        cpu_count = get_cpu_count()
        threads = min(cpu_count * 2, 16)  # 线程数 = CPU核心数 * 2，最大16
        
        print(f"       配置: {threads}线程, CPU核心: {cpu_count}")
        
        # 在后台线程中启动Waitress
        def run_server():
            serve(
                app,
                host='0.0.0.0',
                port=port,
                threads=threads,
                channel_timeout=60,
                cleanup_interval=30,
                max_request_body_size=1073741824,  # 1GB
                expose_tracebacks=False,
                ident='DeviceManagementServer/1.0'
            )
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        time.sleep(2)
        print(f"       {service_name} 已启动 (Waitress: {threads}线程)")
        return server_thread
        
    except Exception as e:
        print(f"[错误] 启动{service_name}失败: {e}")
        print("       降级到Flask开发服务器...")
        return start_service_flask(service_name, app_module, app_var, port)


def start_service_flask(service_name, app_module, app_var, port):
    """使用Flask开发服务器启动（降级方案）"""
    print(f"[启动] {service_name} (端口: {port}) [Flask开发服务器]...")
    
    env = os.environ.copy()
    env['PYTHONPATH'] = str(PROJECT_DIR)
    env['PYTHONIOENCODING'] = 'utf-8'
    
    # 日志文件路径
    log_file = LOGS_DIR / f"{app_module.split('.')[0]}.log"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"Service started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*50}\n")
    
    # 创建启动脚本
    script_content = f"""
import sys
sys.path.insert(0, r'{PROJECT_DIR}')
from {app_module} import {app_var}
{app_var}.run(host='0.0.0.0', port={port}, threaded=True, debug=False)
"""
    script_file = LOGS_DIR / f"start_{app_module.split('.')[0]}.py"
    with open(script_file, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    proc = subprocess.Popen(
        [sys.executable, str(script_file)],
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
    print("性能配置:")
    print("=" * 60)
    cpu_count = get_cpu_count()
    threads = min(cpu_count * 2, 16)
    print(f"  CPU核心数: {cpu_count}")
    print(f"  服务线程数: {threads}")
    print(f"  数据库连接池: 100")
    print(f"  Nginx Worker: auto")
    
    print("\n" + "=" * 60)
    print("日志文件:")
    print("=" * 60)
    print(f"  用户服务: logs/user_service.log")
    print(f"  管理服务: logs/admin_service.log")
    print(f"  手机端服务: logs/mobile_service.log")
    if mode == 'full':
        print(f"  Nginx:    nginx/logs/error.log")

    print("\n" + "=" * 60)
    print("按 Ctrl+C 停止所有服务")
    print("=" * 60 + "\n")


def run_quick_mode():
    """快速模式 - 只启动Python服务"""
    print("\n[模式] 生产环境快速启动 (带端口号)\n")
    
    local_ip = get_local_ip()
    cpu_count = get_cpu_count()
    threads = min(cpu_count * 2, 16)
    
    print(f"系统信息:")
    print(f"  CPU核心数: {cpu_count}")
    print(f"  服务线程数: {threads}")
    print(f"  数据库连接池: 100")
    print()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动服务
    if WAITRESS_AVAILABLE:
        print("使用 Waitress WSGI 服务器 (生产环境)\n")
        user_proc = start_service_waitress("用户服务", "user_service.app", "app", 5000)
        admin_proc = start_service_waitress("管理服务", "admin_service.app", "app", 5001)
        mobile_proc = start_service_waitress("手机端服务", "mobile_service.app", "app", 5002)
    else:
        print("使用 Flask 开发服务器 (降级模式)\n")
        user_proc = start_service_flask("用户服务", "user_service.app", "app", 5000)
        admin_proc = start_service_flask("管理服务", "admin_service.app", "app", 5001)
        mobile_proc = start_service_flask("手机端服务", "mobile_service.app", "app", 5002)
    
    print("\n" + "=" * 60)
    print("所有服务已启动!")
    
    print_access_urls('quick', local_ip)
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


def run_full_mode():
    """完整模式 - 启动Python服务 + Nginx"""
    print("\n[模式] 生产环境完整启动 (带Nginx，不带端口号)\n")
    
    # 检查管理员权限
    if not is_admin():
        print("[错误] 请以管理员身份运行此脚本!")
        print("       Nginx 需要绑定 80 端口，需要管理员权限。")
        print("\n操作方法:")
        print("  1. 右键点击命令提示符/PowerShell")
        print("  2. 选择'以管理员身份运行'")
        print("  3. 运行: python start_production.py full")
        return
    
    # 检查Nginx
    if not check_nginx():
        return
    
    # 检查hosts配置
    if not check_hosts_configured():
        if not setup_hosts():
            return
    
    local_ip = get_local_ip()
    cpu_count = get_cpu_count()
    threads = min(cpu_count * 2, 16)
    
    print(f"系统信息:")
    print(f"  CPU核心数: {cpu_count}")
    print(f"  服务线程数: {threads}")
    print(f"  数据库连接池: 100")
    print()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 先停止可能已运行的Nginx
    stop_nginx()
    time.sleep(1)
    
    # 启动服务
    if WAITRESS_AVAILABLE:
        print("使用 Waitress WSGI 服务器 (生产环境)\n")
        user_proc = start_service_waitress("用户服务", "user_service.app", "app", 5000)
        admin_proc = start_service_waitress("管理服务", "admin_service.app", "app", 5001)
        mobile_proc = start_service_waitress("手机端服务", "mobile_service.app", "app", 5002)
    else:
        print("使用 Flask 开发服务器 (降级模式)\n")
        user_proc = start_service_flask("用户服务", "user_service.app", "app", 5000)
        admin_proc = start_service_flask("管理服务", "admin_service.app", "app", 5001)
        mobile_proc = start_service_flask("手机端服务", "mobile_service.app", "app", 5002)
    
    # 启动Nginx
    if not start_nginx():
        signal_handler(None, None)
        return
    
    print("\n" + "=" * 60)
    print("所有服务已启动!")
    
    print_access_urls('full', local_ip)
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


def main():
    """主函数"""
    print_header()
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='设备管理系统生产环境启动脚本 - 支持100+并发',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start_production.py        # 快速启动（默认）
  python start_production.py quick  # 快速启动（带端口号）
  python start_production.py full   # 完整启动（带Nginx，需要管理员权限）

性能优化:
  - 使用 Waitress WSGI 服务器替代 Flask 开发服务器
  - 数据库连接池: 100连接
  - 自动根据CPU核心数调整线程数
  - Nginx 启用 Gzip 压缩和静态缓存
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
