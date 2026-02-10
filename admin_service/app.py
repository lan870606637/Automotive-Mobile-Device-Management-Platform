# -*- coding: utf-8 -*-
"""
车机与手机设备管理系统 - 管理服务
使用 Flask 实现
端口: 5001
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uuid
import io
import base64
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from dotenv import load_dotenv

# 从 common 导入
from common.models import DeviceStatus, DeviceType, OperationType, EntrySource, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, Admin
from common.api_client import api_client
from common.utils import mask_phone, is_mobile_device
from common.config import SECRET_KEY, SERVER_URL, ADMIN_SERVICE_PORT

load_dotenv()

app = Flask(__name__)
app.secret_key = SECRET_KEY


def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_select'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_admin():
    """获取当前登录管理员信息"""
    return {
        'admin_id': session.get('admin_id', ''),
        'admin_name': session.get('admin_name', '管理员'),
    }


def get_overdue_count():
    """获取逾期设备数量"""
    try:
        all_devices = api_client.get_all_devices()
        overdue_count = 0
        for device in all_devices:
            if device.status == DeviceStatus.BORROWED and device.expected_return_date:
                try:
                    expect_time = device.expected_return_date
                    if isinstance(expect_time, datetime):
                        now = datetime.now()
                        time_diff = now - expect_time
                        if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                            overdue_count += 1
                except Exception:
                    pass
        return overdue_count
    except Exception:
        return 0


# ==================== 后台管理入口 ====================

@app.route('/')
def index():
    """后台管理首页 - 重定向到入口选择"""
    return redirect(url_for('admin_select'))


@app.route('/admin')
def admin_select():
    """后台管理入口选择页面"""
    return render_template('admin/select_admin_type.html')


# ==================== 手机端后台管理 ====================

@app.route('/admin/mobile/login', methods=['GET', 'POST'])
def admin_mobile_login():
    """手机端后台登录页面"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # 验证管理员身份
        admin = api_client.verify_admin_login(username, password)
        if admin:
            session['admin_id'] = admin.get('id', username)
            session['admin_name'] = admin.get('name', username)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    return render_template('admin/mobile/login.html')


def get_device_type_str(device):
    """获取设备类型字符串"""
    if isinstance(device, CarMachine):
        return "车机"
    elif isinstance(device, Instrument):
        return "仪表"
    elif isinstance(device, Phone):
        return "手机"
    elif isinstance(device, SimCard):
        return "手机卡"
    elif isinstance(device, OtherDevice):
        return "其它设备"
    return "未知"


