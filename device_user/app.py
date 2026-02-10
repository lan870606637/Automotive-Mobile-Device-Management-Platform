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

# 从 common 导入模型和API客户端
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.models import DeviceStatus, DeviceType, OperationType, EntrySource, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, ViewRecord
from common.api_client import api_client

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
    """登录验证装饰器 - 未登录跳转到设备选择页面"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
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
        return {
            'user_id': user.id,
            'wechat_name': user.wechat_name,
            'phone': user.phone,
            'borrower_name': user.borrower_name,
            'is_admin': user.is_admin,
        }
    return {}


def is_admin_user(borrower_name):
    """检查指定借用人是否为管理员"""
    return api_client.is_user_admin(borrower_name)


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



def get_device_stats():
    """获取设备统计数据"""
    api_client.reload_data()
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]])
    borrowed_devices_count = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])
    return {
        'total_devices': total_devices,
        'available_devices': available_devices,
        'borrowed_devices_count': borrowed_devices_count
    }


def get_default_status_for_device(device):
    """根据设备类型获取默认状态（在库/保管中）"""
    if isinstance(device, (Phone, SimCard, OtherDevice)):
        return DeviceStatus.IN_CUSTODY
    return DeviceStatus.IN_STOCK


@app.context_processor
def inject_globals():
    """注入全局模板变量和函数"""
    return {
        'is_admin_user': is_admin_user,
    }


def mask_phone(phone):
    """手机号脱敏显示"""
    if len(phone) == 11:
        return phone[:3] + '****' + phone[7:]
    return phone


def is_mobile_device():
    """检测是否为移动设备"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'wechat', 'micromessenger', 'windows phone']
    return any(keyword in user_agent for keyword in mobile_keywords)


def device_route(mobile_route, pc_route):
    """根据设备类型返回对应的路由"""
    if is_mobile_device():
        return redirect(url_for(mobile_route))
    return redirect(url_for(pc_route))


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页 - 根据设备类型自动跳转"""
    if 'user_id' in session:
        # 根据session中保存的登录设备类型跳转
        login_device_type = session.get('login_device_type', 'mobile')
        if login_device_type == 'pc':
            return redirect(url_for('pc_dashboard'))
        else:
            return redirect(url_for('home'))
    # 未登录用户先跳转到设备选择页面
    return redirect(url_for('select_device_type'))


@app.route('/select-device')
def select_device_type():
    """设备选择页面 - 选择手机端或电脑端"""
    return render_template('select_device_type.html')


@app.route('/login/mobile', methods=['GET', 'POST'])
def mobile_login():
    """手机端登录页面 - 带二维码"""
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()

        if not phone or not password:
            return render_template('mobile/login.html', error='请输入手机号和密码')

        user = api_client.verify_user_login(phone, password)
        if user:
            session['user_id'] = user.id
            session['phone'] = user.phone
            session['login_device_type'] = 'mobile'  # 记录登录设备类型

            # 检查是否需要设置借用人名称
            if not user.borrower_name:
                return redirect(url_for('set_borrower_name'))

            return redirect(url_for('home'))
        else:
            return render_template('mobile/login.html', error='手机号或密码错误，或账号已被冻结')

    return render_template('mobile/login.html')


@app.route('/login/pc', methods=['GET', 'POST'])
def pc_login():
    """电脑端登录页面 - 不带二维码"""
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()

        if not phone or not password:
            return render_template('pc/login.html', error='请输入手机号和密码')

        user = api_client.verify_user_login(phone, password)
        if user:
            session['user_id'] = user.id
            session['phone'] = user.phone
            session['login_device_type'] = 'pc'  # 记录登录设备类型

            # 检查是否需要设置借用人名称
            if not user.borrower_name:
                return redirect(url_for('set_borrower_name'))

            return redirect(url_for('pc_dashboard'))
        else:
            return render_template('pc/login.html', error='手机号或密码错误，或账号已被冻结')

    return render_template('pc/login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录页面 - 兼容旧版，重定向到设备选择页面"""
    return redirect(url_for('select_device_type'))


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
            return render_template('register.html', success='注册成功，请前往设备选择页面登录')
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
    """退出登录 - 跳转到设备选择页面"""
    session.clear()
    return redirect(url_for('select_device_type'))


