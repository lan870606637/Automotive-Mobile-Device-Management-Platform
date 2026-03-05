# -*- coding: utf-8 -*-
"""
检查邮件服务状态
"""
import subprocess
import sys

def check_memurai():
    """检查 Memurai 是否运行"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        if r.ping():
            return True, "Memurai (Redis) 运行正常"
    except Exception as e:
        return False, f"Memurai 连接失败: {e}"

def check_celery():
    """检查 Celery 是否运行"""
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True)
        if 'celery.exe' in result.stdout:
            return True, "Celery Worker 运行正常"
        else:
            return False, "Celery Worker 未运行"
    except Exception as e:
        return False, f"检查 Celery 失败: {e}"

def main():
    print("=" * 50)
    print("邮件服务状态检查")
    print("=" * 50)
    print()
    
    # 检查 Memurai
    memurai_ok, memurai_msg = check_memurai()
    print(f"[{'✓' if memurai_ok else '✗'}] {memurai_msg}")
    
    # 检查 Celery
    celery_ok, celery_msg = check_celery()
    print(f"[{'✓' if celery_ok else '✗'}] {celery_msg}")
    
    print()
    print("=" * 50)
    
    if memurai_ok and celery_ok:
        print("✓ 邮件服务已启动，可以正常发送邮件")
    else:
        print("✗ 邮件服务未完全启动")
        print()
        print("请运行以下命令启动邮件服务:")
        print("  python start_all_services.py")
    
    print("=" * 50)

if __name__ == "__main__":
    main()
