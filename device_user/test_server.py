# -*- coding: utf-8 -*-
"""
测试服务器连接性
用于诊断苹果手机无法访问的问题
"""
import socket
import sys

# 获取本机IP
hostname = socket.gethostname()
ips = socket.getaddrinfo(hostname, None)
ip_list = set()
for ip in ips:
    if ip[4][0] not in ['127.0.0.1', '::1'] and ':' not in ip[4][0]:
        ip_list.add(ip[4][0])

print("=" * 50)
print("网络诊断信息")
print("=" * 50)
print(f"\n主机名: {hostname}")
print(f"IP地址: {', '.join(ip_list)}")
print(f"测试端口: 5000")

# 测试端口是否被监听
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('127.0.0.1', 5000))
if result == 0:
    print("\n✓ 端口 5000 正在监听")
else:
    print(f"\n✗ 端口 5000 未监听 (错误码: {result})")
sock.close()

print("\n" + "=" * 50)
print("苹果手机访问建议")
print("=" * 50)
print("""
1. 确保手机和电脑在同一WiFi下
2. 尝试在手机Safari中直接输入:
   http://192.168.10.63:5000/login

3. 如果还是打不开，可能是:
   - Windows防火墙阻止了5000端口
   - 企业网络隔离了有线/无线网段
   - iOS需要信任该IP

4. 快速测试方法:
   在另一台电脑/手机上访问相同地址
   如果其他设备能打开，说明是iOS特定问题

5. 备选方案:
   使用 ngrok 创建外网隧道
   pip install pyngrok
   ngrok http 5000
""")

# 尝试列出所有可用的网络接口
print("\n" + "=" * 50)
print("所有网络接口")
print("=" * 50)
import subprocess
try:
    result = subprocess.run(['ipconfig'], capture_output=True, text=True)
    print(result.stdout)
except:
    pass

print("\n按回车键退出...")
input()