@app.route('/set-borrower-name', methods=['GET', 'POST'])
def set_borrower_name():
    """设置借用人名称（首次登录）"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('select_device_type'))
    
    # 获取用户信息
    user = None
    for u in api_client._users:
        if u.id == user_id:
            user = u
            break
    
    if not user:
        return redirect(url_for('select_device_type'))
    
    # 根据登录设备类型决定跳转目标
    login_device_type = session.get('login_device_type', 'mobile')
    home_route = 'pc_dashboard' if login_device_type == 'pc' else 'home'
    
    # 如果已设置借用人名称，跳转到对应首页
    if user.borrower_name:
        return redirect(url_for(home_route))
    
    if request.method == 'POST':
        borrower_name = request.form.get('borrower_name', '').strip()
        
        if not borrower_name:
            return render_template('set_borrower_name.html', error='借用人名称不能为空')
        
        # 检查是否已存在
        if api_client.update_user_borrower_name(user_id, borrower_name):
            return redirect(url_for(home_route))
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
            # 计算逾期（超过1小时算逾期）
            overdue_days = 0
            overdue_hours = 0
            is_overdue = False
            if device.expected_return_date:
                time_diff = datetime.now() - device.expected_return_date
                if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                    is_overdue = True
                    overdue_hours = int(time_diff.total_seconds() // 3600)
                    overdue_days = int(time_diff.total_seconds() // (24 * 3600))

            borrowed_devices.append({
                'id': device.id,
                'name': device.name,
                'type': '车机' if isinstance(device, CarMachine) else '手机',
                'status': device.status.value,
                'expected_return_date': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else None,
                'is_overdue': is_overdue,
                'overdue_days': overdue_days,
                'overdue_hours': overdue_hours
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
        is_no_cabinet = device.status == DeviceStatus.NO_CABINET
        is_circulating = device.status == DeviceStatus.CIRCULATING
        
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

    # 获取设备类型字符串
    device_type_str = get_device_type_str(device)

    # 记录查看记录
    api_client.add_view_record(device_id, user['borrower_name'], device_type_str)

    # 获取设备备注
    remarks = api_client.get_remarks(device_id, device_type_str)
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
    records = api_client.get_records(device_type=device_type_str, device_name=device.name)
    record_list = []
    for record in records[:50]:  # 显示最近50条
        record_list.append({
            'operation_type': record.operation_type.value,
            'borrower': record.borrower,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'entry_source': record.entry_source,
            'reason': record.reason,
            'remark': record.remark,
        })

    # 获取查看记录
    view_records = api_client.get_view_records(device_id, device_type_str, limit=50)
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
    # 检查是否逾期（超过1小时算逾期）
    is_overdue = False
    overdue_days = 0
    overdue_hours = 0
    remaining_days = 0
    remaining_hours = 0
    can_renew = False
    renew_disabled_reason = ''
    if device.expected_return_date and device.status.value == '借出':
        time_diff = datetime.now() - device.expected_return_date
        if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
            is_overdue = True
            overdue_hours = int(time_diff.total_seconds() // 3600)
            overdue_days = int(time_diff.total_seconds() // (24 * 3600))
            # 逾期超过3天不能续借
            if overdue_days > 3:
                can_renew = False
                renew_disabled_reason = '逾期超过3天，不能续借'
            else:
                can_renew = True
        else:
            # 计算剩余时间
            remaining_seconds = device.expected_return_date.timestamp() - datetime.now().timestamp()
            remaining_hours = int(remaining_seconds // 3600)
            remaining_days = int(remaining_seconds // (24 * 3600))
            # 剩余时间小于24小时才能续借
            can_renew = remaining_hours < 24
            if not can_renew:
                renew_disabled_reason = '剩余时间大于24小时，暂不需要续借'

    return render_template('device_detail.html',
                         device=device,
                         device_type=get_device_type_str(device),
                         is_borrower=is_borrower,
                         is_custodian=is_custodian,
                         is_overdue=is_overdue,
                         overdue_days=overdue_days,
                         overdue_hours=overdue_hours,
                         remaining_days=remaining_days,
                         remaining_hours=remaining_hours,
                         can_renew=can_renew,
                         renew_disabled_reason=renew_disabled_reason,
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

    is_no_cabinet = device.status == DeviceStatus.NO_CABINET
    is_circulating = device.status == DeviceStatus.CIRCULATING
    
    # 检查是否真的是无柜号或流通设备
    if not is_no_cabinet and not is_circulating:
        # 正常设备跳转到正常详情页
        return redirect(url_for('device_detail', device_id=device_id))

    # 获取设备类型字符串
    device_type_str = get_device_type_str(device)

    # 记录查看记录
    api_client.add_view_record(device_id, user['borrower_name'], device_type_str)

    # 获取设备备注
    remarks = api_client.get_remarks(device_id, device_type_str)
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
    view_records = api_client.get_view_records(device_id, device_type_str, limit=50)
    view_record_list = []
    for vr in view_records:
        view_record_list.append({
            'viewer': vr.viewer,
            'view_time': vr.view_time.strftime('%Y-%m-%d %H:%M:%S')
        })

    return render_template('device_detail_simple.html',
                         device=device,
                         device_type=device_type_str,
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
    
    if device.status not in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]:
        return render_template('error.html', message='该设备已被借出'), 400
    
    return render_template('borrow.html',
                         device=device,
                         device_type=get_device_type_str(device),
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
                         device_type=get_device_type_str(device),
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
                         device_type=get_device_type_str(device),
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
                         device_type=get_device_type_str(device))


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
    
    # 分页逻辑 - 每页20条
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total_records = len(record_list)
    total_pages = (total_records + per_page - 1) // per_page
    
    # 确保页码有效
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    # 切片获取当前页数据
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = record_list[start:end]

    return render_template('my_records.html',
                         records=paginated_records,
                         total_records=total_records,
                         page=page,
                         total_pages=total_pages,
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
    
    if device.status not in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]:
        return jsonify({'success': False, 'message': '设备已被借出'})
    
    # 检查用户借用数量限制
    user_borrowed_count = 0
    all_devices = api_client.get_all_devices()
    for d in all_devices:
        if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
            user_borrowed_count += 1
    
    borrow_limit = 10  # 最大借用数量（车机+手机）
    if user_borrowed_count >= borrow_limit:
        return jsonify({'success': False, 'message': '您已超出可借设备上限，请归还后再借'})
    
    # 计算预计归还时间
    if expected_return_date:
        # 使用前端传递的日期，时间设为当前时间
        date_part = datetime.strptime(expected_return_date, '%Y-%m-%d')
        now = datetime.now()
        device.expected_return_date = date_part.replace(hour=now.hour, minute=now.minute, second=now.second)
    
    # 更新设备信息
    device.status = DeviceStatus.BORROWED
    device.borrower = user['borrower_name']
    device.phone = user['phone']
    device.borrow_time = datetime.now()
    device.reason = reason
    device.entry_source = EntrySource.USER.value
    device.previous_borrower = ''  # 清空上一个借用人，因为从在库借用
    
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
        device_type=get_device_type_str(device),
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
    
    # 清空借用信息，根据设备类型设置默认状态
    device.status = get_default_status_for_device(device)
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
    
    # 检查不能转借给自己
    if transfer_to == user['borrower_name']:
        return jsonify({'success': False, 'message': '不能转借给自己'})
    
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
    device.expected_return_date = datetime.now() + timedelta(days=1)  # 转借后预计归还时间刷新为当前时间+1天
    
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
        reason='用户转借',
        remark=remark,
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

    # 获取设备
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})

    # 获取设备类型
    device_type = get_device_type_str(device)

    remark = UserRemark(
        id=str(uuid.uuid4()),
        device_id=device_id,
        device_type=device_type,
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
    
    # 检查用户借用数量限制
    user_borrowed_count = 0
    all_devices = api_client.get_all_devices()
    for d in all_devices:
        if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
            user_borrowed_count += 1
    
    borrow_limit = 10  # 最大借用数量（车机+手机）
    if user_borrowed_count >= borrow_limit:
        return jsonify({'success': False, 'message': f'您已借用 {user_borrowed_count} 台设备，达到上限 ({borrow_limit}台)，无法接受转借'})
    
    original_borrower = device.borrower
    
    # 保存上一个借用人
    device.previous_borrower = device.borrower
    
    # 更新设备信息为当前用户
    device.borrower = user['borrower_name']
    device.phone = user['phone']
    device.entry_source = EntrySource.USER.value
    device.expected_return_date = datetime.now() + timedelta(days=1)  # 转借后预计归还时间刷新为当前时间+1天
    
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
    
    # 归还设备，根据设备类型设置默认状态
    device.status = get_default_status_for_device(device)
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
        device_type=get_device_type_str(device),
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
                'device_type': '车机' if isinstance(device, CarMachine) else '手机',
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
                'name': u.borrower_name,
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
        # 检查用户借用数量限制
        user_borrowed_count = 0
        all_devices = api_client.get_all_devices()
        for d in all_devices:
            if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
                user_borrowed_count += 1
        
        borrow_limit = 10  # 最大借用数量（车机+手机）
        if user_borrowed_count >= borrow_limit:
            return jsonify({'success': False, 'message': f'您已借用 {user_borrowed_count} 台设备，达到上限 ({borrow_limit}台)，无法保留设备'})
        
        # 转给自己，保持借出状态
        device.status = DeviceStatus.BORROWED
        device.borrower = user['borrower_name']
        device.phone = user['phone']
        device.lost_time = None
    elif action == 'return':
        # 归还入库，根据设备类型设置默认状态
        device.status = get_default_status_for_device(device)
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
    if action == 'return':
        borrower_desc = f"找回并归还：{original_borrower or '丢失状态'}"
    else:
        from_desc = original_borrower or '丢失状态'
        to_desc = device.borrower
        borrower_desc = f"找回：{from_desc}——>{to_desc}"
    
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.FOUND,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=borrower_desc,
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
        # 检查用户借用数量限制
        user_borrowed_count = 0
        all_devices = api_client.get_all_devices()
        for d in all_devices:
            if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
                user_borrowed_count += 1
        
        borrow_limit = 10  # 最大借用数量（车机+手机）
        if user_borrowed_count >= borrow_limit:
            return jsonify({'success': False, 'message': f'您已借用 {user_borrowed_count} 台设备，达到上限 ({borrow_limit}台)，无法保留设备'})
        
        # 转给自己，保持借出状态
        device.status = DeviceStatus.BORROWED
        device.borrower = user['borrower_name']
        device.phone = user['phone']
        device.damage_reason = ''
        device.damage_time = None
    elif action == 'return':
        # 归还入库，根据设备类型设置默认状态
        device.status = get_default_status_for_device(device)
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
        
        # 添加记录 - 使用 NOT_FOUND 类型
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.NOT_FOUND,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"未找到：{user['borrower_name']}——>{previous_borrower}",
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

        # 设备转为丢失状态，清空借用人信息
        device.status = DeviceStatus.LOST
        device.previous_borrower = device.borrower
        device.lost_time = datetime.now()
        device.borrower = ''  # 清空借用人，设备不在任何人名下
        device.phone = ''

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
            borrower='未找到：库中未找到',
            phone='',
            reason='借用人未找到设备，设备转为丢失状态，不在任何人名下',
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
    
    # 检查是否逾期超过3天
    if device.expected_return_date:
        from datetime import datetime
        now = datetime.now()
        if now > device.expected_return_date:
            overdue_days = (now.date() - device.expected_return_date.date()).days
            if overdue_days > 3:
                return jsonify({'success': False, 'message': '无法续期，设备已逾期超过3天，请先归还后再借用'})
    
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
    
    # 更新预计归还日期（使用前端日期 + 当前时间）
    date_part = datetime.strptime(new_return_date, '%Y-%m-%d')
    now = datetime.now()
    device.expected_return_date = date_part.replace(hour=now.hour, minute=now.minute, second=now.second)
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


# ==================== PC端路由 ====================

@app.route('/pc')
@login_required
def pc_dashboard():
    """PC端仪表盘"""
    from datetime import datetime
    user = get_current_user()
    
    # 获取统计数据
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    # 在库、保管、流通、无柜号都算可用
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.CIRCULATING, DeviceStatus.NO_CABINET]])
    borrowed_devices_count = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])
    
    # 获取用户当前借用的设备（排除已报废的设备）
    my_borrowed_devices = []
    for device in all_devices:
        if device.borrower == user['borrower_name'] and device.status == DeviceStatus.BORROWED:
            # 计算逾期（超过1小时算逾期）
            overdue_days = 0
            overdue_hours = 0
            is_overdue = False
            remaining_days = 0
            remaining_hours = 0
            can_renew = False
            renew_disabled_reason = ''
            if device.expected_return_date:
                time_diff = datetime.now() - device.expected_return_date
                if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                    is_overdue = True
                    overdue_hours = int(time_diff.total_seconds() // 3600)
                    overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                    # 逾期超过3天不能续借
                    if overdue_days > 3:
                        can_renew = False
                        renew_disabled_reason = '逾期超过3天，不能续借，需要归还后才能再次借用'
                    else:
                        can_renew = True
                else:
                    # 计算剩余时间
                    remaining_seconds = device.expected_return_date.timestamp() - datetime.now().timestamp()
                    remaining_hours = int(remaining_seconds // 3600)
                    remaining_days = int(remaining_seconds // (24 * 3600))
                    # 剩余时间小于24小时才能续借
                    can_renew = remaining_hours < 24
                    if not can_renew:
                        renew_disabled_reason = '剩余时间大于24小时，暂不需要续借'

            my_borrowed_devices.append({
                'id': device.id,
                'name': device.name,
                'type': '车机' if isinstance(device, CarMachine) else '手机',
                'borrow_time': device.borrow_time.strftime('%Y-%m-%d %H:%M'),
                'expected_return_date': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else None,
                'is_overdue': is_overdue,
                'overdue_days': overdue_days,
                'overdue_hours': overdue_hours,
                'remaining_days': remaining_days,
                'remaining_hours': remaining_hours,
                'can_renew': can_renew,
                'renew_disabled_reason': renew_disabled_reason
            })

    # 获取通知信息（我保管/借用但被借走的信息，最近20条）
    notifications = []
    all_records = api_client.get_records()
    for record in all_records:
        device = api_client.get_device_by_id(record.device_id)
        if not device:
            continue

        # 借出/转借相关通知
        if '借出' in record.operation_type.value or '转借' in record.operation_type.value:
            # 显示最终借用人（设备当前借用人）
            final_borrower = device.borrower if device.borrower else record.borrower
            item = {
                'device_name': device.name,
                'device_type': get_device_type_str(device),
                'borrower': final_borrower,
                'time': record.operation_time,
                'type': ''
            }
            # 我保管的设备被别人借走（排除自己操作的）
            if device.cabinet_number == user['borrower_name'] and device.borrower and device.borrower != user['borrower_name'] and record.borrower != user['borrower_name']:
                item['type'] = '保管-被动'
                notifications.append(item)
            # 我正在借用的设备被别人转借走（排除自己操作的）
            elif hasattr(device, 'previous_borrower') and device.previous_borrower == user['borrower_name'] and device.borrower and device.borrower != user['borrower_name'] and record.borrower != user['borrower_name']:
                item['type'] = '借用-被动'
                notifications.append(item)
            # 我主动转借给别人（自己操作的转借）
            elif hasattr(device, 'previous_borrower') and device.previous_borrower == user['borrower_name'] and device.borrower and device.borrower != user['borrower_name'] and record.borrower == user['borrower_name']:
                item['type'] = '借用-主动'
                notifications.append(item)

        # 处理报废通知 - 如果我是该设备的借用人
        elif '报废' in record.operation_type.value:
            # 检查报废记录中的借用人是否是当前用户
            if record.borrower == user['borrower_name']:
                item = {
                    'device_name': device.name,
                    'device_type': get_device_type_str(device),
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '设备报废'
                }
                notifications.append(item)

        # 处理状态变更通知 - 如果我是该设备的借用人或保管人
        elif '状态变更' in record.operation_type.value:
            if record.borrower == user['borrower_name']:
                item = {
                    'device_name': device.name,
                    'device_type': get_device_type_str(device),
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '状态变更',
                    'reason': record.reason
                }
                notifications.append(item)
            elif device.cabinet_number == user['borrower_name']:
                item = {
                    'device_name': device.name,
                    'device_type': get_device_type_str(device),
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '状态变更',
                    'reason': record.reason
                }
                notifications.append(item)

        # 处理保管人变更通知 - 如果我是原保管人或新保管人
        elif '保管人变更' in record.operation_type.value:
            # 检查 reason 中是否包含用户名
            if user['borrower_name'] in record.reason:
                item = {
                    'device_name': device.name,
                    'device_type': get_device_type_str(device),
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '保管人变更',
                    'reason': record.reason
                }
                notifications.append(item)
            # 检查 remark 中是否包含用户名（原保管人）
            elif record.remark and user['borrower_name'] in record.remark:
                item = {
                    'device_name': device.name,
                    'device_type': get_device_type_str(device),
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '保管人变更',
                    'reason': record.reason
                }
                notifications.append(item)
    
    notifications = sorted(notifications, key=lambda x: x['time'], reverse=True)[:20]

    return render_template('pc/dashboard.html',
                         user=user,
                         total_devices=total_devices,
                         available_devices=available_devices,
                         borrowed_devices_count=borrowed_devices_count,
                         my_borrowed_count=len(my_borrowed_devices),
                         my_borrowed_devices=my_borrowed_devices,
                         notifications=notifications,
                         notification_count=len(notifications),
                         active_nav='dashboard')


@app.route('/pc/devices')
@login_required
def pc_device_list():
    """PC端设备列表"""
    device_type = request.args.get('type', '')
    no_cabinet = request.args.get('no_cabinet', '')
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    filter_type = None
    if device_type == 'car':
        filter_type = '车机'
    elif device_type == 'phone':
        filter_type = '手机'
    elif device_type == 'instrument':
        filter_type = '仪表'
    elif device_type == 'simcard':
        filter_type = '手机卡'
    elif device_type == 'other':
        filter_type = '其它设备'
    
    devices = api_client.get_all_devices(filter_type)
    device_list = []
    
    for device in devices:
        is_no_cabinet = device.status == DeviceStatus.NO_CABINET
        is_circulating = device.status == DeviceStatus.CIRCULATING
        
        if no_cabinet == '1':
            if not is_no_cabinet:
                continue
        
        device_list.append({
            'id': device.id,
            'name': device.name,
            'type': get_device_type_str(device),
            'status': device.status.value,
            'remark': device.remark or '-',
            'no_cabinet': is_no_cabinet,
            'is_circulating': is_circulating
        })
    
    total = len(device_list)
    total_pages = (total + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    paginated_devices = device_list[start:end]
    
    stats = get_device_stats()
    
    return render_template('pc/device_list.html',
                         devices=paginated_devices,
                         device_type=device_type,
                         no_cabinet=no_cabinet == '1',
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         user=get_current_user(),
                         **stats,
                         active_nav='devices')


@app.route('/pc/device/<device_id>')
@login_required
def pc_device_detail(device_id):
    """PC端设备详情"""
    from datetime import datetime, date
    user = get_current_user()
    if not user or not user.get('borrower_name'):
        return redirect(url_for('login'))
    api_client.reload_data()

    # 获取设备类型参数，用于区分不同类型设备的相同ID
    device_type_param = request.args.get('device_type')

    # 先尝试根据设备类型查找
    device = None
    if device_type_param:
        devices = api_client.get_all_devices(device_type_param)
        for d in devices:
            if d.id == device_id and not d.is_deleted:
                device = d
                break

    # 如果没找到，使用默认查找方式
    if not device:
        device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    if device.status == DeviceStatus.SCRAPPED:
        return render_template('error.html', message='设备已报废，请联系管理员'), 403

    # 获取设备类型字符串
    device_type_str = get_device_type_str(device)

    api_client.add_view_record(device_id, user['borrower_name'], device_type_str)

    # 获取备注
    remarks = api_client.get_remarks(device_id, device_type_str)
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
    records = api_client.get_records(device_type=device_type_str, device_name=device.name)
    record_list = []
    for record in records[:50]:
        record_list.append({
            'operation_type': record.operation_type.value,
            'borrower': record.borrower,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'entry_source': record.entry_source,
            'reason': record.reason
        })

    # 获取查看记录
    view_records = api_client.get_view_records(device_id, device_type_str, limit=20)
    view_record_list = []
    for vr in view_records:
        view_record_list.append({
            'viewer': vr.viewer,
            'view_time': vr.view_time.strftime('%Y-%m-%d %H:%M:%S')
        })

    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']

    # 检查是否逾期（超过1小时算逾期）
    is_overdue = False
    overdue_days = 0
    overdue_hours = 0
    if device.expected_return_date and device.status.value == '借出':
        time_diff = datetime.now() - device.expected_return_date
        if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
            is_overdue = True
            overdue_hours = int(time_diff.total_seconds() // 3600)
            overdue_days = int(time_diff.total_seconds() // (24 * 3600))

    # 获取所有用户列表（用于转借）
    import json
    all_users = []
    for u in api_client._users:
        if u.borrower_name and u.borrower_name != user['borrower_name'] and not u.is_frozen:
            # 清理特殊字符，防止JSON解析错误
            clean_name = u.borrower_name.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            all_users.append({'borrower_name': clean_name, 'phone': u.phone})

    stats = get_device_stats()
    
    return render_template('pc/device_detail.html',
                         device=device,
                         device_type=get_device_type_str(device),
                         is_borrower=is_borrower,
                         is_custodian=is_custodian,
                         is_overdue=is_overdue,
                         overdue_days=overdue_days,
                         overdue_hours=overdue_hours,
                         remarks=remark_list,
                         records=record_list,
                         view_records=view_record_list,
                         **stats,
                         user=user,
                         all_users=all_users,
                         now=datetime.now().strftime('%Y-%m-%d %H:%M'))


@app.route('/pc/device/<device_id>/simple')
@login_required
def pc_device_detail_simple(device_id):
    """PC端无柜号/流通设备详情"""
    user = get_current_user()
    api_client.reload_data()

    # 获取设备类型参数，用于区分不同类型设备的相同ID
    device_type_param = request.args.get('device_type')

    # 先尝试根据设备类型查找
    device = None
    if device_type_param:
        devices = api_client.get_all_devices(device_type_param)
        for d in devices:
            if d.id == device_id and not d.is_deleted:
                device = d
                break

    # 如果没找到，使用默认查找方式
    if not device:
        device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404

    is_no_cabinet = device.status == DeviceStatus.NO_CABINET
    is_circulating = device.status == DeviceStatus.CIRCULATING
    
    if not is_no_cabinet and not is_circulating:
        return redirect(url_for('pc_device_detail', device_id=device_id))

    # 获取设备类型字符串
    device_type_str = get_device_type_str(device)

    api_client.add_view_record(device_id, user['borrower_name'], device_type_str)

    remarks = api_client.get_remarks(device_id, device_type_str)
    remark_list = []
    for remark in remarks:
        remark_list.append({
            'id': remark.id,
            'content': remark.content,
            'creator': remark.creator,
            'create_time': remark.create_time.strftime('%Y-%m-%d %H:%M'),
            'is_creator': remark.creator == user['borrower_name']
        })

    view_records = api_client.get_view_records(device_id, device_type_str, limit=20)
    view_record_list = []
    for vr in view_records:
        view_record_list.append({
            'viewer': vr.viewer,
            'view_time': vr.view_time.strftime('%Y-%m-%d %H:%M:%S')
        })

    stats = get_device_stats()
    
    return render_template('pc/device_detail_simple.html',
                         device=device,
                         device_type=device_type_str,
                         remarks=remark_list,
                         view_records=view_record_list,
                         is_circulating=is_circulating,
                         user=user,
                         **stats)


@app.route('/pc/my-custodian-devices')
@login_required
def pc_my_custodian_devices():
    """PC端我的保管设备"""
    from datetime import datetime
    user = get_current_user()
    
    # 获取当前用户保管的设备（cabinet_number等于用户名称）
    all_devices = api_client.get_all_devices()
    custodian_devices = []
    
    for device in all_devices:
        if device.cabinet_number == user['borrower_name']:
            # 计算借用时间和逾期情况
            borrow_time_str = ''
            expected_return_str = ''
            time_remaining = ''
            is_overdue = False
            
            if device.borrow_time:
                borrow_time_str = device.borrow_time.strftime('%Y-%m-%d %H:%M')
            
            if device.expected_return_date:
                expected_return_str = device.expected_return_date.strftime('%Y-%m-%d %H:%M')
                now = datetime.now()
                time_diff = device.expected_return_date - now
                
                if time_diff.total_seconds() > 0:
                    # 剩余时间（向上取整，使显示更合理）
                    total_seconds = time_diff.total_seconds()
                    days = int(total_seconds // (24 * 3600))
                    remaining_seconds = total_seconds % (24 * 3600)
                    hours = int(remaining_seconds // 3600)
                    minutes = int((remaining_seconds % 3600) // 60)
                    # 如果有分钟，小时数+1（向上取整）
                    if minutes > 0 and days == 0:
                        hours += 1
                    if days > 0:
                        time_remaining = f'剩余 {days}天{hours}小时'
                    else:
                        time_remaining = f'剩余 {hours}小时'
                else:
                    # 已逾期
                    is_overdue = True
                    overdue_hours = int(abs(time_diff.total_seconds()) // 3600)
                    overdue_days = int(abs(time_diff.total_seconds()) // (24 * 3600))
                    if overdue_days > 0:
                        time_remaining = f'逾期 {overdue_days}天{overdue_hours % 24}小时'
                    else:
                        time_remaining = f'逾期 {overdue_hours}小时'
            
            custodian_devices.append({
                'id': device.id,
                'name': device.name,
                'type': '车机' if isinstance(device, CarMachine) else '手机',
                'borrower': device.borrower or '未借用',
                'status': device.status.value,
                'borrow_time': borrow_time_str,
                'expected_return_date': expected_return_str,
                'time_remaining': time_remaining,
                'is_overdue': is_overdue
            })
    
    stats = get_device_stats()
    
    return render_template('pc/my_custodian_devices.html',
                         devices=custodian_devices,
                         total_count=len(custodian_devices),
                         user=user,
                         **stats,
                         active_nav='my_custodian')


@app.route('/pc/records')
@login_required
def pc_my_records():
    """PC端我的借用记录"""
    user = get_current_user()

    all_records = api_client.get_records()
    user_records = []
    for r in all_records:
        # 记录与当前用户相关的情况：
        # 1. 当前用户是借用者
        # 2. 当前用户是保管人（通过 remark 或 reason 判断保管人变更）
        # 3. 当前用户是操作者（转借等）
        # 4. 记录的原因/备注中包含用户名（管理员操作相关）
        should_include = False

        if r.borrower == user['borrower_name']:
            should_include = True
        elif r.operator == user['borrower_name'] and r.operation_type.value == '转借':
            should_include = True
        elif user['borrower_name'] in r.borrower and ('转借' in r.borrower or '被转借' in r.borrower):
            should_include = True

        # 检查管理员操作是否与当前用户相关
        if not should_include:
            # 状态变更记录：如果借用人是当前用户，或者保管人变更中包含当前用户名
            if r.operation_type.value == '状态变更' and r.borrower == user['borrower_name']:
                should_include = True
            elif r.operation_type.value == '保管人变更':
                # 检查 reason 和 remark 中是否包含用户名
                if user['borrower_name'] in r.reason or user['borrower_name'] in r.remark:
                    should_include = True
            # 其他管理员操作：如果借用人是当前用户
            elif r.borrower == user['borrower_name']:
                should_include = True

        if should_include:
            user_records.append(r)

    user_records.sort(key=lambda x: (x.operation_time, x.id), reverse=True)

    record_list = []
    for record in user_records:
        record_list.append({
            'device_name': record.device_name,
            'device_type': record.device_type,
            'operation_type': record.operation_type.value,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'borrower': record.borrower,
            'operator': record.operator,
            'reason': record.reason,
            'remark': record.remark
        })

    total_records = len(record_list)
    borrow_count = len([r for r in record_list if '借出' in r['operation_type']])
    return_count = len([r for r in record_list if '归还' in r['operation_type']])
    
    # 分页逻辑 - 每页50条
    page = request.args.get('page', 1, type=int)
    per_page = 50
    total_pages = (total_records + per_page - 1) // per_page
    
    # 确保页码有效
    if page < 1:
        page = 1
    if total_pages > 0 and page > total_pages:
        page = total_pages
    
    # 切片获取当前页数据
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = record_list[start:end]
    
    stats = get_device_stats()
    
    return render_template('pc/my_records.html',
                         records=paginated_records,
                         total_records=total_records,
                         borrow_count=borrow_count,
                         return_count=return_count,
                         page=page,
                         total_pages=total_pages,
                         user=user,
                         **stats,
                         active_nav='my_records')


@app.route('/pc/all-records')
@login_required
def pc_all_records():
    """PC端全部借用记录"""
    user = get_current_user()
    
    all_records = api_client.get_records()
    
    # 准备全部记录数据
    all_records_data = []
    for record in all_records:
        all_records_data.append({
            'device_name': record.device_name,
            'device_type': record.device_type,
            'operation_type': record.operation_type.value,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'borrower': record.borrower,
            'operator': record.operator,
            'reason': record.reason,
            'remark': record.remark
        })
    all_records_data.sort(key=lambda x: x['operation_time'], reverse=True)
    
    total_records = len(all_records_data)
    borrow_count = len([r for r in all_records_data if '借出' in r['operation_type']])
    return_count = len([r for r in all_records_data if '归还' in r['operation_type']])
    
    # 分页逻辑 - 每页50条
    page = request.args.get('page', 1, type=int)
    per_page = 50
    total_pages = (total_records + per_page - 1) // per_page
    
    # 确保页码有效
    if page < 1:
        page = 1
    if total_pages > 0 and page > total_pages:
        page = total_pages
    
    # 切片获取当前页数据
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = all_records_data[start:end]
    
    stats = get_device_stats()
    
    return render_template('pc/all_records.html',
                         records=paginated_records,
                         total_records=total_records,
                         borrow_count=borrow_count,
                         return_count=return_count,
                         page=page,
                         total_pages=total_pages,
                         user=user,
                         **stats,
                         active_nav='all_records')


# ==================== 后台管理系统 ====================

def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_select'))
        return f(*args, **kwargs)
    return decorated_function


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


@app.route('/admin/mobile/dashboard')
@admin_required
def admin_mobile_dashboard():
    """手机端后台仪表盘"""
    # 获取统计数据
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    # 在库、保管、流通、无柜号都算可用
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.CIRCULATING, DeviceStatus.NO_CABINET]])
    borrowed_devices = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])
    
    # 计算逾期设备
    overdue_devices = 0
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expect_return_time:
            try:
                expect_time = datetime.strptime(device.expect_return_time, '%Y-%m-%d')
                if expect_time < datetime.now():
                    overdue_devices += 1
            except:
                pass
    
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
    """手机端设置页面（占位）"""
    return redirect(url_for('admin_mobile_dashboard'))


# ==================== 电脑端后台管理 ====================

@app.route('/admin/pc/login', methods=['GET', 'POST'])
def admin_pc_login():
    """电脑端后台登录页面"""
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
    """电脑端后台仪表盘"""
    # 获取统计数据
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    # 在库、保管、流通、无柜号都算可用
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.CIRCULATING, DeviceStatus.NO_CABINET]])
    borrowed_devices = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])
    
    phone_count = len([d for d in all_devices if d.device_type == DeviceType.PHONE])
    car_device_count = len([d for d in all_devices if d.device_type == DeviceType.CAR_MACHINE])
    instrument_count = len([d for d in all_devices if d.device_type == DeviceType.INSTRUMENT])
    simcard_count = len([d for d in all_devices if d.device_type == DeviceType.SIM_CARD])
    other_device_count = len([d for d in all_devices if d.device_type == DeviceType.OTHER_DEVICE])
    
    # 计算逾期设备
    overdue_devices_list = []
    overdue_devices = 0
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                # expected_return_date 已经是 datetime 对象
                if isinstance(expect_time, datetime):
                    # 超过1小时算逾期
                    time_diff = datetime.now() - expect_time
                    if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                        overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                        overdue_hours = int(time_diff.total_seconds() // 3600)
                        overdue_devices += 1
                        overdue_devices_list.append({
                            'device_name': device.name,
                            'device_type': '手机' if device.device_type == DeviceType.PHONE else '车机',
                            'borrower': device.borrower,
                            'overdue_days': overdue_days,
                            'overdue_hours': overdue_hours
                        })
            except Exception as e:
                print(f"计算逾期天数出错: {e}")
                pass
    
    overdue_devices_list.sort(key=lambda x: x['overdue_days'], reverse=True)
    
    # 计算百分比
    available_percent = round(available_devices / total_devices * 100, 1) if total_devices > 0 else 0
    borrowed_percent = round(borrowed_devices / total_devices * 100, 1) if total_devices > 0 else 0
    other_percent = round(100 - available_percent - borrowed_percent, 1)
    
    # 获取最近记录
    all_records = api_client.get_records()
    recent_records = []
    for record in all_records[:10]:
        recent_records.append({
            'action_type': record.operation_type.value,
            'device_name': record.device_name,
            'user_name': record.borrower,
            'time': record.operation_time.strftime('%Y-%m-%d %H:%M')
        })
    
    return render_template('admin/pc/dashboard.html',
                         admin_name=session.get('admin_name', '管理员'),
                         total_devices=total_devices,
                         available_devices=available_devices,
                         borrowed_devices=borrowed_devices,
                         overdue_devices=overdue_devices,
                         phone_count=phone_count,
                         car_device_count=car_device_count,
                         instrument_count=instrument_count,
                         simcard_count=simcard_count,
                         other_device_count=other_device_count,
                         available_percent=available_percent,
                         borrowed_percent=borrowed_percent,
                         other_percent=other_percent,
                         overdue_devices_list=overdue_devices_list[:5],
                         recent_records=recent_records,
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/devices')
@admin_required
def admin_pc_devices():
    """电脑端设备管理页面"""
    all_devices = api_client.get_all_devices()
    users = api_client.get_users()
    
    # 获取所有柜号
    cabinets = list(set([d.cabinet_number for d in all_devices if d.cabinet_number]))
    
    # 准备设备数据
    devices_data = []
    for device in all_devices:
        is_overdue = False
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                if isinstance(expect_time, str):
                    expect_time = datetime.strptime(expect_time, '%Y-%m-%d')
                is_overdue = expect_time < datetime.now()
            except:
                pass
        
        devices_data.append({
            'id': device.id,
            'device_name': device.name,
            'device_type': '手机' if device.device_type == DeviceType.PHONE else '车机',
            'model': getattr(device, 'model', ''),
            'status': device.status.value,
            'borrower': device.borrower,
            'cabinet': device.cabinet_number,
            'expect_return_time': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else None,
            'is_overdue': is_overdue
        })
    
    # 准备用户数据
    users_data = [{'id': u.id, 'name': u.borrower_name, 'weixin_name': u.wechat_name} for u in users]
    
    return render_template('admin/pc/devices.html',
                         admin_name=session.get('admin_name', '管理员'),
                         devices=devices_data,
                         users=users_data,
                         cabinets=cabinets,
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/device/add')
@app.route('/admin/pc/device/<device_id>')
@admin_required
def admin_pc_device_add_edit(device_id=None):
    """电脑端新增/编辑设备页面"""
    device = None
    if device_id:
        device_obj = api_client.get_device(device_id)
        if device_obj:
            device = {
                'id': device_obj.id,
                'device_name': device_obj.name,
                'device_type': '手机' if device_obj.device_type == DeviceType.PHONE else '车机',
                'model': getattr(device_obj, 'model', ''),
                'status': device_obj.status.value,
                'cabinet': device_obj.cabinet_number,
                'borrower': device_obj.borrower,
                'remarks': getattr(device_obj, 'remark', '')
            }
    
    return render_template('admin/pc/device_add.html',
                         admin_name=session.get('admin_name', '管理员'),
                         device=device,
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/users')
@admin_required
def admin_pc_users():
    """电脑端用户管理页面"""
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
    
    return render_template('admin/pc/users.html',
                         admin_name=session.get('admin_name', '管理员'),
                         users=users_data,
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/records')
@admin_required
def admin_pc_records():
    """电脑端记录查询页面"""
    all_records = api_client.get_records()
    
    records_data = []
    for record in all_records[:50]:
        records_data.append({
            'action_type': record.operation_type.value,
            'device_name': record.device_name,
            'device_type': '手机' if record.device_type == DeviceType.PHONE else '车机',
            'user_name': record.borrower,
            'time': record.operation_time.strftime('%Y-%m-%d %H:%M'),
            'remarks': record.remark
        })
    
    return render_template('admin/pc/records.html',
                         admin_name=session.get('admin_name', '管理员'),
                         records=records_data,
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/logs')
@admin_required
def admin_pc_logs():
    """电脑端操作日志页面"""
    # 获取操作日志
    logs = api_client.get_admin_logs(limit=100)
    
    return render_template('admin/pc/logs.html',
                         admin_name=session.get('admin_name', '管理员'),
                         logs=logs,
                         overdue_count=get_overdue_count())


@app.route('/admin/pc/overdue')
@admin_required
def admin_pc_overdue():
    """电脑端过期未还页面"""
    all_devices = api_client.get_all_devices()
    
    overdue_devices = []
    for device in all_devices:
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            try:
                expect_time = device.expected_return_date
                # 超过1小时算逾期
                time_diff = datetime.now() - expect_time
                if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                    overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                    overdue_hours = int(time_diff.total_seconds() // 3600)
                    # 获取用户手机号
                    phone = ''
                    for user in api_client.get_users():
                        if user.borrower_name == device.borrower:
                            phone = user.phone
                            break

                    # 获取设备类型字符串
                    device_type_str = device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type)

                    overdue_devices.append({
                        'id': device.id,
                        'device_name': device.name,
                        'device_type': device_type_str,
                        'borrower': device.borrower,
                        'borrow_time': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else None,
                        'expect_return_time': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else None,
                        'overdue_days': overdue_days,
                        'overdue_hours': overdue_hours,
                        'phone': phone
                    })
            except:
                pass
    
    overdue_devices.sort(key=lambda x: x['overdue_days'], reverse=True)
    
    phone_overdue = len([d for d in overdue_devices if d['device_type'] == '手机'])
    car_overdue = len([d for d in overdue_devices if d['device_type'] == '车机'])
    instrument_overdue = len([d for d in overdue_devices if d['device_type'] == '仪表'])
    simcard_overdue = len([d for d in overdue_devices if d['device_type'] == '手机卡'])
    other_overdue = len([d for d in overdue_devices if d['device_type'] == '其它设备'])
    
    return render_template('admin/pc/overdue.html',
                         admin_name=session.get('admin_name', '管理员'),
                         overdue_devices=overdue_devices,
                         overdue_count=len(overdue_devices),
                         phone_overdue=phone_overdue,
                         car_overdue=car_overdue,
                         instrument_overdue=instrument_overdue,
                         simcard_overdue=simcard_overdue,
                         other_overdue=other_overdue)


@app.route('/admin/logout')
def admin_logout():
    """管理员退出登录"""
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    return redirect(url_for('admin_select'))


# ==================== 后台管理API接口 ====================

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
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '用户名或密码错误'})


@app.route('/api/devices', methods=['GET', 'POST'])
@admin_required
def api_devices():
    """设备列表API / 新增设备API"""
    if request.method == 'GET':
        devices = api_client.get_all_devices()
        devices_data = []
        for device in devices:
            is_overdue = False
            if device.status == DeviceStatus.BORROWED and device.expected_return_date:
                try:
                    expect_time = datetime.strptime(device.expect_return_time, '%Y-%m-%d')
                    is_overdue = expect_time < datetime.now()
                except:
                    pass
            
            # 获取设备类型字符串
            if device.device_type == DeviceType.PHONE:
                device_type_str = '手机'
            elif device.device_type == DeviceType.CAR_MACHINE:
                device_type_str = '车机'
            elif device.device_type == DeviceType.INSTRUMENT:
                device_type_str = '仪表'
            elif device.device_type == DeviceType.SIM_CARD:
                device_type_str = '手机卡'
            elif device.device_type == DeviceType.OTHER_DEVICE:
                device_type_str = '其它设备'
            else:
                device_type_str = '未知'
            
            devices_data.append({
                'id': device.id,
                'device_name': device.name,
                'device_type': device_type_str,
                'model': getattr(device, 'model', ''),
                'status': device.status.value,
                'borrower': device.borrower,
                'cabinet': device.cabinet_number,
                'borrow_time': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else None,
                'expect_return_time': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else None,
                'remarks': getattr(device, 'remark', ''),
                'is_overdue': is_overdue
            })
        return jsonify(devices_data)
    
    else:  # POST
        data = request.get_json()
        # 创建设备
        try:
            device_type = DeviceType.PHONE if data.get('device_type') == '手机' else DeviceType.CAR_MACHINE
            device = api_client.create_device(
                device_type=device_type,
                device_name=data.get('device_name'),
                model=data.get('model', ''),
                cabinet=data.get('cabinet', ''),
                status=data.get('status', '在库'),
                remarks=data.get('remarks', '')
            )
            return jsonify({'success': True, 'device_id': device.id})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def api_device_detail(device_id):
    """设备详情 / 更新 / 删除API"""
    if request.method == 'GET':
        device = api_client.get_device(device_id)
        if device:
            return jsonify({
                'id': device.id,
                'device_name': device.name,
                'device_type': '手机' if device.device_type == DeviceType.PHONE else '车机',
                'model': getattr(device, 'model', ''),
                'status': device.status.value,
                'borrower': device.borrower,
                'cabinet': device.cabinet_number,
                'remarks': getattr(device, 'remark', '')
            })
        return jsonify({'error': '设备不存在'}), 404
    
    elif request.method == 'PUT':
        data = request.get_json()
        try:
            api_client.update_device_by_id(device_id, data)
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
def api_device_borrow(device_id):
    """借出设备API"""
    data = request.get_json()
    try:
        api_client.borrow_device(
            device_id=device_id,
            borrower=data.get('user'),
            days=int(data.get('days', 1)),
            cabinet=data.get('cabinet', '流通'),
            remarks=data.get('remarks', ''),
            operator=session.get('admin_name', '管理员')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>/return', methods=['POST'])
@admin_required
def api_device_return(device_id):
    """归还设备API"""
    try:
        api_client.return_device(
            device_id=device_id,
            operator=session.get('admin_name', '管理员')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>/transfer', methods=['POST'])
@admin_required
def api_device_transfer(device_id):
    """转借设备API"""
    data = request.get_json()
    try:
        api_client.transfer_device(
            device_id=device_id,
            new_borrower=data.get('user'),
            remarks=data.get('remarks', ''),
            operator=session.get('admin_name', '管理员')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/devices/<device_id>/records', methods=['GET'])
@admin_required
def api_device_records(device_id):
    """获取设备的借还记录API"""
    limit = request.args.get('limit', 5, type=int)
    records = api_client.get_device_records(device_id, limit=limit)
    
    records_data = []
    for record in records:
        records_data.append({
            'action_type': record.operation_type.value,
            'user_name': record.borrower,
            'time': record.operation_time.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify(records_data)


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
                # 超过1小时算逾期
                time_diff = datetime.now() - expect_time
                if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
                    overdue_days = int(time_diff.total_seconds() // (24 * 3600))
                    overdue_hours = int(time_diff.total_seconds() // 3600)
                    # 获取用户手机号
                    phone = ''
                    for user in api_client.get_users():
                        if user.borrower_name == device.borrower:
                            phone = user.phone
                            break

                    # 获取设备类型字符串
                    device_type_str = device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type)

                    overdue_devices.append({
                        'id': device.id,
                        'device_name': device.name,
                        'device_type': device_type_str,
                        'borrower': device.borrower,
                        'borrow_time': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else None,
                        'expect_return_time': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else None,
                        'overdue_days': overdue_days,
                        'overdue_hours': overdue_hours,
                        'phone': phone
                    })
            except:
                pass
    
    overdue_devices.sort(key=lambda x: x['overdue_days'], reverse=True)
    
    return jsonify({'devices': overdue_devices, 'count': len(overdue_devices)})


@app.route('/api/admin/users', methods=['GET', 'POST'])
@admin_required
def api_admin_users():
    """用户列表 / 新增用户API (后台管理)"""
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


@app.route('/api/users/<user_id>', methods=['PUT', 'DELETE'])
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
    """设置管理员API"""
    try:
        api_client.set_user_admin(user_id, True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/users/<user_id>/remove_admin', methods=['POST'])
@admin_required
def api_user_remove_admin(user_id):
    """取消管理员API"""
    try:
        api_client.set_user_admin(user_id, False)
        return jsonify({'success': True})
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
    app.run(debug=True, host='0.0.0.0', port=5000)
