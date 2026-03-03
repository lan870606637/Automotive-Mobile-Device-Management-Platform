# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'd:/Automotive-Mobile-Device-Management-Platform')

from user_service.app import app

print('测试移动端页面路由')
print('=' * 50)

with app.test_client() as client:
    # 使用session来保持登录状态
    with client.session_transaction() as sess:
        sess['user_id'] = 'pis.fang@carbit.com.cn'
        sess['email'] = 'pis.fang@carbit.com.cn'
        sess['borrower_name'] = '方平'

    # 测试设备列表
    print('\n1. 测试 /devices?type=car')
    response = client.get('/devices?type=car')
    print(f'   状态码: {response.status_code}')
    if response.status_code == 302:
        print(f'   重定向到: {response.location}')
    elif response.status_code == 200:
        content = response.data.decode('utf-8', errors='ignore')
        if 'mobile-device-list' in content:
            print('   ✓ 使用移动端模板')
        elif 'pc-device-list' in content or 'pc/' in content:
            print('   ✗ 使用了PC端模板')
        else:
            print('   ? 模板类型不确定')
            # 打印部分内容用于调试
            print(f'   内容片段: {content[:300]}...')

    # 测试设备详情
    print('\n2. 测试 /device/1')
    response = client.get('/device/1?device_type=car')
    print(f'   状态码: {response.status_code}')
    if response.status_code == 302:
        print(f'   重定向到: {response.location}')
    elif response.status_code == 200:
        content = response.data.decode('utf-8', errors='ignore')
        if 'mobile-device-detail' in content:
            print('   ✓ 使用移动端模板')
        elif 'pc-device-detail' in content or 'pc/' in content:
            print('   ✗ 使用了PC端模板')
        else:
            print('   ? 模板类型不确定')
            print(f'   内容片段: {content[:300]}...')

    # 测试记录页面
    print('\n3. 测试 /my-records')
    response = client.get('/my-records')
    print(f'   状态码: {response.status_code}')
    if response.status_code == 302:
        print(f'   重定向到: {response.location}')
    elif response.status_code == 200:
        content = response.data.decode('utf-8', errors='ignore')
        if 'mobile-records' in content:
            print('   ✓ 使用移动端模板')
        elif 'pc-records' in content or 'pc/' in content:
            print('   ✗ 使用了PC端模板')
        else:
            print('   ? 模板类型不确定')
            print(f'   内容片段: {content[:300]}...')

print('\n' + '=' * 50)
print('测试完成')
