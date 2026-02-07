# -*- coding: utf-8 -*-
"""
车机与手机设备管理系统 - 用户端（手机网页）
使用 Flask 实现，适配微信内置浏览器
"""
import os
import uuid
import io
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from dotenv import load_dotenv

# 从管理端导入模型和API客户端
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'device_manager'))
from models import DeviceStatus, DeviceType, OperationType, EntrySource, CarMachine, Phone, Record, UserRemark, User, ViewRecord
from api_client import api_client

# 尝试导入qrcode，如果没有安装则使用备用方案
try:
    import qrcode
    from qrcode.image.pil import PilImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    print("警告: qrcode模块未安装，二维码功能将使用备用方案")

load_dotenv()

# 服务器配置 - 用于二维码生成
# 可以设置为外网IP或域名，如: http://192.168.1.100:5000 或 http://your-domain.com
# 设置方法:
# 1. 在 .env 文件中添加: SERVER_URL=http://192.168.1.100:5000
# 2. 或在系统环境变量中设置 SERVER_URL
SERVER_URL = os.getenv('SERVER_URL', '').rstrip('/')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
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
        return {
            'user_id': user.id,
            'wechat_name': user.wechat_name,
            'phone': user.phone,
            'borrower_name': user.borrower_name,
        }
    return {}


def mask_phone(phone):
    """手机号脱敏显示"""
    if len(phone) == 11:
        return phone[:3] + '****' + phone[7:]
    return phone


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页"""
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录页面"""
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()

        if not phone or not password:
            return render_template('login.html', error='请输入手机号和密码')

        user = api_client.verify_user_login(phone, password)
        if user:
            session['user_id'] = user.id
            session['phone'] = user.phone

            # 检查是否需要设置借用人名称
            if not user.borrower_name:
                return redirect(url_for('set_borrower_name'))

            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='手机号或密码错误，或账号已被冻结')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册页面"""
    if request.method == 'POST':
        borrower_name = request.form.get('borrower_name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # 验证输入
        if not borrower_name or not phone or not password:
            return render_template('register.html', error='请填写所有必填项')

        if len(phone) != 11 or not phone.isdigit():
            return render_template('register.html', error='手机号格式不正确')

        if len(password) < 6:
            return render_template('register.html', error='密码至少6位')

        if password != confirm_password:
            return render_template('register.html', error='两次输入的密码不一致')

        # 注册用户
        success, message = api_client.register_user(phone, password, borrower_name)
        if success:
            return render_template('register.html', success='注册成功，请登录')
        else:
            return render_template('register.html', error=message)

    return render_template('register.html')


@app.route('/login/qrcode')
def login_qrcode():
    """生成登录二维码"""
    try:
        # 获取服务器URL，优先使用配置的 SERVER_URL
        if SERVER_URL:
            base_url = SERVER_URL
        else:
            base_url = request.url_root.rstrip('/')
            # 如果检测到 localhost 或 127.0.0.1，给出提示
            if 'localhost' in base_url or '127.0.0.1' in base_url:
                print(f"警告: 二维码使用的是本地地址 {base_url}")
                print("请在 .env 文件中设置 SERVER_URL=你的外网IP或域名")

        # 生成完整的登录页面URL
        login_url = f"{base_url}/login"

        if QRCODE_AVAILABLE:
            # 使用qrcode库生成二维码
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(login_url)
            qr.make(fit=True)

            # 创建图像
            img = qr.make_image(fill_color="black", back_color="white")

            # 保存到内存
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)

            response = make_response(img_io.getvalue())
            response.headers['Content-Type'] = 'image/png'
            return response
        else:
            # 备用方案：使用Google Chart API生成二维码
            import urllib.request
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(login_url)}"

            try:
                with urllib.request.urlopen(qr_url, timeout=5) as response:
                    image_data = response.read()

                resp = make_response(image_data)
                resp.headers['Content-Type'] = 'image/png'
                return resp
            except Exception as e:
                # 如果外部API失败，返回一个占位图
                return "二维码生成失败，请使用账号密码登录", 500

    except Exception as e:
        print(f"生成二维码失败: {e}")
        return "二维码生成失败", 500


@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/set-borrower-name', methods=['GET', 'POST'])
def set_borrower_name():
    """设置借用人名称（首次登录）"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    # 获取用户信息
    user = None
    for u in api_client._users:
        if u.id == user_id:
            user = u
            break
    
    if not user:
        return redirect(url_for('login'))
    
    # 如果已设置借用人名称，跳转到首页
    if user.borrower_name:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        borrower_name = request.form.get('borrower_name', '').strip()
        
        if not borrower_name:
            return render_template('set_borrower_name.html', error='借用人名称不能为空')
        
        # 检查是否已存在
        if api_client.update_user_borrower_name(user_id, borrower_name):
            return redirect(url_for('home'))
        else:
            return render_template('set_borrower_name.html', error='该借用人名称已被使用，请更换')
    
    return render_template('set_borrower_name.html', phone=user.phone)


