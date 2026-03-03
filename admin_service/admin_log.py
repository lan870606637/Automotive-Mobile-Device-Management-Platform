# -*- coding: utf-8 -*-
"""
后台管理操作日志模块
提供装饰器和工具函数用于记录后台管理操作
"""
import uuid
import json
from functools import wraps
from datetime import datetime
from flask import request, session, g

# 操作类型定义
class AdminActionType:
    """后台管理操作类型"""
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    DEVICE_CREATE = "DEVICE_CREATE"
    DEVICE_UPDATE = "DEVICE_UPDATE"
    DEVICE_DELETE = "DEVICE_DELETE"
    DEVICE_BORROW = "DEVICE_BORROW"
    DEVICE_RETURN = "DEVICE_RETURN"
    DEVICE_TRANSFER = "DEVICE_TRANSFER"
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_DELETE = "USER_DELETE"
    USER_FREEZE = "USER_FREEZE"
    USER_UNFREEZE = "USER_UNFREEZE"
    USER_SET_ADMIN = "USER_SET_ADMIN"
    USER_REMOVE_ADMIN = "USER_REMOVE_ADMIN"
    ANNOUNCEMENT_CREATE = "ANNOUNCEMENT_CREATE"
    ANNOUNCEMENT_UPDATE = "ANNOUNCEMENT_UPDATE"
    ANNOUNCEMENT_DELETE = "ANNOUNCEMENT_DELETE"
    ANNOUNCEMENT_TOGGLE = "ANNOUNCEMENT_TOGGLE"
    BOUNTY_MANAGE = "BOUNTY_MANAGE"
    REMARK_MANAGE = "REMARK_MANAGE"
    SYSTEM_SETTING = "SYSTEM_SETTING"
    DATA_IMPORT = "DATA_IMPORT"
    DATA_EXPORT = "DATA_EXPORT"
    OVERDUE_REMIND = "OVERDUE_REMIND"
    OTHER = "OTHER"


# 操作类型中文名称映射
ACTION_TYPE_NAMES = {
    AdminActionType.LOGIN: "登录",
    AdminActionType.LOGOUT: "退出",
    AdminActionType.DEVICE_CREATE: "创建设备",
    AdminActionType.DEVICE_UPDATE: "更新设备",
    AdminActionType.DEVICE_DELETE: "删除设备",
    AdminActionType.DEVICE_BORROW: "借出设备",
    AdminActionType.DEVICE_RETURN: "归还设备",
    AdminActionType.DEVICE_TRANSFER: "转借设备",
    AdminActionType.USER_CREATE: "创建用户",
    AdminActionType.USER_UPDATE: "更新用户",
    AdminActionType.USER_DELETE: "删除用户",
    AdminActionType.USER_FREEZE: "冻结用户",
    AdminActionType.USER_UNFREEZE: "解冻用户",
    AdminActionType.USER_SET_ADMIN: "设置管理员",
    AdminActionType.USER_REMOVE_ADMIN: "取消管理员",
    AdminActionType.ANNOUNCEMENT_CREATE: "创建公告",
    AdminActionType.ANNOUNCEMENT_UPDATE: "更新公告",
    AdminActionType.ANNOUNCEMENT_DELETE: "删除公告",
    AdminActionType.ANNOUNCEMENT_TOGGLE: "切换公告状态",
    AdminActionType.BOUNTY_MANAGE: "管理悬赏",
    AdminActionType.REMARK_MANAGE: "管理备注",
    AdminActionType.SYSTEM_SETTING: "系统设置",
    AdminActionType.DATA_IMPORT: "数据导入",
    AdminActionType.DATA_EXPORT: "数据导出",
    AdminActionType.OVERDUE_REMIND: "逾期提醒",
    AdminActionType.OTHER: "其他操作",
}


# 操作对象类型定义
class TargetType:
    """操作对象类型"""
    DEVICE = "DEVICE"
    USER = "USER"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    BOUNTY = "BOUNTY"
    REMARK = "REMARK"
    SYSTEM = "SYSTEM"


