# -*- coding: utf-8 -*-
"""
修复 app.py 文件中的 DatabaseStore 调用
"""
import re

# 修复 user_service/app.py
with open('user_service/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换 DatabaseStore.xxx() 为 api_client._db.xxx()
content = re.sub(r'DatabaseStore\.', 'api_client._db.', content)

with open('user_service/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ user_service/app.py 修复完成")

# 修复 admin_service/app.py
with open('admin_service/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换 DatabaseStore.xxx() 为 api_client._db.xxx()
content = re.sub(r'DatabaseStore\.', 'api_client._db.', content)

with open('admin_service/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ admin_service/app.py 修复完成")
print("\n所有文件修复完成！")