@app.route('/home')
@login_required
def home():
    """用户首页"""
    from datetime import datetime
    user = get_current_user()
    
    # 获取用户当前借用的设备（使用借用人名称匹配）
    borrowed_devices = []
    for device in api_client.get_all_devices():
        if device.borrower == user['borrower_name'] and device.status == DeviceStatus.BORROWED:
            # 计算逾期天数
            overdue_days = 0
            is_overdue = False
            if device.expected_return_date:
                if datetime.now().date() > device.expected_return_date.date():
                    overdue_days = (datetime.now().date() - device.expected_return_date.date()).days
                    is_overdue = True
            
            borrowed_devices.append({
                'id': device.id,
                'name': device.name,
                'type': '车机' if isinstance(device, CarMachine) else '手机',
                'status': device.status.value,
                'expected_return_date': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else None,
                'is_overdue': is_overdue,
                'overdue_days': overdue_days
            })
    
    return render_template('home.html', 
                         user=user,
                         phone_mask=mask_phone(user['phone']),
                         borrowed_devices=borrowed_devices)


@app.route('/devices')
@login_required
def device_list():
    """设备列表页"""
    device_type = request.args.get('type', '')  # 'car' 或 'phone'
    no_cabinet = request.args.get('no_cabinet', '')  # '1' 表示只显示无柜号设备
    page = request.args.get('page', 1, type=int)  # 当前页码
    per_page = 12  # 每页显示数量
    
    # 获取设备列表（隐藏敏感信息）
    filter_type = None
    if device_type == 'car':
        filter_type = '车机'
    elif device_type == 'phone':
        filter_type = '手机'
    
    devices = api_client.get_all_devices(filter_type)
    device_list = []
    
    for device in devices:
        cabinet = device.cabinet_number or ''
        is_no_cabinet = not cabinet.strip()
        is_circulating = cabinet.strip() == '流通'
        
        # 如果是无柜号筛选，只显示柜号为空的设备
        if no_cabinet == '1':
            if not is_no_cabinet:
                continue
        
        device_list.append({
            'id': device.id,
            'name': device.name,
            'type': '车机' if isinstance(device, CarMachine) else '手机',
            'status': device.status.value,
            'remark': device.remark or '-',
            'no_cabinet': is_no_cabinet,  # 标记是否为无柜号设备
            'is_circulating': is_circulating  # 标记是否为流通设备
        })
    
    # 分页逻辑
    total = len(device_list)
    total_pages = (total + per_page - 1) // per_page  # 向上取整
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    paginated_devices = device_list[start:end]
    
    return render_template('device_list.html', 
                         devices=paginated_devices,
                         device_type=device_type,
                         no_cabinet=no_cabinet == '1',
                         page=page,
                         total_pages=total_pages,
                         total=total)


