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

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response, send_file
from dotenv import load_dotenv

# 从 common 导入
from common.models import DeviceStatus, DeviceType, OperationType, EntrySource, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, Admin, Announcement, BountyStatus, PointsTransactionType
from common.api_client import api_client
from common.db_store import DatabaseStore, init_database
from common.utils import mask_phone, is_mobile_device
from common.config import SECRET_KEY, SERVER_URL, ADMIN_SERVICE_PORT
from common.points_service import points_service
from admin_service.admin_log import (
    log_admin_operation, log_admin_operation_manual,
    AdminActionType, TargetType, ACTION_TYPE_NAMES
)

load_dotenv()

app = Flask(__name__)
app.secret_key = SECRET_KEY

# 初始化数据库（创建必要的表）
init_database()

# 辅助函数：处理Excel中的nan值
def safe_str_from_excel(value):
    """从Excel读取的值转换为字符串，处理nan值"""
    import math
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    return str(value).strip()

# 测试后台管理操作日志表是否存在
try:
    test_logs = api_client.get_admin_operation_logs(limit=1)
    print(f"✓ 后台管理操作日志系统初始化成功，当前日志数量: {len(test_logs)}")
except Exception as e:
    print(f"⚠ 后台管理操作日志系统检查失败: {e}")


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
    """获取逾期设备数量（使用SQL优化查询）"""
    try:
        return api_client._db.get_overdue_count()
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
    # 方式1：通过实例类型判断
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

    # 方式2：通过 device_type 属性判断（当实例类型不匹配时）
    if hasattr(device, 'device_type') and device.device_type:
        if isinstance(device.device_type, DeviceType):
            return device.device_type.value
        return str(device.device_type)

    return "未知"


def get_device_type_value(device):
    """安全获取设备类型的值（字符串）"""
    if hasattr(device, 'device_type') and device.device_type:
        if isinstance(device.device_type, DeviceType):
            return device.device_type.value
        return str(device.device_type)
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
    
    # 使用SQL优化查询获取逾期设备（替代循环遍历）
    try:
        overdue_devices_list = api_client._db.get_overdue_devices(limit=10)
        overdue_devices = len(overdue_devices_list)
    except Exception as e:
        print(f"获取逾期设备出错: {e}")
        overdue_devices = 0
        overdue_devices_list = []

    # 设备类型分布
    phone_count = len([d for d in all_devices if get_device_type_value(d) == '手机'])
    car_device_count = len([d for d in all_devices if get_device_type_value(d) == '车机'])
    instrument_count = len([d for d in all_devices if get_device_type_value(d) == '仪表'])
    simcard_count = len([d for d in all_devices if get_device_type_value(d) == '手机卡'])
    other_device_count = len([d for d in all_devices if get_device_type_value(d) == '其它设备'])

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
            admin_id = admin.get('id', username)
            admin_name = admin.get('name', username)
            session['admin_id'] = admin_id
            session['admin_name'] = admin_name

            # 记录登录日志
            log_admin_operation_manual(
                action_type=AdminActionType.LOGIN,
                target_type=TargetType.SYSTEM,
                description=f"管理员 {admin_name} 登录PC端后台",
                result='SUCCESS'
            )

            return jsonify({'success': True})
        else:
            # 记录登录失败日志
            log_admin_operation_manual(
                action_type=AdminActionType.LOGIN,
                target_type=TargetType.SYSTEM,
                description=f"用户 {username} 尝试登录PC端后台失败",
                result='FAILED',
                error_message='用户名或密码错误'
            )
            return jsonify({'success': False, 'message': '用户名或密码错误'})

    return render_template('admin/pc/login.html')


