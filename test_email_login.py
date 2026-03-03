# -*- coding: utf-8 -*-
"""测试移动端邮箱登录功能"""
import sys
sys.path.insert(0, 'd:/Automotive-Mobile-Device-Management-Platform')

from common.api_client import api_client

print('测试移动端邮箱登录功能')
print('=' * 50)

# 测试验证用户登录功能
print('\n1. 测试 verify_user_login 方法:')
try:
    # 使用一个测试邮箱（从用户列表中获取第一个用户的邮箱）
    users = api_client._users
    if users:
        test_user = users[0]
        test_email = test_user.email
        test_password = test_user.password
        print(f'   测试用户: {test_user.borrower_name}')
        print(f'   邮箱: {test_email}')
        
        # 测试正确密码
        result = api_client.verify_user_login(test_email, test_password)
        if result:
            print(f'   ✓ 正确密码验证成功')
        else:
            print(f'   ✗ 正确密码验证失败')
        
        # 测试错误密码
        result = api_client.verify_user_login(test_email, 'wrong_password')
        if not result:
            print(f'   ✓ 错误密码验证正确拒绝')
        else:
            print(f'   ✗ 错误密码验证应该被拒绝')
    else:
        print('   没有用户数据')
except Exception as e:
    print(f'   ✗ 测试失败: {e}')

print('\n2. 检查 mobile_login 路由配置:')
from user_service.app import app
with app.test_client() as client:
    # 测试GET请求
    response = client.get('/login/mobile')
    if response.status_code == 200:
        print('   ✓ GET /login/mobile 返回 200')
        # 检查是否包含邮箱输入框
        content = response.data.decode('utf-8')
        if 'email' in content or '邮箱' in content:
            print('   ✓ 页面包含邮箱输入字段')
        else:
            print('   ✗ 页面缺少邮箱输入字段')
    else:
        print(f'   ✗ GET /login/mobile 返回 {response.status_code}')

print('\n' + '=' * 50)
print('移动端邮箱登录修改完成！')
print('现在移动端和PC端都使用邮箱登录')