@app.route('/device/<device_id>')
@login_required
def device_detail(device_id):
    """设备详情页"""
    user = get_current_user()
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    # 检查设备是否已报废
    if device.status == DeviceStatus.SCRAPPED:
        return render_template('error.html', message='设备已报废，请联系管理员'), 403
    
    # 记录查看记录
    api_client.add_view_record(device_id, user['borrower_name'])
    
    # 获取设备备注
    remarks = api_client.get_remarks(device_id)
    remark_list = []
    for remark in remarks:
        remark_list.append({
            'id': remark.id,
            'content': remark.content,
            'creator': remark.creator,
            'create_time': remark.create_time.strftime('%Y-%m-%d %H:%M'),
            'is_creator': remark.creator == user['borrower_name']
        })
    
    # 获取借用记录
    records = api_client.get_records(device_name=device.name)
    record_list = []
    for record in records[:50]:  # 显示最近50条
        record_list.append({
            'operation_type': record.operation_type.value,
            'borrower': record.borrower,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'entry_source': record.entry_source,
        })
    
    # 获取查看记录
    view_records = api_client.get_view_records(device_id, limit=50)
    view_record_list = []
    for vr in view_records:
        view_record_list.append({
            'viewer': vr.viewer,
            'view_time': vr.view_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # 判断页面显示情况
    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']  # 是否是保管人
    
    # 计算是否超时
    is_overdue = False
    overdue_days = 0
    if device.expected_return_date and device.status.value == '借出':
        from datetime import date
        today = date.today()
        if today > device.expected_return_date.date():
            is_overdue = True
            overdue_days = (today - device.expected_return_date.date()).days
    
    return render_template('device_detail.html',
                         device=device,
                         device_type='车机' if isinstance(device, CarMachine) else '手机',
                         is_borrower=is_borrower,
                         is_custodian=is_custodian,
                         is_overdue=is_overdue,
                         overdue_days=overdue_days,
                         remarks=remark_list,
                         records=record_list,
                         view_records=view_record_list,
                         user=user)


@app.route('/device/<device_id>/simple')
@login_required
def device_detail_simple(device_id):
    """无柜号/流通设备详情页（只显示基本信息，无借用功能）"""
    user = get_current_user()
    api_client.reload_data()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    cabinet = device.cabinet_number or ''
    is_no_cabinet = not cabinet.strip()
    is_circulating = cabinet.strip() == '流通'
    
    # 检查是否真的是无柜号或流通设备
    if not is_no_cabinet and not is_circulating:
        # 正常设备跳转到正常详情页
        return redirect(url_for('device_detail', device_id=device_id))
    
    # 记录查看记录
    api_client.add_view_record(device_id, user['borrower_name'])
    
    # 获取设备备注
    remarks = api_client.get_remarks(device_id)
    remark_list = []
    for remark in remarks:
        remark_list.append({
            'id': remark.id,
            'content': remark.content,
            'creator': remark.creator,
            'create_time': remark.create_time.strftime('%Y-%m-%d %H:%M'),
            'is_creator': remark.creator == user['borrower_name']
        })
    
    # 获取查看记录
    view_records = api_client.get_view_records(device_id, limit=50)
    view_record_list = []
    for vr in view_records:
        view_record_list.append({
            'viewer': vr.viewer,
            'view_time': vr.view_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return render_template('device_detail_simple.html',
                         device=device,
                         device_type='车机' if isinstance(device, CarMachine) else '手机',
                         remarks=remark_list,
                         view_records=view_record_list,
                         is_circulating=is_circulating)


@app.route('/borrow/<device_id>')
@login_required
def borrow_page(device_id):
    """借用登记页"""
    user = get_current_user()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    if device.status != DeviceStatus.IN_STOCK:
        return render_template('error.html', message='该设备已被借出'), 400
    
    return render_template('borrow.html',
                         device=device,
                         device_type='车机' if isinstance(device, CarMachine) else '手机',
                         user=user,
                         phone_mask=mask_phone(user['phone']))


@app.route('/return/<device_id>')
@login_required
def return_page(device_id):
    """归还确认页"""
    user = get_current_user()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    if device.status != DeviceStatus.BORROWED:
        return render_template('error.html', message='该设备未借出'), 400
    
    # 检查是否为借用人（只有借用人才能归还）
    is_borrower = device.borrower == user['borrower_name']
    
    if not is_borrower:
        return render_template('error.html', message='您无权归还此设备'), 403
    
    return render_template('return.html',
                         device=device,
                         device_type='车机' if isinstance(device, CarMachine) else '手机',
                         user=user,
                         is_borrower=is_borrower)


@app.route('/transfer/<device_id>')
@login_required
def transfer_page(device_id):
    """转借页面"""
    user = get_current_user()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    if device.status != DeviceStatus.BORROWED:
        return render_template('error.html', message='该设备未借出'), 400
    
    # 只有当前借用人可以转借
    if device.borrower != user['borrower_name']:
        return render_template('error.html', message='您无权转借此设备'), 403
    
    # 获取所有用户列表（排除自己）
    all_users = []
    for u in api_client._users:
        if u.borrower_name and u.borrower_name != user['borrower_name']:
            all_users.append({
                'borrower_name': u.borrower_name,
                'phone': u.phone
            })
    
    return render_template('transfer.html',
                         device=device,
                         device_type='车机' if isinstance(device, CarMachine) else '手机',
                         all_users=all_users)


@app.route('/remark/add/<device_id>')
@login_required
def add_remark_page(device_id):
    """添加备注页"""
    device = api_client.get_device_by_id(device_id)
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    return render_template('remark_add.html', 
                         device=device,
                         device_type='车机' if isinstance(device, CarMachine) else '手机')


@app.route('/remark/edit/<remark_id>')
@login_required
def edit_remark_page(remark_id):
    """编辑备注页"""
    # 查找备注
    remark = None
    for r in api_client.get_remarks():
        if r.id == remark_id:
            remark = r
            break
    
    if not remark:
        return render_template('error.html', message='备注不存在'), 404
    
    user = get_current_user()
    if remark.creator != user['borrower_name']:
        return render_template('error.html', message='您无权编辑此备注'), 403
    
    device = api_client.get_device_by_id(remark.device_id)
    
    return render_template('remark_edit.html', remark=remark, device=device)


@app.route('/my-records')
@login_required
def my_records():
    """我的借用记录"""
    user = get_current_user()

    # 获取该用户的所有记录
    all_records = api_client.get_records()
    user_records = []
    for r in all_records:
        # 1. 普通借用/归还/损坏/丢失记录 - 当前用户是借用人
        if r.borrower == user['borrower_name']:
            user_records.append(r)
        # 2. 转借记录（操作人是当前用户）
        elif r.operator == user['borrower_name'] and r.operation_type.value == '转借':
            user_records.append(r)
        # 3. 被转借记录（借用人字段包含当前用户名）
        elif user['borrower_name'] in r.borrower and ('转借' in r.borrower or '被转借' in r.borrower):
            user_records.append(r)

    # 按时间倒序排列（时间相同的按记录ID排序确保稳定）
    user_records.sort(key=lambda x: (x.operation_time, x.id), reverse=True)

    record_list = []
    for record in user_records:
        record_list.append({
            'device_name': record.device_name,
            'device_type': record.device_type,
            'operation_type': record.operation_type.value,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'borrower': record.borrower,
            'reason': record.reason,
            'remark': record.remark
        })

    return render_template('my_records.html',
                         records=record_list,
                         user=user)


# ==================== API 接口 ====================

@app.route('/api/borrow', methods=['POST'])
@login_required
def api_borrow():
    """借用设备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    reason = data.get('reason', '')
    expected_return_date = data.get('expected_return_date', '')
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status == DeviceStatus.SHIPPED:
        return jsonify({'success': False, 'message': '设备已寄出，暂不可借用'})
    
    if device.status == DeviceStatus.DAMAGED:
        return jsonify({'success': False, 'message': '设备已损坏，暂不可借用'})
    
    if device.status != DeviceStatus.IN_STOCK:
        return jsonify({'success': False, 'message': '设备已被借出'})
    
    # 更新设备信息
    device.status = DeviceStatus.BORROWED
    device.borrower = user['borrower_name']
    device.phone = user['phone']
    device.borrow_time = datetime.now()
    device.reason = reason
    device.entry_source = EntrySource.USER.value
    if expected_return_date:
        device.expected_return_date = datetime.strptime(expected_return_date, '%Y-%m-%d')
    
    api_client.update_device(device)
    
    # 解析原因和备注（格式：原因 - 详细说明）
    reason_parts = reason.split(' - ', 1)
    reason_main = reason_parts[0] if reason_parts else reason
    remark_text = reason_parts[1] if len(reason_parts) > 1 else ''
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.BORROW,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=user['borrower_name'],
        phone=user['phone'],
        reason=reason_main,
        remark=remark_text,
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    # 添加操作日志并保存数据
    api_client.add_operation_log(f"用户借用: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '借用成功'})


@app.route('/api/return', methods=['POST'])
@login_required
def api_return():
    """归还设备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    return_reason_full = data.get('reason', '设备完好，无异常')
    
    # 解析归还原因和备注（格式：原因 - 备注）
    reason_parts = return_reason_full.split(' - ', 1)
    reason_main = reason_parts[0] if reason_parts else return_reason_full
    remark_text = reason_parts[1] if len(reason_parts) > 1 else ''
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备未借出'})
    
    # 检查权限
    is_borrower = device.borrower == user['borrower_name']
    is_admin_entry = device.entry_source == EntrySource.ADMIN.value
    
    if not is_borrower and not is_admin_entry:
        return jsonify({'success': False, 'message': '无权归还此设备'})
    
    borrower = device.borrower
    
    # 清空借用信息
    device.status = DeviceStatus.IN_STOCK
    device.borrower = ''
    device.phone = ''
    device.borrow_time = None
    device.reason = ''
    device.entry_source = ''
    device.expected_return_date = None
    device.previous_borrower = ''  # 清空上一个借用人
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.RETURN,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=borrower,
        reason=reason_main,
        remark=remark_text
    )
    api_client._records.append(record)
    
    # 添加操作日志并保存数据
    api_client.add_operation_log(f"用户归还: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '归还成功'})


@app.route('/api/transfer', methods=['POST'])
@login_required
def api_transfer():
    """转借设备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    transfer_to = data.get('transfer_to', '').strip()
    location = data.get('location', '').strip()
    reason = data.get('reason', '').strip()
    expected_return_date = data.get('expected_return_date', '')
    
    if not device_id or not transfer_to:
        return jsonify({'success': False, 'message': '请选择转借人'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备未借出，无法转借'})
    
    # 只有当前借用人可以转借
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '您无权转借此设备'})
    
    # 获取转借人的手机号
    transfer_phone = ''
    for u in api_client._users:
        if u.borrower_name == transfer_to:
            transfer_phone = u.phone
            break
    
    original_borrower = device.borrower
    remark = data.get('remark', '')
    
    # 更新设备信息为新的借用人
    device.borrower = transfer_to
    device.phone = transfer_phone
    device.entry_source = EntrySource.USER.value
    
    api_client.update_device(device)
    
    # 添加转借记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.TRANSFER,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"转借：{original_borrower}——>{transfer_to}",
        phone=transfer_phone,
        reason=remark or '用户转借',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    # 添加操作日志并保存数据
    api_client.add_operation_log(f"转借：{original_borrower}——>{transfer_to}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '转借成功'})


@app.route('/api/remark/add', methods=['POST'])
@login_required
def api_add_remark():
    """添加备注API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'message': '备注内容不能为空'})
    
    remark = UserRemark(
        id=str(uuid.uuid4()),
        device_id=device_id,
        content=content,
        creator=user['borrower_name'],
        create_time=datetime.now()
    )
    api_client._remarks.append(remark)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '备注已添加'})