@app.route('/admin/mobile/dashboard')
@admin_required
def admin_mobile_dashboard():
    """手机端后台仪表盘"""
    # 获取统计数据
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.CIRCULATING, DeviceStatus.NO_CABINET]])
    borrowed_devices = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])
    
    # 计算逾期设备
    overdue_devices = 0
    overdue_devices_list = []
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                # expected_return_date 已经是 datetime 对象
                if isinstance(expect_time, datetime):
                    # 超过1小时算逾期
                    now = datetime.now()
                    time_diff = now - expect_time
                    if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                        overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                        overdue_hours = int(time_diff.total_seconds() // 3600)
                        overdue_devices += 1
                        overdue_devices_list.append({
                            'device_name': device.name,
                            'device_type': device.device_type.value if hasattr(device.device_type, 'value') else device.device_type,
                            'borrower': device.borrower or '未知',
                            'overdue_days': overdue_days,
                            'overdue_hours': overdue_hours
                        })
            except Exception as e:
                print(f"计算逾期设备出错: {e}")
                pass

    # 设备类型分布
    phone_count = len([d for d in all_devices if d.device_type.value == '手机'])
    car_device_count = len([d for d in all_devices if d.device_type.value == '车机'])
    instrument_count = len([d for d in all_devices if d.device_type.value == '仪表'])
    simcard_count = len([d for d in all_devices if d.device_type.value == '手机卡'])
    other_device_count = len([d for d in all_devices if d.device_type.value == '其它设备'])
    
    # 状态分布百分比
    if total_devices > 0:
        available_percent = round(available_devices / total_devices * 100)
        borrowed_percent = round(borrowed_devices / total_devices * 100)
        other_percent = 100 - available_percent - borrowed_percent
    else:
        available_percent = 0
        borrowed_percent = 0
        other_percent = 0
    
    # 获取最近记录
    all_records = api_client.get_records()
    recent_records = []
    for record in all_records[:10]:
        recent_records.append({
            'action_type': record.operation_type.value,
            'device_name': record.device_name,
            'user_name': record.borrower,
            'time': record.operation_time.strftime('%m-%d %H:%M')
        })
    
    return render_template('admin/mobile/dashboard.html',
                         admin_name=session.get('admin_name', '管理员'),
                         total_devices=total_devices,
                         available_devices=available_devices,
                         borrowed_devices=borrowed_devices,
                         overdue_devices=overdue_devices,
                         recent_records=recent_records)


@app.route('/admin/mobile/devices')
@admin_required
def admin_mobile_devices():
    """手机端设备查询页面"""
    return render_template('admin/mobile/devices.html',
                         admin_name=session.get('admin_name', '管理员'))


@app.route('/admin/mobile/device/add')
@admin_required
def admin_mobile_device_add():
    """手机端设备录入页面"""
    return render_template('admin/mobile/device_add.html',
                         admin_name=session.get('admin_name', '管理员'))


@app.route('/admin/mobile/settings')
@admin_required
def admin_mobile_settings():
    """手机端设置页面"""
    return render_template('admin/mobile/settings.html',
                         admin_name=session.get('admin_name', '管理员'))


# ==================== PC端后台管理 ====================

@app.route('/admin/pc/login', methods=['GET', 'POST'])
def admin_pc_login():
    """PC端后台登录页面"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # 验证管理员身份
        admin = api_client.verify_admin_login(username, password)
        if admin:
            session['admin_id'] = admin.get('id', username)
            session['admin_name'] = admin.get('name', username)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    return render_template('admin/pc/login.html')


@app.route('/admin/pc/dashboard')
@admin_required
def admin_pc_dashboard():
    """PC端后台仪表盘"""
    # 获取统计数据
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.CIRCULATING, DeviceStatus.NO_CABINET]])
    borrowed_devices = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])
    damaged_devices = len([d for d in all_devices if d.status == DeviceStatus.DAMAGED])
    lost_devices = len([d for d in all_devices if d.status == DeviceStatus.LOST])
    
    # 计算逾期设备
    overdue_devices = 0
    overdue_devices_list = []
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                # expected_return_date 已经是 datetime 对象
                if isinstance(expect_time, datetime):
                    # 超过1小时算逾期
                    now = datetime.now()
                    time_diff = now - expect_time
                    if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                        overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                        overdue_hours = int(time_diff.total_seconds() // 3600)
                        overdue_devices += 1
                        overdue_devices_list.append({
                            'device_name': device.name,
                            'device_type': device.device_type.value if hasattr(device.device_type, 'value') else device.device_type,
                            'borrower': device.borrower or '未知',
                            'overdue_days': overdue_days,
                            'overdue_hours': overdue_hours
                        })
            except Exception as e:
                print(f"计算逾期设备出错: {e}")
                pass

    # 设备类型分布
    phone_count = len([d for d in all_devices if d.device_type.value == '手机'])
    car_device_count = len([d for d in all_devices if d.device_type.value == '车机'])
    instrument_count = len([d for d in all_devices if d.device_type.value == '仪表'])
    simcard_count = len([d for d in all_devices if d.device_type.value == '手机卡'])
    other_device_count = len([d for d in all_devices if d.device_type.value == '其它设备'])
    
    # 状态分布百分比
    if total_devices > 0:
        available_percent = round(available_devices / total_devices * 100)
        borrowed_percent = round(borrowed_devices / total_devices * 100)
        other_percent = 100 - available_percent - borrowed_percent
    else:
        available_percent = 0
        borrowed_percent = 0
        other_percent = 0
    
    # 获取最近记录
    all_records = api_client.get_records()
    recent_records = []
    for record in all_records[:20]:
        recent_records.append({
            'action_type': record.operation_type.value,
            'device_name': record.device_name,
            'device_type': record.device_type,
            'user_name': record.borrower,
            'time': record.operation_time.strftime('%Y-%m-%d %H:%M')
        })
    
    return render_template('admin/pc/dashboard.html',
                         admin_name=session.get('admin_name', '管理员'),
                         total_devices=total_devices,
                         available_devices=available_devices,
                         borrowed_devices=borrowed_devices,
                         damaged_devices=damaged_devices,
                         lost_devices=lost_devices,
                         overdue_devices=overdue_devices,
                         phone_count=phone_count,
                         car_device_count=car_device_count,
                         instrument_count=instrument_count,
                         simcard_count=simcard_count,
                         other_device_count=other_device_count,
                         available_percent=available_percent,
                         borrowed_percent=borrowed_percent,
                         other_percent=other_percent,
                         overdue_devices_list=overdue_devices_list,
                         recent_records=recent_records,
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/devices')
@admin_required
def admin_pc_devices():
    """PC端设备管理页面"""
    device_type = request.args.get('type', 'all')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    
    # 获取设备
    if device_type == 'car':
        devices = api_client.get_all_devices('车机')
        title = '车机设备管理'
    elif device_type == 'phone':
        devices = api_client.get_all_devices('手机')
        title = '手机设备管理'
    elif device_type == 'instrument':
        devices = api_client.get_all_devices('仪表')
        title = '仪表设备管理'
    elif device_type == 'simcard':
        devices = api_client.get_all_devices('手机卡')
        title = '手机卡设备管理'
    elif device_type == 'other':
        devices = api_client.get_all_devices('其它设备')
        title = '其它设备管理'
    else:
        devices = api_client.get_all_devices()
        title = '全部设备管理'
    
    # 状态过滤
    if status == 'available':
        devices = [d for d in devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]]
    elif status == 'borrowed':
        devices = [d for d in devices if d.status == DeviceStatus.BORROWED]
    elif status == 'damaged':
        devices = [d for d in devices if d.status == DeviceStatus.DAMAGED]
    elif status == 'lost':
        devices = [d for d in devices if d.status == DeviceStatus.LOST]
    
    # 搜索过滤
    if search:
        devices = [d for d in devices if search.lower() in d.name.lower() 
                   or search.lower() in d.model.lower()
                   or search.lower() in d.borrower.lower()]
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(devices)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_devices = devices[start:end]
    
    # 获取各类型设备数量统计
    all_devices_for_stats = api_client.get_all_devices()
    phone_count = len([d for d in all_devices_for_stats if d.device_type.value == '手机'])
    car_count = len([d for d in all_devices_for_stats if d.device_type.value == '车机'])
    instrument_count = len([d for d in all_devices_for_stats if d.device_type.value == '仪表'])
    simcard_count = len([d for d in all_devices_for_stats if d.device_type.value == '手机卡'])
    other_count = len([d for d in all_devices_for_stats if d.device_type.value == '其它设备'])
    
    return render_template('admin/pc/devices.html',
                         devices=paginated_devices,
                         title=title,
                         device_type=device_type,
                         status=status,
                         search=search,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         phone_count=phone_count,
                         car_count=car_count,
                         instrument_count=instrument_count,
                         simcard_count=simcard_count,
                         other_count=other_count,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/device/add')
@app.route('/admin/pc/device/<device_id>')
@admin_required
def admin_pc_device_detail(device_id=None):
    """PC端设备添加/编辑页面"""
    device = None
    if device_id:
        device = api_client.get_device_by_id(device_id)
    
    # 获取所有用户（用于选择借用人）
    users = api_client.get_all_users()
    available_users = [u for u in users if u.borrower_name and not u.is_frozen]
    
    return render_template('admin/pc/device_detail.html',
                         device=device,
                         users=available_users,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/users')
@admin_required
def admin_pc_users():
    """PC端用户管理页面"""
    # 获取所有用户
    users = api_client.get_all_users()
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(users)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_users = users[start:end]
    
    return render_template('admin/pc/users.html',
                         users=paginated_users,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/records')
@admin_required
def admin_pc_records():
    """PC端记录查询页面"""
    # 获取所有记录
    all_records = api_client.get_records()
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(all_records)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = all_records[start:end]
    
    return render_template('admin/pc/records.html',
                         records=paginated_records,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/logs')
@admin_required
def admin_pc_logs():
    """PC端操作日志页面"""
    logs = api_client.get_admin_logs(limit=100)
    
    return render_template('admin/pc/logs.html',
                         logs=logs,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/overdue')
@admin_required
def admin_pc_overdue():
    """PC端逾期设备页面"""
    all_devices = api_client.get_all_devices()
    
    # 获取逾期设备
    overdue_devices = []
    phone_overdue = 0
    car_overdue = 0
    instrument_overdue = 0
    simcard_overdue = 0
    other_overdue = 0
    
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                # expected_return_date 已经是 datetime 对象
                if isinstance(expect_time, datetime):
                    # 超过1小时算逾期
                    now = datetime.now()
                    time_diff = now - expect_time
                    if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                        overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                        overdue_hours = int(time_diff.total_seconds() // 3600)
                        
                        # 获取设备类型
                        if isinstance(device, Phone):
                            device_type = '手机'
                            phone_overdue += 1
                        elif isinstance(device, CarMachine):
                            device_type = '车机'
                            car_overdue += 1
                        elif isinstance(device, Instrument):
                            device_type = '仪表'
                            instrument_overdue += 1
                        elif isinstance(device, SimCard):
                            device_type = '手机卡'
                            simcard_overdue += 1
                        elif isinstance(device, OtherDevice):
                            device_type = '其它设备'
                            other_overdue += 1
                        else:
                            device_type = '未知'
                        
                        overdue_devices.append({
                            'id': device.id,
                            'device_name': device.name,
                            'device_type': device_type,
                            'borrower': device.borrower,
                            'borrow_time': device.borrow_time.strftime('%Y-%m-%d') if device.borrow_time else '',
                            'expect_return_time': expect_time.strftime('%Y-%m-%d'),
                            'overdue_days': overdue_days,
                            'overdue_hours': overdue_hours,
                            'phone': device.phone
                        })
            except Exception as e:
                print(f"处理逾期设备出错: {e}")
                pass

    # 按逾期天数排序
    overdue_devices.sort(key=lambda x: x['overdue_days'], reverse=True)
    
    return render_template('admin/pc/overdue.html',
                         overdue_devices=overdue_devices,
                         overdue_count=len(overdue_devices),
                         phone_overdue=phone_overdue,
                         car_overdue=car_overdue,
                         instrument_overdue=instrument_overdue,
                         simcard_overdue=simcard_overdue,
                         other_overdue=other_overdue,
                         admin_name=session.get('admin_name', '管理员'))


@app.route('/api/devices/overdue', methods=['GET'])
@admin_required
def api_devices_overdue():
    """获取逾期设备列表API"""
    all_devices = api_client.get_all_devices()
    
    overdue_devices = []
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                if isinstance(expect_time, datetime):
                    now = datetime.now()
                    time_diff = now - expect_time
                    if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                        overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                        overdue_hours = int(time_diff.total_seconds() // 3600)
                        
                        # 获取设备类型
                        if isinstance(device, Phone):
                            device_type = '手机'
                        elif isinstance(device, CarMachine):
                            device_type = '车机'
                        elif isinstance(device, Instrument):
                            device_type = '仪表'
                        elif isinstance(device, SimCard):
                            device_type = '手机卡'
                        elif isinstance(device, OtherDevice):
                            device_type = '其它设备'
                        else:
                            device_type = '未知'
                        
                        overdue_devices.append({
                            'id': device.id,
                            'device_name': device.name,
                            'device_type': device_type,
                            'borrower': device.borrower,
                            'borrow_time': device.borrow_time.strftime('%Y-%m-%d') if device.borrow_time else '',
                            'expect_return_time': expect_time.strftime('%Y-%m-%d'),
                            'overdue_days': overdue_days,
                            'overdue_hours': overdue_hours,
                            'phone': device.phone
                        })
            except Exception as e:
                print(f"处理逾期设备出错: {e}")
                pass
    
    # 按逾期天数排序
    overdue_devices.sort(key=lambda x: x['overdue_days'], reverse=True)
    
    return jsonify({'devices': overdue_devices, 'count': len(overdue_devices)})


@app.route('/api/devices/<device_id>/remind', methods=['POST'])
@admin_required
def api_device_remind(device_id):
    """提醒用户归还设备API"""
    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 这里可以实现发送提醒的逻辑（如短信、邮件等）
    # 目前仅记录操作日志
    api_client.add_operation_log(f"发送归还提醒给: {device.borrower}", device.name)
    
    return jsonify({'success': True, 'message': '提醒已发送'})


@app.route('/api/overdue/remind_all', methods=['POST'])
@admin_required
def api_overdue_remind_all():
    """批量提醒所有逾期用户API"""
    all_devices = api_client.get_all_devices()
    
    remind_count = 0
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                if isinstance(expect_time, datetime):
                    now = datetime.now()
                    time_diff = now - expect_time
                    if time_diff.total_seconds() > 3600:
                        remind_count += 1
                        api_client.add_operation_log(f"批量提醒: {device.borrower}", device.name)
            except Exception:
                pass
    
    return jsonify({'success': True, 'count': remind_count, 'message': f'已发送 {remind_count} 条提醒'})


@app.route('/api/overdue/export', methods=['GET'])
@admin_required
def api_overdue_export():
    """导出逾期设备列表API"""
    all_devices = api_client.get_all_devices()
    
    overdue_devices = []
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                if isinstance(expect_time, datetime):
                    now = datetime.now()
                    time_diff = now - expect_time
                    if time_diff.total_seconds() > 3600:
                        overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                        overdue_hours = int(time_diff.total_seconds() // 3600)
                        
                        # 获取设备类型
                        if isinstance(device, Phone):
                            device_type = '手机'
                        elif isinstance(device, CarMachine):
                            device_type = '车机'
                        elif isinstance(device, Instrument):
                            device_type = '仪表'
                        elif isinstance(device, SimCard):
                            device_type = '手机卡'
                        elif isinstance(device, OtherDevice):
                            device_type = '其它设备'
                        else:
                            device_type = '未知'
                        
                        overdue_devices.append({
                            '设备名称': device.name,
                            '设备类型': device_type,
                            '借用人': device.borrower,
                            '借出时间': device.borrow_time.strftime('%Y-%m-%d') if device.borrow_time else '',
                            '预计归还': expect_time.strftime('%Y-%m-%d'),
                            '逾期天数': overdue_days if overdue_hours >= 24 else f'{overdue_hours}小时',
                            '联系方式': device.phone or '-'
                        })
            except Exception:
                pass
    
    # 按逾期天数排序
    overdue_devices.sort(key=lambda x: x['逾期天数'] if isinstance(x['逾期天数'], int) else 0, reverse=True)
    
    # 创建 CSV 内容
    import csv
    import io
    output = io.StringIO()
    if overdue_devices:
        writer = csv.DictWriter(output, fieldnames=overdue_devices[0].keys())
        writer.writeheader()
        writer.writerows(overdue_devices)
    
    # 创建响应
    from flask import Response
    response = Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=逾期设备_{datetime.now().strftime("%Y%m%d")}.csv'}
    )
    return response


@app.route('/admin/logout')
def admin_logout():
    """管理员退出登录"""
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    return redirect(url_for('admin_select'))


# ==================== API 接口 ====================

@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    """管理员登录API"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    admin = api_client.verify_admin_login(username, password)
    if admin:
        session['admin_id'] = admin.get('id', username)
        session['admin_name'] = admin.get('name', username)
        return jsonify({'success': True, 'admin': admin})
    else:
        return jsonify({'success': False, 'message': '用户名或密码错误'})


@app.route('/api/admin/users', methods=['GET', 'POST'])
@admin_required
def api_admin_users():
    """用户列表 / 新增用户API (后台管理)"""
    if request.method == 'GET':
        users = api_client.get_all_users()
        users_data = []
        for user in users:
            if not user.is_deleted:
                users_data.append({
                    'id': user.id,
                    'name': user.borrower_name,
                    'weixin_name': user.wechat_name,
                    'phone': user.phone,
                    'borrow_count': user.borrow_count,
                    'is_admin': user.is_admin,
                    'is_frozen': user.is_frozen,
                    'register_time': user.create_time.strftime('%Y-%m-%d') if hasattr(user, 'create_time') and user.create_time else '-'
                })
        return jsonify(users_data)
    
    else:  # POST
        data = request.get_json()
        try:
            user = api_client.create_user(
                borrower_name=data.get('name'),
                wechat_name=data.get('weixin_name', ''),
                phone=data.get('phone', ''),
                password=data.get('password'),
                is_admin=data.get('is_admin', False)
            )
            return jsonify({'success': True, 'user_id': user.id})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/admin/users/<user_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_user_detail(user_id):
    """更新用户 / 删除用户API"""
    if request.method == 'PUT':
        data = request.get_json()
        try:
            api_client.update_user(user_id, data)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    else:  # DELETE
        try:
            api_client.delete_user(user_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/users/<user_id>/freeze', methods=['POST'])
@admin_required
def api_user_freeze(user_id):
    """冻结用户API"""
    try:
        api_client.freeze_user(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/users/<user_id>/unfreeze', methods=['POST'])
@admin_required
def api_user_unfreeze(user_id):
    """解冻用户API"""
    try:
        api_client.unfreeze_user(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/users/<user_id>/set_admin', methods=['POST'])
@admin_required
def api_user_set_admin(user_id):
    """设置用户为管理员API"""
    try:
        api_client.set_user_admin(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/users/<user_id>/remove_admin', methods=['POST'])
@admin_required
def api_user_remove_admin(user_id):
    """取消用户管理员权限API"""
    try:
        api_client.cancel_user_admin(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices', methods=['GET', 'POST'])
@admin_required
def api_devices():
    """获取/创建设备API"""
    if request.method == 'GET':
        device_type = request.args.get('type')
        devices = api_client.get_all_devices(device_type)
        
        devices_data = []
        for device in devices:
            # 获取设备类型字符串
            if isinstance(device, Phone):
                device_type_str = '手机'
            elif isinstance(device, CarMachine):
                device_type_str = '车机'
            elif isinstance(device, Instrument):
                device_type_str = '仪表'
            elif isinstance(device, SimCard):
                device_type_str = '手机卡'
            elif isinstance(device, OtherDevice):
                device_type_str = '其它设备'
            else:
                device_type_str = '未知'
            
            devices_data.append({
                'id': device.id,
                'device_name': device.name,
                'device_type': device_type_str,
                'model': device.model,
                'cabinet': device.cabinet_number,
                'status': device.status.value,
                'borrower': device.borrower,
                'phone': device.phone,
                'borrow_time': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                'expected_return': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else '',
                'remarks': device.remark
            })
        
        return jsonify(devices_data)
    
    else:  # POST
        data = request.get_json()
        try:
            device_type = data.get('device_type')
            device_name = data.get('device_name')
            model = data.get('model', '')
            cabinet = data.get('cabinet', '')
            status = data.get('status', '在库')
            remarks = data.get('remarks', '')
            
            device = api_client.create_device(
                device_type=DeviceType.PHONE if device_type == '手机' else DeviceType.CAR_MACHINE,
                device_name=device_name,
                model=model,
                cabinet=cabinet,
                status=status,
                remarks=remarks
            )
            return jsonify({'success': True, 'device_id': device.id})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def api_device_detail(device_id):
    """获取/更新/删除设备API"""
    if request.method == 'GET':
        device = api_client.get_device(device_id)
        if not device:
            return jsonify({'success': False, 'message': '设备不存在'})
        
        return jsonify({
            'id': device.id,
            'name': device.name,
            'device_type': '手机' if isinstance(device, Phone) else '车机',
            'model': device.model,
            'cabinet': device.cabinet_number,
            'status': device.status.value,
            'borrower': device.borrower,
            'phone': device.phone,
            'remarks': device.remark
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        try:
            operator = session.get('admin_name', '管理员')
            api_client.update_device_by_id(device_id, data, operator)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    else:  # DELETE
        try:
            api_client.delete_device(device_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>/borrow', methods=['POST'])
@admin_required
def api_admin_borrow(device_id):
    """管理员录入借出API"""
    data = request.get_json()
    borrower = data.get('borrower')
    days = data.get('days', 1)
    cabinet = data.get('cabinet', '流通')
    remarks = data.get('remarks', '')

    if not borrower:
        return jsonify({'success': False, 'message': '请选择借用人'})

    try:
        success = api_client.borrow_device(
            device_id=device_id,
            borrower=borrower,
            days=int(days),
            cabinet=cabinet,
            remarks=remarks,
            operator=session.get('admin_name', '管理员')
        )
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)})

    if success:
        return jsonify({'success': True, 'message': '录入成功'})
    else:
        return jsonify({'success': False, 'message': '录入失败'})


@app.route('/api/devices/<device_id>/return', methods=['POST'])
@admin_required
def api_admin_return(device_id):
    """管理员强制归还API"""
    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 清空借用信息
    device.status = DeviceStatus.IN_STOCK
    original_borrower = device.borrower
    device.borrower = ''
    device.phone = ''
    device.borrow_time = None
    device.location = ''
    device.reason = ''
    device.entry_source = ''
    device.expected_return_date = None
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.FORCE_RETURN,
        operator=session.get('admin_name', '管理员'),
        operation_time=datetime.now(),
        borrower=original_borrower,
        reason='管理员强制归还'
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"强制归还: {original_borrower}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '归还成功'})


@app.route('/api/devices/<device_id>/transfer', methods=['POST'])
@admin_required
def api_admin_transfer(device_id):
    """管理员转借API"""
    data = request.get_json()
    new_borrower = data.get('borrower')
    
    if not new_borrower:
        return jsonify({'success': False, 'message': '请选择新借用人'})
    
    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备未借出，无法转借'})
    
    original_borrower = device.borrower
    
    # 获取新借用人的手机号
    new_phone = ''
    for user in api_client._users:
        if user.borrower_name == new_borrower:
            new_phone = user.phone
            break
    
    # 更新设备
    device.borrower = new_borrower
    device.phone = new_phone
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.TRANSFER,
        operator=session.get('admin_name', '管理员'),
        operation_time=datetime.now(),
        borrower=f"{original_borrower} → {new_borrower}",
        reason='管理员转借'
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"转借: {original_borrower} -> {new_borrower}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '转借成功'})


@app.route('/api/devices/<device_id>/force-borrow', methods=['POST'])
@admin_required
def api_force_borrow(device_id):
    """管理员强制借出（录入登记）API"""
    data = request.get_json()
    borrower = data.get('borrower')
    phone = data.get('phone', '')
    location = data.get('location', '')
    reason = data.get('reason', '')
    days = data.get('days', 1)
    remark = data.get('remark', '')
    
    if not borrower:
        return jsonify({'success': False, 'message': '请输入借用人'})
    
    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.IN_STOCK:
        return jsonify({'success': False, 'message': '设备不可用'})
    
    # 设置当前管理员
    api_client.set_current_admin(session.get('admin_name', '管理员'))
    
    expected_return_date = datetime.now() + timedelta(days=int(days))
    
    success = api_client.force_borrow(
        device_id=device_id,
        borrower=borrower,
        phone=phone,
        location=location,
        reason=reason,
        expected_return_date=expected_return_date,
        remark=remark
    )
    
    if success:
        return jsonify({'success': True, 'message': '录入登记成功'})
    else:
        return jsonify({'success': False, 'message': '录入登记失败'})


@app.route('/api/users', methods=['GET', 'POST'])
@admin_required
def api_users():
    """获取/创建用户API"""
    if request.method == 'GET':
        users = api_client.get_users()
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'name': user.borrower_name,
                'weixin_name': user.wechat_name,
                'phone': user.phone,
                'borrow_count': user.borrow_count,
                'is_admin': user.is_admin,
                'is_frozen': user.is_frozen,
                'register_time': user.create_time.strftime('%Y-%m-%d') if hasattr(user, 'create_time') and user.create_time else '-'
            })
        return jsonify(users_data)
    
    else:  # POST
        data = request.get_json()
        try:
            user = api_client.create_user(
                borrower_name=data.get('name'),
                wechat_name=data.get('weixin_name', ''),
                phone=data.get('phone', ''),
                password=data.get('password'),
                is_admin=data.get('is_admin', False)
            )
            return jsonify({'success': True, 'user_id': user.id})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/records', methods=['GET'])
@admin_required
def api_records():
    """记录查询API"""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    records = api_client.get_records()
    
    records_data = []
    for record in records:
        records_data.append({
            'action_type': record.operation_type.value,
            'device_name': record.device_name,
            'device_type': '手机' if record.device_type == DeviceType.PHONE else '车机',
            'user_name': record.borrower,
            'time': record.operation_time.strftime('%Y-%m-%d %H:%M'),
            'remarks': record.remark
        })
    
    # 分页
    total = len(records_data)
    total_pages = (total + limit - 1) // limit
    start = (page - 1) * limit
    end = start + limit
    paginated = records_data[start:end]
    
    return jsonify({
        'records': paginated,
        'page': page,
        'total_pages': total_pages,
        'total': total
    })


@app.route('/api/records/export', methods=['POST'])
@admin_required
def api_records_export():
    """导出记录API"""
    # 这里应该返回Excel文件
    # 简化处理，返回JSON
    return jsonify({'success': True, 'message': '导出功能待实现'})


@app.route('/api/logs', methods=['GET'])
@admin_required
def api_logs():
    """操作日志API"""
    limit = request.args.get('limit', 100, type=int)
    logs = api_client.get_admin_logs(limit=limit)
    return jsonify(logs)


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message='页面未找到'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message='服务器内部错误'), 500


if __name__ == '__main__':
    print(f"管理服务启动在端口 {ADMIN_SERVICE_PORT}")
    app.run(debug=True, host='0.0.0.0', port=ADMIN_SERVICE_PORT)
