# -*- coding: utf-8 -*-
"""
车机与手机设备管理系统 - 用户服务
使用 Flask 实现，适配微信内置浏览器
端口: 5000
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uuid
import io
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from dotenv import load_dotenv

# 从 common 导入
from common.models import DeviceStatus, DeviceType, OperationType, EntrySource, CarMachine, Phone, Record, UserRemark, User, ViewRecord
from common.api_client import api_client
from common.utils import mask_phone, is_mobile_device
from common.config import SECRET_KEY, SERVER_URL, USER_SERVICE_PORT

# 尝试导入qrcode，如果没有安装则使用备用方案
try:
    import qrcode
    from qrcode.image.pil import PilImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    print("警告: qrcode模块未安装，二维码功能将使用备用方案")

load_dotenv()

app = Flask(__name__)
app.secret_key = SECRET_KEY


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


@app.context_processor
def inject_globals():
    """注入全局模板变量和函数"""
    return {
        'is_admin_user': is_admin_user,
    }


def device_route(mobile_route, pc_route):
    """根据设备类型返回对应的路由"""
    if is_mobile_device(request):
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
        if not all([borrower_name, phone, password, confirm_password]):
            return render_template('register.html', error='请填写所有必填项')

        if password != confirm_password:
            return render_template('register.html', error='两次输入的密码不一致')

        # 尝试注册
        success, result = api_client.register_user(phone, password, borrower_name)
        if success:
            return redirect(url_for('login'))
        else:
            return render_template('register.html', error=result)

    return render_template('register.html')


@app.route('/login/qrcode')
def login_qrcode():
    """生成登录二维码"""
    try:
        # 获取服务器URL
        server_url = SERVER_URL or request.host_url.rstrip('/')
        
        # 生成二维码内容 - 跳转到登录页面
        qr_content = f"{server_url}/login/mobile"
        
        if QRCODE_AVAILABLE:
            # 使用qrcode模块生成
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_content)
            qr.make(fit=True)
            
            # 创建图像
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 转换为base64
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return jsonify({
                'success': True,
                'qrcode': f'data:image/png;base64,{img_str}',
                'url': qr_content
            })
        else:
            # 备用方案：返回URL，让前端使用JS生成二维码
            return jsonify({
                'success': True,
                'qrcode': None,
                'url': qr_content
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'生成二维码失败: {str(e)}'
        })


@app.route('/logout')
def logout():
    """用户退出登录"""
    session.clear()
    return redirect(url_for('select_device_type'))


@app.route('/set-borrower-name', methods=['GET', 'POST'])
def set_borrower_name():
    """设置借用人名称（首次登录）"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        borrower_name = request.form.get('borrower_name', '').strip()
        
        if not borrower_name:
            return render_template('set_borrower_name.html', error='请输入借用人名称')
        
        # 更新用户借用人名称
        success = api_client.update_user_borrower_name(user_id, borrower_name)
        if success:
            # 根据登录设备类型跳转到不同页面
            login_device_type = session.get('login_device_type', 'mobile')
            if login_device_type == 'pc':
                return redirect(url_for('pc_dashboard'))
            else:
                return redirect(url_for('home'))
        else:
            return render_template('set_borrower_name.html', error='该借用人名称已被使用')
    
    return render_template('set_borrower_name.html')


# ==================== 移动端路由 ====================

@app.route('/home')
@login_required
def home():
    """手机端首页 - 显示用户概览"""
    user = get_current_user()
    
    # 获取用户当前借用的设备
    borrowed_devices = []
    all_devices = api_client.get_all_devices()
    for device in all_devices:
        if device.borrower == user['borrower_name']:
            borrowed_devices.append(device)
    
    # 统计信息
    total_borrowed = len(borrowed_devices)
    
    # 获取最近记录
    recent_records = []
    all_records = api_client.get_records()
    for record in all_records[:5]:
        if user['borrower_name'] in record.borrower or record.operator == user['borrower_name']:
            recent_records.append(record)
    
    return render_template('home.html',
                         user=user,
                         total_borrowed=total_borrowed,
                         borrowed_devices=borrowed_devices,
                         recent_records=recent_records)