@app.route('/admin/pc/dashboard')
@admin_required
def admin_pc_dashboard():
    """PC端后台仪表盘 - 使用SQL聚合查询优化"""
    # 使用优化的统计查询方法
    stats = api_client._db.get_device_statistics()
    
    # 获取逾期设备列表（使用SQL优化查询）
    overdue_devices_list = api_client._db.get_overdue_devices(limit=100)
    overdue_devices = len(overdue_devices_list)
    
    # 从统计结果中提取设备类型数量
    type_stats = stats['by_type']
    phone_count = type_stats.get('手机', 0)
    car_device_count = type_stats.get('车机', 0)
    instrument_count = type_stats.get('仪表', 0)
    simcard_count = type_stats.get('手机卡', 0)
    other_device_count = type_stats.get('其它设备', 0)
    
    # 状态分布百分比
    total_devices = stats['total']
    available_devices = stats['available']
    borrowed_devices = stats['borrowed']
    
    if total_devices > 0:
        available_percent = round(available_devices / total_devices * 100)
        borrowed_percent = round(borrowed_devices / total_devices * 100)
        other_percent = 100 - available_percent - borrowed_percent
    else:
        available_percent = 0
        borrowed_percent = 0
        other_percent = 0
    
    # 获取最近记录（使用优化查询）
    recent_records = api_client._db.get_recent_records(limit=20)
    
    # 获取今日借出和归还数量（使用SQL优化查询）
    today_counts = api_client._db.get_today_borrow_return_count()
    
    return render_template('admin/pc/dashboard.html',
                         admin_name=session.get('admin_name', '管理员'),
                         total_devices=total_devices,
                         available_devices=available_devices,
                         borrowed_devices=borrowed_devices,
                         damaged_devices=stats['damaged'],
                         lost_devices=stats['lost'],
                         overdue_devices=overdue_devices,
                         phone_count=phone_count,
                         car_device_count=car_device_count,
                         instrument_count=instrument_count,
                         simcard_count=simcard_count,
                         other_device_count=other_device_count,
                         in_stock_count=stats['in_stock'],
                         in_custody_count=stats['in_custody'],
                         no_cabinet_count=stats['no_cabinet'],
                         circulating_count=stats['circulating'],
                         scrapped_count=stats['scrapped'],
                         shipped_count=stats['shipped'],
                         sealed_count=stats['sealed'],
                         available_percent=available_percent,
                         borrowed_percent=borrowed_percent,
                         other_percent=other_percent,
                         overdue_devices_list=overdue_devices_list,
                         recent_records=recent_records,
                         overdue_count=get_overdue_count(),
                         today_borrow_count=today_counts['borrow'],
                         today_return_count=today_counts['return'])


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
    phone_count = len([d for d in all_devices_for_stats if get_device_type_value(d) == '手机'])
    car_count = len([d for d in all_devices_for_stats if get_device_type_value(d) == '车机'])
    instrument_count = len([d for d in all_devices_for_stats if get_device_type_value(d) == '仪表'])
    simcard_count = len([d for d in all_devices_for_stats if get_device_type_value(d) == '手机卡'])
    other_count = len([d for d in all_devices_for_stats if get_device_type_value(d) == '其它设备'])

    # 获取所有可用用户（用于借出和转借）
    all_users = api_client.get_all_users()
    users = [u for u in all_users if u.borrower_name and not u.is_frozen]

    return render_template('admin/pc/devices.html',
                         devices=paginated_devices,
                         users=users,
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
    """PC端用户管理页面 - 纯前端加载，后端只提供空模板"""
    return render_template('admin/pc/users.html',
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/records')
@admin_required
def admin_pc_records():
    """PC端记录查询页面 - 使用数据库分页优化"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # 使用优化的分页查询
    from common.db_store import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 获取总数
        cursor.execute("SELECT COUNT(*) as total FROM records")
        total = cursor.fetchone()['total']

        # 获取分页数据
        offset = (page - 1) * per_page
        cursor.execute("""
            SELECT operation_type, device_name, device_type, borrower,
                   operator, operation_time, remark
            FROM records
            ORDER BY operation_time DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

        rows = cursor.fetchall()
        records = []
        for row in rows:
            records.append({
                'action_type': row['operation_type'],
                'device_name': row['device_name'],
                'device_type': row['device_type'],
                'user_name': row['borrower'],
                'operator': row['operator'],
                'time': row['operation_time'].strftime('%Y-%m-%d %H:%M') if row['operation_time'] else '',
                'remarks': row['remark']
            })

    total_pages = (total + per_page - 1) // per_page

    return render_template('admin/pc/records.html',
                         records=records,
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
    """PC端逾期设备页面 - 使用SQL优化查询"""
    # 使用优化的SQL查询获取逾期设备
    overdue_devices = api_client._db.get_overdue_devices()
    
    # 统计各类型逾期设备数量
    phone_overdue = sum(1 for d in overdue_devices if d['device_type'] == '手机')
    car_overdue = sum(1 for d in overdue_devices if d['device_type'] == '车机')
    instrument_overdue = sum(1 for d in overdue_devices if d['device_type'] == '仪表')
    simcard_overdue = sum(1 for d in overdue_devices if d['device_type'] == '手机卡')
    other_overdue = sum(1 for d in overdue_devices if d['device_type'] == '其它设备')
    
    return render_template('admin/pc/overdue.html',
                         overdue_devices=overdue_devices,
                         overdue_count=len(overdue_devices),
                         phone_overdue=phone_overdue,
                         car_overdue=car_overdue,
                         instrument_overdue=instrument_overdue,
                         simcard_overdue=simcard_overdue,
                         other_overdue=other_overdue,
                         admin_name=session.get('admin_name', '管理员'))


@app.route('/admin/pc/announcements')
@admin_required
def admin_pc_announcements():
    """PC端公告管理页面"""
    # 获取所有公告
    announcements = api_client.get_announcements()
    
    # 分类统计
    normal_count = len([a for a in announcements if a.announcement_type == 'normal'])
    special_count = len([a for a in announcements if a.announcement_type == 'special'])
    active_count = len([a for a in announcements if a.is_active])
    
    return render_template('admin/pc/announcements.html',
                         announcements=announcements,
                         normal_count=normal_count,
                         special_count=special_count,
                         active_count=active_count,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/remarks')
@admin_required
def admin_pc_remarks():
    """PC端备注管理页面"""
    # 获取筛选参数
    search = request.args.get('search', '').strip()
    device_type_filter = request.args.get('device_type', '')
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 重新加载数据以获取最新备注（解决多服务数据同步问题）
    api_client.reload_data()
    
    # 获取所有备注
    all_remarks = api_client.get_remarks()
    
    # 获取设备信息用于显示设备名称
    all_devices = api_client.get_all_devices()
    device_map = {d.id: d for d in all_devices}
    
    # 处理备注数据
    processed_remarks = []
    for remark in all_remarks:
        device = device_map.get(remark.device_id)
        if device:
            processed_remarks.append({
                'id': remark.id,
                'device_id': remark.device_id,
                'device_name': device.name,
                'device_type': remark.device_type or device.device_type.value,
                'content': remark.content,
                'creator': remark.creator,
                'create_time': remark.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_inappropriate': remark.is_inappropriate
            })
        else:
            # 设备已删除或不存在，仍然显示备注
            processed_remarks.append({
                'id': remark.id,
                'device_id': remark.device_id,
                'device_name': '[已删除设备]',
                'device_type': remark.device_type or '未知',
                'content': remark.content,
                'creator': remark.creator,
                'create_time': remark.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_inappropriate': remark.is_inappropriate
            })
    
    # 搜索过滤
    if search:
        processed_remarks = [r for r in processed_remarks 
                            if search.lower() in r['device_name'].lower() 
                            or search.lower() in r['content'].lower()
                            or search.lower() in r['creator'].lower()]
    
    # 设备类型过滤
    if device_type_filter:
        processed_remarks = [r for r in processed_remarks if r['device_type'] == device_type_filter]
    
    # 状态过滤
    if status_filter == 'normal':
        processed_remarks = [r for r in processed_remarks if not r['is_inappropriate']]
    elif status_filter == 'inappropriate':
        processed_remarks = [r for r in processed_remarks if r['is_inappropriate']]
    
    # 统计
    total_count = len(processed_remarks)
    normal_count = len([r for r in processed_remarks if not r['is_inappropriate']])
    inappropriate_count = len([r for r in processed_remarks if r['is_inappropriate']])
    
    # 今日新增统计
    today = datetime.now().strftime('%Y-%m-%d')
    today_count = len([r for r in processed_remarks if r['create_time'].startswith(today)])
    
    # 分页
    total_pages = (total_count + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    paginated_remarks = processed_remarks[start:end]
    
    return render_template('admin/pc/remarks.html',
                         remarks=paginated_remarks,
                         total_count=total_count,
                         normal_count=normal_count,
                         inappropriate_count=inappropriate_count,
                         today_count=today_count,
                         page=page,
                         total_pages=total_pages,
                         search=search,
                         device_type_filter=device_type_filter,
                         status_filter=status_filter,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/api/devices/overdue', methods=['GET'])
@admin_required
def api_devices_overdue():
    """获取逾期设备列表API - 使用SQL优化查询"""
    # 使用优化的SQL查询获取逾期设备
    overdue_devices = api_client._db.get_overdue_devices()
    return jsonify({'devices': overdue_devices, 'count': len(overdue_devices)})


@app.route('/api/devices/<device_id>/remind', methods=['POST'])
@admin_required
def api_device_remind(device_id):
    """提醒用户归还设备API"""
    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 发送通知给借用人
    api_client.notify_overdue_reminder(
        device_id=device_id,
        device_name=device.name,
        borrower=device.borrower,
        operator=session.get('admin_name', '管理员')
    )
    
    # 通知保管人（如果存在且不是借用人）
    if device.cabinet_number and device.cabinet_number != device.borrower:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备逾期归还提醒",
                content=f"您保管的设备「{device.name}」已被借用人 {device.borrower} 逾期，请协助催促归还。",
                device_name=device.name,
                device_id=device.id,
                notification_type="warning"
            )
    
    api_client.add_operation_log(f"发送归还提醒给: {device.borrower}", device.name)

    # 记录逾期提醒日志
    log_admin_operation_manual(
        action_type=AdminActionType.OVERDUE_REMIND,
        target_type=TargetType.DEVICE,
        target_id=device_id,
        target_name=device.name,
        description=f"发送逾期归还提醒给: {device.borrower}",
        result='SUCCESS'
    )

    return jsonify({'success': True, 'message': '提醒已发送'})


@app.route('/api/overdue/remind_all', methods=['POST'])
@admin_required
def api_overdue_remind_all():
    """批量提醒所有逾期用户API - 使用SQL优化查询"""
    # 使用优化的SQL查询获取逾期设备
    overdue_devices = api_client._db.get_overdue_devices()
    
    remind_count = 0
    reminded_borrowers = set()  # 记录已提醒的借用人，避免重复提醒
    
    for device_data in overdue_devices:
        try:
            borrower = device_data['borrower']
            if borrower in reminded_borrowers:
                continue
                
            # 发送通知给借用人
            api_client.notify_overdue_reminder(
                device_id=device_data['id'],
                device_name=device_data['device_name'],
                borrower=borrower,
                operator=session.get('admin_name', '管理员')
            )
            
            remind_count += 1
            reminded_borrowers.add(borrower)
            api_client.add_operation_log(f"批量提醒: {borrower}", device_data['device_name'])
        except Exception:
            pass
    
    # 记录批量提醒日志
    if remind_count > 0:
        log_admin_operation_manual(
            action_type=AdminActionType.OVERDUE_REMIND,
            target_type=TargetType.SYSTEM,
            description=f"批量发送逾期提醒，共 {remind_count} 条",
            result='SUCCESS'
        )

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
                    # 只要过了预期归还时间就算逾期
                    if time_diff.total_seconds() > 0:
                        overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                        overdue_hours = int(time_diff.total_seconds() // 3600)

                        # 获取设备类型
                        device_type = get_device_type_str(device)

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


# ==================== 公告管理API ====================

@app.route('/api/announcements', methods=['GET'])
@admin_required
def api_get_announcements():
    """获取公告列表API"""
    announcement_type = request.args.get('type', None)
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    
    announcements = api_client.get_announcements(announcement_type, active_only)
    
    return jsonify({
        'success': True,
        'announcements': [a.to_dict() for a in announcements]
    })


@app.route('/api/announcements', methods=['POST'])
@admin_required
def api_create_announcement():
    """创建公告API"""
    data = request.get_json()
    
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    announcement_type = data.get('announcement_type', 'normal')
    sort_order = data.get('sort_order', 0)
    
    if not title or not content:
        return jsonify({'success': False, 'message': '标题和内容不能为空'})
    
    if announcement_type not in ['normal', 'special']:
        return jsonify({'success': False, 'message': '公告类型无效'})
    
    try:
        announcement = api_client.create_announcement(
            title=title,
            content=content,
            announcement_type=announcement_type,
            sort_order=int(sort_order),
            creator=session.get('admin_name', '管理员')
        )
        
        # 添加操作日志
        api_client.add_operation_log(
            f"创建{'特殊' if announcement_type == 'special' else '普通'}公告: {title}",
            "公告管理"
        )
        
        return jsonify({
            'success': True,
            'announcement': announcement.to_dict(),
            'message': '公告创建成功'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'})


@app.route('/api/announcements/<announcement_id>', methods=['GET'])
@admin_required
def api_get_announcement(announcement_id):
    """获取单个公告API"""
    announcement = api_client.get_announcement_by_id(announcement_id)
    if not announcement:
        return jsonify({'success': False, 'message': '公告不存在'})
    
    return jsonify({
        'success': True,
        'announcement': announcement.to_dict()
    })


@app.route('/api/announcements/<announcement_id>', methods=['PUT'])
@admin_required
def api_update_announcement(announcement_id):
    """更新公告API"""
    data = request.get_json()
    
    try:
        announcement = api_client.update_announcement(announcement_id, data)
        if not announcement:
            return jsonify({'success': False, 'message': '公告不存在'})
        
        # 添加操作日志
        api_client.add_operation_log(
            f"更新公告: {announcement.title}",
            "公告管理"
        )
        
        return jsonify({
            'success': True,
            'announcement': announcement.to_dict(),
            'message': '公告更新成功'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})


@app.route('/api/announcements/<announcement_id>/toggle', methods=['POST'])
@admin_required
def api_toggle_announcement(announcement_id):
    """切换公告上架/下架状态API"""
    announcement = api_client.toggle_announcement_status(announcement_id)
    if not announcement:
        return jsonify({'success': False, 'message': '公告不存在'})
    
    status = "上架" if announcement.is_active else "下架"
    api_client.add_operation_log(
        f"{status}公告: {announcement.title}",
        "公告管理"
    )
    
    return jsonify({
        'success': True,
        'is_active': announcement.is_active,
        'message': f'公告已{status}'
    })


@app.route('/api/announcements/<announcement_id>', methods=['DELETE'])
@admin_required
def api_delete_announcement(announcement_id):
    """删除公告API"""
    announcement = api_client.get_announcement_by_id(announcement_id)
    if not announcement:
        return jsonify({'success': False, 'message': '公告不存在'})
    
    title = announcement.title
    success = api_client.delete_announcement(announcement_id)
    if success:
        api_client.add_operation_log(
            f"删除公告: {title}",
            "公告管理"
        )
        return jsonify({'success': True, 'message': '公告已删除'})
    else:
        return jsonify({'success': False, 'message': '删除失败'})


@app.route('/api/announcements/<announcement_id>/force-show', methods=['POST'])
@admin_required
def api_force_show_announcement(announcement_id):
    """再次公告API - 增加版本号让用户重新看到弹窗"""
    announcement = api_client.force_show_announcement(announcement_id)
    if not announcement:
        return jsonify({'success': False, 'message': '公告不存在'})
    
    api_client.add_operation_log(
        f"再次公告: {announcement.title} (版本{announcement.force_show_version})",
        "公告管理"
    )
    
    return jsonify({
        'success': True,
        'message': '已触发再次公告，用户将重新看到此公告弹窗',
        'force_show_version': announcement.force_show_version
    })


@app.route('/api/announcements/<announcement_id>/move', methods=['POST'])
@admin_required
def api_move_announcement(announcement_id):
    """移动公告顺序API - 上移或下移"""
    data = request.get_json() or {}
    direction = data.get('direction', '')
    
    if direction not in ['up', 'down']:
        return jsonify({'success': False, 'message': '移动方向无效'})
    
    result = api_client.move_announcement(announcement_id, direction)
    if not result:
        return jsonify({'success': False, 'message': '公告不存在或无法移动'})
    
    action_text = '上移' if direction == 'up' else '下移'
    api_client.add_operation_log(
        f"{action_text}公告: {result['announcement_title']}",
        "公告管理"
    )
    
    return jsonify({
        'success': True,
        'message': f'已{action_text}'
    })


@app.route('/admin/logout')
def admin_logout():
    """管理员退出登录"""
    # 记录退出日志
    admin_name = session.get('admin_name', '未知')
    log_admin_operation_manual(
        action_type=AdminActionType.LOGOUT,
        target_type=TargetType.SYSTEM,
        description=f"管理员 {admin_name} 退出登录",
        result='SUCCESS'
    )

    session.pop('admin_id', None)
    session.pop('admin_name', None)
    return redirect(url_for('admin_select'))


# ==================== 悬赏管理 ====================

@app.route('/admin/pc/bounties')
@admin_required
def admin_pc_bounties():
    """PC端悬赏管理页面"""
    # 先自动取消过期悬赏
    expired_bounties = api_client._db.auto_cancel_expired_bounties()
    if expired_bounties:
        # 退还积分给发布人
        for bounty in expired_bounties:
            # 退还发布费10积分
            points_service.add_points(
                user_id=bounty.publisher_id,
                points=10,
                transaction_type=PointsTransactionType.CREATE_BOUNTY,
                description=f'悬赏过期自动取消退还发布费: {bounty.title}',
                related_id=bounty.id
            )
            # 退还悬赏积分
            points_service.add_points(
                user_id=bounty.publisher_id,
                points=bounty.reward_points,
                transaction_type=PointsTransactionType.RECEIVE_BOUNTY,
                description=f'悬赏过期自动取消退还悬赏积分: {bounty.title}',
                related_id=bounty.id
            )

    # 获取所有悬赏
    bounties = api_client._db.get_all_bounties()

    # 统计
    stats = {
        'total': len(bounties),
        'pending': len([b for b in bounties if b.status == BountyStatus.PENDING]),
        'found': len([b for b in bounties if b.status == BountyStatus.FOUND]),
        'completed': len([b for b in bounties if b.status == BountyStatus.COMPLETED]),
        'cancelled': len([b for b in bounties if b.status == BountyStatus.CANCELLED])
    }

    return render_template('admin/pc/bounties.html',
                         bounties=bounties,
                         stats=stats,
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_count=get_overdue_count())


@app.route('/admin/api/bounties', methods=['GET'])
@admin_required
def api_admin_get_bounties():
    """获取悬赏列表API（后台管理用）"""
    status = request.args.get('status', None)
    active = request.args.get('active', None)
    keyword = request.args.get('keyword', '').strip()

    # 先自动取消过期悬赏
    expired_bounties = api_client._db.auto_cancel_expired_bounties()
    if expired_bounties:
        for bounty in expired_bounties:
            points_service.add_points(
                user_id=bounty.publisher_id,
                points=10,
                transaction_type=PointsTransactionType.CREATE_BOUNTY,
                description=f'悬赏过期自动取消退还发布费: {bounty.title}',
                related_id=bounty.id
            )
            points_service.add_points(
                user_id=bounty.publisher_id,
                points=bounty.reward_points,
                transaction_type=PointsTransactionType.RECEIVE_BOUNTY,
                description=f'悬赏过期自动取消退还悬赏积分: {bounty.title}',
                related_id=bounty.id
            )

    # 获取悬赏列表
    if status:
        bounties = api_client._db.get_all_bounties(status=status)
    else:
        bounties = api_client._db.get_all_bounties()

    # 筛选上架状态
    if active is not None and active != '':
        is_active = active.lower() == 'true'
        bounties = [b for b in bounties if b.is_active == is_active]

    # 关键词搜索
    if keyword:
        keyword_lower = keyword.lower()
        bounties = [b for b in bounties if
                    keyword_lower in b.title.lower() or
                    keyword_lower in b.device_name.lower() or
                    keyword_lower in b.publisher_name.lower()]

    return jsonify({
        'success': True,
        'bounties': [b.to_dict() for b in bounties]
    })


@app.route('/admin/api/bounties/<bounty_id>/deactivate', methods=['POST'])
@admin_required
def api_admin_deactivate_bounty(bounty_id):
    """下架悬赏API（管理员下架并退还积分）"""
    bounty = api_client._db.get_bounty_by_id(bounty_id)
    if not bounty:
        return jsonify({'success': False, 'message': '悬赏不存在'})

    if bounty.status != BountyStatus.PENDING:
        return jsonify({'success': False, 'message': '只能下架待认领的悬赏'})

    # 下架悬赏
    bounty.is_active = False
    bounty.status = BountyStatus.CANCELLED
    api_client._db.save_bounty(bounty)

    # 退还发布费10积分
    points_service.add_points(
        user_id=bounty.publisher_id,
        points=10,
        transaction_type=PointsTransactionType.CREATE_BOUNTY,
        description=f'管理员下架悬赏退还发布费: {bounty.title}',
        related_id=bounty.id
    )

    # 退还悬赏积分
    points_service.add_points(
        user_id=bounty.publisher_id,
        points=bounty.reward_points,
        transaction_type=PointsTransactionType.RECEIVE_BOUNTY,
        description=f'管理员下架悬赏退还悬赏积分: {bounty.title}',
        related_id=bounty.id
    )

    # 添加操作日志
    api_client.add_operation_log(
        f"下架悬赏: {bounty.title} (退还 {bounty.reward_points + 10} 积分)",
        "悬赏管理"
    )

    return jsonify({
        'success': True,
        'message': '悬赏已下架，积分已退还',
        'refunded_points': bounty.reward_points + 10
    })


@app.route('/admin/api/bounties/<bounty_id>/activate', methods=['POST'])
@admin_required
def api_admin_activate_bounty(bounty_id):
    """上架悬赏API（管理员重新上架已下架的悬赏）"""
    bounty = api_client._db.get_bounty_by_id(bounty_id)
    if not bounty:
        return jsonify({'success': False, 'message': '悬赏不存在'})

    # 上架悬赏
    bounty.is_active = True
    api_client._db.save_bounty(bounty)

    # 添加操作日志
    api_client.add_operation_log(
        f"上架悬赏: {bounty.title}",
        "悬赏管理"
    )

    return jsonify({
        'success': True,
        'message': '悬赏已上架'
    })


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
    """用户列表 / 新增用户API (后台管理) - 使用缓存和分页优化"""
    if request.method == 'GET':
        # 获取分页和搜索参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip() or None

        # 使用缓存的分页查询
        from common.cache_manager import data_cache
        result = data_cache.get_cached_users_paginated(
            page=page,
            per_page=per_page,
            search=search
        )

        return jsonify({
            'users': result['users'],
            'total': result['total'],
            'page': result['page'],
            'per_page': result['per_page'],
            'total_pages': result['total_pages']
        })

    else:  # POST
        data = request.get_json()
        try:
            user = api_client.create_user(
                borrower_name=data.get('name'),
                email=data.get('email', ''),
                password=data.get('password'),
                is_admin=data.get('is_admin', False)
            )
            # 创建用户后使缓存失效
            from common.cache_manager import data_cache
            data_cache.invalidate_users_cache()
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
            # 更新用户后使缓存失效
            from common.cache_manager import data_cache
            data_cache.invalidate_users_cache()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    else:  # DELETE
        try:
            success, message = api_client.delete_user(user_id)
            # 删除用户后使缓存失效
            from common.cache_manager import data_cache
            data_cache.invalidate_users_cache()
            return jsonify({'success': success, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/users/<user_id>/freeze', methods=['POST'])
@admin_required
def api_user_freeze(user_id):
    """冻结用户API"""
    try:
        api_client.freeze_user(user_id)
        # 冻结用户后使缓存失效
        from common.cache_manager import data_cache
        data_cache.invalidate_users_cache()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/users/<user_id>/unfreeze', methods=['POST'])
@admin_required
def api_user_unfreeze(user_id):
    """解冻用户API"""
    try:
        api_client.unfreeze_user(user_id)
        # 解冻用户后使缓存失效
        from common.cache_manager import data_cache
        data_cache.invalidate_users_cache()
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


@app.route('/api/admin/users/<user_id>/reset_password', methods=['POST'])
@admin_required
def api_user_reset_password(user_id):
    """重置用户密码API"""
    try:
        api_client.reset_user_password(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/admin/users/import', methods=['POST'])
@admin_required
def api_users_import():
    """批量导入用户API"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '请选择文件'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '请选择文件'})
        
        # 读取Excel文件
        import pandas as pd
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # 检查必要的列
        required_columns = ['姓名', '邮箱']
        column_mapping = {}
        
        # 查找列名（支持中英文）
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in ['姓名', 'name', '用户名', '借用人']:
                column_mapping['name'] = col
            elif col_str in ['邮箱', 'email', '邮件', '电子邮箱']:
                column_mapping['email'] = col
        
        if 'name' not in column_mapping or 'email' not in column_mapping:
            return jsonify({'success': False, 'message': '文件格式错误，需要包含「姓名」和「邮箱」列'})
        
        success_count = 0
        failed_count = 0
        failed_reasons = []
        
        for index, row in df.iterrows():
            try:
                name = str(row[column_mapping['name']]).strip()
                email = str(row[column_mapping['email']]).strip()
                
                if not name or not email:
                    continue
                
                # 检查邮箱是否已存在
                existing_user = api_client.get_user_by_email(email)
                if existing_user:
                    failed_count += 1
                    failed_reasons.append(f"第{index+2}行：邮箱 {email} 已存在")
                    continue
                
                # 检查用户名是否已存在
                all_users = api_client.get_all_users()
                name_exists = any(u.borrower_name == name for u in all_users)
                if name_exists:
                    failed_count += 1
                    failed_reasons.append(f"第{index+2}行：用户名 {name} 已存在")
                    continue
                
                # 创建用户
                api_client.create_user(
                    borrower_name=name,
                    email=email,
                    password='123456',
                    is_admin=False
                )
                success_count += 1
                
            except Exception as e:
                failed_count += 1
                failed_reasons.append(f"第{index+2}行：{str(e)}")
        
        return jsonify({
            'success': True,
            'success_count': success_count,
            'failed_count': failed_count,
            'failed_reasons': failed_reasons
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'导入失败：{str(e)}'})


@app.route('/api/devices', methods=['GET', 'POST'])
@admin_required
def api_devices():
    """获取/创建设备API"""
    if request.method == 'GET':
        type_param = request.args.get('type')
        # 映射URL参数到设备类型
        type_map = {
            'phone': '手机',
            'car': '车机',
            'instrument': '仪表',
            'sim': '手机卡',
            'simcard': '手机卡',
            'other': '其它设备'
        }
        device_type = type_map.get(type_param, type_param)
        devices = api_client.get_all_devices(device_type)
        
        devices_data = []
        for device in devices:
            # 获取设备类型字符串
            device_type_str = get_device_type_str(device)
            
            # 判断是否为使用保管人的设备类型
            is_custodian_type = device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]
            
            # 根据设备类型判断状态显示
            if is_custodian_type and device.status == DeviceStatus.NO_CABINET:
                # 手机、手机卡、其它设备：检查custodian_id
                if not device.custodian_id:
                    status_display = '无保管人'
                else:
                    status_display = '保管中'
            else:
                status_display = device.status.value
            
            device_data = {
                'id': device.id,
                'device_name': device.name,
                'device_type': device_type_str,
                'model': device.model,
                'cabinet': device.cabinet_number,
                'status': status_display,
                'borrower': device.borrower,
                'phone': device.phone,
                'borrow_time': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                'expected_return': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else '',
                'remarks': device.remark,
                'jira_address': device.jira_address,
                'create_time': device.create_time.strftime('%Y-%m-%d %H:%M:%S') if device.create_time else ''
            }
            
            # 手机特有字段
            if device_type_str == '手机':
                device_data['system_version'] = device.system_version
                device_data['imei'] = device.imei
                device_data['sn'] = device.sn
                device_data['carrier'] = device.carrier
                device_data['asset_number'] = device.asset_number
                device_data['purchase_amount'] = device.purchase_amount
            
            # 车机和仪表特有字段（JIRA地址后）
            if device_type_str in ('车机', '仪表'):
                device_data['project_attribute'] = device.project_attribute
                device_data['connection_method'] = device.connection_method
                device_data['os_version'] = device.os_version
                device_data['os_platform'] = device.os_platform
                device_data['product_name'] = device.product_name
                device_data['screen_orientation'] = device.screen_orientation
                device_data['screen_resolution'] = device.screen_resolution

            devices_data.append(device_data)
        
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
            asset_number = data.get('asset_number', '')
            purchase_amount = float(data.get('purchase_amount', 0)) if data.get('purchase_amount') else 0.0

            # 根据设备类型字符串获取对应的DeviceType
            device_type_map = {
                '手机': DeviceType.PHONE,
                '车机': DeviceType.CAR_MACHINE,
                '仪表': DeviceType.INSTRUMENT,
                '手机卡': DeviceType.SIM_CARD,
                '其它设备': DeviceType.OTHER_DEVICE
            }
            device_type_enum = device_type_map.get(device_type, DeviceType.CAR_MACHINE)

            # 准备额外字段
            kwargs = {}
            if device_type == '手机':
                kwargs['sn'] = data.get('sn', '')
                kwargs['imei'] = data.get('imei', '')
                kwargs['system_version'] = data.get('system_version', '')
                kwargs['carrier'] = data.get('carrier', '')
            elif device_type == '手机卡':
                kwargs['carrier'] = data.get('carrier', '')

            device = api_client.create_device(
                device_type=device_type_enum,
                device_name=device_name,
                model=model,
                cabinet=cabinet,
                status=status,
                remarks=remarks,
                asset_number=asset_number,
                purchase_amount=purchase_amount,
                **kwargs
            )

            # 记录创建设备日志
            log_admin_operation_manual(
                action_type=AdminActionType.DEVICE_CREATE,
                target_type=TargetType.DEVICE,
                target_id=device.id,
                target_name=device_name,
                description=f"创建{device_type}设备: {device_name}",
                result='SUCCESS'
            )

            return jsonify({'success': True, 'device_id': device.id})
        except Exception as e:
            import traceback
            print(f"[DEBUG] api_devices - create device error: {e}")
            print(f"[DEBUG] api_devices - traceback: {traceback.format_exc()}")
            # 记录失败日志
            log_admin_operation_manual(
                action_type=AdminActionType.DEVICE_CREATE,
                target_type=TargetType.DEVICE,
                target_name=device_name,
                description=f"创建设备失败: {device_name}",
                result='FAILED',
                error_message=str(e)
            )
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def api_device_detail(device_id):
    """获取/更新/删除设备API"""
    if request.method == 'GET':
        device = api_client.get_device(device_id)
        if not device:
            return jsonify({'success': False, 'message': '设备不存在'})
        
        # 根据 device_type 枚举获取设备类型字符串
        device_type_str = device.device_type.value if device.device_type else '车机'
        
        return jsonify({
            'id': device.id,
            'name': device.name,
            'device_type': device_type_str,
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
            # 获取设备信息用于日志
            device = api_client.get_device(device_id)
            device_name = device.name if device else device_id

            operator = session.get('admin_name', '管理员')
            api_client.update_device_by_id(device_id, data, operator)

            # 记录更新设备日志
            log_admin_operation_manual(
                action_type=AdminActionType.DEVICE_UPDATE,
                target_type=TargetType.DEVICE,
                target_id=device_id,
                target_name=device_name,
                description=f"更新设备信息: {device_name}",
                result='SUCCESS'
            )

            return jsonify({'success': True})
        except Exception as e:
            # 记录失败日志
            log_admin_operation_manual(
                action_type=AdminActionType.DEVICE_UPDATE,
                target_type=TargetType.DEVICE,
                target_id=device_id,
                description=f"更新设备失败",
                result='FAILED',
                error_message=str(e)
            )
            return jsonify({'success': False, 'message': str(e)})

    else:  # DELETE
        try:
            # 获取设备信息用于日志
            device = api_client.get_device(device_id)
            device_name = device.name if device else device_id

            api_client.delete_device(device_id)

            # 记录删除设备日志
            log_admin_operation_manual(
                action_type=AdminActionType.DEVICE_DELETE,
                target_type=TargetType.DEVICE,
                target_id=device_id,
                target_name=device_name,
                description=f"删除设备: {device_name}",
                result='SUCCESS'
            )

            return jsonify({'success': True})
        except Exception as e:
            # 记录失败日志
            log_admin_operation_manual(
                action_type=AdminActionType.DEVICE_DELETE,
                target_type=TargetType.DEVICE,
                target_id=device_id,
                description=f"删除设备失败",
                result='FAILED',
                error_message=str(e)
            )
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>/permanent-delete', methods=['DELETE'])
@admin_required
def api_permanent_delete_device(device_id):
    """物理删除设备API - 彻底从数据库删除"""
    try:
        from common.db_store import get_db_transaction
        from common.models import ReservationStatus
        
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            
            # 先查询设备信息用于日志
            cursor.execute(
                "SELECT name, device_type FROM devices WHERE id = %s",
                (device_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'success': False, 'message': '设备不存在'})
            
            device_name = row['name']
            device_type = row['device_type']
            
            # 先删除关联的预约记录
            cursor.execute(
                "DELETE FROM reservations WHERE device_id = %s AND device_type = %s",
                (device_id, device_type)
            )
            
            # 物理删除设备
            cursor.execute(
                "DELETE FROM devices WHERE id = %s",
                (device_id,)
            )
            
            conn.commit()
        
        # 记录操作日志
        api_client.add_operation_log(
            f"彻底删除设备: {device_name}",
            f"{device_type}管理"
        )
        
        return jsonify({'success': True, 'message': '设备已彻底删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})


@app.route('/api/devices/<device_id>/borrow', methods=['POST'])
@admin_required
def api_admin_borrow(device_id):
    """管理员录入借出API"""
    data = request.get_json()
    borrower = data.get('borrower')
    days = data.get('days', 1)
    remarks = data.get('remarks', '')

    if not borrower:
        return jsonify({'success': False, 'message': '请选择借用人'})

    # 检查是否是邮箱，如果是则通过邮箱查找用户获取borrower_name
    actual_borrower = borrower
    if '@' in borrower:
        user = api_client.get_user_by_email(borrower)
        if not user:
            return jsonify({'success': False, 'message': f'未找到邮箱为 {borrower} 的用户'})
        actual_borrower = user.borrower_name

    # 获取设备信息，记录原借用人
    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    original_borrower = device.borrower if device.status == DeviceStatus.BORROWED else None

    try:
        success = api_client.borrow_device(
            device_id=device_id,
            borrower=actual_borrower,
            days=int(days),
            remarks=remarks,
            operator=session.get('admin_name', '管理员'),
            entry_source=EntrySource.ADMIN.value
        )
        # 发送通知
        if success:
            device = api_client.get_device(device_id)
            if device:
                # 1. 通知新借用人
                api_client.notify_borrow(
                    device_id=device_id,
                    device_name=device.name,
                    borrower=actual_borrower,
                    operator=session.get('admin_name', '管理员')
                )
                # 2. 通知原借用人（如果设备之前被借用且原借用人不是新借用人）
                if original_borrower and original_borrower != actual_borrower:
                    original_user = None
                    for u in api_client._users:
                        if u.borrower_name == original_borrower:
                            original_user = u
                            break
                    if original_user:
                        api_client.add_notification(
                            user_id=original_user.id,
                            user_name=original_user.borrower_name,
                            title="设备被转借通知",
                            content=f"您借用的设备「{device.name}」已被管理员借出给 {actual_borrower}。",
                            device_name=device.name,
                            device_id=device.id,
                            notification_type="warning"
                        )
                # 3. 通知保管人（如果保管人不是借用人自己）
                if device.cabinet_number and device.cabinet_number != actual_borrower:
                    custodian_user = None
                    for u in api_client._users:
                        if u.borrower_name == device.cabinet_number:
                            custodian_user = u
                            break
                    if custodian_user:
                        api_client.add_notification(
                            user_id=custodian_user.id,
                            user_name=custodian_user.borrower_name,
                            title="设备被借用通知",
                            content=f"您保管的设备「{device.name}」已被管理员借出给 {actual_borrower}。",
                            device_name=device.name,
                            device_id=device.id,
                            notification_type="info"
                        )
    except ValueError as e:
        # 记录借出失败日志
        log_admin_operation_manual(
            action_type=AdminActionType.DEVICE_BORROW,
            target_type=TargetType.DEVICE,
            target_id=device_id,
            target_name=device.name if device else '',
            description=f"借出设备失败: {actual_borrower}",
            result='FAILED',
            error_message=str(e)
        )
        return jsonify({'success': False, 'message': str(e)})

    if success:
        # 记录借出成功日志
        log_admin_operation_manual(
            action_type=AdminActionType.DEVICE_BORROW,
            target_type=TargetType.DEVICE,
            target_id=device_id,
            target_name=device.name if device else '',
            description=f"借出设备给: {actual_borrower}",
            result='SUCCESS'
        )
        return jsonify({'success': True, 'message': '录入成功'})
    else:
        # 记录借出失败日志
        log_admin_operation_manual(
            action_type=AdminActionType.DEVICE_BORROW,
            target_type=TargetType.DEVICE,
            target_id=device_id,
            target_name=device.name if device else '',
            description=f"借出设备失败: {actual_borrower}",
            result='FAILED',
            error_message='录入失败'
        )
        return jsonify({'success': False, 'message': '录入失败'})


@app.route('/api/devices/<device_id>/return', methods=['POST'])
@admin_required
def api_admin_return(device_id):
    """管理员强制归还API"""
    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})

    # 记录原借用人和保管人
    original_borrower = device.borrower
    original_custodian = device.cabinet_number

    # 根据设备类型设置归还后的状态
    # 手机、手机卡、其它设备 -> 保管中；车机、仪表 -> 在库
    if device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]:
        device.status = DeviceStatus.IN_CUSTODY
    else:
        device.status = DeviceStatus.IN_STOCK

    device.borrower = ''
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
        reason='管理员强制归还',
        entry_source=EntrySource.ADMIN.value
    )
    api_client._db.save_record(record)
    api_client.add_operation_log(f"强制归还: {original_borrower}", device.name)
    
    # 更新原借用人的归还次数
    if original_borrower:
        for u in api_client._users:
            if u.borrower_name == original_borrower:
                u.return_count += 1
                api_client._db.save_user(u)
                break
    
    # 发送通知
    # 1. 通知原借用人
    if original_borrower:
        api_client.notify_return(
            device_id=device_id,
            device_name=device.name,
            borrower=original_borrower,
            operator=session.get('admin_name', '管理员')
        )
    # 2. 通知保管人（如果保管人不是原借用人）
    if original_custodian and original_custodian != original_borrower:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == original_custodian:
                custodian_user = u
                break
        if custodian_user:
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备强制归还通知",
                content=f"您保管的设备「{device.name}」已被管理员从 {original_borrower or '无'} 处强制归还。",
                device_name=device.name,
                device_id=device.id,
                notification_type="info"
            )

    # 记录归还日志
    log_admin_operation_manual(
        action_type=AdminActionType.DEVICE_RETURN,
        target_type=TargetType.DEVICE,
        target_id=device_id,
        target_name=device.name,
        description=f"强制归还设备，原借用人: {original_borrower}",
        result='SUCCESS'
    )

    return jsonify({'success': True, 'message': '归还成功'})


@app.route('/api/devices/<device_id>/transfer', methods=['POST'])
@admin_required
def api_admin_transfer(device_id):
    """管理员转借API"""
    data = request.get_json()
    new_borrower = data.get('borrower')

    if not new_borrower:
        return jsonify({'success': False, 'message': '请选择新借用人'})

    # 检查是否是邮箱，如果是则通过邮箱查找用户获取borrower_name
    actual_new_borrower = new_borrower
    if '@' in new_borrower:
        user = api_client.get_user_by_email(new_borrower)
        if not user:
            return jsonify({'success': False, 'message': f'未找到邮箱为 {new_borrower} 的用户'})
        actual_new_borrower = user.borrower_name

    device = api_client.get_device(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})

    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备未借出，无法转借'})

    original_borrower = device.borrower

    # 更新设备
    device.borrower = actual_new_borrower
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
        borrower=f"{original_borrower} → {actual_new_borrower}",
        reason='管理员转借',
        entry_source=EntrySource.ADMIN.value
    )
    api_client._db.save_record(record)
    api_client.add_operation_log(f"转借: {original_borrower} -> {actual_new_borrower}", device.name)

    # 发送通知
    api_client.notify_transfer(
        device_id=device_id,
        device_name=device.name,
        original_borrower=original_borrower,
        new_borrower=actual_new_borrower,
        operator=session.get('admin_name', '管理员')
    )
    # 通知保管人（如果保管人不是转借双方）
    if device.cabinet_number and device.cabinet_number != original_borrower and device.cabinet_number != actual_new_borrower:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备转借通知",
                content=f"您保管的设备「{device.name}」已被管理员从 {original_borrower} 转借给 {actual_new_borrower}。",
                device_name=device.name,
                device_id=device.id,
                notification_type="info"
            )

    # 记录转借日志
    log_admin_operation_manual(
        action_type=AdminActionType.DEVICE_TRANSFER,
        target_type=TargetType.DEVICE,
        target_id=device_id,
        target_name=device.name,
        description=f"转借设备: {original_borrower} → {actual_new_borrower}",
        result='SUCCESS'
    )

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
        # 记录强制借出日志
        log_admin_operation_manual(
            action_type=AdminActionType.DEVICE_BORROW,
            target_type=TargetType.DEVICE,
            target_id=device_id,
            target_name=device.name,
            description=f"强制借出(录入登记)给: {borrower}",
            result='SUCCESS'
        )
        return jsonify({'success': True, 'message': '录入登记成功'})
    else:
        # 记录失败日志
        log_admin_operation_manual(
            action_type=AdminActionType.DEVICE_BORROW,
            target_type=TargetType.DEVICE,
            target_id=device_id,
            target_name=device.name,
            description=f"强制借出(录入登记)失败: {borrower}",
            result='FAILED',
            error_message='录入登记失败'
        )
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
                'email': user.email,
                'borrow_count': user.borrow_count,
                'is_admin': user.is_admin,
                'is_frozen': user.is_frozen,
                'is_first_login': user.is_first_login,
                'register_time': user.create_time.strftime('%Y-%m-%d') if hasattr(user, 'create_time') and user.create_time else '-'
            })
        return jsonify(users_data)
    
    else:  # POST
        data = request.get_json()
        try:
            user = api_client.create_user(
                borrower_name=data.get('name'),
                email=data.get('email', ''),
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
            'operator': record.operator,
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
    """操作日志API - 使用新的后台管理操作日志系统"""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    action_type = request.args.get('action_type', None)
    target_type = request.args.get('target_type', None)
    result = request.args.get('result', None)

    logs = api_client.get_admin_operation_logs_for_display(
        limit=limit,
        offset=offset
    )
    return jsonify(logs)


@app.route('/api/admin-logs', methods=['GET'])
@admin_required
def api_admin_logs():
    """后台管理操作日志API - 支持分页和筛选"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    action_type = request.args.get('action_type', None)
    target_type = request.args.get('target_type', None)
    result = request.args.get('result', None)

    offset = (page - 1) * per_page

    # 获取日志列表
    logs = api_client.get_admin_operation_logs_for_display(
        limit=per_page,
        offset=offset
    )

    # 获取总数
    total = api_client.get_admin_operation_logs_count(
        action_type=action_type,
        target_type=target_type,
        result=result
    )

    return jsonify({
        'logs': logs,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': (total + per_page - 1) // per_page
    })


@app.route('/api/admin-logs/action-types', methods=['GET'])
@admin_required
def api_admin_logs_action_types():
    """获取所有操作类型"""
    return jsonify(ACTION_TYPE_NAMES)


@app.route('/api/admin-logs/test', methods=['POST'])
@admin_required
def api_admin_logs_test():
    """测试日志记录功能"""
    try:
        # 手动记录一条测试日志
        result = log_admin_operation_manual(
            action_type=AdminActionType.SYSTEM_SETTING,
            target_type=TargetType.SYSTEM,
            description="测试日志记录功能",
            result='SUCCESS'
        )

        if result:
            return jsonify({'success': True, 'message': '测试日志记录成功'})
        else:
            return jsonify({'success': False, 'message': '测试日志记录失败'})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': str(e), 'traceback': traceback.format_exc()})


# ==================== 备注管理API ====================

@app.route('/api/remarks/<remark_id>', methods=['DELETE'])
@admin_required
def api_delete_remark(remark_id):
    """删除备注API"""
    success = api_client.delete_remark(remark_id)
    if success:
        api_client.add_operation_log(f"删除备注", f"备注ID: {remark_id}")
        return jsonify({'success': True, 'message': '备注已删除'})
    else:
        return jsonify({'success': False, 'message': '备注不存在或删除失败'})


@app.route('/api/remarks/<remark_id>/mark-inappropriate', methods=['POST'])
@admin_required
def api_mark_inappropriate(remark_id):
    """标记备注为不当内容API"""
    success = api_client.mark_inappropriate(remark_id)
    if success:
        api_client.add_operation_log(f"标记备注为不当内容", f"备注ID: {remark_id}")
        return jsonify({'success': True, 'message': '已标记为不当内容'})
    else:
        return jsonify({'success': False, 'message': '备注不存在'})


@app.route('/api/remarks/<remark_id>/unmark-inappropriate', methods=['POST'])
@admin_required
def api_unmark_inappropriate(remark_id):
    """取消备注不当标记API"""
    success = api_client.unmark_inappropriate(remark_id)
    if success:
        api_client.add_operation_log(f"取消备注不当标记", f"备注ID: {remark_id}")
        return jsonify({'success': True, 'message': '已取消不当标记'})
    return jsonify({'success': False, 'message': '备注不存在'})


@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    """获取通知列表API"""
    user_id = session.get('user_id')
    user_name = session.get('borrower_name')

    unread_only = request.args.get('unread_only', 'false').lower() == 'true'

    notifications = api_client.get_notifications(
        user_id=user_id,
        user_name=user_name,
        unread_only=unread_only
    )

    return jsonify({'notifications': [n.to_dict() for n in notifications]})


@app.route('/api/notifications/unread-count', methods=['GET'])
def api_notification_unread_count():
    """获取未读通知数量API"""
    user_id = session.get('user_id')
    user_name = session.get('borrower_name')

    count = api_client.get_unread_count(user_id=user_id, user_name=user_name)

    return jsonify({'count': count})


@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
def api_mark_notification_read(notification_id):
    """标记通知为已读API"""
    success = api_client.mark_notification_read(notification_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '通知不存在'})


@app.route('/api/notifications/read-all', methods=['POST'])
def api_mark_all_read():
    """标记所有通知为已读API"""
    user_id = session.get('user_id')
    user_name = session.get('borrower_name')

    count = api_client.mark_all_read(user_id=user_id, user_name=user_name)

    return jsonify({'success': True, 'count': count})


@app.route('/admin/template/<device_type>')
@admin_required
def download_template(device_type):
    """下载设备导入模板"""
    import pandas as pd
    from io import BytesIO

    templates = {
        'car': {
            'columns': ['jira地址', '型号', '设备名称', '柜号', '项目属性', '连接方式', '车机系统版本', '系统平台', '产品名称', '芯片型号', '屏幕方向', '车机分辨率'],
            'example': [['NAV-2866', 'WCLW01', 'AE-WCLW01-1', '26-27', '国内前装', '安卓USB,安卓无感连接（扫码）,苹果USB直连,苹果无感连接（扫码）', '12', 'Android', '亿连手机互联标准版', '芯驰X9HP', '横屏', '1920*1080']]
        },
        'instrument': {
            'columns': ['jira地址', '型号', '设备名称', '柜号', '项目属性', '连接方式', '系统版本', '系统平台', '产品名称', '芯片型号', '屏幕方向', '分辨率'],
            'example': [['JIRA-002', 'Model-B', '仪表-001', 'B-01', '项目B', 'CAN', 'Linux', 'Linux', '产品Y', '芯片B', '竖屏', '1280x720']]
        },
        'phone': {
            'columns': ['jira地址', '型号', '设备名称', '保管人', '状态', '系统版本', 'IMEI', 'SN码', '运营商', '固定资产编号', '购买金额(元)'],
            'example': [['JIRA-003', 'iPhone 14', '手机-001', '张三', '保管中', 'iOS 16', '123456789012345', 'SN123456', '移动', 'ZC-2024-001', '5999']]
        },
        'sim': {
            'columns': ['jira地址', '号码', '设备名称', '保管人', '运营商', '套餐类型'],
            'example': [['JIRA-004', '13800138000', '手机卡-001', '李四', '移动', '5G套餐']]
        },
        'other': {
            'columns': ['jira地址', '型号', '设备名称', '保管人', '备注'],
            'example': [['JIRA-005', 'Tool-A', '工具-001', '王五', '测试工具']]
        }
    }

    if device_type not in templates:
        return jsonify({'success': False, 'message': '未知的设备类型'}), 400

    template = templates[device_type]

    # 创建Excel文件
    df = pd.DataFrame(template['example'], columns=template['columns'])
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    # 设置文件名
    type_names = {
        'car': '车机',
        'instrument': '仪表',
        'phone': '手机',
        'sim': '手机卡',
        'other': '其它设备'
    }
    filename = f"{type_names.get(device_type, device_type)}导入模板.xlsx"

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@app.route('/admin/api/import-devices', methods=['POST'])
@admin_required
def api_import_devices():
    """批量导入设备API"""
    import pandas as pd
    from common.models import DeviceType, DeviceStatus, CarMachine, Instrument, Phone, SimCard, OtherDevice

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '请选择文件'}), 400

    file = request.files['file']
    device_type = request.form.get('device_type')

    if file.filename == '':
        return jsonify({'success': False, 'message': '请选择文件'}), 400

    if not device_type:
        return jsonify({'success': False, 'message': '请选择设备类型'}), 400

    try:
        # 读取Excel文件
        df = pd.read_excel(file, engine='openpyxl')

        if df.empty:
            return jsonify({'success': False, 'message': '文件为空'}), 400

        imported_count = 0
        errors = []

        # 辅助函数：根据柜号/保管人判断状态
        def get_status_from_cabinet(cabinet_value):
            if not cabinet_value:
                return DeviceStatus.NO_CABINET
            cabinet_str = str(cabinet_value).strip()
            if cabinet_str == '' or cabinet_str == '无柜号':
                return DeviceStatus.NO_CABINET
            # 提取前两个字判断特殊状态
            prefix = cabinet_str[:2]
            if prefix == '流通' or cabinet_str == '流通':
                return DeviceStatus.CIRCULATING
            if prefix == '封存' or cabinet_str == '封存':
                return DeviceStatus.SEALED
            return DeviceStatus.IN_STOCK

        # 根据设备类型处理数据
        for index, row in df.iterrows():
            try:
                row_num = index + 2  # Excel行号（从1开始，第1行是标题）

                if device_type == 'car':
                    # 车机导入
                    cabinet = str(row.get('柜号', '')).strip()
                    device = CarMachine(
                        id=str(uuid.uuid4()),
                        name=str(row.get('设备名称', '')).strip(),
                        model=str(row.get('型号', '')).strip(),
                        cabinet_number=cabinet,
                        status=get_status_from_cabinet(cabinet),
                        jira_address=str(row.get('jira地址', '')).strip(),
                        project_attribute=str(row.get('项目属性', '')).strip(),
                        connection_method=str(row.get('连接方式', '')).strip(),
                        os_version=str(row.get('车机系统版本', '')).strip(),
                        os_platform=str(row.get('系统平台', '')).strip(),
                        product_name=str(row.get('产品名称', '')).strip(),
                        hardware_version=str(row.get('芯片型号', '')).strip(),
                        screen_orientation=str(row.get('屏幕方向', '')).strip(),
                        screen_resolution=str(row.get('车机分辨率', '')).strip(),
                        entry_source='批量导入'
                    )
                    api_client._db.save_device(device)

                elif device_type == 'instrument':
                    # 仪表导入
                    cabinet = str(row.get('柜号', '')).strip()
                    device = Instrument(
                        id=str(uuid.uuid4()),
                        name=str(row.get('设备名称', '')).strip(),
                        model=str(row.get('型号', '')).strip(),
                        cabinet_number=cabinet,
                        status=get_status_from_cabinet(cabinet),
                        jira_address=str(row.get('jira地址', '')).strip(),
                        project_attribute=str(row.get('项目属性', '')).strip(),
                        connection_method=str(row.get('连接方式', '')).strip(),
                        os_version=str(row.get('系统版本', '')).strip(),
                        os_platform=str(row.get('系统平台', '')).strip(),
                        product_name=str(row.get('产品名称', '')).strip(),
                        hardware_version=str(row.get('芯片型号', '')).strip(),
                        screen_orientation=str(row.get('屏幕方向', '')).strip(),
                        screen_resolution=str(row.get('分辨率', '')).strip(),
                        entry_source='批量导入'
                    )
                    api_client._db.save_device(device)

                elif device_type == 'phone':
                    # 手机导入
                    cabinet = safe_str_from_excel(row.get('保管人', ''))
                    # 读取状态列，如果没有则根据保管人判断
                    status_str = safe_str_from_excel(row.get('状态', ''))
                    if status_str:
                        try:
                            device_status = DeviceStatus(status_str)
                        except ValueError:
                            # 状态值无效，根据保管人判断
                            device_status = DeviceStatus.IN_CUSTODY if cabinet else DeviceStatus.NO_CABINET
                    else:
                        # 手机设备：有保管人就是保管中，无保管人就是无保管人
                        device_status = DeviceStatus.IN_CUSTODY if cabinet else DeviceStatus.NO_CABINET
                    # 读取购买金额
                    purchase_amount_str = safe_str_from_excel(row.get('购买金额(元)', ''))
                    purchase_amount = 0.0
                    if purchase_amount_str:
                        try:
                            purchase_amount = float(purchase_amount_str)
                        except ValueError:
                            purchase_amount = 0.0
                    device = Phone(
                        id=str(uuid.uuid4()),
                        name=safe_str_from_excel(row.get('设备名称', '')),
                        model=safe_str_from_excel(row.get('型号', '')),
                        cabinet_number=cabinet,
                        status=device_status,
                        jira_address=safe_str_from_excel(row.get('jira地址', '')),
                        system_version=safe_str_from_excel(row.get('系统版本', '')),
                        imei=safe_str_from_excel(row.get('IMEI', '')),
                        sn=safe_str_from_excel(row.get('SN码', '')),
                        carrier=safe_str_from_excel(row.get('运营商', '')),
                        asset_number=safe_str_from_excel(row.get('固定资产编号', '')),
                        purchase_amount=purchase_amount,
                        entry_source='批量导入'
                    )
                    api_client._db.save_device(device)

                elif device_type == 'sim':
                    # 手机卡导入
                    cabinet = str(row.get('保管人', '')).strip()
                    device = SimCard(
                        id=str(uuid.uuid4()),
                        name=str(row.get('设备名称', '')).strip(),
                        model=str(row.get('号码', '')).strip(),
                        cabinet_number=cabinet,
                        status=get_status_from_cabinet(cabinet),
                        jira_address=str(row.get('jira地址', '')).strip(),
                        carrier=str(row.get('运营商', '')).strip(),
                        entry_source='批量导入'
                    )
                    api_client._db.save_device(device)

                elif device_type == 'other':
                    # 其它设备导入
                    cabinet = str(row.get('保管人', '')).strip()
                    device = OtherDevice(
                        id=str(uuid.uuid4()),
                        name=str(row.get('设备名称', '')).strip(),
                        model=str(row.get('型号', '')).strip(),
                        cabinet_number=cabinet,
                        status=get_status_from_cabinet(cabinet),
                        jira_address=str(row.get('jira地址', '')).strip(),
                        remark=str(row.get('备注', '')).strip(),
                        entry_source='批量导入'
                    )
                    api_client._db.save_device(device)

                imported_count += 1

            except Exception as e:
                errors.append(f'第{row_num}行: {str(e)}')

        # 记录操作日志
        api_client.add_operation_log(
            f'批量导入{imported_count}个设备',
            device_type
        )

        result = {
            'success': True,
            'imported_count': imported_count,
            'message': f'成功导入 {imported_count} 个设备'
        }

        if errors:
            result['errors'] = errors[:10]  # 最多返回10条错误
            if len(errors) > 10:
                result['errors'].append(f'...还有 {len(errors) - 10} 条错误')

        return jsonify(result)

    except Exception as e:
        print(f'导入失败: {e}')
        return jsonify({'success': False, 'message': f'导入失败: {str(e)}'}), 500


@app.route('/admin/api/reload-data', methods=['POST'])
@admin_required
def api_reload_data():
    """重新加载数据API - 从Excel文件重新加载所有数据"""
    try:
        # 重置初始化标志，强制重新加载数据
        from common.api_client import APIClient
        APIClient._initialized = False
        
        # 创建新的APIClient实例，触发数据重新加载
        new_client = APIClient()
        
        # 重新赋值给全局api_client
        global api_client
        api_client = new_client
        
        # 获取各类型设备数量
        car_count = len(api_client._car_machines)
        instrument_count = len(api_client._instruments)
        phone_count = len(api_client._phones)
        sim_count = len(api_client._sim_cards)
        other_count = len(api_client._other_devices)
        
        return jsonify({
            'success': True,
            'message': '数据重新加载成功',
            'counts': {
                '车机': car_count,
                '仪表': instrument_count,
                '手机': phone_count,
                '手机卡': sim_count,
                '其它设备': other_count
            }
        })
    except Exception as e:
        print(f'重新加载数据失败: {e}')
        return jsonify({'success': False, 'message': f'重新加载数据失败: {str(e)}'}), 500


@app.route('/api/stats/borrow-return', methods=['GET'])
@admin_required
def api_borrow_return_stats():
    """获取借出归还统计数据API - 用于折线图展示"""
    try:
        range_type = request.args.get('range', 'week')  # week, month, year
        
        # 获取所有记录
        all_records = api_client.get_records()
        
        # 根据时间范围确定日期格式和天数
        if range_type == 'week':
            days = 7
            date_format = '%m-%d'
            label_format = lambda d: d.strftime('%m-%d')
        elif range_type == 'month':
            days = 30
            date_format = '%m-%d'
            label_format = lambda d: d.strftime('%m-%d')
        elif range_type == 'year':
            days = 365
            date_format = '%Y-%m'
            label_format = lambda d: d.strftime('%Y-%m')
        else:
            days = 7
            date_format = '%m-%d'
            label_format = lambda d: d.strftime('%m-%d')
        
        # 生成日期标签
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 初始化统计数据
        labels = []
        borrow_data = []
        return_data = []
        
        if range_type == 'year':
            # 按月份统计
            for i in range(12):
                month_date = end_date - timedelta(days=(11-i)*30)
                month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
                
                labels.append(month_date.strftime('%Y-%m'))
                
                # 统计该月的借出和归还
                month_borrow = 0
                month_return = 0
                for record in all_records:
                    if month_start <= record.operation_time <= month_end:
                        if record.operation_type in [OperationType.BORROW, OperationType.FORCE_BORROW]:
                            month_borrow += 1
                        elif record.operation_type in [OperationType.RETURN, OperationType.FORCE_RETURN]:
                            month_return += 1
                
                borrow_data.append(month_borrow)
                return_data.append(month_return)
        else:
            # 按天统计
            for i in range(days):
                date = start_date + timedelta(days=i+1)
                date_str = date.strftime('%Y-%m-%d')
                labels.append(label_format(date))
                
                # 统计该日的借出和归还
                day_borrow = 0
                day_return = 0
                for record in all_records:
                    record_date = record.operation_time.strftime('%Y-%m-%d')
                    if record_date == date_str:
                        if record.operation_type in [OperationType.BORROW, OperationType.FORCE_BORROW]:
                            day_borrow += 1
                        elif record.operation_type in [OperationType.RETURN, OperationType.FORCE_RETURN]:
                            day_return += 1
                
                borrow_data.append(day_borrow)
                return_data.append(day_return)
        
        return jsonify({
            'success': True,
            'labels': labels,
            'borrow': borrow_data,
            'return': return_data
        })
    except Exception as e:
        print(f'获取借出归还统计数据失败: {e}')
        return jsonify({'success': False, 'message': f'获取统计数据失败: {str(e)}'}), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message='页面未找到'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message='服务器内部错误'), 500


if __name__ == '__main__':
    print(f"管理服务启动在端口 {ADMIN_SERVICE_PORT}")
    # threaded=True 启用多线程支持高并发
    app.run(debug=False, host='0.0.0.0', port=ADMIN_SERVICE_PORT, threaded=True)
