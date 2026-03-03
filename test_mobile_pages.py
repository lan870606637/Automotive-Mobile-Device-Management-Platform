# -*- coding: utf-8 -*-
"""测试移动端页面"""
import sys
sys.path.insert(0, 'd:/Automotive-Mobile-Device-Management-Platform')

from user_service.app import app

print('测试移动端页面')
print('=' * 50)

with app.test_client() as client:
    # 先登录
    login_data = {
        'email': 'pis.fang@carbit.com.cn',
        'password': '123456'
    }
    client.post('/login/mobile', data=login_data)

    # 测试设备列表页面
    print('\n1. 测试设备列表 /devices...')
    response = client.get('/devices?type=car')
    if response.status_code == 200:
        print('   ✓ GET /devices 返回 200')
        content = response.data.decode('utf-8')
        if 'mobile-device-list' in content or '车机设备' in content:
            print('   ✓ 使用移动端模板')
        else:
            print('   ✗ 未使用移动端模板')
    else:
        print(f'   ✗ GET /devices 返回 {response.status_code}')

    # 测试设备详情页面
    print('\n2. 测试设备详情 /device/<id>...')
    response = client.get('/device/1?device_type=car')
    if response.status_code == 200:
        print('   ✓ GET /device/1 返回 200')
        content = response.data.decode('utf-8')
        if 'mobile-device-detail' in content or '设备详情' in content:
            print('   ✓ 使用移动端模板')
        else:
            print('   ✗ 未使用移动端模板')
    else:
        print(f'   ✗ GET /device/1 返回 {response.status_code}')

    # 测试记录页面
    print('\n3. 测试记录页面 /my-records...')
    response = client.get('/my-records')
    if response.status_code == 200:
        print('   ✓ GET /my-records 返回 200')
        content = response.data.decode('utf-8')
        if 'mobile-records' in content or '我的记录' in content:
            print('   ✓ 使用移动端模板')
        else:
            print('   ✗ 未使用移动端模板')
    else:
        print(f'   ✗ GET /my-records 返回 {response.status_code}')

print('\n' + '=' * 50)
print('移动端页面测试完成！')
