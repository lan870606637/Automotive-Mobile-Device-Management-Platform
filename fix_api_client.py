# -*- coding: utf-8 -*-
"""
修复 api_client.py 中的 DatabaseStore 调用
"""

with open('common/api_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换所有的 DatabaseStore. 为 self._db.
content = content.replace('DatabaseStore.', 'self._db.')

with open('common/api_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("修复完成！所有的 DatabaseStore. 已替换为 self._db.")