@app.route('/api/transfer-to-me', methods=['POST'])
@login_required
def api_transfer_to_me():
    """转给自己API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备未借出，无法转借'})
    
    # 不能转借给自己
    if device.borrower == user['borrower_name']:
        return jsonify({'success': False, 'message': '该设备已在您名下'})
    
    original_borrower = device.borrower
    
    # 保存上一个借用人
    device.previous_borrower = device.borrower
    
    # 更新设备信息为当前用户
    device.borrower = user['borrower_name']
    device.phone = user['phone']
    device.entry_source = EntrySource.USER.value
    
    api_client.update_device(device)
    
    # 添加转借记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.TRANSFER,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"被转借：{original_borrower}——>{user['borrower_name']}",
        phone=user['phone'],
        reason='用户转借给自己',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    # 添加操作日志并保存数据
    api_client.add_operation_log(f"被转借：{original_borrower}——>{user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '转借成功'})


@app.route('/api/return-by-custodian', methods=['POST'])
@login_required
def api_return_by_custodian():
    """保管人收回借用API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备未借出，无法收回'})
    
    # 验证当前用户是保管人
    if device.cabinet_number != user['borrower_name']:
        return jsonify({'success': False, 'message': '只有保管人才能收回设备'})
    
    original_borrower = device.borrower
    
    # 归还设备
    device.status = DeviceStatus.IN_STOCK
    device.borrower = ''
    device.phone = ''
    device.borrow_time = None
    device.location = ''
    device.reason = ''
    device.entry_source = ''
    device.expected_return_date = None
    device.previous_borrower = ''  # 清空上一个借用人
    
    api_client.update_device(device)
    
    # 添加归还记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.RETURN,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=original_borrower,
        phone='',
        reason='保管人收回',
        entry_source='保管人收回'
    )
    api_client._records.append(record)
    
    # 添加操作日志并保存数据
    api_client.add_operation_log(f"保管人收回: {original_borrower}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '收回成功'})


@app.route('/api/remark/edit', methods=['POST'])
@login_required
def api_edit_remark():
    """编辑备注API"""
    user = get_current_user()
    data = request.json
    
    remark_id = data.get('remark_id')
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'message': '备注内容不能为空'})
    
    # 查找并更新备注
    for remark in api_client._remarks:
        if remark.id == remark_id:
            if remark.creator != user['borrower_name']:
                return jsonify({'success': False, 'message': '无权编辑此备注'})
            remark.content = content
            api_client._save_data()
            return jsonify({'success': True, 'message': '备注已更新'})
    
    return jsonify({'success': False, 'message': '备注不存在'})