@app.route('/devices')
@login_required
def device_list():
    """设备列表页面 - 手机端"""
    device_type = request.args.get('type', 'all')
    no_cabinet = request.args.get('no_cabinet', '')
    
    if device_type == 'car':
        devices = api_client.get_all_devices('车机')
        title = '车机设备'
        active_nav = 'devices'
    elif device_type == 'phone':
        devices = api_client.get_all_devices('手机')
        title = '手机设备'
        active_nav = 'devices'
    else:
        devices = api_client.get_all_devices()
        title = '全部设备'
        active_nav = 'devices'
    
    # 无柜号筛选
    if no_cabinet:
        devices = [d for d in devices if d.cabinet_number in ['无', '']] + [d for d in devices if d.cabinet_number not in ['无', ''] and (not d.cabinet_number or d.is_circulating)]
    
    # 分类统计
    available_count = len([d for d in devices if d.status == DeviceStatus.IN_STOCK])
    borrowed_count = len([d for d in devices if d.status == DeviceStatus.BORROWED])
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(devices)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_devices = devices[start:end]
    
    return render_template('device_list.html',
                         devices=paginated_devices,
                         title=title,
                         device_type=device_type,
                         no_cabinet=no_cabinet,
                         available_count=available_count,
                         borrowed_count=borrowed_count,
                         active_nav=active_nav,
                         page=page,
                         total_pages=total_pages,
                         total=total)


