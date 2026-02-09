# -*- coding: utf-8 -*-
"""
工具函数模块
"""


def mask_phone(phone):
    """手机号脱敏显示"""
    if len(phone) == 11:
        return phone[:3] + '****' + phone[7:]
    return phone


def is_mobile_device(request):
    """检测是否为移动设备"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'wechat', 'micromessenger', 'windows phone']
    return any(keyword in user_agent for keyword in mobile_keywords)