@app.route('/api/remark/delete', methods=['POST'])
@login_required
def api_delete_remark():
    """删除备注API"""
    user = get_current_user()
    data = request.json
    
    remark_id = data.get('remark_id')
    
    # 查找并删除备注
    for i, remark in enumerate(api_client._remarks):
        if remark.id == remark_id:
            if remark.creator != user['borrower_name']:
                return jsonify({'success': False, 'message': '无权删除此备注'})
            del api_client._remarks[i]
            api_client._save_data()
            return jsonify({'success': True, 'message': '备注已删除'})
    
    return jsonify({'success': False, 'message': '备注不存在'})


@app.route('/api/search')
@login_required
def api_search():
    """搜索设备API"""
    keyword = request.args.get('keyword', '').strip()
    
    devices = api_client.get_all_devices()
    result = []
    
    for device in devices:
        # 处理设备名中的换行符和多余空格
        device_name_normalized = device.name.lower().replace('\n', ' ').replace('  ', ' ').strip()
        if not keyword or keyword.lower() in device_name_normalized or \
           keyword.lower() in (device.model or '').lower() or \
           keyword.lower() in (device.remark or '').lower():
            cabinet = device.cabinet_number or ''
            result.append({
                'id': device.id,
                'name': device.name,
                'type': '车机' if isinstance(device, CarMachine) else '手机',
                'status': device.status.value,
                'remark': device.remark or '-',
                'is_scrapped': device.status == DeviceStatus.SCRAPPED,
                'no_cabinet': not cabinet.strip(),
                'is_circulating': cabinet.strip() == '流通'
            })
    
    return jsonify({'success': True, 'devices': result})