@app.route('/device/<device_id>')
@login_required
def device_detail(device_id):
    """设备详情页面 - 手机端"""
    user = get_current_user()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    # 添加查看记录
    if user['borrower_name']:
        api_client.add_view_record(device_id, user['borrower_name'])
    
    # 获取设备备注
    raw_remarks = api_client.get_remarks(device_id)
    remark_list = []
    for remark in raw_remarks:
        remark_list.append({
            'id': remark.id,
            'content': remark.content,
            'creator': remark.creator,
            'create_time': remark.create_time.strftime('%Y-%m-%d %H:%M'),
            'is_creator': remark.creator == user['borrower_name']
        })
    
    # 获取设备操作记录
    device_records = api_client.get_device_records(device_id, limit=10)
    
    # 获取查看记录
    view_records = api_client.get_view_records(device_id, limit=20)
    
    # 检查当前用户是否借用了该设备
    is_borrowed_by_me = (device.borrower == user['borrower_name'])
    
    # 检查当前用户是否是保管人（管理员）
    is_custodian = user.get('is_admin', False)
    
    # 检查是否可以借用（设备在库且用户没有借用超过限制）
    can_borrow = (device.status == DeviceStatus.IN_STOCK)
    
    # 检查是否逾期（超过1小时算逾期）
    is_overdue = False
    overdue_days = 0
    overdue_hours = 0
    if device.expected_return_date and device.borrower:
        from datetime import datetime
        time_diff = datetime.now() - device.expected_return_date
        if time_diff.total_seconds() > 3600:  # 超过1小时算逾期
            is_overdue = True
            overdue_hours = int(time_diff.total_seconds() // 3600)
            overdue_days = int(time_diff.total_seconds() // (24 * 3600))
    
    # 检查用户借用数量
    user_borrowed_count = 0
    all_devices = api_client.get_all_devices()
    for d in all_devices:
        if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
            user_borrowed_count += 1
    
    # 借用限制检查
    borrow_limit = 5  # 最大借用数量
    if user_borrowed_count >= borrow_limit:
        can_borrow = False
        borrow_limit_message = f'您已借用 {user_borrowed_count} 台设备，达到上限 ({borrow_limit}台)'
    else:
        borrow_limit_message = None
    
    # 获取设备类型
    device_type = '车机' if isinstance(device, CarMachine) else '手机'
    
    return render_template('device_detail.html',
                         device=device,
                         device_type=device_type,
                         user=user,
                         remarks=remarks,
                         records=device_records,
                         view_records=view_records,
                         is_borrower=is_borrowed_by_me,
                         is_custodian=is_custodian,
                         is_overdue=is_overdue,
                         overdue_days=overdue_days,
                         can_borrow=can_borrow,
                         borrow_limit_message=borrow_limit_message,
                         active_nav='devices')


@app.route('/device/<device_id>/simple')
@login_required
def device_detail_simple(device_id):
    """设备详情页面（简化版）- 用于借还确认"""
    user = get_current_user()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    # 添加查看记录
    if user['borrower_name']:
        api_client.add_view_record(device_id, user['borrower_name'])
    
    action = request.args.get('action', 'view')
    
    # 获取查看记录
    view_records = api_client.get_view_records(device_id, limit=20)
    
    return render_template('device_detail_simple.html',
                         device=device,
                         action=action,
                         view_records=view_records)


@app.route('/borrow/<device_id>')
@login_required
def borrow_device(device_id):
    """借用设备页面"""
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    if device.status != DeviceStatus.IN_STOCK:
        return render_template('error.html', message='设备不可用'), 400
    
    user = get_current_user()
    
    return render_template('borrow.html',
                         device=device,
                         user=user)


@app.route('/return/<device_id>')
@login_required
def return_device(device_id):
    """归还设备页面"""
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    user = get_current_user()
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return render_template('error.html', message='您不是该设备的当前借用人'), 403
    
    return render_template('return.html',
                         device=device,
                         user=user)


@app.route('/transfer/<device_id>')
@login_required
def transfer_device(device_id):
    """转借设备页面"""
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    user = get_current_user()
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return render_template('error.html', message='您不是该设备的当前借用人'), 403
    
    # 获取所有用户列表（用于选择转借对象）
    users = api_client.get_all_users()
    available_users = [u for u in users if u.borrower_name and u.borrower_name != user['borrower_name'] and not u.is_frozen]
    
    return render_template('transfer.html',
                         device=device,
                         user=user,
                         users=available_users)


@app.route('/remark/add/<device_id>')
@login_required
def add_remark(device_id):
    """添加备注页面"""
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    return render_template('remark_add.html', device=device)


@app.route('/remark/edit/<remark_id>')
@login_required
def edit_remark(remark_id):
    """编辑备注页面"""
    # 查找备注
    remark = None
    for r in api_client._remarks:
        if r.id == remark_id:
            remark = r
            break
    
    if not remark:
        return render_template('error.html', message='备注不存在'), 404
    
    # 检查是否是备注创建者
    user = get_current_user()
    if remark.creator != user['borrower_name']:
        return render_template('error.html', message='您只能编辑自己的备注'), 403
    
    device = api_client.get_device_by_id(remark.device_id)
    
    return render_template('remark_edit.html', 
                         remark=remark,
                         device=device)


@app.route('/my-records')
@login_required
def my_records():
    """我的记录页面"""
    user = get_current_user()
    
    # 获取当前用户的记录
    my_records_list = []
    all_records = api_client.get_records()
    
    for record in all_records:
        # 检查是否与当前用户相关
        if (user['borrower_name'] in record.borrower or 
            record.operator == user['borrower_name'] or
            record.borrower == user['borrower_name']):
            my_records_list.append(record)
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total = len(my_records_list)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = my_records_list[start:end]
    
    return render_template('my_records.html',
                         records=paginated_records,
                         page=page,
                         total_pages=total_pages,
                         total_records=total,
                         active_nav='records')


# ==================== PC端路由 ====================

@app.route('/pc')
@login_required
def pc_dashboard():
    """PC端首页/仪表盘"""
    from datetime import datetime
    user = get_current_user()

    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    # 获取统计数据
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    available_devices = len([d for d in all_devices if d.status == DeviceStatus.IN_STOCK])
    borrowed_devices_count = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])

    # 获取当前用户借用的设备，并计算剩余/逾期时间
    raw_borrowed_devices = [d for d in all_devices if d.borrower == user['borrower_name']]
    my_borrowed_devices = []
    for device in raw_borrowed_devices:
        device.is_overdue = False
        device.overdue_days = 0
        device.overdue_hours = 0
        device.remaining_days = 0
        device.remaining_hours = 0

        if device.expected_return_date:
            time_diff = device.expected_return_date - datetime.now()
            total_seconds = time_diff.total_seconds()

            if total_seconds < 0:
                # 已逾期
                device.is_overdue = True
                device.overdue_hours = int(abs(total_seconds) // 3600)
                device.overdue_days = int(abs(total_seconds) // (24 * 3600))
            else:
                # 剩余时间
                device.remaining_hours = int(total_seconds // 3600)
                device.remaining_days = int(total_seconds // (24 * 3600))

        my_borrowed_devices.append(device)

    my_borrowed_count = len(my_borrowed_devices)

    # 获取最近记录
    recent_records = []
    all_records = api_client.get_records()
    for record in all_records[:10]:
        if user['borrower_name'] in record.borrower or record.operator == user['borrower_name']:
            recent_records.append(record)

    return render_template('pc/dashboard.html',
                         user=user,
                         total_devices=total_devices,
                         available_devices=available_devices,
                         borrowed_devices_count=borrowed_devices_count,
                         my_borrowed_devices=my_borrowed_devices,
                         my_borrowed_count=my_borrowed_count,
                         recent_records=recent_records)


@app.route('/pc/devices')
@login_required
def pc_device_list():
    """PC端设备列表页面"""
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    device_type = request.args.get('type', 'all')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()

    # 获取设备
    if device_type == 'car':
        devices = api_client.get_all_devices('车机')
        title = '车机设备'
    elif device_type == 'phone':
        devices = api_client.get_all_devices('手机')
        title = '手机设备'
    else:
        devices = api_client.get_all_devices()
        title = '全部设备'
    
    # 状态过滤
    if status == 'available':
        devices = [d for d in devices if d.status == DeviceStatus.IN_STOCK]
    elif status == 'borrowed':
        devices = [d for d in devices if d.status == DeviceStatus.BORROWED]
    
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
    
    return render_template('pc/device_list.html',
                         devices=paginated_devices,
                         title=title,
                         device_type=device_type,
                         status=status,
                         search=search,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         user=get_current_user())


@app.route('/pc/device/<device_id>')
@login_required
def pc_device_detail(device_id):
    """PC端设备详情页面"""
    user = get_current_user()
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()
    device = api_client.get_device_by_id(device_id)

    if not device:
        return render_template('error.html', message='设备不存在'), 404

    # 添加查看记录
    if user['borrower_name']:
        api_client.add_view_record(device_id, user['borrower_name'])
    
    # 获取设备备注
    raw_remarks = api_client.get_remarks(device_id)
    remark_list = []
    for remark in raw_remarks:
        remark_list.append({
            'id': remark.id,
            'content': remark.content,
            'creator': remark.creator,
            'create_time': remark.create_time.strftime('%Y-%m-%d %H:%M'),
            'is_creator': remark.creator == user['borrower_name']
        })

    # 获取设备借用记录
    raw_records = api_client.get_device_records(device_id, limit=20)
    record_list = []
    for record in raw_records:
        record_list.append({
            'operation_type': record.operation_type.value,
            'borrower': record.borrower,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'entry_source': record.entry_source,
            'reason': record.reason
        })

    # 获取查看记录
    raw_view_records = api_client.get_view_records(device_id, limit=20)
    view_record_list = []
    for vr in raw_view_records:
        view_record_list.append({
            'viewer': vr.viewer,
            'view_time': vr.view_time.strftime('%Y-%m-%d %H:%M:%S')
        })

    # 检查当前用户是否借用了该设备
    is_borrowed_by_me = (device.borrower == user['borrower_name'])

    # 检查当前用户是否是保管人（管理员）
    is_custodian = user.get('is_admin', False)

    # 检查是否可以借用
    can_borrow = (device.status == DeviceStatus.IN_STOCK)

    # 获取设备类型
    device_type = '车机' if isinstance(device, CarMachine) else '手机'

    return render_template('pc/device_detail.html',
                         device=device,
                         device_type=device_type,
                         remarks=remark_list,
                         records=record_list,
                         view_records=view_record_list,
                         is_borrower=is_borrowed_by_me,
                         is_custodian=is_custodian,
                         can_borrow=can_borrow,
                         user=user,
                         now=datetime.now().strftime('%Y-%m-%d %H:%M'))


@app.route('/pc/device/<device_id>/simple')
@login_required
def pc_device_detail_simple(device_id):
    """PC端设备详情页面（简化版）- 用于借还确认"""
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return render_template('error.html', message='设备不存在'), 404
    
    action = request.args.get('action', 'view')
    
    return render_template('pc/device_detail_simple.html',
                         device=device,
                         action=action,
                         user=get_current_user())


@app.route('/pc/records')
@login_required
def pc_records():
    """PC端个人记录页面"""
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    user = get_current_user()

    # 获取当前用户的记录
    my_records_list = []
    all_records = api_client.get_records()
    
    for record in all_records:
        if (user['borrower_name'] in record.borrower or 
            record.operator == user['borrower_name'] or
            record.borrower == user['borrower_name']):
            my_records_list.append(record)
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(my_records_list)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = my_records_list[start:end]
    
    # 统计
    borrow_count = len([r for r in my_records_list if '借出' in r.operation_type.value])
    return_count = len([r for r in my_records_list if '归还' in r.operation_type.value])
    
    return render_template('pc/my_records.html',
                         records=paginated_records,
                         total_records=total,
                         borrow_count=borrow_count,
                         return_count=return_count,
                         page=page,
                         total_pages=total_pages,
                         user=user)


@app.route('/pc/all-records')
@login_required
def pc_all_records():
    """PC端所有记录页面"""
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    # 获取所有记录
    all_records_list = api_client.get_records()
    
    # 统计借用和归还次数
    borrow_count = len([r for r in all_records_list if '借出' in r.operation_type.value])
    return_count = len([r for r in all_records_list if '归还' in r.operation_type.value])
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(all_records_list)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = all_records_list[start:end]
    
    return render_template('pc/all_records.html',
                         records=paginated_records,
                         total_records=total,
                         borrow_count=borrow_count,
                         return_count=return_count,
                         page=page,
                         total_pages=total_pages,
                         user=get_current_user())


# ==================== API 接口 ====================

@app.route('/api/borrow', methods=['POST'])
@login_required
def api_borrow():
    """借用设备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    location = data.get('location', '').strip()
    reason = data.get('reason', '').strip()
    days = data.get('days', 7)
    
    # 验证输入
    if not location:
        return jsonify({'success': False, 'message': '请输入借用地点'})
    if not reason:
        return jsonify({'success': False, 'message': '请输入借用原因'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status != DeviceStatus.IN_STOCK:
        return jsonify({'success': False, 'message': '设备不可用'})
    
    # 检查用户借用数量限制
    user_borrowed_count = 0
    all_devices = api_client.get_all_devices()
    for d in all_devices:
        if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
            user_borrowed_count += 1
    
    borrow_limit = 5
    if user_borrowed_count >= borrow_limit:
        return jsonify({'success': False, 'message': f'您已借用 {user_borrowed_count} 台设备，达到上限'})
    
    # 获取用户手机号
    user_phone = user['phone']
    
    # 更新设备信息
    device.status = DeviceStatus.BORROWED
    device.borrower = user['borrower_name']
    device.phone = user_phone
    device.borrow_time = datetime.now()
    device.location = location
    device.reason = reason
    device.entry_source = EntrySource.USER.value
    device.expected_return_date = datetime.now() + timedelta(days=int(days))
    
    api_client.update_device(device)
    
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
        phone=user_phone,
        location=location,
        reason=reason,
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    # 更新用户借用次数
    for u in api_client._users:
        if u.id == user['user_id']:
            u.borrow_count += 1
            break
    
    api_client.add_operation_log(f"借出设备: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '借用成功'})


@app.route('/api/return', methods=['POST'])
@login_required
def api_return():
    """归还设备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    return_location = data.get('return_location', '').strip()
    return_reason = data.get('return_reason', '').strip()
    
    # 验证输入
    if not return_location:
        return jsonify({'success': False, 'message': '请输入归还地点'})
    if not return_reason:
        return jsonify({'success': False, 'message': '请输入归还原因'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    original_borrower = device.borrower
    
    # 清空借用信息
    device.status = DeviceStatus.IN_STOCK
    device.borrower = ''
    device.phone = ''
    device.borrow_time = None
    device.location = return_location
    device.reason = return_reason
    device.entry_source = ''
    device.expected_return_date = None
    
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
        borrower=original_borrower,
        phone=user['phone'],
        location=return_location,
        reason=return_reason,
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    api_client.add_operation_log(f"归还设备: {original_borrower}", device.name)
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
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    if not transfer_to:
        return jsonify({'success': False, 'message': '请选择转借对象'})
    
    # 检查转借对象是否存在
    target_user = None
    for u in api_client._users:
        if u.borrower_name == transfer_to:
            target_user = u
            break
    
    if not target_user:
        return jsonify({'success': False, 'message': '转借对象不存在'})
    
    if target_user.is_frozen:
        return jsonify({'success': False, 'message': '转借对象账号已被冻结'})
    
    original_borrower = device.borrower
    
    # 更新设备信息 - 保存上一个借用人
    device.previous_borrower = original_borrower
    device.borrower = transfer_to
    device.phone = target_user.phone
    device.entry_source = EntrySource.USER.value
    
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
        borrower=f"{original_borrower}——>{transfer_to}",
        phone=target_user.phone,
        reason=f"用户转借: {original_borrower} 转给 {transfer_to}",
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    api_client.add_operation_log(f"转借设备: {original_borrower} -> {transfer_to}", device.name)
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
        return jsonify({'success': False, 'message': '请输入备注内容'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 创建备注
    remark = UserRemark(
        id=str(uuid.uuid4()),
        device_id=device_id,
        content=content,
        creator=user['borrower_name'],
        create_time=datetime.now()
    )
    api_client._remarks.append(remark)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '添加成功'})


@app.route('/api/transfer-to-me', methods=['POST'])
@login_required
def api_transfer_to_me():
    """转给自己API（用于遗失找回）"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备状态
    if device.status != DeviceStatus.LOST and device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常，无法操作'})
    
    # 保存原借用人信息
    original_borrower = device.borrower
    
    # 更新设备信息 - 转给自己
    device.previous_borrower = original_borrower
    device.borrower = user['borrower_name']
    device.phone = user['phone']
    device.status = DeviceStatus.BORROWED
    device.lost_time = None  # 清除丢失时间
    device.entry_source = EntrySource.USER.value
    
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
        borrower=f"转给自己：{original_borrower}——>{user['borrower_name']}",
        phone=user['phone'],
        reason='设备找回后转给自己保管',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    api_client.add_operation_log(f"转给自己: {original_borrower} -> {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '操作成功，设备已转给您保管'})


@app.route('/api/return-by-custodian', methods=['POST'])
@login_required
def api_return_by_custodian():
    """保管人代还API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备是否处于丢失状态
    if device.status != DeviceStatus.LOST:
        return jsonify({'success': False, 'message': '设备状态异常，仅限丢失设备使用此功能'})
    
    # 检查当前用户是否为管理员
    if not user.get('is_admin'):
        return jsonify({'success': False, 'message': '仅限管理员使用此功能'})
    
    original_borrower = device.borrower
    
    # 清空借用信息
    device.status = DeviceStatus.IN_STOCK
    device.borrower = ''
    device.phone = ''
    device.borrow_time = None
    device.location = ''
    device.reason = ''
    device.entry_source = ''
    device.expected_return_date = None
    device.lost_time = None
    
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
        borrower=f"保管人代还：{original_borrower}",
        reason='保管人代还设备',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    api_client.add_operation_log(f"保管人代还: {original_borrower}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '代还成功'})


@app.route('/api/remark/edit', methods=['POST'])
@login_required
def api_edit_remark():
    """编辑备注API"""
    user = get_current_user()
    data = request.json
    
    remark_id = data.get('remark_id')
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'message': '请输入备注内容'})
    
    # 查找备注
    remark = None
    for r in api_client._remarks:
        if r.id == remark_id:
            remark = r
            break
    
    if not remark:
        return jsonify({'success': False, 'message': '备注不存在'})
    
    # 检查是否是备注创建者
    if remark.creator != user['borrower_name']:
        return jsonify({'success': False, 'message': '您只能编辑自己的备注'})
    
    remark.content = content
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '修改成功'})


@app.route('/api/remark/delete', methods=['POST'])
@login_required
def api_delete_remark():
    """删除备注API"""
    user = get_current_user()
    data = request.json
    
    remark_id = data.get('remark_id')
    
    # 查找备注
    remark = None
    for r in api_client._remarks:
        if r.id == remark_id:
            remark = r
            break
    
    if not remark:
        return jsonify({'success': False, 'message': '备注不存在'})
    
    # 检查是否是备注创建者或管理员
    if remark.creator != user['borrower_name'] and not user.get('is_admin'):
        return jsonify({'success': False, 'message': '您只能删除自己的备注'})
    
    api_client._remarks.remove(remark)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '删除成功'})


@app.route('/api/search')
@login_required
def api_search():
    """搜索API"""
    keyword = request.args.get('keyword', '').strip()
    
    if not keyword:
        return jsonify([])
    
    results = []
    all_devices = api_client.get_all_devices()
    
    for device in all_devices:
        if (keyword.lower() in device.name.lower() or 
            keyword.lower() in device.model.lower() or
            keyword.lower() in device.borrower.lower()):
            results.append({
                'id': device.id,
                'name': device.name,
                'model': device.model,
                'status': device.status.value,
                'borrower': device.borrower
            })
    
    return jsonify(results)


@app.route('/api/users')
@login_required
def api_users():
    """获取用户列表API"""
    users = api_client.get_all_users()
    result = []
    for user in users:
        if user.borrower_name and not user.is_frozen:
            result.append({
                'id': user.id,
                'name': user.borrower_name,
                'weixin_name': user.wechat_name
            })
    return jsonify(result)


@app.route('/api/report-lost', methods=['POST'])
@login_required
def api_report_lost():
    """报备丢失API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    # 更新设备状态为丢失
    device.status = DeviceStatus.LOST
    device.lost_time = datetime.now()
    device.previous_borrower = device.borrower
    
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
        borrower=user['borrower_name'],
        phone=device.phone,
        reason='用户报备丢失',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    api_client.add_operation_log(f"报备丢失: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '丢失报备成功'})


@app.route('/api/report-damage', methods=['POST'])
@login_required
def api_report_damage():
    """报备损坏API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    damage_reason = data.get('damage_reason', '').strip()
    action = data.get('action', 'repair')  # repair 或 return
    
    if not damage_reason:
        return jsonify({'success': False, 'message': '请输入损坏情况'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    original_borrower = device.borrower
    
    # 更新设备状态
    device.status = DeviceStatus.DAMAGED
    device.damage_reason = damage_reason
    device.damage_time = datetime.now()
    
    api_client.update_device(device)
    
    # 添加记录
    if action == 'return':
        # 归还并报备损坏
        device.borrower = ''
        device.phone = ''
        device.borrow_time = None
        device.location = ''
        device.reason = ''
        device.entry_source = ''
        device.expected_return_date = None
        
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.REPORT_DAMAGE,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"损坏归还：{original_borrower}",
            phone=device.phone,
            reason=damage_reason,
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"损坏归还: {user['borrower_name']}", device.name)
    else:
        # 仅报备损坏，继续借用
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.REPORT_DAMAGE,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=user['borrower_name'],
            phone=device.phone,
            reason=damage_reason,
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"报备损坏: {user['borrower_name']}", device.name)
    
    api_client._records.append(record)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '损坏报备成功'})


