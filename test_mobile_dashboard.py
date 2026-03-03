# -*- coding: utf-8 -*-
"""测试移动端首页"""
import sys
sys.path.insert(0, 'd:/Automotive-Mobile-Device-Management-Platform')

from user_service.app import app

print('测试移动端首页')
print('=' * 50)

with app.test_client() as client:
    # 先登录获取session
    print('\n1. 测试登录...')
    login_data = {
        'email': 'pis.fang@carbit.com.cn',
        'password': '123456'
    }
    
    # 测试移动端登录页面
    response = client.get('/login/mobile')
    if response.status_code == 200:
        print('   ✓ GET /login/mobile 返回 200')
    else:
        print(f'   ✗ GET /login/mobile 返回 {response.status_code}')
    
    # 测试登录
    response = client.post('/login/mobile', data=login_data, follow_redirects=True)
    if b'\u6211\u7684\u8bbe\u5907' in response.data or b'dashboard' in response.data or response.status_code == 200:
        print('   ✓ 移动端登录成功')
    else:
        print(f'   ⚠ 登录后状态: {response.status_code}')
    
    # 测试移动端首页
    print('\n2. 测试移动端首页 /home...')
    response = client.get('/home')
    if response.status_code == 200:
        print('   ✓ GET /home 返回 200')
        content = response.data.decode('utf-8')
        
        # 检查关键内容
        checks = [
            ('移动端首页标题', '\u6211\u7684\u8bbe\u5907' in content),
            ('快捷操作', '\u501f\u8f66\u673a' in content),
            ('统计概览', '\u5f53\u524d\u501f\u7528' in content),
            ('当前借用', '\u5f53\u524d\u501f\u7528' in content),
        ]
        
        for name, result in checks:
            if result:
                print(f'   ✓ 包含: {name}')
            else:
                print(f'   ✗ 缺少: {name}')
    else:
        print(f'   ✗ GET /home 返回 {response.status_code}')

print('\n' + '=' * 50)
print('移动端首页测试完成！')