@app.route('/api/users')
@login_required
def api_users():
    """获取用户列表API"""
    user = get_current_user()
    users = []
    for u in api_client._users:
        if u.borrower_name and u.borrower_name != user['borrower_name'] and not u.is_frozen:
            users.append({
                'borrower_name': u.borrower_name,
                'phone': u.phone
            })
    return jsonify({'success': True, 'users': users})


@app.route('/api/report-lost', methods=['POST'])
@login_required
def api_report_lost():
    """丢失报备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '只有借出状态的设备可以报备丢失'})
    
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '只有借用人可以报备丢失'})
    
    # 保存上一个借用人
    device.previous_borrower = device.borrower
    # 更新状态为丢失
    device.status = DeviceStatus.LOST
    device.lost_time = datetime.now()
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.REPORT_LOST,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"丢失报备：{user['borrower_name']}",
        phone=device.phone,
        reason='丢失报备',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"丢失报备: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '丢失报备成功'})


@app.route('/api/report-damage', methods=['POST'])
@login_required
def api_report_damage():
    """损坏报备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    damage_reason = data.get('damage_reason', '').strip()
    
    if not damage_reason:
        return jsonify({'success': False, 'message': '请填写损坏原因'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '只有借出状态的设备可以报备损坏'})
    
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '只有借用人可以报备损坏'})
    
    # 保存上一个借用人
    device.previous_borrower = device.borrower
    # 更新状态为损坏
    device.status = DeviceStatus.DAMAGED
    device.damage_reason = damage_reason
    device.damage_time = datetime.now()
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.REPORT_DAMAGE,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=device.borrower,
        phone=device.phone,
        reason=f'损坏原因：{damage_reason}',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"损坏报备: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '损坏报备成功'})