def get_client_ip():
    """获取客户端IP地址"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or ''


def mask_sensitive_data(data):
    """脱敏敏感数据"""
    if not isinstance(data, dict):
        return data

    sensitive_fields = ['password', 'passwd', 'pwd', 'secret', 'token', 'key', 'credit_card', 'id_card']
    masked = {}
    for k, v in data.items():
        if any(field in k.lower() for field in sensitive_fields):
            masked[k] = '***'
        elif isinstance(v, dict):
            masked[k] = mask_sensitive_data(v)
        elif isinstance(v, list):
            masked[k] = [mask_sensitive_data(item) if isinstance(item, dict) else item for item in v]
        else:
            masked[k] = v
    return masked


def log_admin_operation(action_type, action_name=None, target_type=None, target_id_getter=None,
                        target_name_getter=None, description_getter=None, log_params=False):
    """后台管理操作日志装饰器

    Args:
        action_type: 操作类型
        action_name: 操作名称（可选，默认从ACTION_TYPE_NAMES获取）
        target_type: 操作对象类型
        target_id_getter: 获取目标ID的函数，接收(*args, **kwargs)返回目标ID
        target_name_getter: 获取目标名称的函数，接收(*args, **kwargs)返回目标名称
        description_getter: 获取描述信息的函数，接收(*args, **kwargs, result, error)返回描述
        log_params: 是否记录请求参数
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 获取管理员信息
            admin_id = session.get('admin_id', '')
            admin_name = session.get('admin_name', '未知')

            # 如果没有管理员信息，直接执行原函数
            if not admin_id:
                return f(*args, **kwargs)

            # 准备日志数据
            _action_name = action_name or ACTION_TYPE_NAMES.get(action_type, action_type)
            _target_type = target_type or TargetType.SYSTEM
            _target_id = ''
            _target_name = ''
            _description = ''
            _result = 'SUCCESS'
            _error_message = ''

            # 获取请求信息
            _ip_address = get_client_ip()
            _user_agent = request.headers.get('User-Agent', '')[:500]  # 限制长度
            _request_method = request.method
            _request_path = request.path
            _request_params = ''

            if log_params:
                try:
                    params = {}
                    if request.method == 'GET':
                        params = dict(request.args)
                    elif request.is_json:
                        params = request.get_json(silent=True) or {}
                    else:
                        params = dict(request.form)

                    # 脱敏并序列化
                    masked_params = mask_sensitive_data(params)
                    _request_params = json.dumps(masked_params, ensure_ascii=False)[:2000]  # 限制长度
                except Exception:
                    _request_params = ''

            # 尝试获取目标信息
            try:
                if target_id_getter:
                    _target_id = target_id_getter(*args, **kwargs) or ''
                if target_name_getter:
                    _target_name = target_name_getter(*args, **kwargs) or ''
            except Exception:
                pass

            # 执行原函数
            result_data = None
            error = None
            try:
                result_data = f(*args, **kwargs)
                _result = 'SUCCESS'
            except Exception as e:
                _result = 'FAILED'
                _error_message = str(e)[:500]  # 限制长度
                error = e

            # 获取描述信息
            try:
                if description_getter:
                    _description = description_getter(*args, **kwargs, result=result_data, error=error) or ''
            except Exception:
                pass

            # 记录日志
            try:
                import sys
                import os
                # 确保项目根目录在路径中
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                from common.api_client import api_client
                api_client.add_admin_operation_log(
                    admin_id=admin_id,
                    admin_name=admin_name,
                    action_type=action_type,
                    action_name=_action_name,
                    target_type=_target_type,
                    target_id=_target_id,
                    target_name=_target_name,
                    description=_description,
                    ip_address=_ip_address,
                    user_agent=_user_agent,
                    request_method=_request_method,
                    request_path=_request_path,
                    request_params=_request_params,
                    result=_result,
                    error_message=_error_message
                )
            except Exception as e:
                # 日志记录失败不应影响主流程
                import traceback
                print(f"记录后台管理操作日志失败: {e}")
                print(traceback.format_exc())

            # 如果有异常，重新抛出
            if error:
                raise error

            return result_data
        return decorated_function
    return decorator


def log_admin_operation_manual(action_type, target_type=None, target_id='', target_name='',
                                description='', result='SUCCESS', error_message='',
                                action_name=None, log_params=False):
    """手动记录后台管理操作日志

    用于在视图函数内部手动记录日志

    Args:
        action_type: 操作类型
        target_type: 操作对象类型
        target_id: 操作对象ID
        target_name: 操作对象名称
        description: 操作描述
        result: 操作结果
        error_message: 错误信息
        action_name: 操作名称（可选）
        log_params: 是否记录请求参数
    """
    try:
        admin_id = session.get('admin_id', '')
        admin_name = session.get('admin_name', '未知')

        if not admin_id:
            return False

        _action_name = action_name or ACTION_TYPE_NAMES.get(action_type, action_type)
        _target_type = target_type or TargetType.SYSTEM

        # 获取请求信息
        _ip_address = get_client_ip()
        _user_agent = request.headers.get('User-Agent', '')[:500]
        _request_method = request.method
        _request_path = request.path
        _request_params = ''

        if log_params:
            try:
                params = {}
                if request.method == 'GET':
                    params = dict(request.args)
                elif request.is_json:
                    params = request.get_json(silent=True) or {}
                else:
                    params = dict(request.form)

                masked_params = mask_sensitive_data(params)
                _request_params = json.dumps(masked_params, ensure_ascii=False)[:2000]
            except Exception:
                _request_params = ''

        import sys
        import os
        # 确保项目根目录在路径中
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from common.api_client import api_client
        api_client.add_admin_operation_log(
            admin_id=admin_id,
            admin_name=admin_name,
            action_type=action_type,
            action_name=_action_name,
            target_type=_target_type,
            target_id=target_id,
            target_name=target_name,
            description=description,
            ip_address=_ip_address,
            user_agent=_user_agent,
            request_method=_request_method,
            request_path=_request_path,
            request_params=_request_params,
            result=result,
            error_message=error_message
        )
        return True
    except Exception as e:
        import traceback
        print(f"手动记录后台管理操作日志失败: {e}")
        print(traceback.format_exc())
        return False