@app.route('/api/found-device', methods=['POST'])
@login_required
def api_found_device():
    """设备找回API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备是否处于丢失状态
    if device.status != DeviceStatus.LOST:
        return jsonify({'success': False, 'message': '设备未处于丢失状态'})
    
    original_borrower = device.borrower
    
    # 更新设备状态
    device.status = DeviceStatus.BORROWED
    device.lost_time = None

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
        borrower=original_borrower,
        phone=device.phone,
        reason='设备已找回',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    
    api_client.add_operation_log(f"设备找回: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '设备找回成功'})


@app.route('/api/repair-device', methods=['POST'])
@login_required
def api_repair_device():
    """设备修复API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    action = data.get('action', 'keep')  # keep 或 return
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备是否处于损坏状态
    if device.status != DeviceStatus.DAMAGED:
        return jsonify({'success': False, 'message': '设备未处于损坏状态'})
    
    original_borrower = device.borrower
    
    if action == 'return':
        # 修复并归还
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

        api_client.update_device(device)

        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.REPAIRED,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"修复并归还：{original_borrower}",
            phone=device.phone,
            reason='设备已修复并归还',
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"修复归还: {user['borrower_name']}", device.name)
    else:
        # 仅修复，继续借用
        device.status = DeviceStatus.BORROWED
        device.damage_reason = ''
        device.damage_time = None

        api_client.update_device(device)
        
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type='车机' if isinstance(device, CarMachine) else '手机',
            operation_type=OperationType.REPAIRED,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"修复：{original_borrower}——>{device.borrower}",
            phone=device.phone,
            reason='设备已修复',
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"设备修复: {user['borrower_name']}", device.name)
    
    api_client._records.append(record)
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
    """直接标记为未找到（丢失）API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    original_borrower = device.borrower
    
    # 转为丢失状态
    device.status = DeviceStatus.LOST
    device.previous_borrower = original_borrower
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
        borrower=f"未找到：{original_borrower}",
        phone=device.phone,
        reason='设备未找到，标记为丢失',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"未找到标记丢失: {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '已标记为丢失'})


@app.route('/api/transfer-custodian', methods=['POST'])
@login_required
def api_transfer_custodian():
    """转给保管人API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备是否处于丢失状态
    if device.status != DeviceStatus.LOST:
        return jsonify({'success': False, 'message': '设备未处于丢失状态'})
    
    # 检查当前用户是否为管理员
    if not user.get('is_admin'):
        return jsonify({'success': False, 'message': '仅限管理员使用此功能'})
    
    original_borrower = device.borrower
    
    # 转给管理员（保管人）
    device.previous_borrower = original_borrower
    device.borrower = user['borrower_name']
    device.phone = user['phone']
    device.status = DeviceStatus.BORROWED
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.CUSTODIAN_CHANGE,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"转给保管人：{original_borrower}——>{user['borrower_name']}",
        phone=user['phone'],
        reason='丢失设备转给保管人',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"转给保管人: {original_borrower} -> {user['borrower_name']}", device.name)
    api_client._save_data()
    
    return jsonify({'success': True, 'message': '设备已转给保管人'})