@app.route('/api/found-device', methods=['POST'])
@login_required
def api_found_device():
    """我已找到（丢失设备恢复）API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    action = data.get('action', '')  # 'keep', 'return', 'transfer'
    transfer_to = data.get('transfer_to', '')
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.LOST:
        return jsonify({'success': False, 'message': '设备不是丢失状态'})
    
    original_borrower = device.borrower
    
    if action == 'keep':
        # 转给自己，保持借出状态
        device.status = DeviceStatus.BORROWED
        device.borrower = user['borrower_name']
        device.phone = user['phone']
        device.lost_time = None
    elif action == 'return':
        # 归还入库
        device.status = DeviceStatus.IN_STOCK
        device.borrower = ''
        device.phone = ''
        device.borrow_time = None
        device.location = ''
        device.reason = ''
        device.entry_source = ''
        device.expected_return_date = None
        device.lost_time = None
        device.previous_borrower = ''  # 清空上一个借用人
    elif action == 'transfer':
        if not transfer_to:
            return jsonify({'success': False, 'message': '请选择转借人'})
        # 转给别人
        transfer_phone = ''
        for u in api_client._users:
            if u.borrower_name == transfer_to:
                transfer_phone = u.phone
                break
        device.status = DeviceStatus.BORROWED
        device.borrower = transfer_to
        device.phone = transfer_phone
        device.lost_time = None
    else:
        return jsonify({'success': False, 'message': '无效的操作'})
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.FOUND,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"找回：{original_borrower}——>{device.borrower}" if action != 'return' else f"找回并归还：{original_borrower}",
        phone=device.phone,
        reason='设备已找到',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"设备找回: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '操作成功'})


@app.route('/api/repair-device', methods=['POST'])
@login_required
def api_repair_device():
    """我已修好（损坏设备恢复）API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    action = data.get('action', '')  # 'keep', 'return', 'transfer'
    transfer_to = data.get('transfer_to', '')
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.DAMAGED:
        return jsonify({'success': False, 'message': '设备不是损坏状态'})
    
    original_borrower = device.borrower
    
    if action == 'keep':
        # 转给自己，保持借出状态
        device.status = DeviceStatus.BORROWED
        device.borrower = user['borrower_name']
        device.phone = user['phone']
        device.damage_reason = ''
        device.damage_time = None
    elif action == 'return':
        # 归还入库
        device.status = DeviceStatus.IN_STOCK
        device.borrower = ''
        device.phone = ''
        device.borrow_time = None
        device.location = ''
        device.reason = ''
        device.entry_source = ''
        device.expected_return_date = None
        device.damage_reason = ''
        device.damage_time = None
        device.previous_borrower = ''  # 清空上一个借用人
    elif action == 'transfer':
        if not transfer_to:
            return jsonify({'success': False, 'message': '请选择转借人'})
        # 转给别人
        transfer_phone = ''
        for u in api_client._users:
            if u.borrower_name == transfer_to:
                transfer_phone = u.phone
                break
        device.status = DeviceStatus.BORROWED
        device.borrower = transfer_to
        device.phone = transfer_phone
        device.damage_reason = ''
        device.damage_time = None
    else:
        return jsonify({'success': False, 'message': '无效的操作'})
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.REPAIRED,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"修复：{original_borrower}——>{device.borrower}" if action != 'return' else f"修复并归还：{original_borrower}",
        phone=device.phone,
        reason='设备已修复',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"设备修复: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '操作成功'})


