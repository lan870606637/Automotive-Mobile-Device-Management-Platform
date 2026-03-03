# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'd:/Automotive-Mobile-Device-Management-Platform')

from user_service.app import app

print('检查移动端路由配置')
print('=' * 50)

# 获取所有路由
with app.app_context():
    rules = list(app.url_map.iter_rules())
    
    # 查找移动端路由
    mobile_routes = [r for r in rules if not r.rule.startswith('/pc') and not r.rule.startswith('/static')]
    
    print('\n移动端相关路由:')
    for rule in sorted(mobile_routes, key=lambda x: x.rule):
        if rule.rule in ['/devices', '/device/<device_id>', '/my-records', '/home', '/login/mobile']:
            print(f'  {rule.rule} -> {rule.endpoint}')

print('\n' + '=' * 50)
print('检查完成')
