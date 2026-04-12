# -*- coding: utf-8 -*-
"""
批量创建测试用户脚本
用于 JMeter 压测准备
"""
import requests
import json

# 配置
BASE_URL = "http://localhost:5001"
ADMIN_USERNAME = "admin"  # 修改为你的管理员账号
ADMIN_PASSWORD = "admin123"  # 修改为你的管理员密码
USER_COUNT = 100

# 先登录管理员
session = requests.Session()
login_resp = session.post(
    f"{BASE_URL}/api/admin/login",
    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
)

if not login_resp.json().get('success'):
    print("管理员登录失败:", login_resp.json())
    exit(1)

print("管理员登录成功")

# 批量创建用户
users_file = "test_users.csv"
with open(users_file, "w", encoding="utf-8") as f:
    f.write("email,password\n")  # CSV 头部
    
    for i in range(1, USER_COUNT + 1):
        user_data = {
            "name": f"测试用户{i}",
            "email": f"test{i}@example.com",
            "password": "123456",
            "is_admin": False
        }
        
        resp = session.post(
            f"{BASE_URL}/api/admin/users",
            json=user_data
        )
        
        if resp.json().get('success'):
            f.write(f"{user_data['email']},{user_data['password']}\n")
            print(f"✓ 创建用户 {i}/100: {user_data['email']}")
        else:
            print(f"✗ 创建用户 {i}/100 失败: {resp.json()}")

print(f"\n完成！用户列表已保存到 {users_file}")
print("可以在 JMeter 中使用 CSV Data Set Config 读取该文件")