@app.route('/api/not-found', methods=['POST'])
@login_required
def api_not_found():
    """未找到（转给自己后的退回）API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '只有当前借用人可以操作'})
    
    previous_borrower = device.previous_borrower
    
    if previous_borrower:
        # 有上一个借用人，转回给他
        # 获取上一个借用人的手机号
        prev_phone = ''
        for u in api_client._users:
            if u.borrower_name == previous_borrower:
                prev_phone = u.phone
                break
        
        device.borrower = previous_borrower
        device.phone = prev_phone
        device.previous_borrower = ''  # 清空上一个借用人
        
        api_client.update_device(device)
        
        # 添加记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.TRANSFER,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"未找到退回：{user['borrower_name']}——>{previous_borrower}",
            phone=prev_phone,
            reason='设备未找到，退回给上一个借用人',
            entry_source=EntrySource.USER.value
        )
        api_client._records.append(record)
        api_client.add_operation_log(f"未找到退回: {user['borrower_name']} -> {previous_borrower}", device.name)
    else:
        # 没有上一个借用人，转为丢失状态
        device.status = DeviceStatus.LOST
        device.previous_borrower = device.borrower
        device.lost_time = datetime.now()
        
        api_client.update_device(device)
        
        # 添加记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.REPORT_LOST,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"未找到转丢失：{user['borrower_name']}",
            phone=device.phone,
            reason='设备未找到，转为丢失状态',
            entry_source=EntrySource.USER.value
        )
        api_client._records.append(record)
        api_client.add_operation_log(f"未找到转丢失: {user['borrower_name']}", device.name)
    
    api_client._save_data()
    return jsonify({'success': True, 'message': '操作成功'})


@app.route('/api/not-found-direct', methods=['POST'])
@login_required
def api_not_found_direct():
    """未找到报备API - 记录借用人未找到，同时设备转为丢失状态"""
    user = get_current_user()
    data = request.json

    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)

    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})

    # 借用中设备：需要是当前借用人
    if device.status == DeviceStatus.BORROWED:
        if device.borrower != user['borrower_name']:
            return jsonify({'success': False, 'message': '只有当前借用人可以操作'})

        # 设备转为丢失状态
        device.status = DeviceStatus.LOST
        device.previous_borrower = device.borrower
        device.lost_time = datetime.now()

        api_client.update_device(device)

        # 添加记录：借用人未找到
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.NOT_FOUND,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=user['borrower_name'],
            phone='',
            reason='借用人未找到设备，设备转为丢失状态',
            entry_source=EntrySource.USER.value
        )
        api_client._records.append(record)
        api_client.add_operation_log(f"借用人未找到，设备转丢失: {device.name}", device.name)

        api_client._save_data()
        return jsonify({'success': True, 'message': '已记录：借用人未找到，设备已转为丢失状态'})

    return jsonify({'success': False, 'message': '设备状态异常'})


@app.route('/api/transfer-custodian', methods=['POST'])
@login_required
def api_transfer_custodian():
    """手机保管人转让API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    new_custodian = data.get('new_custodian', '').strip()
    
    if not new_custodian:
        return jsonify({'success': False, 'message': '请选择新的保管人'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if not isinstance(device, Phone):
        return jsonify({'success': False, 'message': '只有手机可以转让保管人'})
    
    if device.cabinet_number != user['borrower_name']:
        return jsonify({'success': False, 'message': '只有当前保管人可以转让'})
    
    old_custodian = device.cabinet_number
    device.cabinet_number = new_custodian
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='手机',
        operation_type=OperationType.CUSTODIAN_CHANGE,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=device.borrower,
        reason=f'保管人变更：{old_custodian}——>{new_custodian}',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"保管人变更: {old_custodian} -> {new_custodian}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '保管人转让成功'})


@app.route('/api/renew', methods=['POST'])
@login_required
def api_renew():
    """借用续期API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    new_return_date = data.get('new_return_date', '').strip()
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    if not new_return_date:
        return jsonify({'success': False, 'message': '请选择续期日期'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '只有借出状态的设备可以续期'})
    
    # 只有当前借用人可以续期
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '只有借用人可以续期'})
    
    # 验证新日期是否有效（不能早于今天）
    try:
        new_date = datetime.strptime(new_return_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        if new_date < today:
            return jsonify({'success': False, 'message': '续期日期不能早于今天'})
    except ValueError:
        return jsonify({'success': False, 'message': '日期格式不正确'})
    
    # 保存旧的预计归还日期用于记录
    old_return_date = device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else '无'
    
    # 更新预计归还日期
    device.expected_return_date = datetime.strptime(new_return_date, '%Y-%m-%d')
    api_client.update_device(device)
    
    # 添加续期记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.RENEW,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=user['borrower_name'],
        phone=user['phone'],
        reason=f'借用续期：{old_return_date} → {new_return_date}',
        remark='',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"借用续期: {user['borrower_name']}, 新归还日期: {new_return_date}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': f'续期成功，新的预计归还日期：{new_return_date}'})


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message='页面未找到'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message='服务器内部错误'), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