@app.route('/api/renew', methods=['POST'])
@login_required
def api_renew():
    """续借设备API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    days = data.get('days', 7)
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人
    if device.borrower != user['borrower_name']:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人'})
    
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    # 更新预计归还日期
    if device.expected_return_date:
        device.expected_return_date = device.expected_return_date + timedelta(days=int(days))
    else:
        device.expected_return_date = datetime.now() + timedelta(days=int(days))
    
    api_client.update_device(device)
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type='车机' if isinstance(device, CarMachine) else '手机',
        operation_type=OperationType.RENEW,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=user['borrower_name'],
        phone=device.phone,
        reason=f'续借 {days} 天',
        entry_source=EntrySource.USER.value
    )
    api_client._records.append(record)
    api_client.add_operation_log(f"续借设备: {user['borrower_name']}, {days}天", device.name)
    api_client._save_data()
    
    return jsonify({
        'success': True, 
        'message': f'续借成功，新的预计归还日期: {device.expected_return_date.strftime("%Y-%m-%d")}'
    })


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message='页面未找到'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message='服务器内部错误'), 500


if __name__ == '__main__':
    print(f"用户服务启动在端口 {USER_SERVICE_PORT}")
    app.run(debug=True, host='0.0.0.0', port=USER_SERVICE_PORT)

