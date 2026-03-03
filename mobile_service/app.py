# -*- coding: utf-8 -*-
"""
车机与手机设备管理系统 - 手机端服务
使用 Flask 实现，适配手机浏览器
端口: 5002
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uuid
import json
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from dotenv import load_dotenv

# 从 common 导入
from common.models import DeviceStatus, DeviceType, OperationType, EntrySource, ReservationStatus
from common.api_client import api_client
from common.db_store import init_database
from common.utils import mask_phone
from common.config import SECRET_KEY, SERVER_URL, MOBILE_SERVICE_PORT

load_dotenv()

app = Flask(__name__, template_folder='../user_service/templates', static_folder='../user_service/static')
app.secret_key = SECRET_KEY

# 初始化数据库（创建必要的表）
init_database()


def login_required(f):
    """登录验证装饰器 - 未登录跳转到设备选择页面"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('select_device_type'))
        # 检查用户是否仍然存在（可能已被管理员删除）
        user = get_current_user()
        if not user:
            session.clear()
            return redirect(url_for('select_device_type'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """获取当前登录用户信息"""
    user_id = session.get('user_id', '')
    user = None
    for u in api_client._users:
        if u.id == user_id:
            user = u
            break

    if user:
        # 获取用户当前积分
        user_points = api_client._db.get_user_points(user_id)
        points = user_points.points if user_points else 0

        return {
            'user_id': user.id,
            'email': user.email,
            'borrower_name': user.borrower_name,
            'avatar': user.avatar,
            'is_admin': user.is_admin,
            'points': points
        }
    return None


def get_device_type_mapping(device_type):
    """将设备类型映射为中文"""
    mapping = {
        'car_machine': '车机',
        'car': '车机',
        'phone': '手机',
        'instrument': '仪表',
        'simcard': '手机卡',
        'other': '其它设备'
    }
    return mapping.get(device_type, '车机')


def is_admin_user(borrower_name):
    """检查指定借用人是否为管理员"""
    return api_client.is_user_admin(borrower_name)


@app.context_processor
def inject_globals():
    """注入全局模板变量和函数"""
    return {
        'is_admin_user': is_admin_user
    }


def device_to_dict(device):
    """将设备对象转换为字典"""
    return {
        'id': device.id,
        'name': device.name,
        'model': device.model,
        'device_type': device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
        'status': device.status.value if hasattr(device.status, 'value') else str(device.status),
        'borrower': device.borrower,
        'borrow_time': device.borrow_time.isoformat() if device.borrow_time else None,
        'expected_return_date': device.expected_return_date.isoformat() if device.expected_return_date else None,
        'remark': device.remark,
        'jira_address': device.jira_address if hasattr(device, 'jira_address') else '',
        'create_time': device.create_time.isoformat() if device.create_time else None,
    }


@app.route('/')
def index():
    """首页 - 根据设备类型和登录状态重定向"""
    # 如果已登录，跳转到设备列表
    if 'user_id' in session:
        return redirect(url_for('device_list'))

    # 未登录则跳转到设备类型选择页面
    return redirect(url_for('select_device_type'))


@app.route('/home')
@login_required
def home():
    """首页/仪表盘页面"""
    return redirect(url_for('device_list'))


@app.route('/select-device-type')
def select_device_type():
    """选择设备类型页面"""
    return render_template('select_device_type.html')


@app.route('/auth/<device_type>')
def auth(device_type):
    """认证页面"""
    if device_type not in ['car_machine', 'phone']:
        return redirect(url_for('select_device_type'))

    # 如果已登录，直接跳转到设备列表
    if 'user_id' in session:
        return redirect(url_for('device_list'))

    # 设置设备类型到session
    session['device_type'] = device_type

    # 根据设备类型选择模板
    if device_type == 'phone':
        return render_template('mobile/login.html')
    else:
        return render_template('auth.html', device_type=device_type)


@app.route('/api/login', methods=['POST'])
def api_login():
    """登录API"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    device_type = data.get('device_type', session.get('device_type', 'car_machine'))

    if not email or not password:
        return jsonify({'success': False, 'message': '请输入邮箱和密码'})

    # 验证用户
    user = None
    for u in api_client._users:
        if u.email.lower() == email:
            user = u
            break

    if not user:
        return jsonify({'success': False, 'message': '邮箱或密码错误'})

    # 验证密码
    if user.password != password:
        return jsonify({'success': False, 'message': '邮箱或密码错误'})

    # 设置session
    session['user_id'] = user.id
    session['device_type'] = device_type
    session.permanent = True

    return jsonify({
        'success': True,
        'message': '登录成功',
        'user': {
            'id': user.id,
            'email': user.email,
            'borrower_name': user.borrower_name,
            'avatar': user.avatar,
            'is_admin': user.is_admin
        }
    })


@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('select_device_type'))


@app.route('/devices')
@login_required
def device_list():
    """设备列表页面"""
    device_type = session.get('device_type', 'car_machine')
    current_user = get_current_user()

    # 重新加载数据
    api_client.reload_data()

    # 获取设备数据 - 使用正确的方法
    device_type_cn = get_device_type_mapping(device_type)
    devices = api_client.get_all_devices(device_type_cn)

    # 转换为字典列表
    device_list_data = [device_to_dict(d) for d in devices]

    # 获取当前用户的借用记录 - 使用正确的方法
    all_records = api_client.get_records()
    borrowing_device_ids = []
    for record in all_records:
        if (record.borrower == current_user['borrower_name'] and
            hasattr(record, 'operation_type') and
            '借出' in str(record.operation_type)):
            borrowing_device_ids.append(record.device_id)

    # 标记已借用的设备
    for device in device_list_data:
        device['is_borrowing'] = device['id'] in borrowing_device_ids

    # 分页参数
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(device_list_data)
    total_pages = (total + per_page - 1) // per_page

    # 分页数据
    start = (page - 1) * per_page
    end = start + per_page
    paginated_devices = device_list_data[start:end]

    return render_template('device_list.html',
                         devices=paginated_devices,
                         device_type=device_type,
                         current_user=current_user,
                         page=page,
                         total_pages=total_pages,
                         total=total)


@app.route('/device/<device_id>')
@login_required
def device_detail(device_id):
    """设备详情页面"""
    device_type = session.get('device_type', 'car_machine')
    current_user = get_current_user()

    # 重新加载数据
    api_client.reload_data()

    # 获取设备信息 - 使用正确的方法
    device = api_client.get_device_by_id(device_id)
    if not device:
        return render_template('device_detail.html',
                             error='设备不存在',
                             device_type=device_type,
                             current_user=current_user)

    # 转换为字典
    device_data = device_to_dict(device)

    # 获取设备的借用记录
    records = api_client._db.get_records_by_device(device_id)

    # 检查当前用户是否正在借用此设备
    is_borrowing = False
    for record in records:
        if (record.borrower == current_user['borrower_name'] and
            hasattr(record, 'operation_type') and
            '借出' in str(record.operation_type)):
            is_borrowing = True
            break

    return render_template('device_detail.html',
                         device=device_data,
                         device_type=device_type,
                         current_user=current_user,
                         is_borrowing=is_borrowing,
                         records=records)


@app.route('/device/<device_id>/simple')
@login_required
def device_detail_simple(device_id):
    """设备详情页面（简化版）"""
    # 简化版直接重定向到普通详情页
    return redirect(url_for('device_detail', device_id=device_id))


@app.route('/api/borrow', methods=['POST'])
@login_required
def api_borrow():
    """借用设备API"""
    data = request.get_json()
    device_id = data.get('device_id')
    device_type = data.get('device_type', session.get('device_type', 'car_machine'))
    remark = data.get('remark', '')

    current_user = get_current_user()

    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})

    # 重新加载数据
    api_client.reload_data()

    # 检查设备是否可借用
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})

    # 检查设备状态
    if device.status not in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]:
        return jsonify({'success': False, 'message': '设备当前不可借用'})

    # 创建借用记录
    record_id = str(uuid.uuid4())
    record_data = {
        'id': record_id,
        'device_id': device_id,
        'device_type': device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
        'borrower_id': current_user['user_id'],
        'borrower_name': current_user['borrower_name'],
        'borrower_email': current_user['email'],
        'borrow_time': datetime.now(),
        'status': DeviceStatus.BORROWED,
        'remark': remark,
        'entry_source': EntrySource.WEB
    }

    # 保存记录
    api_client._db.add_record(record_data)

    # 更新设备状态
    api_client._db.update_device_status(device_id, device.device_type, DeviceStatus.BORROWED)

    return jsonify({
        'success': True,
        'message': '借用成功',
        'record_id': record_id
    })


@app.route('/api/return', methods=['POST'])
@login_required
def api_return():
    """归还设备API"""
    data = request.get_json()
    device_id = data.get('device_id')
    device_type = data.get('device_type', session.get('device_type', 'car_machine'))

    current_user = get_current_user()

    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})

    # 重新加载数据
    api_client.reload_data()

    # 查找借用记录 - 使用正确的方法
    all_records = api_client.get_records()
    borrow_record = None
    for record in all_records:
        if (record.device_id == device_id and
            record.borrower == current_user['borrower_name'] and
            hasattr(record, 'operation_type') and
            '借出' in str(record.operation_type)):
            borrow_record = record
            break

    if not borrow_record:
        return jsonify({'success': False, 'message': '没有找到借用记录'})

    # 创建设备类型对象
    device_type_value = device_type
    if device_type == 'car_machine' or device_type == 'car':
        device_type_value = '车机'
    elif device_type == 'phone':
        device_type_value = '手机'
    elif device_type == 'instrument':
        device_type_value = '仪表'

    # 获取设备信息
    device = api_client.get_device_by_id(device_id)
    if device:
        # 更新设备状态
        api_client._db.update_device_status(device_id, device_type_value, DeviceStatus.IN_STOCK)

    return jsonify({
        'success': True,
        'message': '归还成功'
    })


@app.route('/api/devices', methods=['GET'])
@login_required
def api_devices():
    """获取设备列表API"""
    device_type = request.args.get('device_type', session.get('device_type', 'car_machine'))

    # 重新加载数据
    api_client.reload_data()

    # 获取设备数据
    device_type_cn = get_device_type_mapping(device_type)
    devices = api_client.get_all_devices(device_type_cn)

    # 转换为字典列表
    device_list_data = [device_to_dict(d) for d in devices]

    return jsonify({'success': True, 'devices': device_list_data})


@app.route('/api/user/info', methods=['GET'])
@login_required
def api_user_info():
    """获取用户信息API"""
    current_user = get_current_user()
    return jsonify({'success': True, 'user': current_user})


@app.route('/my-records')
@login_required
def my_records():
    """我的记录页面"""
    current_user = get_current_user()

    # 重新加载数据
    api_client.reload_data()

    # 获取所有记录并筛选当前用户的
    all_records = api_client.get_records()
    user_records = []
    for record in all_records:
        if current_user['borrower_name'] in record.borrower or record.borrower == current_user['borrower_name']:
            user_records.append(record)

    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(user_records)
    total_pages = (total + per_page - 1) // per_page

    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = user_records[start:end]

    return render_template('my_records.html',
                         records=paginated_records,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         current_user=current_user)


@app.route('/api/user/records', methods=['GET'])
@login_required
def api_user_records():
    """获取用户借用记录API"""
    current_user = get_current_user()

    # 重新加载数据
    api_client.reload_data()

    # 获取所有记录并筛选当前用户的
    all_records = api_client.get_records()
    user_records = []
    for record in all_records:
        if current_user['borrower_name'] in record.borrower or record.borrower == current_user['borrower_name']:
            user_records.append(record)

    record_list = []
    for record in user_records:
        record_data = {
            'id': record.id,
            'device_id': record.device_id,
            'device_name': record.device_name if hasattr(record, 'device_name') else '',
            'borrow_time': record.operation_time.isoformat() if hasattr(record, 'operation_time') and record.operation_time else None,
            'return_time': None,
            'status': str(record.operation_type) if hasattr(record, 'operation_type') else 'unknown',
            'remark': record.remark if hasattr(record, 'remark') else ''
        }
        record_list.append(record_data)

    return jsonify({'success': True, 'records': record_list})


if __name__ == '__main__':
    print(f"手机端服务启动在端口 {MOBILE_SERVICE_PORT}")
    app.run(debug=False, host='0.0.0.0', port=MOBILE_SERVICE_PORT)
