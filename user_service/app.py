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
import re
import json
import calendar
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response, send_file, send_from_directory
from dotenv import load_dotenv

# 从 common 导入
from common.models import DeviceStatus, DeviceType, OperationType, EntrySource, ReservationStatus, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, ViewRecord, PointsTransactionType
from common.api_client import api_client
from common.db_store import DatabaseStore, init_database
from common.utils import mask_phone, is_mobile_device
from common.config import SECRET_KEY, SERVER_URL, USER_SERVICE_PORT
from common.points_service import points_service

# 尝试导入qrcode，如果没有安装则使用备用方案
try:
    import qrcode
    from qrcode.image.pil import PilImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    print("警告: qrcode模块未安装，二维码功能将使用备用方案")

# 尝试导入APScheduler用于定时任务
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    print("警告: APScheduler模块未安装，定时任务功能将不可用")

load_dotenv()

app = Flask(__name__)
app.secret_key = SECRET_KEY

# 初始化数据库（创建必要的表）
init_database()

# 自定义Jinja2过滤器：处理nan值
import math
@app.template_filter('nan_to_empty')
def nan_to_empty(value):
    """将nan值转换为空字符串或'-'"""
    if value is None:
        return '-'
    if isinstance(value, float) and math.isnan(value):
        return '-'
    return value

@app.template_filter('nan_to_default')
def nan_to_default(value, default='-'):
    """将nan值转换为指定默认值"""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    return value


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


def get_user_total_points(user_id: str) -> int:
    """获取用户当前总积分"""
    user_points = api_client._db.get_user_points(user_id)
    return user_points.points if user_points else 0


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
            'current_theme': user.current_theme,
            'points': points,
        }
    return {}


def is_admin_user(borrower_name):
    """检查指定借用人是否为管理员"""
    return api_client.is_user_admin(borrower_name)


def get_current_theme_icon(user_id):
    """获取用户当前主题的图标标识"""
    if not user_id:
        return None
    user = api_client._db.get_user_by_id(user_id)
    if user and user.current_theme:
        theme_item = api_client._db.get_shop_item_by_id(user.current_theme)
        if theme_item:
            return theme_item.icon
    return None


def get_user_equipment(user_id):
    """获取用户装备信息（称号、头像边框、主题皮肤）"""
    user = api_client._db.get_user_by_id(user_id)
    if not user:
        return {'title': None, 'avatar_frame': None, 'theme': None}

    result = {'title': None, 'avatar_frame': None, 'theme': None}

    # 获取当前称号
    if user.current_title:
        title_item = api_client._db.get_shop_item_by_id(user.current_title)
        if title_item:
            result['title'] = {
                'id': title_item.id,
                'name': title_item.name,
                'color': title_item.color or '#1890ff'
            }
        else:
            # 可能是隐藏称号，从背包中查找
            user_inventory = api_client._db.get_user_inventory(user_id)
            for inv_item in user_inventory:
                if inv_item.item_id == user.current_title and inv_item.item_type.value == '称号':
                    result['title'] = {
                        'id': inv_item.item_id,
                        'name': inv_item.item_name,
                        'color': inv_item.item_color or '#1890ff'
                    }
                    break

    # 获取当前头像边框
    if user.current_avatar_frame:
        frame_item = api_client._db.get_shop_item_by_id(user.current_avatar_frame)
        if frame_item:
            result['avatar_frame'] = {
                'id': frame_item.id,
                'name': frame_item.name,
                'color': frame_item.color or '#1890ff',
                'icon': frame_item.icon or 'simple'
            }

    # 获取当前主题皮肤
    if user.current_theme:
        theme_item = api_client._db.get_shop_item_by_id(user.current_theme)
        if theme_item:
            result['theme'] = {
                'id': theme_item.id,
                'name': theme_item.name,
                'icon': theme_item.icon or 'default'
            }

    return result


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


def get_device_stats():
    """获取设备统计数据"""
    api_client.reload_data()
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.CIRCULATING, DeviceStatus.NO_CABINET]])
    borrowed_devices_count = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])

    # 详细状态统计
    in_stock_count = len([d for d in all_devices if d.status == DeviceStatus.IN_STOCK])  # 在库
    in_custody_count = len([d for d in all_devices if d.status == DeviceStatus.IN_CUSTODY])  # 保管中
    no_cabinet_count = len([d for d in all_devices if d.status == DeviceStatus.NO_CABINET])  # 无柜号
    circulating_count = len([d for d in all_devices if d.status == DeviceStatus.CIRCULATING])  # 流通
    sealed_count = len([d for d in all_devices if d.status == DeviceStatus.SEALED])  # 封存

    # 获取车机/仪表筛选选项
    car_devices = [d for d in all_devices if d.device_type.value in ['车机', '仪表']]
    os_versions = sorted(set(d.os_version for d in car_devices if d.os_version))
    os_platforms = sorted(set(d.os_platform for d in car_devices if d.os_platform))
    product_names = sorted(set(d.product_name for d in car_devices if d.product_name))
    resolutions = sorted(set(d.screen_resolution for d in car_devices if d.screen_resolution))

    # 计算无法使用的设备数量
    unavailable_count = len([d for d in all_devices if d.status in [DeviceStatus.LOST, DeviceStatus.DAMAGED, DeviceStatus.SHIPPED, DeviceStatus.SCRAPPED, DeviceStatus.SEALED]])

    return {
        'total_devices': total_devices,
        'available_devices': available_devices,
        'borrowed_devices_count': borrowed_devices_count,
        'in_stock_count': in_stock_count,
        'in_custody_count': in_custody_count,
        'no_cabinet_count': no_cabinet_count,
        'circulating_count': circulating_count,
        'sealed_count': sealed_count,
        'unavailable_count': unavailable_count,
        'os_versions': os_versions,
        'os_platforms': os_platforms,
        'product_names': product_names,
        'resolutions': resolutions
    }


def get_user_rank_data(user_name):
    """获取当前用户的排行数据"""
    if not user_name:
        return {
            'borrow_rank': None,
            'borrow_total': 0,
            'borrow_title': None,
            'return_rank': None,
            'return_total': 0,
            'return_title': None
        }

    # 借用次数排行
    borrow_rankings = api_client.get_user_rankings('borrow')
    borrow_rank = None
    borrow_total = 0
    borrow_title = None
    for ranking in borrow_rankings:
        if ranking['user_name'] == user_name:
            borrow_rank = ranking['rank']
            borrow_total = ranking['count']
            borrow_title = ranking.get('title')
            break

    # 归还次数排行
    return_rankings = api_client.get_user_rankings('return')
    return_rank = None
    return_total = 0
    return_title = None
    for ranking in return_rankings:
        if ranking['user_name'] == user_name:
            return_rank = ranking['rank']
            return_total = ranking['count']
            return_title = ranking.get('title')
            break

    return {
        'borrow_rank': borrow_rank,
        'borrow_total': borrow_total,
        'borrow_title': borrow_title,
        'return_rank': return_rank,
        'return_total': return_total,
        'return_title': return_title
    }


@app.context_processor
def inject_globals():
    """注入全局模板变量和函数"""
    user = get_current_user()
    rank_data = get_user_rank_data(user.get('borrower_name', ''))

    # 获取用户称号（基于累计积分排名）
    user_title = None
    if user and user.get('user_id'):
        try:
            points_rank_info = points_service.get_user_points_rank(user['user_id'])
            if points_rank_info and points_rank_info.get('rank') and points_rank_info['rank'] <= 10:
                rank = points_rank_info['rank']
                user_title = points_service.POINTS_TITLES[rank - 1] if rank <= len(points_service.POINTS_TITLES) else points_service.POINTS_TITLES[-1]
        except Exception:
            pass

    # 获取用户装备的称号和头像边框
    user_equipped_title = None
    user_avatar_frame = None
    if user and user.get('user_id'):
        try:
            equipment = get_user_equipment(user['user_id'])
            user_equipped_title = equipment.get('title')
            user_avatar_frame = equipment.get('avatar_frame')
        except Exception:
            pass

    # 获取用户当前鼠标皮肤
    current_cursor_skin = None
    if user and user.get('user_id'):
        try:
            full_user = api_client._db.get_user_by_id(user['user_id'])
            if full_user and full_user.current_cursor:
                cursor_item = api_client._db.get_shop_item_by_id(full_user.current_cursor)
                if cursor_item:
                    current_cursor_skin = cursor_item.icon
        except Exception:
            pass

    # 鼠标皮肤图标映射
    cursor_emoji_map = {
        'cat-paw-pink': '🐾',
        'unicorn-rainbow': '🦄',
        'bunny-ears': '🐰',
        'magic-star': '⭐',
        'candy-heart': '🍬',
        'cloud-cotton': '☁️',
        'butterfly-wing': '🦋',
        'pearl-shell': '🐚',
        'cyber-lightsaber': '⚔️',
        'mechanical-gear': '⚙️',
        'gaming-blade': '🗡️',
        'quantum-core': '🔮',
        'dragon-scale': '🐲',
        'obsidian-edge': '💎',
        'minimal-geo': '◆',
        'gradient-flow': '🌈',
        'ink-wash': '🎨',
        'star-trail': '✨',
        'crystal-prism': '💠',
    }

    def get_cursor_emoji(icon):
        return cursor_emoji_map.get(icon, '🖱️')

    def get_cursor_svg_base64(icon):
        """生成鼠标皮肤的SVG并返回Base64编码"""
        import base64
        emoji = cursor_emoji_map.get(icon, '🖱️')
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><text x="0" y="24" font-size="24">{emoji}</text></svg>'''
        return base64.b64encode(svg.encode('utf-8')).decode('utf-8')

    return {
        'is_admin_user': is_admin_user,
        'user_title': user_title,
        'user_equipped_title': user_equipped_title,
        'user_avatar_frame': user_avatar_frame,
        'current_cursor_skin': current_cursor_skin,
        'get_cursor_emoji': get_cursor_emoji,
        'get_cursor_svg_base64': get_cursor_svg_base64,
        **rank_data
    }


def device_route(mobile_route, pc_route):
    """根据设备类型返回对应的路由"""
    if is_mobile_device(request):
        return redirect(url_for(mobile_route))
    return redirect(url_for(pc_route))


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页 - 直接跳转到电脑端登录"""
    if 'user_id' in session:
        # 已登录用户跳转到PC端首页
        return redirect(url_for('pc_dashboard'))
    # 未登录用户直接跳转到电脑端登录页面
    return redirect(url_for('pc_login'))


@app.route('/select-device')
def select_device_type():
    """设备选择页面"""
    return render_template('select_device_type.html')


@app.route('/login/mobile', methods=['GET', 'POST'])
def mobile_login():
    """手机端登录页面 - 使用邮箱登录，与PC端保持一致"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template('mobile/login.html', error='请输入邮箱和密码')

        # 使用与PC端相同的验证方式
        user = api_client.verify_user_login(email, password)
        if user:
            session['user_id'] = user.id
            session['email'] = user.email
            session['login_device_type'] = 'mobile'

            # 首次登录奖励积分
            points_result = points_service.first_login_reward(user.id)
            if points_result['success']:
                session['first_login_points'] = points_result['points']
                session['points_message'] = points_result['message']
                daily_result = points_service.daily_login_reward(user.id)
                if daily_result['success']:
                    session['daily_login_points'] = daily_result['points']
                    session['daily_login_message'] = daily_result['message']
            else:
                daily_result = points_service.daily_login_reward(user.id)
                if daily_result['success']:
                    session['daily_login_points'] = daily_result['points']
                    session['daily_login_message'] = daily_result['message']

            # 检查是否需要设置借用人名称
            if not user.borrower_name:
                return redirect(url_for('set_borrower_name'))

            # 检查是否是首次登录
            if user.is_first_login:
                return redirect(url_for('change_password'))

            return redirect(url_for('home'))
        else:
            return render_template('mobile/login.html', error='邮箱或密码错误，或账号已被冻结')

    return render_template('mobile/login.html')


@app.route('/login/pc', methods=['GET', 'POST'])
def pc_login():
    """电脑端登录页面 - 不带二维码"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template('pc/login.html', error='请输入邮箱和密码')

        user = api_client.verify_user_login(email, password)
        if user:
            session['user_id'] = user.id
            session['email'] = user.email
            session['login_device_type'] = 'pc'  # 记录登录设备类型

            # 首次登录奖励积分（在设置session之后）
            points_result = points_service.first_login_reward(user.id)
            if points_result['success']:
                session['first_login_points'] = points_result['points']
                session['points_message'] = points_result['message']
                # 首次登录也发放每日登录奖励
                daily_result = points_service.daily_login_reward(user.id)
                if daily_result['success']:
                    session['daily_login_points'] = daily_result['points']
                    session['daily_login_message'] = daily_result['message']
            else:
                # 不是首次登录，只发放每日登录奖励
                daily_result = points_service.daily_login_reward(user.id)
                if daily_result['success']:
                    session['daily_login_points'] = daily_result['points']
                    session['daily_login_message'] = daily_result['message']

            # 检查是否需要设置借用人名称
            if not user.borrower_name:
                return redirect(url_for('set_borrower_name'))

            # 检查是否是首次登录，如果是则要求修改密码
            if user.is_first_login:
                return redirect(url_for('change_password'))

            return redirect(url_for('pc_dashboard'))
        else:
            return render_template('pc/login.html', error='邮箱或密码错误，或账号已被冻结')

    # 获取预填充的邮箱（从URL参数或session中）
    prefilled_email = request.args.get('email', '') or session.get('prefilled_email', '')
    # 如果使用了session中的预填充邮箱，使用后清除
    if 'prefilled_email' in session:
        session.pop('prefilled_email', None)
    return render_template('pc/login.html', prefilled_email=prefilled_email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录页面 - 直接重定向到电脑端登录"""
    return redirect(url_for('pc_login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册页面"""
    if request.method == 'POST':
        borrower_name = request.form.get('borrower_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # 验证输入
        if not all([borrower_name, email, password, confirm_password]):
            return render_template('register.html', error='请填写所有必填项')

        if password != confirm_password:
            return render_template('register.html', error='两次输入的密码不一致')

        # 尝试注册
        success, result = api_client.register_user(email, password, borrower_name)
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


@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """修改密码（首次登录或主动修改）"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = api_client.get_user_by_id(user_id)
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password or not confirm_password:
            return render_template('change_password.html', error='请填写所有必填项', is_first_login=user.is_first_login)
        
        if new_password != confirm_password:
            return render_template('change_password.html', error='两次输入的密码不一致', is_first_login=user.is_first_login)
        
        if len(new_password) < 6:
            return render_template('change_password.html', error='密码长度至少6位', is_first_login=user.is_first_login)
        
        # 修改密码
        success = api_client.change_user_password(user_id, new_password)
        if success:
            # 密码修改成功后，保存邮箱并清除session，要求重新登录
            user_email = session.get('email', '')
            session.clear()
            session['prefilled_email'] = user_email
            return redirect(url_for('pc_login'))
        else:
            return render_template('change_password.html', error='修改密码失败', is_first_login=user.is_first_login)
    
    return render_template('change_password.html', is_first_login=user.is_first_login if user else False)


# ==================== 移动端路由 ====================

@app.route('/home')
@login_required
def home():
    """手机端首页 - 显示我的借用、归还、转借、预约等基础操作"""
    from datetime import datetime
    user = get_current_user()

    # 检查用户是否存在（可能已被删除）
    if not user or 'borrower_name' not in user:
        session.clear()
        return redirect(url_for('login'))

    # 重新加载数据以获取最新数据
    api_client.reload_data()

    # 获取所有设备
    all_devices = api_client.get_all_devices()

    # 获取我保管的设备数量
    my_custodian_devices = [d for d in all_devices if d.cabinet_number == user['borrower_name']]
    my_custodian_count = len(my_custodian_devices)

    # 获取当前用户借用的设备，并计算剩余逾期时间
    raw_borrowed_devices = [d for d in all_devices if d.borrower == user['borrower_name'] and d.status != DeviceStatus.SHIPPED]
    my_borrowed_devices = []
    for device in raw_borrowed_devices:
        device.is_overdue = False
        device.overdue_days = 0
        device.remaining_time_display = ''
        device.can_renew = False

        if device.expected_return_date:
            time_diff = device.expected_return_date - datetime.now()
            total_seconds = time_diff.total_seconds()

            if total_seconds < -60:
                # 已逾期超过1分钟
                device.is_overdue = True
                device.overdue_days = int(abs(total_seconds) // (24 * 3600))
                if device.overdue_days <= 3:
                    device.can_renew = True
            elif total_seconds < 0:
                # 逾期1分钟内
                device.remaining_time_display = '0 分钟'
                device.can_renew = True
            else:
                # 剩余时间
                remaining_days = int(total_seconds // (24 * 3600))
                actual_remaining_hours = int(total_seconds // 3600)
                if remaining_days > 0:
                    device.remaining_time_display = f"{remaining_days} 天"
                elif actual_remaining_hours > 0:
                    device.remaining_time_display = f"{actual_remaining_hours} 小时"
                else:
                    mins = int(total_seconds // 60)
                    device.remaining_time_display = f"{mins} 分钟"

                # 剩余时间小于24小时才能续借
                total_hours_float = total_seconds / 3600
                total_hours_int = int(total_hours_float)
                remaining_hours = total_hours_int if total_hours_float == total_hours_int else total_hours_int + 1
                device.can_renew = remaining_hours < 24
        else:
            device.remaining_time_display = '长期借用'
            device.can_renew = False

        my_borrowed_devices.append(device)

    my_borrowed_count = len(my_borrowed_devices)

    # 获取我的预约
    my_reservations = api_client.get_user_reservations(user['user_id'])

    # 筛选需要显示的预约
    active_reservations = []
    now = datetime.now()

    for r in my_reservations:
        if r.status in ['待保管人确认', '待借用人确认', '待2人确认']:
            active_reservations.append(r)
        elif r.status == '已同意':
            if r.start_time and r.start_time > now:
                active_reservations.append(r)
        elif r.status == '已拒绝':
            if r.start_time and r.start_time > now:
                active_reservations.append(r)

    my_reservation_count = len(active_reservations)

    # 获取需要当前用户确认的预约（作为保管人或借用人）
    pending_confirm_reservations = []
    for device in all_devices:
        is_custodian = device.cabinet_number == user['borrower_name']
        is_borrower = (device.borrower and user['borrower_name'] in device.borrower) and device.status == DeviceStatus.BORROWED

        if not is_custodian and not is_borrower:
            continue

        reservations = api_client.get_device_reservations(device.id, None, False)

        for r in reservations:
            if is_custodian and r.status in ['待保管人确认', '待2人确认'] and not r.custodian_approved:
                if r.custodian_id == user['user_id'] or (not r.custodian_id and device.cabinet_number == user['borrower_name']):
                    pending_confirm_reservations.append({
                        'id': r.id,
                        'reserver_name': r.reserver_name,
                        'reserver_id': r.reserver_id,
                        'device_id': device.id,
                        'device_name': device.name,
                        'device_type': get_device_type_str(device),
                        'start_time': r.start_time,
                        'end_time': r.end_time,
                        'confirm_role': 'custodian',
                        'role_display': '保管人确认'
                    })

            if is_borrower and r.status in ['待借用人确认', '待2人确认'] and not r.borrower_approved:
                is_current_borrower = (
                    r.current_borrower_id == user['user_id'] or
                    r.current_borrower_name == user['borrower_name'] or
                    device.borrower == user['borrower_name']
                )
                if is_current_borrower:
                    pending_confirm_reservations.append({
                        'id': r.id,
                        'reserver_name': r.reserver_name,
                        'reserver_id': r.reserver_id,
                        'device_id': device.id,
                        'device_name': device.name,
                        'device_type': get_device_type_str(device),
                        'start_time': r.start_time,
                        'end_time': r.end_time,
                        'confirm_role': 'borrower',
                        'role_display': '借用人确认'
                    })

    return render_template('mobile/dashboard.html',
                         user=user,
                         my_borrowed_devices=my_borrowed_devices,
                         my_borrowed_count=my_borrowed_count,
                         my_custodian_count=my_custodian_count,
                         my_reservation_count=my_reservation_count,
                         my_reservations=active_reservations,
                         pending_confirm_reservations=pending_confirm_reservations)


@app.route('/devices')
@login_required
def device_list():
    """移动端设备列表"""
    user = get_current_user()
    device_type = request.args.get('type', 'car')

    # 重新加载数据
    api_client.reload_data()

    # 获取所有设备
    all_devices = api_client.get_all_devices()

    # 根据类型筛选
    if device_type == 'car':
        devices = [d for d in all_devices if d.device_type.value == '车机']
    elif device_type == 'phone':
        devices = [d for d in all_devices if d.device_type.value == '手机']
    elif device_type == 'instrument':
        devices = [d for d in all_devices if d.device_type.value == '仪表']
    elif device_type == 'simcard':
        devices = [d for d in all_devices if d.device_type.value == '手机卡']
    elif device_type == 'other':
        devices = [d for d in all_devices if d.device_type.value == '其它']
    else:
        devices = all_devices

    return render_template('mobile/device_list.html',
                         devices=devices,
                         device_type=device_type,
                         user=user)


@app.route('/device/<device_id>')
@login_required
def device_detail(device_id):
    """移动端设备详情"""
    user = get_current_user()
    device_type = request.args.get('device_type', 'car')

    # 重新加载数据
    api_client.reload_data()

    # 获取设备详情
    device = api_client.get_device(device_id)
    if not device:
        return render_template('mobile/device_detail.html', error='设备不存在', user=user)

    return render_template('mobile/device_detail.html',
                         device=device,
                         device_type=device_type,
                         user=user)


@app.route('/device/<device_id>/simple')
@login_required
def device_detail_simple(device_id):
    """设备详情页面（简化版）- 直接重定向到PC端"""
    device_type = request.args.get('device_type', '')
    if device_type:
        return redirect(url_for('pc_device_detail_simple', device_id=device_id, device_type=device_type))
    return redirect(url_for('pc_device_detail_simple', device_id=device_id))


@app.route('/borrow/<device_id>')
@login_required
def borrow_device(device_id):
    """借用设备页面 - 直接重定向到PC端"""
    return redirect(url_for('pc_device_detail', device_id=device_id))


@app.route('/return/<device_id>')
@login_required
def return_device(device_id):
    """归还设备页面 - 直接重定向到PC端"""
    return redirect(url_for('pc_device_detail', device_id=device_id))


@app.route('/transfer/<device_id>')
@login_required
def transfer_device(device_id):
    """转借设备页面 - 直接重定向到PC端"""
    return redirect(url_for('pc_device_detail', device_id=device_id))


@app.route('/remark/add/<device_id>')
@login_required
def add_remark(device_id):
    """添加备注页面 - 直接重定向到PC端"""
    return redirect(url_for('pc_device_detail', device_id=device_id))


@app.route('/remark/edit/<remark_id>')
@login_required
def edit_remark(remark_id):
    """编辑备注页面 - 直接重定向到PC端"""
    # 查找备注获取设备ID
    remark = None
    for r in api_client._remarks:
        if r.id == remark_id:
            remark = r
            break
    if remark:
        return redirect(url_for('pc_device_detail', device_id=remark.device_id))
    return redirect(url_for('pc_device_list'))


@app.route('/my-records')
@login_required
def my_records():
    """移动端我的记录"""
    user = get_current_user()
    filter_type = request.args.get('filter_type', 'all')

    # 重新加载数据
    api_client.reload_data()

    # 获取所有记录
    all_records = api_client.get_records()

    # 筛选当前用户的记录
    my_records_list = [r for r in all_records if r.borrower == user['borrower_name']]

    # 根据筛选类型过滤
    if filter_type == 'borrowed':
        # 借用中的记录（没有归还时间的借用记录）
        records = [r for r in my_records_list if r.action == '借用' and not r.return_time]
    elif filter_type == 'returned':
        # 已归还的记录
        records = [r for r in my_records_list if r.return_time]
    else:
        # 全部记录
        records = my_records_list

    return render_template('mobile/records.html',
                         records=records,
                         filter_type=filter_type,
                         user=user)


# ==================== PC端路由 ====================

@app.route('/pc')
@login_required
def pc_dashboard():
    """PC端首页仪表盘"""
    from datetime import datetime
    user = get_current_user()

    # 检查用户是否存在（可能已被删除）
    if not user or 'borrower_name' not in user:
        session.clear()
        return redirect(url_for('login'))

    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    # 获取统计数据
    all_devices = api_client.get_all_devices()
    total_devices = len(all_devices)
    available_devices = len([d for d in all_devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.CIRCULATING, DeviceStatus.NO_CABINET]])
    borrowed_devices_count = len([d for d in all_devices if d.status == DeviceStatus.BORROWED])

    # 详细状态统计
    in_stock_count = len([d for d in all_devices if d.status == DeviceStatus.IN_STOCK])  # 在库
    in_custody_count = len([d for d in all_devices if d.status == DeviceStatus.IN_CUSTODY])  # 保管中
    no_cabinet_count = len([d for d in all_devices if d.status == DeviceStatus.NO_CABINET])  # 无柜号
    circulating_count = len([d for d in all_devices if d.status == DeviceStatus.CIRCULATING])  # 流通
    unavailable_count = len([d for d in all_devices if d.status in [DeviceStatus.LOST, DeviceStatus.DAMAGED, DeviceStatus.SHIPPED, DeviceStatus.SCRAPPED, DeviceStatus.SEALED]])  # 无法使用

    # 获取我保管的设备
    my_custodian_devices = [d for d in all_devices if d.cabinet_number == user['borrower_name']]
    my_custodian_count = len(my_custodian_devices)

    # 获取当前用户借用的设备，并计算剩余逾期时间
    # 排除已寄出状态的设备
    raw_borrowed_devices = [d for d in all_devices if d.borrower == user['borrower_name'] and d.status != DeviceStatus.SHIPPED]
    my_borrowed_devices = []
    for device in raw_borrowed_devices:
        device.is_overdue = False
        device.overdue_days = 0
        device.overdue_hours = 0
        device.overdue_minutes = 0
        device.remaining_days = 0
        device.remaining_hours = 0
        device.remaining_minutes = 0
        device.remaining_time_display = ''  # 格式化后的剩余时间显示
        device.can_renew = False
        device.renew_disabled_reason = ''

        if device.expected_return_date:
            time_diff = device.expected_return_date - datetime.now()
            total_seconds = time_diff.total_seconds()

            if total_seconds < -60:
                # 已逾期超过1分钟
                device.is_overdue = True
                device.overdue_hours = int(abs(total_seconds) // 3600)
                device.overdue_days = int(abs(total_seconds) // (24 * 3600))
                device.overdue_minutes = int(abs(total_seconds) // 60)
                # 逾期超过3天不能续借
                if device.overdue_days > 3:
                    device.can_renew = False
                    device.renew_disabled_reason = '逾期超过3天，不能续借，需要归还后才能再次借用'
                else:
                    device.can_renew = True
            elif total_seconds < 0:
                # 逾期1分钟内，不算逾期，显示剩余0分钟
                device.is_overdue = False
                device.remaining_days = 0
                device.remaining_hours = 0
                device.remaining_minutes = 0
                device.remaining_time_display = '0 分钟'
                # 剩余时间小于24小时才能续借
                device.can_renew = True
            else:
                # 剩余时间（向上取整）
                device.remaining_days = int(total_seconds // (24 * 3600))
                # remaining_hours 表示总剩余小时数（向上取整），用于模板判断 remaining_hours < 24
                total_hours_float = total_seconds / 3600
                total_hours_int = int(total_hours_float)
                device.remaining_hours = total_hours_int if total_hours_float == total_hours_int else total_hours_int + 1

                # 计算剩余分钟数（用于小于1小时的显示）
                device.remaining_minutes = int(total_seconds // 60)

                # 生成格式化的剩余时间显示
                # 计算实际剩余小时数（向下取整，用于显示）
                actual_remaining_hours = int(total_seconds // 3600)
                if device.remaining_days > 0:
                    # 大于1天，显示天、小时和分钟
                    remaining_hours_after_days = int((total_seconds % (24 * 3600)) // 3600)
                    remaining_mins = int((total_seconds % 3600) // 60)
                    if remaining_hours_after_days > 0 and remaining_mins > 0:
                        device.remaining_time_display = f"{device.remaining_days} 天 {remaining_hours_after_days} 小时 {remaining_mins} 分钟"
                    elif remaining_hours_after_days > 0:
                        device.remaining_time_display = f"{device.remaining_days} 天 {remaining_hours_after_days} 小时"
                    else:
                        device.remaining_time_display = f"{device.remaining_days} 天"
                elif actual_remaining_hours > 0:
                    # 小于24小时，显示小时和分钟
                    remaining_mins = int((total_seconds % 3600) // 60)
                    if remaining_mins > 0:
                        device.remaining_time_display = f"{actual_remaining_hours} 小时 {remaining_mins} 分钟"
                    else:
                        device.remaining_time_display = f"{actual_remaining_hours} 小时"
                else:
                    # 小于1小时，显示分钟
                    mins = int(total_seconds // 60)
                    device.remaining_time_display = f"{mins} 分钟"

                # 剩余时间小于24小时才能续借
                device.can_renew = device.remaining_hours < 24
                if not device.can_renew:
                    device.renew_disabled_reason = '剩余时间大于24小时，暂不需要续借'
        else:
            # 长期借用，无固定归还时间
            device.remaining_time_display = '长期借用'
            device.can_renew = False  # 长期借用不需要续借
            device.renew_disabled_reason = '长期借用无需续借'

        my_borrowed_devices.append(device)

    my_borrowed_count = len(my_borrowed_devices)

    # 获取我的预约
    from datetime import datetime
    my_reservations = api_client.get_user_reservations(user['user_id'])
    
    # 筛选需要显示的预约：
    # 1. 待确认的预约（始终显示）
    # 2. 已同意的预约（如果预约开始时间未到，显示；如果已到，不显示，因为已自动转为借用）
    # 3. 已拒绝的预约（保留显示到预约开始时间，但如果该设备有更新状态的预约记录则隐藏）
    # 4. 已取消的预约（不显示）
    active_reservations = []
    now = datetime.now()
    
    # 按设备ID分组，找出每个设备最新的预约记录时间
    device_latest_reservation_time = {}
    for r in my_reservations:
        if r.device_id not in device_latest_reservation_time:
            device_latest_reservation_time[r.device_id] = r.created_at
        elif r.created_at and r.created_at > device_latest_reservation_time[r.device_id]:
            device_latest_reservation_time[r.device_id] = r.created_at
    
    for r in my_reservations:
        # 待确认的预约始终显示
        if r.status in ['待保管人确认', '待借用人确认', '待2人确认']:
            active_reservations.append(r)
        # 已同意的预约，只显示预约开始时间未到期的
        elif r.status == '已同意':
            if r.start_time and r.start_time > now:
                active_reservations.append(r)
        # 已拒绝的预约，保留显示到预约开始时间
        # 但如果该设备有更新状态的预约记录（即不是该设备最新的预约），则隐藏
        elif r.status == '已拒绝':
            if r.start_time and r.start_time > now:
                # 检查该预约是否是该设备最新的预约
                # 如果不是最新的（有更新的预约记录），则隐藏
                if r.created_at and r.created_at >= device_latest_reservation_time.get(r.device_id, r.created_at):
                    active_reservations.append(r)
        # 已取消的预约不显示
        # elif r.status == '已取消':
        #     pass
    
    my_reservation_count = len(active_reservations)

    # 统计各类型借用设备数量
    my_borrowed_type_counts = {}
    for device in my_borrowed_devices:
        type_name = device.device_type.value
        my_borrowed_type_counts[type_name] = my_borrowed_type_counts.get(type_name, 0) + 1

    # 获取最近记录（限制100条，提高性能）
    recent_records = []
    all_records = api_client.get_records(limit=100)
    for record in all_records[:10]:
        if user['borrower_name'] in record.borrower or record.operator == user['borrower_name']:
            recent_records.append(record)

    # 获取我保管/借用但被借走的信息（最近100条记录中筛选）
    my_items_borrowed = []
    seen_notifications = set()  # 用于去重：设备名+借用人+类型

    for record in all_records:
        device = api_client.get_device_by_id(record.device_id)
        if not device:
            continue

        # 借出/转借相关通知
        if '借出' in record.operation_type.value or '转借' in record.operation_type.value:
            # 显示最终借用人（设备当前借用人）
            final_borrower = device.borrower if device.borrower else record.borrower
            # 生成稳定的通知ID：设备名_类型_时间戳
            notification_id = f"{device.name}_{record.operation_type.value}_{record.operation_time.strftime('%Y%m%d%H%M%S')}"
            item = {'device_name': device.name, 'device_type': device.device_type.value, 'borrower': final_borrower, 'time': record.operation_time, 'type': '', 'id': notification_id}

            # 我保管的设备被别人借走（排除自己操作的）
            if device.cabinet_number == user['borrower_name'] and device.borrower and device.borrower != user['borrower_name'] and record.borrower != user['borrower_name']:
                item['type'] = '保管-被动'
                # 去重检查：同一设备+同一借用人+同一类型只保留一条
                dedup_key = f"{device.name}_{final_borrower}_保管-被动"
                if dedup_key not in seen_notifications:
                    seen_notifications.add(dedup_key)
                    my_items_borrowed.append(item)
            # 我正在借用的设备被别人转借走（排除自己操作的）
            elif device.previous_borrower == user['borrower_name'] and device.borrower and device.borrower != user['borrower_name'] and record.borrower != user['borrower_name']:
                item['type'] = '借用-被动'
                # 去重检查
                dedup_key = f"{device.name}_{final_borrower}_借用-被动"
                if dedup_key not in seen_notifications:
                    seen_notifications.add(dedup_key)
                    my_items_borrowed.append(item)
            # 我主动转借给别人（自己操作的转借）
            elif device.previous_borrower == user['borrower_name'] and device.borrower and device.borrower != user['borrower_name'] and record.borrower == user['borrower_name']:
                item['type'] = '借用-主动'
                # 去重检查
                dedup_key = f"{device.name}_{final_borrower}_借用-主动"
                if dedup_key not in seen_notifications:
                    seen_notifications.add(dedup_key)
                    my_items_borrowed.append(item)

        # 处理报废通知 - 如果我是该设备的借用人
        elif '报废' in record.operation_type.value:
            if record.borrower == user['borrower_name']:
                notification_id = f"{device.name}_报废_{record.operation_time.strftime('%Y%m%d%H%M%S')}"
                item = {
                    'id': notification_id,
                    'device_name': device.name,
                    'device_type': device.device_type.value,
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '设备报废'
                }
                my_items_borrowed.append(item)

        # 处理状态变更通知 - 如果我是该设备的借用人或保管人
        elif '状态变更' in record.operation_type.value:
            if record.borrower == user['borrower_name']:
                notification_id = f"{device.name}_状态变更_{record.operation_time.strftime('%Y%m%d%H%M%S')}"
                item = {
                    'id': notification_id,
                    'device_name': device.name,
                    'device_type': device.device_type.value,
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '状态变更',
                    'reason': record.reason
                }
                my_items_borrowed.append(item)
            elif device.cabinet_number == user['borrower_name']:
                notification_id = f"{device.name}_状态变更_{record.operation_time.strftime('%Y%m%d%H%M%S')}"
                item = {
                    'id': notification_id,
                    'device_name': device.name,
                    'device_type': device.device_type.value,
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '状态变更',
                    'reason': record.reason
                }
                my_items_borrowed.append(item)

        # 处理保管人变更通知 - 如果我是原保管人或新保管人
        elif '保管人变更' in record.operation_type.value:
            if user['borrower_name'] in record.reason:
                notification_id = f"{device.name}_保管人变更_{record.operation_time.strftime('%Y%m%d%H%M%S')}"
                item = {
                    'id': notification_id,
                    'device_name': device.name,
                    'device_type': device.device_type.value,
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '保管人变更',
                    'reason': record.reason
                }
                my_items_borrowed.append(item)
            elif record.remark and user['borrower_name'] in record.remark:
                notification_id = f"{device.name}_保管人变更_{record.operation_time.strftime('%Y%m%d%H%M%S')}"
                item = {
                    'id': notification_id,
                    'device_name': device.name,
                    'device_type': device.device_type.value,
                    'borrower': record.borrower,
                    'time': record.operation_time,
                    'type': '保管人变更',
                    'reason': record.reason
                }
                my_items_borrowed.append(item)

    my_items_borrowed = sorted(my_items_borrowed, key=lambda x: x['time'], reverse=True)[:20]

    # 获取系统通知（包括逾期提醒等）
    system_notifications = api_client.get_notifications(
        user_id=user['user_id'],
        user_name=user['borrower_name'],
        unread_only=False
    )
    
    # 将系统通知转换为与 my_items_borrowed 相同的格式
    for notification in system_notifications:
        my_items_borrowed.append({
            'device_name': notification.device_name or '',
            'device_type': '',
            'borrower': notification.user_name or '',
            'time': notification.create_time,
            'type': '系统通知',
            'title': notification.title,
            'content': notification.content,
            'notification_id': notification.id,
            'is_read': notification.is_read
        })
    
    # 按时间排序，取最新的20条
    my_items_borrowed = sorted(my_items_borrowed, key=lambda x: x['time'], reverse=True)[:20]

    # 获取待认领的悬赏列表（用于首页弹窗）
    from common.models import BountyStatus
    all_bounties = api_client._db.get_all_bounties()
    pending_bounties = [
        {
            'id': b.id,
            'title': b.title,
            'device_name': b.device_name,
            'reward_points': b.reward_points,
            'publisher_name': b.publisher_name
        }
        for b in all_bounties
        if b.status == BountyStatus.PENDING
    ]

    # 获取需要当前用户处理的悬赏（已找到，等待确认）
    my_pending_bounties = [
        {
            'id': b.id,
            'title': b.title,
            'device_name': b.device_name,
            'reward_points': b.reward_points,
            'claimer_name': b.claimer_name,
            'finder_description': b.finder_description
        }
        for b in all_bounties
        if b.status == BountyStatus.FOUND and b.publisher_id == user['user_id']
    ]

    # 获取需要当前用户确认的预约（作为保管人或借用人）
    pending_confirm_reservations = []
    for device in all_devices:
        # 检查用户是否是保管人
        is_custodian = device.cabinet_number == user['borrower_name']
        # 检查用户是否是借用人
        is_borrower = (device.borrower and user['borrower_name'] in device.borrower) and device.status == DeviceStatus.BORROWED
        
        if not is_custodian and not is_borrower:
            continue
        
        # 获取该设备的所有预约
        reservations = api_client.get_device_reservations(device.id, None, False)
        
        for r in reservations:
            # 保管人需要确认的预约
            if is_custodian and r.status in ['待保管人确认', '待2人确认'] and not r.custodian_approved:
                if r.custodian_id == user['user_id'] or (not r.custodian_id and device.cabinet_number == user['borrower_name']):
                    pending_confirm_reservations.append({
                        'id': r.id,
                        'reserver_name': r.reserver_name,
                        'reserver_id': r.reserver_id,
                        'device_id': device.id,
                        'device_name': device.name,
                        'device_type': get_device_type_str(device),
                        'start_time': r.start_time.strftime('%m-%d %H:%M') if r.start_time else '',
                        'end_time': r.end_time.strftime('%m-%d %H:%M') if r.end_time else '',
                        'confirm_role': 'custodian',
                        'role_display': '保管人确认'
                    })
            
            # 借用人需要确认的预约
            if is_borrower and r.status in ['待借用人确认', '待2人确认'] and not r.borrower_approved:
                is_current_borrower = (
                    r.current_borrower_id == user['user_id'] or 
                    r.current_borrower_name == user['borrower_name'] or
                    device.borrower == user['borrower_name']
                )
                if is_current_borrower:
                    pending_confirm_reservations.append({
                        'id': r.id,
                        'reserver_name': r.reserver_name,
                        'reserver_id': r.reserver_id,
                        'device_id': device.id,
                        'device_name': device.name,
                        'device_type': get_device_type_str(device),
                        'start_time': r.start_time.strftime('%m-%d %H:%M') if r.start_time else '',
                        'end_time': r.end_time.strftime('%m-%d %H:%M') if r.end_time else '',
                        'confirm_role': 'borrower',
                        'role_display': '借用人确认'
                    })

    # 获取当前用户的排行（使用与排行榜页面一致的数据源）
    current_user_name = user['borrower_name']
    
    # 借用次数排行
    borrow_rankings = api_client.get_user_rankings('borrow')
    borrow_rank = None
    borrow_total = 0
    for ranking in borrow_rankings:
        if ranking['user_name'] == current_user_name:
            borrow_rank = ranking['rank']
            borrow_total = ranking['count']
            break
    
    # 归还次数排行
    return_rankings = api_client.get_user_rankings('return')
    return_rank = None
    return_total = 0
    for ranking in return_rankings:
        if ranking['user_name'] == current_user_name:
            return_rank = ranking['rank']
            return_total = ranking['count']
            break
    
    # 获取用户积分和积分排名
    user_points_info = points_service.get_user_points_rank(user['user_id'])
    user_points = user_points_info['points']
    points_rank = user_points_info['rank']

    # 获取用户累计积分
    user_points_data = points_service.get_or_create_user_points(user['user_id'])
    total_earned = user_points_data.total_earned if user_points_data else 0

    # 获取积分称号（前10名）
    points_title = None
    if points_rank and points_rank <= 10:
        points_title = points_service.POINTS_TITLES[points_rank - 1] if points_rank <= len(points_service.POINTS_TITLES) else points_service.POINTS_TITLES[-1]
    
    # 获取首次登录积分提示
    first_login_points = session.pop('first_login_points', None)
    points_message = session.pop('points_message', None)
    
    # 获取每日登录积分提示
    daily_login_points = session.pop('daily_login_points', None)
    daily_login_message = session.pop('daily_login_message', None)

    # 获取当前主题
    current_theme = None
    if user and user.get('current_theme'):
        theme_item = api_client._db.get_shop_item_by_id(user['current_theme'])
        if theme_item:
            current_theme = theme_item.icon

    return render_template('pc/dashboard.html',
                         user=user,
                         total_devices=total_devices,
                         available_devices=available_devices,
                         borrowed_devices_count=borrowed_devices_count,
                         in_stock_count=in_stock_count,
                         in_custody_count=in_custody_count,
                         no_cabinet_count=no_cabinet_count,
                         circulating_count=circulating_count,
                         unavailable_count=unavailable_count,
                         my_borrowed_devices=my_borrowed_devices,
                         my_borrowed_count=my_borrowed_count,
                         my_borrowed_type_counts=my_borrowed_type_counts,
                         my_custodian_count=my_custodian_count,
                         recent_records=recent_records,
                         notifications=my_items_borrowed,
                         notification_count=len([n for n in my_items_borrowed if not n.get('is_read', False)]),
                         borrow_rank=borrow_rank,
                         borrow_total=borrow_total,
                         return_rank=return_rank,
                         return_total=return_total,
                         my_reservation_count=my_reservation_count,
                         my_reservations=active_reservations,
                         user_points=user_points,
                         total_earned=total_earned,
                         points_rank=points_rank,
                         points_title=points_title,
                         pending_bounties=pending_bounties,
                         my_pending_bounties=my_pending_bounties,
                         pending_confirm_reservations=pending_confirm_reservations,
                         first_login_points=first_login_points,
                         points_message=points_message,
                         daily_login_points=daily_login_points,
                         daily_login_message=daily_login_message,
                         current_theme=current_theme)


@app.route('/api/all-devices')
@login_required
def api_get_all_devices():
    """获取所有设备数据（用于全局搜索）"""
    api_client.reload_data()
    devices = api_client.get_all_devices()
    
    device_list = []
    for device in devices:
        # 确保所有字段都有值
        device_name = getattr(device, 'name', '') or ''
        device_model = getattr(device, 'model', '') or ''
        device_id = getattr(device, 'id', '') or ''
        
        device_type_val = ''
        if hasattr(device, 'device_type'):
            device_type_val = device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type)
        
        device_list.append({
            'id': device_id,
            'name': device_name,
            'model': device_model,
            'device_type': device_type_val,
            'status': device.status.value if hasattr(device.status, 'value') else str(device.status)
        })
    
    return jsonify({
        'success': True,
        'devices': device_list
    })


@app.route('/pc/devices')
@login_required
def pc_device_list():
    """PC端设备列表页面"""
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    user = get_current_user()
    device_type = request.args.get('type', 'all')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    no_cabinet = request.args.get('no_cabinet', '')

    # 获取组合筛选参数（车机/仪表）
    filter_project = request.args.get('filter_project', '').strip()
    filter_connection = request.args.get('filter_connection', '').strip()
    filter_os_version = request.args.get('filter_os_version', '').strip()
    filter_os_platform = request.args.get('filter_os_platform', '').strip()
    filter_product = request.args.get('filter_product', '').strip()
    filter_orientation = request.args.get('filter_orientation', '').strip()
    filter_resolution = request.args.get('filter_resolution', '').strip()

    # 获取设备
    if device_type == 'all':
        devices = api_client.get_all_devices()  # 获取所有设备
        title = '全部设备'
    elif device_type == 'car':
        devices = api_client.get_all_devices('车机')
        title = '车机设备'
    elif device_type == 'phone':
        devices = api_client.get_all_devices('手机')
        title = '手机设备'
    elif device_type == 'instrument':
        devices = api_client.get_all_devices('仪表')
        title = '仪表设备'
    elif device_type == 'simcard':
        devices = api_client.get_all_devices('手机卡')
        title = '手机卡设备'
    elif device_type == 'other':
        devices = api_client.get_all_devices('其它设备')
        title = '其它设备'
    else:
        devices = api_client.get_all_devices('车机')
        title = '车机设备'

    # 状态过滤
    if status == 'available':
        # 在库或保管中都算可用
        devices = [d for d in devices if d.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]]
    elif status == 'borrowed':
        devices = [d for d in devices if d.status == DeviceStatus.BORROWED]

    # 搜索过滤 - 支持所有字段和组合搜索（移除空格进行模糊匹配）
    if search:
        # 移除搜索词中的所有空格
        search_normalized = search.lower().replace(' ', '').replace('\t', '').replace('\n', '')
        filtered_devices = []
        for d in devices:
            # 基础字段搜索（移除空格后匹配）
            match = (search_normalized in d.name.lower().replace(' ', '') or
                     search_normalized in (d.model or '').lower().replace(' ', '') or
                     search_normalized in (d.borrower or '').lower().replace(' ', '') or
                     search_normalized in (d.jira_address or '').lower().replace(' ', '') or
                     search_normalized in (d.remark or '').lower().replace(' ', '') or
                     search_normalized in d.status.value.lower().replace(' ', '') or
                     search_normalized in d.device_type.value.lower().replace(' ', ''))

            # 车机/仪表特有字段
            if not match and d.device_type.value in ['车机', '仪表']:
                match = (search_normalized in (d.project_attribute or '').lower().replace(' ', '') or
                         search_normalized in (d.connection_method or '').lower().replace(' ', '') or
                         search_normalized in (d.os_version or '').lower().replace(' ', '') or
                         search_normalized in (d.os_platform or '').lower().replace(' ', '') or
                         search_normalized in (d.product_name or '').lower().replace(' ', '') or
                         search_normalized in (d.screen_orientation or '').lower().replace(' ', '') or
                         search_normalized in (d.screen_resolution or '').lower().replace(' ', '') or
                         search_normalized in (d.hardware_version or '').lower().replace(' ', ''))

            # 手机特有字段
            if not match and d.device_type.value == '手机':
                match = (search_normalized in (d.system_version or '').lower().replace(' ', '') or
                         search_normalized in (d.imei or '').lower().replace(' ', '') or
                         search_normalized in (d.sn or '').lower().replace(' ', '') or
                         search_normalized in (d.carrier or '').lower().replace(' ', ''))

            # 手机卡特有字段
            if not match and d.device_type.value == '手机卡':
                match = search_normalized in (d.carrier or '').lower().replace(' ', '')

            if match:
                filtered_devices.append(d)
        devices = filtered_devices

    # 级联筛选：计算每个下拉框的可用选项（基于其他筛选条件，不包括自己）
    if device_type in ['car', 'instrument']:
        # 基础筛选设备列表（创建副本，避免修改原始列表）
        base_devices = list(devices)
        if no_cabinet == '1':
            base_devices = [d for d in base_devices if d.status == DeviceStatus.NO_CABINET]

        # 辅助函数：提取独立的选项值（将"国内前装、海外前装"拆分为["国内前装", "海外前装"]）
        def extract_unique_options(devices_list, attr_name):
            """从设备列表中提取指定属性的所有独立选项值"""
            options = set()
            for d in devices_list:
                value = getattr(d, attr_name, None)
                if value:
                    # 按常见分隔符拆分（、,，;；等）
                    parts = re.split(r'[、,，;；/\\|]+', value)
                    for part in parts:
                        part = part.strip()
                        if part:
                            options.add(part)
            return sorted(options)

        # 辅助函数：模糊匹配筛选（检查属性值是否包含筛选值）
        def fuzzy_match_filter(devices_list, attr_name, filter_value):
            """使用模糊匹配筛选设备"""
            if not filter_value:
                return devices_list
            return [d for d in devices_list if filter_value in (getattr(d, attr_name, '') or '')]

        # 计算每个下拉框的选项（基于除自己外的其他筛选条件，使用模糊匹配）
        # 项目属性选项：基于除项目属性外的其他筛选条件
        filtered_for_project = base_devices
        filtered_for_project = fuzzy_match_filter(filtered_for_project, 'connection_method', filter_connection)
        filtered_for_project = fuzzy_match_filter(filtered_for_project, 'os_version', filter_os_version)
        filtered_for_project = fuzzy_match_filter(filtered_for_project, 'os_platform', filter_os_platform)
        filtered_for_project = fuzzy_match_filter(filtered_for_project, 'product_name', filter_product)
        filtered_for_project = fuzzy_match_filter(filtered_for_project, 'screen_orientation', filter_orientation)
        filtered_for_project = fuzzy_match_filter(filtered_for_project, 'screen_resolution', filter_resolution)
        project_attributes = extract_unique_options(filtered_for_project, 'project_attribute')
        # 确保当前选中的值在选项列表中
        if filter_project and filter_project not in project_attributes:
            project_attributes.append(filter_project)
            project_attributes.sort()

        # 连接方式选项：基于除连接方式外的其他筛选条件
        filtered_for_connection = base_devices
        filtered_for_connection = fuzzy_match_filter(filtered_for_connection, 'project_attribute', filter_project)
        filtered_for_connection = fuzzy_match_filter(filtered_for_connection, 'os_version', filter_os_version)
        filtered_for_connection = fuzzy_match_filter(filtered_for_connection, 'os_platform', filter_os_platform)
        filtered_for_connection = fuzzy_match_filter(filtered_for_connection, 'product_name', filter_product)
        filtered_for_connection = fuzzy_match_filter(filtered_for_connection, 'screen_orientation', filter_orientation)
        filtered_for_connection = fuzzy_match_filter(filtered_for_connection, 'screen_resolution', filter_resolution)
        connection_methods = extract_unique_options(filtered_for_connection, 'connection_method')
        # 确保当前选中的值在选项列表中
        if filter_connection and filter_connection not in connection_methods:
            connection_methods.append(filter_connection)
            connection_methods.sort()

        # 系统版本选项
        filtered_for_os_version = base_devices
        filtered_for_os_version = fuzzy_match_filter(filtered_for_os_version, 'project_attribute', filter_project)
        filtered_for_os_version = fuzzy_match_filter(filtered_for_os_version, 'connection_method', filter_connection)
        filtered_for_os_version = fuzzy_match_filter(filtered_for_os_version, 'os_platform', filter_os_platform)
        filtered_for_os_version = fuzzy_match_filter(filtered_for_os_version, 'product_name', filter_product)
        filtered_for_os_version = fuzzy_match_filter(filtered_for_os_version, 'screen_orientation', filter_orientation)
        filtered_for_os_version = fuzzy_match_filter(filtered_for_os_version, 'screen_resolution', filter_resolution)
        os_versions = extract_unique_options(filtered_for_os_version, 'os_version')
        # 确保当前选中的值在选项列表中
        if filter_os_version and filter_os_version not in os_versions:
            os_versions.append(filter_os_version)
            os_versions.sort()

        # 系统平台选项
        filtered_for_os_platform = base_devices
        filtered_for_os_platform = fuzzy_match_filter(filtered_for_os_platform, 'project_attribute', filter_project)
        filtered_for_os_platform = fuzzy_match_filter(filtered_for_os_platform, 'connection_method', filter_connection)
        filtered_for_os_platform = fuzzy_match_filter(filtered_for_os_platform, 'os_version', filter_os_version)
        filtered_for_os_platform = fuzzy_match_filter(filtered_for_os_platform, 'product_name', filter_product)
        filtered_for_os_platform = fuzzy_match_filter(filtered_for_os_platform, 'screen_orientation', filter_orientation)
        filtered_for_os_platform = fuzzy_match_filter(filtered_for_os_platform, 'screen_resolution', filter_resolution)
        os_platforms = extract_unique_options(filtered_for_os_platform, 'os_platform')
        # 确保当前选中的值在选项列表中
        if filter_os_platform and filter_os_platform not in os_platforms:
            os_platforms.append(filter_os_platform)
            os_platforms.sort()

        # 产品名称选项
        filtered_for_product = base_devices
        filtered_for_product = fuzzy_match_filter(filtered_for_product, 'project_attribute', filter_project)
        filtered_for_product = fuzzy_match_filter(filtered_for_product, 'connection_method', filter_connection)
        filtered_for_product = fuzzy_match_filter(filtered_for_product, 'os_version', filter_os_version)
        filtered_for_product = fuzzy_match_filter(filtered_for_product, 'os_platform', filter_os_platform)
        filtered_for_product = fuzzy_match_filter(filtered_for_product, 'screen_orientation', filter_orientation)
        filtered_for_product = fuzzy_match_filter(filtered_for_product, 'screen_resolution', filter_resolution)
        product_names = extract_unique_options(filtered_for_product, 'product_name')
        # 确保当前选中的值在选项列表中
        if filter_product and filter_product not in product_names:
            product_names.append(filter_product)
            product_names.sort()

        # 屏幕方向选项
        filtered_for_orientation = base_devices
        filtered_for_orientation = fuzzy_match_filter(filtered_for_orientation, 'project_attribute', filter_project)
        filtered_for_orientation = fuzzy_match_filter(filtered_for_orientation, 'connection_method', filter_connection)
        filtered_for_orientation = fuzzy_match_filter(filtered_for_orientation, 'os_version', filter_os_version)
        filtered_for_orientation = fuzzy_match_filter(filtered_for_orientation, 'os_platform', filter_os_platform)
        filtered_for_orientation = fuzzy_match_filter(filtered_for_orientation, 'product_name', filter_product)
        filtered_for_orientation = fuzzy_match_filter(filtered_for_orientation, 'screen_resolution', filter_resolution)
        orientations = extract_unique_options(filtered_for_orientation, 'screen_orientation')
        # 确保当前选中的值在选项列表中
        if filter_orientation and filter_orientation not in orientations:
            orientations.append(filter_orientation)
            orientations.sort()

        # 分辨率选项
        filtered_for_resolution = base_devices
        filtered_for_resolution = fuzzy_match_filter(filtered_for_resolution, 'project_attribute', filter_project)
        filtered_for_resolution = fuzzy_match_filter(filtered_for_resolution, 'connection_method', filter_connection)
        filtered_for_resolution = fuzzy_match_filter(filtered_for_resolution, 'os_version', filter_os_version)
        filtered_for_resolution = fuzzy_match_filter(filtered_for_resolution, 'os_platform', filter_os_platform)
        filtered_for_resolution = fuzzy_match_filter(filtered_for_resolution, 'product_name', filter_product)
        filtered_for_resolution = fuzzy_match_filter(filtered_for_resolution, 'screen_orientation', filter_orientation)
        resolutions = extract_unique_options(filtered_for_resolution, 'screen_resolution')
        # 确保当前选中的值在选项列表中
        if filter_resolution and filter_resolution not in resolutions:
            resolutions.append(filter_resolution)
            resolutions.sort()
    else:
        project_attributes = []
        connection_methods = []
        os_versions = []
        os_platforms = []
        product_names = []
        orientations = []
        resolutions = []

    # 应用所有筛选条件得到最终设备列表（使用模糊匹配）
    if device_type in ['car', 'instrument']:
        if filter_project:
            devices = [d for d in devices if filter_project in (d.project_attribute or '')]
        if filter_connection:
            devices = [d for d in devices if filter_connection in (d.connection_method or '')]
        if filter_os_version:
            devices = [d for d in devices if filter_os_version in (d.os_version or '')]
        if filter_os_platform:
            devices = [d for d in devices if filter_os_platform in (d.os_platform or '')]
        if filter_product:
            devices = [d for d in devices if filter_product in (d.product_name or '')]
        if filter_orientation:
            devices = [d for d in devices if filter_orientation in (d.screen_orientation or '')]
        if filter_resolution:
            devices = [d for d in devices if filter_resolution in (d.screen_resolution or '')]

    # 处理设备列表，添加 no_cabinet 和 is_circulating 属性
    device_list = []
    for device in devices:
        is_circulating = device.status == DeviceStatus.CIRCULATING
        is_sealed = device.status == DeviceStatus.SEALED
        
        # 判断是否为使用保管人的设备类型（手机、手机卡、其它设备）
        is_custodian_type = device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]

        if is_custodian_type:
            # 手机、手机卡、其它设备：根据custodian_id判断是否有保管人
            is_no_cabinet = not device.custodian_id or device.custodian_id.strip() == ''
        else:
            # 车机、仪表：根据status判断是否为无柜号状态
            is_no_cabinet = device.status == DeviceStatus.NO_CABINET

        # 如果是无柜号筛选，只显示柜号/保管人为空的设备
        if no_cabinet == '1':
            if not is_no_cabinet:
                continue

        # 直接给设备对象添加额外属性
        device.no_cabinet = is_no_cabinet
        device.is_circulating = is_circulating
        device.is_sealed = is_sealed
        device.is_custodian_type = is_custodian_type
        device_list.append(device)

    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(device_list)
    total_pages = (total + per_page - 1) // per_page

    start = (page - 1) * per_page
    end = start + per_page
    paginated_devices = device_list[start:end]
    
    # 获取全局统计（用于侧边栏显示）
    stats = get_device_stats()

    return render_template('pc/device_list.html',
                         devices=paginated_devices,
                         title=title,
                         device_type=device_type,
                         status=status,
                         search=search,
                         no_cabinet=no_cabinet == '1',
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         user=user,
                         filter_project=filter_project,
                         filter_connection=filter_connection,
                         filter_os_version=filter_os_version,
                         filter_os_platform=filter_os_platform,
                         filter_product=filter_product,
                         filter_orientation=filter_orientation,
                         filter_resolution=filter_resolution,
                         project_attributes=project_attributes,
                         connection_methods=connection_methods,
                         os_versions=os_versions,
                         os_platforms=os_platforms,
                         product_names=product_names,
                         orientations=orientations,
                         resolutions=resolutions,
                         total_devices=stats['total_devices'],
                         available_devices=stats['available_devices'],
                         borrowed_devices_count=stats['borrowed_devices_count'],
                         in_stock_count=stats['in_stock_count'],
                         in_custody_count=stats['in_custody_count'],
                         no_cabinet_count=stats['no_cabinet_count'],
                         circulating_count=stats['circulating_count'],
                         unavailable_count=stats['unavailable_count'],
                         hide_search=True,
                         current_theme=get_current_theme_icon(user['user_id']))


@app.route('/pc/device/<device_id>')
@login_required
def pc_device_detail(device_id):
    """PC端设备详情页面"""
    user = get_current_user()
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    # 获取设备类型参数，用于区分不同类型设备的相同ID
    device_type_param = request.args.get('device_type')

    # 先尝试根据设备类型查询
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

    # 获取设备类型字符串
    device_type = get_device_type_str(device)

    # 添加查看记录
    if user['borrower_name']:
        api_client.add_view_record(device_id, user['borrower_name'], device_type)

    # 获取设备备注（过滤不当内容）
    raw_remarks = api_client.get_remarks(device_id, device_type, exclude_inappropriate=True)
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
    all_raw_records = api_client.get_device_records(device_id, device_type, limit=10000)

    # 格式化显示用的记录列表（限制20条）
    raw_records = all_raw_records[:20]
    record_list = []
    for record in raw_records:
        record_list.append({
            'operation_type': record.operation_type.value,
            'borrower': record.borrower,
            'operation_time': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'entry_source': record.entry_source,
            'reason': record.reason or '',
            'remark': record.remark or ''
        })

    # 获取查看记录
    raw_view_records = api_client.get_view_records(device_id, device_type, limit=20)
    view_record_list = []
    for vr in raw_view_records:
        view_record_list.append({
            'viewer': vr.viewer,
            'view_time': vr.view_time.strftime('%Y-%m-%d %H:%M:%S')
        })

    # 检查当前用户是否借用了该设备
    is_borrowed_by_me = (device.borrower == user['borrower_name'])

    # 检查当前用户是否是该设备的保管人
    is_custodian = (device.cabinet_number == user['borrower_name'])

    # 检查是否可以借用（在库或保管中都可以借用）
    can_borrow = (device.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY])

    # 计算续借相关状态
    can_renew = False
    renew_disabled_reason = ''
    remaining_hours = 0
    remaining_days = 0
    remaining_minutes = 0
    is_overdue = False
    overdue_hours = 0
    overdue_days = 0
    is_long_term_borrow = False  # 是否为长期借用

    # 计算剩余时间（无论设备状态如何，只要有预计归还日期）
    if device.expected_return_date:
        time_diff = datetime.now() - device.expected_return_date
        total_seconds = time_diff.total_seconds()
        if total_seconds > 60:  # 已逾期超过1分钟才算逾期
            is_overdue = True
            overdue_days = int(total_seconds // (24 * 3600))
            overdue_hours = int(total_seconds // 3600)
            remaining_hours = -overdue_hours
            remaining_days = -overdue_days
            remaining_minutes = 0
        elif total_seconds > 0:  # 逾期1分钟内，显示剩余0分钟
            is_overdue = False
            remaining_seconds = 0
            remaining_hours = 0
            remaining_days = 0
            remaining_minutes = 0
        else:  # 未逾期
            remaining_seconds = abs(total_seconds)
            remaining_hours = int(remaining_seconds // 3600)
            remaining_days = int(remaining_seconds // (24 * 3600))
            remaining_minutes = int(remaining_seconds // 60)
    else:
        # 长期借用，无固定归还时间
        is_long_term_borrow = True

    # 只有当设备被当前用户借用且状态为借用时，才计算是否可以续借
    if is_borrowed_by_me and device.status == DeviceStatus.BORROWED:
        if is_long_term_borrow:
            # 长期借用不需要续借
            can_renew = False
            renew_disabled_reason = '长期借用无需续借'
        elif remaining_hours < 0:  # 已逾期
            overdue_days = -remaining_days
            if overdue_days > 3:
                can_renew = False
                renew_disabled_reason = '逾期超过3天，不能续借，需要归还后才能再次借用'
            else:
                can_renew = True
        else:  # 未逾期
            can_renew = remaining_hours < 24
            if not can_renew:
                renew_disabled_reason = '剩余时间大于24小时，暂不需要续借'

    stats = get_device_stats()
    
    device_images = get_device_images(device_id)
    device_attachments = get_device_attachments(device_id)
    
    borrower_info = None
    if device.borrower:
        borrower_user = api_client.get_user_by_borrower_name(device.borrower)
        if borrower_user:
            borrower_equipment = get_user_equipment(borrower_user.id)
            borrower_info = {
                'user_id': borrower_user.id,
                'user_name': borrower_user.borrower_name,
                'avatar': borrower_user.avatar,
                'avatar_frame': borrower_equipment.get('avatar_frame'),
                'title': borrower_equipment.get('title')
            }

    custodian_info = None
    if device.cabinet_number:
        custodian_user = api_client.get_user_by_borrower_name(device.cabinet_number)
        if custodian_user:
            custodian_equipment = get_user_equipment(custodian_user.id)
            custodian_info = {
                'user_id': custodian_user.id,
                'user_name': custodian_user.borrower_name,
                'avatar': custodian_user.avatar,
                'avatar_frame': custodian_equipment.get('avatar_frame'),
                'title': custodian_equipment.get('title')
            }
    
    return render_template('pc/device_detail.html',
                         device=device,
                         device_type=device_type,
                         remarks=remark_list,
                         records=record_list,
                         view_records=view_record_list,
                         is_borrower=is_borrowed_by_me,
                         is_custodian=is_custodian,
                         can_borrow=can_borrow,
                         can_renew=can_renew,
                         renew_disabled_reason=renew_disabled_reason,
                         is_overdue=is_overdue,
                         overdue_hours=overdue_hours,
                         overdue_days=overdue_days,
                         remaining_days=remaining_days,
                         remaining_hours=remaining_hours,
                         remaining_minutes=remaining_minutes,
                         is_long_term_borrow=is_long_term_borrow,
                         user=user,
                         now=datetime.now().strftime('%Y-%m-%d %H:%M'),
                         device_images=device_images,
                         device_attachments=device_attachments,
                         borrower_info=borrower_info,
                         custodian_info=custodian_info,
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


@app.route('/pc/device/<device_id>/simple')
@login_required
def pc_device_detail_simple(device_id):
    """PC端设备详情页面（简化版） 用于借还确认"""
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    # 获取设备类型参数，用于区分不同类型设备的相同ID
    device_type_param = request.args.get('device_type')

    # 先尝试根据设备类型查询
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

    action = request.args.get('action', 'view')

    # 获取设备类型
    device_type = get_device_type_str(device)

    # 判断设备状态
    is_circulating = device.status == DeviceStatus.CIRCULATING
    is_sealed = device.status == DeviceStatus.SEALED
    is_no_cabinet = device.status == DeviceStatus.NO_CABINET

    # 添加查看记录
    user = get_current_user()
    if user['borrower_name']:
        api_client.add_view_record(device_id, user['borrower_name'], device_type)

    # 获取设备图片和附件
    device_images = get_device_images(device_id)
    device_attachments = get_device_attachments(device_id)

    # 格式化附件大小
    for att in device_attachments:
        att['size_formatted'] = format_file_size(att['size'])

    stats = get_device_stats()

    return render_template('pc/device_detail_simple.html',
                         device=device,
                         device_type=device_type,
                         action=action,
                         is_circulating=is_circulating,
                         is_sealed=is_sealed,
                         is_no_cabinet=is_no_cabinet,
                         user=user,
                         current_theme=get_current_theme_icon(user['user_id']),
                         device_images=device_images,
                         device_attachments=device_attachments,
                         **stats)


@app.route('/pc/my-custodian-devices')
@login_required
def pc_my_custodian_devices():
    """PC端我的保管设备"""
    from datetime import datetime
    api_client.reload_data()
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
                    # 如果有分钟，小时+1（向上取整）
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
                'type': get_device_type_str(device),
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
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


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
        should_include = False

        # 原有的条件：用户名在 borrower 中，或用户是操作人
        if user['borrower_name'] in record.borrower or record.operator == user['borrower_name'] or record.borrower == user['borrower_name']:
            should_include = True

        # 检查管理员操作是否与当前用户相关
        if not should_include:
            # 状态变更记录：如果借用人是当前用户
            if '状态变更' in record.operation_type.value and record.borrower == user['borrower_name']:
                should_include = True
            # 保管人变更记录：检查 reason 或 remark 中是否包含用户名
            elif '保管人变更' in record.operation_type.value:
                if user['borrower_name'] in record.reason:
                    should_include = True
                elif record.remark and user['borrower_name'] in record.remark:
                    should_include = True
            # 其他管理员操作：如果借用人是当前用户
            elif record.borrower == user['borrower_name']:
                should_include = True

        if should_include:
            my_records_list.append(record)

    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(my_records_list)
    total_pages = (total + per_page - 1) // per_page

    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = my_records_list[start:end]

    # 统计 - 使用用户表中的 borrow_count 和 return_count，与排行榜保持一致
    borrow_count = 0
    return_count = 0
    for u in api_client._users:
        if u.id == user['user_id']:
            borrow_count = u.borrow_count
            return_count = u.return_count
            break

    stats = get_device_stats()

    return render_template('pc/my_records.html',
                         records=paginated_records,
                         total_records=total,
                         borrow_count=borrow_count,
                         return_count=return_count,
                         page=page,
                         total_pages=total_pages,
                         user=user,
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


@app.route('/pc/all-records')
@login_required
def pc_all_records():
    """PC端所有记录页面"""
    # 重新加载数据以获取最新Excel数据
    api_client.reload_data()

    # 获取所有记录
    all_records_list = api_client.get_records()
    
    # 统计借用和归还次数（借出+转借都算作借用，归还+强制归还都算作归还）
    borrow_count = len([r for r in all_records_list if '借出' in r.operation_type.value or r.operation_type.value == '转借'])
    return_count = len([r for r in all_records_list if r.operation_type.value in ['归还', '强制归还']])
    
    # 分页
    page = request.args.get('page', 1, type=int)
    per_page = 20
    total = len(all_records_list)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_records = all_records_list[start:end]
    
    stats = get_device_stats()
    
    user = get_current_user()
    return render_template('pc/all_records.html',
                         records=paginated_records,
                         total_records=total,
                         borrow_count=borrow_count,
                         return_count=return_count,
                         page=page,
                         total_pages=total_pages,
                         user=user,
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


@app.route('/pc/user-rankings')
@login_required
def pc_user_rankings():
    """PC端用户排行榜页面"""
    stats = get_device_stats()
    user = get_current_user()
    return render_template('pc/user_rankings.html',
                         ranking_type='borrow',
                         user=user,
                         hide_search=True,
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


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
    expected_return_date = data.get('expected_return_date', '').strip()
    days = data.get('days', 1)

    # 验证输入
    if not reason:
        return jsonify({'success': False, 'message': '请输入借用原因'})
    
    # 重新加载数据以获取最新状态
    api_client.reload_data()
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    if device.status not in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]:
        return jsonify({'success': False, 'message': '设备不可借'})
    
    # 记录原借用人（如果设备当前被借用）
    original_borrower = device.borrower if device.status == DeviceStatus.BORROWED else None
    
    # 检查用户借用数量限制
    user_borrowed_count = 0
    all_devices = api_client.get_all_devices()
    for d in all_devices:
        if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
            user_borrowed_count += 1

    borrow_limit = 10  # 最大借用数量（车机+手机卡）
    if user_borrowed_count >= borrow_limit:
        return jsonify({'success': False, 'message': '您已超出可借设备上限，请归还后再借'})
    
    # 获取用户邮箱（替代原来的手机号）
    user_email = user.get('email', '')
    
    # 计算预计归还时间
    borrow_start_time = datetime.now()
    if expected_return_date:
        # 使用前端传递的完整日期时间
        from datetime import datetime as dt
        try:
            # 尝试解析完整格式 YYYY-MM-DD HH:MM:SS
            device.expected_return_date = dt.strptime(expected_return_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # 兼容旧格式 YYYY-MM-DD，时间设为当前时间
            date_part = dt.strptime(expected_return_date, '%Y-%m-%d')
            now_time = dt.now()
            device.expected_return_date = date_part.replace(hour=now_time.hour, minute=now_time.minute, second=now_time.second)
    else:
        # 长期借用，不设置归还日期（空字符串或None都表示长期借用）
        device.expected_return_date = None
    
    # 检查是否有预约冲突（只检查与预约时间重合的情况，自己的预约不视为冲突）
    has_conflict, conflict_info = api_client.check_reservation_conflict(
        device_id=device_id,
        device_type=get_device_type_str(device),
        start_time=borrow_start_time,
        end_time=device.expected_return_date,
        current_user_id=user['user_id']
    )
    
    if has_conflict:
        if conflict_info['type'] == 'reservation':
            return jsonify({
                'success': False, 
                'message': f"该设备已被 {conflict_info['conflict_with']} 预约，预约时间 {conflict_info['start_time'].strftime('%Y-%m-%d %H:%M')} 至 {conflict_info['end_time'].strftime('%Y-%m-%d %H:%M')}，请修改借用时长或者联系 {conflict_info['conflict_with']} 取消预约"
            })
    
    # 更新设备信息
    device.status = DeviceStatus.BORROWED
    device.borrower = user['borrower_name']
    device.borrow_time = datetime.now()
    device.location = location
    device.reason = reason
    device.entry_source = EntrySource.USER.value
    device.previous_borrower = ''  # 清空上一个借用人，因为从在库借用
    
    api_client.update_device(device, source="user")
    
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
        reason=reason_main,
        remark=remark_text,
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)
    
    # 更新用户借用次数
    for u in api_client._users:
        if u.id == user['user_id']:
            u.borrow_count += 1
            api_client._db.save_user(u)
            break

    api_client.add_operation_log(f"借出设备: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")

    # 借用成功，奖励积分
    points_result = points_service.borrow_reward(user['user_id'], device.name, device.id)
    points_message = f"，{points_result['message']}" if points_result['success'] else ""

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    # 发送通知（用户自己借设备，不需要通知自己）
    # 1. 通知原借用人（如果设备之前被借用且原借用人不是自己）
    if original_borrower and original_borrower != user['borrower_name']:
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
                content=f"您借用的设备「{device.name}」已被 {user['borrower_name']} 借用",
                device_name=device.name,
                device_id=device.id,
                notification_type="warning"
            )
    # 2. 通知保管人（如果保管人不是借用人自己）
    if device.cabinet_number and device.cabinet_number != user['borrower_name']:
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
                content=f"您保管的设备「{device.name}」已被 {user['borrower_name']} 借用",
                device_name=device.name,
                device_id=device.id,
                notification_type="info"
            )

    return jsonify({
        'success': True,
        'message': f'借用成功{points_message}',
        'points_added': points_result.get('points_change', 0) if points_result.get('success') else 0,
        'total_points': total_points
    })


@app.route('/api/return', methods=['POST'])
@login_required
def api_return():
    """归还设备API"""
    user = get_current_user()
    data = request.json
    
    # 重新加载数据以获取最新状态
    api_client.reload_data()
    
    device_id = data.get('device_id')
    return_location = data.get('return_location', '').strip() or '设备柜'
    return_reason = data.get('return_reason', '').strip() or data.get('reason', '').strip()
    
    # 验证输入
    if not return_reason:
        return jsonify({'success': False, 'message': '请输入归还原因'})
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人或保管人
    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']
    
    if not is_borrower and not is_custodian:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人或保管人'})
    
    # 借用人只能在借出状态转借
    if is_borrower and device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    original_borrower = device.borrower

    # 根据设备类型设置归还后的状态
    # 手机、手机卡、其它设备 -> 保管中；车机、仪表 -> 在库
    if device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]:
        device.status = DeviceStatus.IN_CUSTODY
    else:
        device.status = DeviceStatus.IN_STOCK

    device.borrower = ''
    device.phone = ''
    device.borrow_time = None
    device.location = return_location
    device.reason = return_reason
    device.entry_source = ''
    device.expected_return_date = None
    
    api_client.update_device(device, source="user")
    
    # 解析归还原因和备注（格式：原因 - 备注）
    reason_parts = return_reason.split(' - ', 1)
    reason_main = reason_parts[0] if reason_parts else return_reason
    remark_text = reason_parts[1] if len(reason_parts) > 1 else ''
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.RETURN,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=original_borrower,
        reason=reason_main,
        remark=remark_text,
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)

    api_client.add_operation_log(f"归还设备: {original_borrower}", device.name, operator=user['borrower_name'], source="user")
    
    # 更新原借用人的归还次数
    for u in api_client._users:
        if u.borrower_name == original_borrower:
            u.return_count += 1
            api_client._db.save_user(u)
            break
    
    # 归还成功，奖励积分（给原借用人）
    points_message = ""
    # 查找原借用人的用户ID
    original_borrower_user_id = None
    for u in api_client._users:
        if u.borrower_name == original_borrower:
            original_borrower_user_id = u.id
            break
    
    if original_borrower_user_id:
        # 检查是否逾期
        is_overdue = False
        if device.expected_return_date:
            from datetime import datetime as dt
            now = dt.now()
            if now > device.expected_return_date:
                # 逾期超过1分钟才算逾期
                time_diff = now - device.expected_return_date
                if time_diff.total_seconds() > 60:
                    is_overdue = True
        
        if is_overdue:
            # 逾期扣15分
            points_result = points_service.overdue_penalty(original_borrower_user_id, device.name, device.id)
            if points_result['success']:
                points_message = f"，{points_result['message']}"
        else:
            # 正常归还加10分
            points_result = points_service.return_reward(original_borrower_user_id, device.name, device.id)
            if points_result['success']:
                points_message = f"，{points_result['message']}"

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])
    points_change = points_result.get('points_change', 0) if points_result.get('success') else 0

    # 检查是否有等待的预约，通知第一个等待的预约人
    device_type = get_device_type_str(device)
    waiting_reservations = api_client._db.get_reservations_by_device(device_id, device_type)
    notified_reserver = None
    for reservation in waiting_reservations:
        # 只通知已同意且预约开始时间在未来或现在的预约
        if (reservation.status == ReservationStatus.APPROVED.value and
            reservation.start_time <= datetime.now() + timedelta(days=1)):  # 预约时间在现在或明天内
            api_client.add_notification(
                user_id=reservation.reserver_id,
                user_name=reservation.reserver_name,
                title="设备已归还",
                content=f"您预约的设备「{device.name}」已被归还，可以借用了",
                device_name=device.name,
                device_id=device.id,
                notification_type="success"
            )
            notified_reserver = reservation.reserver_name
            break  # 只通知第一个


    # 归还通知逻辑：
    # - 借用人自己归还：通知保管人（设备回到保管人处）
    # - 保管人归还：不需要通知（自己操作的）
    # - 无需通知原借用人（设备已归还，与原借用人无关了）
    if is_borrower and device.cabinet_number and device.cabinet_number != user['borrower_name']:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            content = f"您保管的设备「{device.name}」已被 {user['borrower_name']} 归还"
            if notified_reserver:
                content += f"，已通知预约人 {notified_reserver}"
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备归还通知",
                content=content,
                device_name=device.name,
                device_id=device.id,
                notification_type="success"
            )

    return jsonify({
        'success': True,
        'message': f'归还成功{points_message}',
        'points_added': points_change,
        'total_points': total_points
    })


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

    # 获取设备类型
    device_type = get_device_type_str(device)

    # 创建备注
    remark = UserRemark(
        id=str(uuid.uuid4()),
        device_id=device_id,
        device_type=device_type,
        content=content,
        creator=user['borrower_name'],
        create_time=datetime.now()
    )
    api_client._db.save_remark(remark)

    return jsonify({'success': True, 'message': '添加成功'})


def _approve_my_reservation(api_client, reservation, user):
    """
    自动同意用户自己的预约
    作为借用人自动同意预约
    """
    from common.models import ReservationStatus
    
    # 如果预约已经是同意状态，不需要处理
    if reservation.status == ReservationStatus.APPROVED.value:
        return
    
    now = datetime.now()
    
    # 自动作为借用人同意
    if not reservation.borrower_approved:
        reservation.borrower_approved = True
        reservation.borrower_approved_at = now
        
        # 更新状态
        if reservation.status == ReservationStatus.PENDING_BORROWER.value:
            reservation.status = ReservationStatus.APPROVED.value
        elif reservation.status == ReservationStatus.PENDING_BOTH.value:
            if reservation.custodian_approved:
                reservation.status = ReservationStatus.APPROVED.value
            else:
                reservation.status = ReservationStatus.PENDING_CUSTODIAN.value
    
    reservation.updated_at = now
    api_client._db.save_reservation(reservation)


@app.route('/api/transfer-to-me', methods=['POST'])
@login_required
def api_transfer_to_me():
    """转给自己API（用于遗失找回）"""
    user = get_current_user()
    data = request.json
    
    # 重新加载数据以获取最新状态
    api_client.reload_data()
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备状态
    if device.status != DeviceStatus.LOST and device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常，无法操作'})
    
    # 检查用户借用数量限制
    user_borrowed_count = 0
    all_devices = api_client.get_all_devices()
    for d in all_devices:
        if d.borrower == user['borrower_name'] and d.status == DeviceStatus.BORROWED:
            user_borrowed_count += 1
    
    borrow_limit = 10  # 最大借用数量（车机+手机卡）
    if user_borrowed_count >= borrow_limit:
        return jsonify({'success': False, 'message': f'您已借用 {user_borrowed_count} 台设备，达到上限 ({borrow_limit}台)，无法接收设备'})
    
    # 检查是否强制转借
    force = data.get('force', False)
    
    # 检查预约冲突（排除当前用户自己的预约）
    my_reservation = None  # 记录用户自己的预约
    if not force:
        conflict_check = api_client.check_transfer_conflict(device_id)
        if conflict_check['has_conflict']:
            # 分离当前用户自己的预约和其他人的预约
            my_reservations = [
                r for r in conflict_check['reservations'] 
                if r.reserver_name == user['borrower_name']
            ]
            other_reservations = [
                r for r in conflict_check['reservations'] 
                if r.reserver_name != user['borrower_name']
            ]
            
            # 如果有其他人的预约，返回冲突
            if other_reservations:
                r = other_reservations[0]
                return jsonify({
                    'success': False,
                    'code': 'RESERVATION_CONFLICT',
                    'message': f'该设备已被 {r.reserver_name} 预约借用，时间：{r.start_time.strftime("%Y-%m-%d %H:%M")} 至 {r.end_time.strftime("%Y-%m-%d %H:%M")}',
                    'conflict_info': {
                        'reserver_name': r.reserver_name,
                        'reserver_id': r.reserver_id,
                        'start_time': r.start_time.strftime('%Y-%m-%d %H:%M'),
                        'end_time': r.end_time.strftime('%Y-%m-%d %H:%M'),
                        'reservation_id': r.id
                    }
                }), 409
            
            # 记录自己的预约，后面自动同意
            if my_reservations:
                my_reservation = my_reservations[0]
    
    # 强制转借：取消相关预约
    if force:
        cancelled_count = api_client.cancel_reservations_due_to_transfer(
            device_id=device_id,
            transfer_to=user['borrower_name'],
            cancelled_by=user['borrower_name']
        )
    
    # 保存原借用人信息
    original_borrower = device.borrower
    
    # 计算预计归还时间：如果有自己的预约，使用预约结束时间；否则默认1天
    if my_reservation:
        expected_return = my_reservation.end_time
        # 自动同意自己的预约
        _approve_my_reservation(api_client, my_reservation, user)
    else:
        expected_return = datetime.now() + timedelta(days=1)
    
    # 更新设备信息 - 转给自己
    device.previous_borrower = original_borrower
    device.borrower = user['borrower_name']
    device.status = DeviceStatus.BORROWED
    device.lost_time = None  # 清除丢失时间
    device.entry_source = EntrySource.USER.value
    device.expected_return_date = expected_return  # 使用预约结束时间或默认1天
    
    api_client.update_device(device, source="user")
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.TRANSFER,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"被转借：{original_borrower}——>{user['borrower_name']}",
        reason='用户转借给自己',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)
    
    # 给自己增加借用次数
    for u in api_client._users:
        if u.borrower_name == user['borrower_name']:
            u.borrow_count += 1
            api_client._db.save_user(u)
            break

    api_client.add_operation_log(f"转给自己: {original_borrower} -> {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    
    
    # 通知原借用人（如果存在且不是当前用户）
    if original_borrower and original_borrower != user['borrower_name']:
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
                content=f"您借用的设备「{device.name}」已被 {user['borrower_name']} 转借走",
                device_name=device.name,
                device_id=device.id,
                notification_type="warning"
            )
    
    # 通知保管人（如果存在且不是相关人）
    if device.cabinet_number and device.cabinet_number != original_borrower and device.cabinet_number != user['borrower_name']:
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
                content=f"您保管的设备「{device.name}」已被 {user['borrower_name']} 从 {original_borrower} 处转借走",
                device_name=device.name,
                device_id=device.id,
                notification_type="info"
            )
    
    # 转给自己成功，发放积分奖励（+5分）
    points_result = points_service.add_points(
        user_id=user['user_id'],
        points=5,
        transaction_type=PointsTransactionType.TRANSFER,
        description=f'转给自己: {device.name}',
        related_id=device.id
    )
    points_message = ''
    if points_result['success']:
        points_message = f'，{points_result["message"]}'
    
    return jsonify({'success': True, 'message': '操作成功，设备已转给您保管' + points_message})


@app.route('/api/return-by-custodian', methods=['POST'])
@login_required
def api_return_by_custodian():
    """保管人代还API"""
    user = get_current_user()
    data = request.json
    
    # 重新加载数据以获取最新状态
    api_client.reload_data()
    
    device_id = data.get('device_id')
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备是否处于借出状态
    if device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常，仅限借出设备使用此功能'})
    
    # 检查当前用户是否为该设备的保管人
    if device.cabinet_number != user['borrower_name']:
        return jsonify({'success': False, 'message': '仅限该设备的保管人使用此功能'})
    
    original_borrower = device.borrower

    # 根据设备类型设置归还后的状态
    # 手机、手机卡、其它设备 -> 保管中；车机、仪表 -> 在库
    if device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]:
        device.status = DeviceStatus.IN_CUSTODY
    else:
        device.status = DeviceStatus.IN_STOCK

    device.borrower = ''
    device.phone = ''
    device.borrow_time = None
    device.location = ''
    device.reason = ''
    device.entry_source = ''
    device.expected_return_date = None
    device.lost_time = None

    api_client.update_device(device, source="user")

    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.RETURN,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"保管人代还：{original_borrower}",
        reason='保管人代还设备',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)

    api_client.add_operation_log(f"保管人代还 {original_borrower}", device.name, operator=user['borrower_name'], source="user")
    
    # 更新原借用人的归还次数
    for u in api_client._users:
        if u.borrower_name == original_borrower:
            u.return_count += 1
            api_client._db.save_user(u)
            break
    
    # 通知原借用人
    if original_borrower:
        api_client.notify_return(
            device_id=device_id,
            device_name=device.name,
            borrower=original_borrower,
            operator=f"保管人:{user['borrower_name']}"
        )

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
    api_client._db.save_remark(remark)

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

    api_client._db.delete_remark(remark_id)

    return jsonify({'success': True, 'message': '删除成功'})


@app.route('/api/search')
@login_required
def api_search():
    """搜索API"""
    keyword = request.args.get('keyword', '').strip()
    
    results = []
    all_devices = api_client.get_all_devices()
    
    for device in all_devices:
        # 如果有搜索关键词，进行过滤；否则返回所有设备
        if keyword:
            keyword_lower = keyword.lower()
            name_match = keyword_lower in (device.name or '').lower()
            model_match = keyword_lower in (device.model or '').lower()
            borrower_match = keyword_lower in (device.borrower or '').lower()
            # 车机和仪表字段搜索
            jira_match = keyword_lower in (device.jira_address or '').lower()
            project_match = keyword_lower in (device.project_attribute or '').lower()
            connection_match = keyword_lower in (device.connection_method or '').lower()
            os_version_match = keyword_lower in (device.os_version or '').lower()
            os_platform_match = keyword_lower in (device.os_platform or '').lower()
            product_match = keyword_lower in (device.product_name or '').lower()
            orientation_match = keyword_lower in (device.screen_orientation or '').lower()
            resolution_match = keyword_lower in (device.screen_resolution or '').lower()
            # 手机字段搜索
            system_version_match = keyword_lower in (device.system_version or '').lower()
            imei_match = keyword_lower in (device.imei or '').lower()
            sn_match = keyword_lower in (device.sn or '').lower()
            carrier_match = keyword_lower in (device.carrier or '').lower()
            
            if not (name_match or model_match or borrower_match or 
                    jira_match or project_match or connection_match or 
                    os_version_match or os_platform_match or product_match or 
                    orientation_match or resolution_match or 
                    system_version_match or imei_match or sn_match or carrier_match):
                continue
        
        # 判断是否为使用保管人的设备类型（手机、手机卡、其它设备）
        is_custodian_type = device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]

        if is_custodian_type:
            # 手机、手机卡、其它设备：根据custodian_id判断是否有保管人
            is_no_cabinet = not device.custodian_id or device.custodian_id.strip() == ''
            is_circulating = False  # 保管人设备不支持流通状态
        else:
            # 车机、仪表：根据cabinet_number判断
            cabinet = device.cabinet_number or ''
            is_no_cabinet = not cabinet.strip() or cabinet.strip() == '无'
            is_circulating = cabinet.strip() == '流转'
        is_sealed = device.status == DeviceStatus.SEALED

        results.append({
            'id': device.id,
            'name': device.name,
            'device_type': get_device_type_str(device),
            'model': device.model,
            'status': device.status.value,
            'borrower': device.borrower,
            'remark': device.remark or '-',
            'no_cabinet': is_no_cabinet,
            'is_circulating': is_circulating,
            'is_sealed': is_sealed,
            'is_custodian_type': is_custodian_type,
            # 车机和仪表字段
            'jira_address': device.jira_address or '',
            'project_attribute': device.project_attribute or '',
            'connection_method': device.connection_method or '',
            'os_version': device.os_version or '',
            'os_platform': device.os_platform or '',
            'product_name': device.product_name or '',
            'screen_orientation': device.screen_orientation or '',
            'screen_resolution': device.screen_resolution or '',
            # 手机字段
            'system_version': device.system_version or '',
            'imei': device.imei or '',
            'sn': device.sn or '',
            'carrier': device.carrier or '',
            'asset_number': device.asset_number or '',
            'purchase_amount': device.purchase_amount or ''
        })
    
    return jsonify({'success': True, 'devices': results})


@app.route('/api/add-search-points', methods=['POST'])
@login_required
def api_add_search_points():
    """添加搜索积分API"""
    user = get_current_user()
    result = points_service.search_reward(user['user_id'])

    # 获取用户当前总积分
    total_points = 0
    if result.get('success'):
        user_points_data = api_client._db.get_user_points(user['user_id'])
        if user_points_data:
            total_points = user_points_data.points

    return jsonify({
        'success': result.get('success', False),
        'points_added': result.get('points_change', 0) if result.get('success') else 0,
        'total_points': total_points,
        'message': result.get('message', '')
    })


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
                'email': user.email
            })
    return jsonify({'success': True, 'users': result})


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
    
    # 检查是否是当前借用人或保管人
    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']
    
    if not is_borrower and not is_custodian:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人或保管人'})
    
    # 检查设备状态：借用人只能报备借出状态的设备，保管人可以报备在库/保管中/借出状态的设备
    if is_borrower and device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    if is_custodian and device.status not in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY, DeviceStatus.BORROWED]:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    # 更新设备状态为丢失
    device.previous_status = device.status.value  # 保存原始状态
    device.status = DeviceStatus.LOST
    device.lost_time = datetime.now()
    device.previous_borrower = device.borrower
    
    api_client.update_device(device, source="user")
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.REPORT_LOST,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=user['borrower_name'],
        phone=device.phone,
        reason='用户报备丢失',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)
    
    api_client.add_operation_log(f"报备丢失: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    
    
    # 通知保管人（如果存在且不是报备人自己）
    if device.cabinet_number and device.cabinet_number != user['borrower_name']:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备丢失报备通知",
                content=f"您保管的设备「{device.name}」已被借用人 {user['borrower_name']} 报备丢失",
                device_name=device.name,
                device_id=device.id,
                notification_type="error"
            )
    
    # 丢失报备成功，发放积分奖励
    points_result = points_service.report_reward(user['user_id'], 'lost', device.name)
    points_message = ''
    points_change = 0
    if points_result['success']:
        points_message = f'，{points_result["message"]}'
        points_change = points_result.get('points_change', 0)

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    return jsonify({
        'success': True,
        'message': '丢失报备成功' + points_message,
        'points_added': points_change,
        'total_points': total_points
    })


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
    
    # 检查是否是当前借用人或保管人
    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']
    
    if not is_borrower and not is_custodian:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人或保管人'})
    
    # 借用人只能在借出状态转借
    if is_borrower and device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    original_borrower = device.borrower
    
    # 更新设备状态
    device.previous_status = device.status.value  # 保存原始状态
    device.status = DeviceStatus.DAMAGED
    device.damage_reason = damage_reason
    device.damage_time = datetime.now()
    
    api_client.update_device(device, source="user")
    
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
            device_type=get_device_type_str(device),
            operation_type=OperationType.REPORT_DAMAGE,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"损坏归还：{original_borrower}",
            phone=device.phone,
            reason=damage_reason,
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"损坏归还: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    else:
        # 仅报备损坏，继续借用
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.REPORT_DAMAGE,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=user['borrower_name'],
            phone=device.phone,
            reason=damage_reason,
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"报备损坏: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    
    api_client._db.save_record(record)
    

    # 通知保管人（如果存在且不是报备人自己）
    if device.cabinet_number and device.cabinet_number != user['borrower_name']:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备损坏报备通知",
                content=f"您保管的设备「{device.name}」已被借用人 {user['borrower_name']} 报备损坏",
                device_name=device.name,
                device_id=device.id,
                notification_type="warning"
            )

    # 损坏报备成功，发放积分奖励
    points_result = points_service.report_reward(user['user_id'], 'damaged', device.name)
    points_message = ''
    points_change = 0
    if points_result['success']:
        points_message = f'，{points_result["message"]}'
        points_change = points_result.get('points_change', 0)

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    return jsonify({
        'success': True,
        'message': '损坏报备成功' + points_message,
        'points_added': points_change,
        'total_points': total_points
    })


@app.route('/api/ship-device', methods=['POST'])
@login_required
def api_ship_device():
    """设备寄出API"""
    user = get_current_user()
    data = request.json

    device_id = data.get('device_id')
    ship_time_str = data.get('ship_time', '').strip()
    remark = data.get('remark', '').strip()

    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})

    # 检查是否是借用人或保管人
    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']

    if not is_borrower and not is_custodian:
        return jsonify({'success': False, 'message': '您不是该设备的借用人或保管人'})

    # 只有车机和仪表可以寄出
    if device.device_type not in (DeviceType.CAR_MACHINE, DeviceType.INSTRUMENT):
        return jsonify({'success': False, 'message': '只有车机和仪表可以寄出'})

    # 解析寄出时间
    ship_time = datetime.now()
    if ship_time_str:
        try:
            ship_time = datetime.fromisoformat(ship_time_str.replace('Z', '+00:00').replace('+00:00', ''))
        except:
            pass

    # 保存当前借用信息以便还原（如果在库则记录当前操作用户）
    device.pre_ship_borrower = device.borrower or user['borrower_name']
    device.pre_ship_borrow_time = device.borrow_time or datetime.now()
    device.pre_ship_expected_return_date = device.expected_return_date

    # 更新设备状态
    device.status = DeviceStatus.SHIPPED
    device.ship_time = ship_time
    device.ship_remark = remark
    device.ship_by = user['borrower_name']

    api_client.update_device(device, source="user")

    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.SHIP,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=device.pre_ship_borrower or user['borrower_name'],
        phone=device.phone,
        reason='已寄出',
        remark=remark,
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)

    api_client.add_operation_log(f"寄出设备: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    

    return jsonify({'success': True, 'message': '寄出登记成功'})


@app.route('/api/unship-device', methods=['POST'])
@login_required
def api_unship_device():
    """设备未寄出（还原）API"""
    user = get_current_user()
    data = request.json

    device_id = data.get('device_id')

    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})

    if device.status != DeviceStatus.SHIPPED:
        return jsonify({'success': False, 'message': '设备不是寄出状态'})

    # 还原借用信息
    if device.pre_ship_borrower:
        device.status = DeviceStatus.BORROWED
        device.borrower = device.pre_ship_borrower
        device.borrow_time = device.pre_ship_borrow_time
        device.expected_return_date = device.pre_ship_expected_return_date
    else:
        # 如果没有之前的借用信息，改为在库
        device.status = DeviceStatus.IN_STOCK

    # 清除寄出信息
    device.ship_time = None
    device.ship_remark = ''
    device.ship_by = ''
    device.pre_ship_borrower = ''
    device.pre_ship_borrow_time = None
    device.pre_ship_expected_return_date = None

    api_client.update_device(device, source="user")

    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.SHIP,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=device.borrower,
        phone=device.phone,
        reason='未寄出（还原）',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)

    api_client.add_operation_log(f"未寄出还原 {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    

    return jsonify({'success': True, 'message': '已还原为借用状态'})


@app.route('/api/found-device', methods=['POST'])
@login_required
def api_found_device():
    """设备找回API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    action = data.get('action', 'return')  # return:保管人自用 transfer:转借他人
    transfer_to = data.get('transfer_to', '').strip()
    
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备是否处于丢失状态
    if device.status != DeviceStatus.LOST:
        return jsonify({'success': False, 'message': '设备未处于丢失状态'})
    
    original_borrower = device.borrower
    
    if action == 'transfer':
        # 转借他人
        if not transfer_to:
            return jsonify({'success': False, 'message': '请选择转借人'})
        
        # 检查不能转借给自己
        if transfer_to == user['borrower_name']:
            return jsonify({'success': False, 'message': '不能转借给自己'})
        
        # 检查不能转借给当前借用人（已经在借用设备的人）
        if transfer_to == device.borrower:
            return jsonify({'success': False, 'message': '该用户已经在借用此设备'})
        
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
        
        # 更新设备状态
        device.status = DeviceStatus.BORROWED
        device.borrower = transfer_to
        device.lost_time = None
        device.previous_status = ''  # 清空原始状态记录
        
        api_client.update_device(device, source="user")
        
        # 添加记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.FOUND,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"找回转借：{original_borrower or '丢失'}——>{transfer_to}",
            reason='设备找回后转借',
            entry_source=EntrySource.USER.value
        )
        api_client._db.save_record(record)
        api_client.add_operation_log(f"设备找回转借 {transfer_to}", device.name, operator=user['borrower_name'], source="user")
    elif action == 'keep':
        # 转给自己 - 设备变为借出状态
        device.status = DeviceStatus.BORROWED
        device.borrower = user['borrower_name']
        device.borrow_time = datetime.now()
        device.lost_time = None
        device.previous_status = ''  # 清空原始状态记录
        
        api_client.update_device(device, source="user")
        
        # 添加记录
        from_desc = original_borrower or '丢失状态'
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.FOUND,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"找回：{from_desc}——>{user['borrower_name']}",
            reason='设备已找回，转给自己',
            entry_source=EntrySource.USER.value
        )
        api_client._db.save_record(record)
        api_client.add_operation_log(f"设备找回转给自己: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    else:
        # 归还入库 - 恢复设备原始状态（流通、无柜号、封存等）
        previous_status = device.previous_status
        if previous_status:
            try:
                device.status = DeviceStatus(previous_status)
            except ValueError:
                # 如果原始状态无效，默认恢复为在库
                device.status = DeviceStatus.IN_STOCK
        else:
            # 如果没有记录原始状态，默认恢复为在库
            device.status = DeviceStatus.IN_STOCK
        device.borrower = ''
        device.borrow_time = None
        device.expected_return_date = None
        device.lost_time = None
        device.previous_status = ''  # 清空原始状态记录

        api_client.update_device(device, source="user")

        # 添加记录
        from_desc = original_borrower or '丢失状态'
        to_status = device.status.value
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.FOUND,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"找回：{from_desc}——>{to_status}",
            reason=f'设备已找回，恢复为{to_status}状态',
            entry_source=EntrySource.USER.value
        )
        api_client._db.save_record(record)
        api_client.add_operation_log(f"设备找回归还: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    
    
    
    # 通知保管人（如果存在且不是当前用户）
    if device.cabinet_number and device.cabinet_number != user['borrower_name']:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            if action == 'transfer':
                action_desc = f'被找回并转借给 {transfer_to}'
            else:
                action_desc = '被找回并归还'
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备找回通知",
                content=f"您保管的设备「{device.name}」{action_desc}",
                device_name=device.name,
                device_id=device.id,
                notification_type="success"
            )
    
    # 设备找回成功，发放积分奖励
    points_result = points_service.report_reward(user['user_id'], 'found', device.name)
    points_message = ''
    points_change = 0
    if points_result['success']:
        points_message = f'，{points_result["message"]}'
        points_change = points_result.get('points_change', 0)

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    return jsonify({
        'success': True,
        'message': '设备找回成功' + points_message,
        'points_added': points_change,
        'total_points': total_points
    })


@app.route('/api/repair-device', methods=['POST'])
@login_required
def api_repair_device():
    """设备修复API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    action = data.get('action', 'return')  # return:保管人自用 transfer:转借他人
    transfer_to = data.get('transfer_to', '').strip()
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查设备是否处于损坏状态
    if device.status != DeviceStatus.DAMAGED:
        return jsonify({'success': False, 'message': '设备未处于损坏状态'})
    
    original_borrower = device.borrower
    
    if action == 'transfer':
        # 转借他人
        if not transfer_to:
            return jsonify({'success': False, 'message': '请选择转借人'})
        
        # 检查不能转借给自己
        if transfer_to == user['borrower_name']:
            return jsonify({'success': False, 'message': '不能转借给自己'})
        
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
        
        # 修复并转借
        device.status = DeviceStatus.BORROWED
        device.borrower = transfer_to
        device.damage_reason = ''
        device.damage_time = None
        device.previous_status = ''  # 清空原始状态记录

        api_client.update_device(device, source="user")

        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.REPAIRED,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"修复转借：{original_borrower or '损坏'}——>{transfer_to}",
            reason='设备已修复并转借',
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"修复转借 {transfer_to}", device.name, operator=user['borrower_name'], source="user")
    elif action == 'keep':
        # 转给自己 - 设备变为借出状态
        device.status = DeviceStatus.BORROWED
        device.borrower = user['borrower_name']
        device.borrow_time = datetime.now()
        device.damage_reason = ''
        device.damage_time = None
        device.previous_status = ''  # 清空原始状态记录

        api_client.update_device(device, source="user")
        
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.REPAIRED,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"修复：{original_borrower or '损坏'}——>{user['borrower_name']}",
            reason='设备已修复，转给自己',
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"修复转给自己: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    else:
        # 归还入库 - 恢复设备原始状态（流通、无柜号、封存等）
        previous_status = device.previous_status
        if previous_status:
            try:
                device.status = DeviceStatus(previous_status)
            except ValueError:
                # 如果原始状态无效，默认恢复为在库
                device.status = DeviceStatus.IN_STOCK
        else:
            # 如果没有记录原始状态，默认恢复为在库
            device.status = DeviceStatus.IN_STOCK
        device.borrower = ''
        device.borrow_time = None
        device.expected_return_date = None
        device.damage_reason = ''
        device.damage_time = None
        device.previous_status = ''  # 清空原始状态记录

        api_client.update_device(device, source="user")
        
        to_status = device.status.value
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.REPAIRED,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"修复：{original_borrower or '损坏'}——>{to_status}",
            reason=f'设备已修复，恢复为{to_status}状态',
            entry_source=EntrySource.USER.value
        )
        api_client.add_operation_log(f"修复归还: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    
    api_client._db.save_record(record)
    
    
    # 通知保管人（如果存在且不是当前用户）
    if device.cabinet_number and device.cabinet_number != user['borrower_name']:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            if action == 'transfer':
                action_desc = f'被修复并转借给 {transfer_to}'
            else:
                action_desc = '被修复并归还'
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备修复通知",
                content=f"您保管的设备「{device.name}」{action_desc}",
                device_name=device.name,
                device_id=device.id,
                notification_type="success"
            )
    
    # 设备修复成功，发放积分奖励
    points_result = points_service.report_reward(user['user_id'], 'fixed', device.name)
    points_message = ''
    points_change = 0
    if points_result['success']:
        points_message = f'，{points_result["message"]}'
        points_change = points_result.get('points_change', 0)

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    return jsonify({
        'success': True,
        'message': '操作成功' + points_message,
        'points_added': points_change,
        'total_points': total_points
    })


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
        device.borrower = previous_borrower
        device.phone = ''  # 清空手机号
        device.previous_borrower = ''  # 清空上一个借用人
        
        api_client.update_device(device, source="user")
        
        # 添加记录 - 使用 NOT_FOUND 类型
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.NOT_FOUND,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"未找到：{user['borrower_name']}——>{previous_borrower}",
            phone='',
            reason='设备未找到，退回给上一个借用人',
            entry_source=EntrySource.USER.value
        )
        api_client._db.save_record(record)
        api_client.add_operation_log(f"未找到退回 {user['borrower_name']} -> {previous_borrower}", device.name, operator=user['borrower_name'], source="user")
    else:
        # 没有上一个借用人，转为丢失状态
        device.previous_status = device.status.value  # 保存原始状态
        device.status = DeviceStatus.LOST
        device.previous_borrower = device.borrower
        device.lost_time = datetime.now()
        
        api_client.update_device(device, source="user")
        
        # 添加记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.REPORT_LOST,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=f"未找到转丢失：{user['borrower_name']}",
            phone=device.phone,
            reason='设备未找到，转为丢失状态',
            entry_source=EntrySource.USER.value
        )
        api_client._db.save_record(record)
        api_client.add_operation_log(f"未找到转丢失: {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    
    
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
    
    # 转为丢失状态，清空借用人信息
    device.previous_status = device.status.value  # 保存原始状态
    device.status = DeviceStatus.LOST
    device.previous_borrower = original_borrower
    device.lost_time = datetime.now()
    device.borrower = ''  # 清空借用人，设备不在任何人名下
    device.phone = ''
    
    api_client.update_device(device, source="user")
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.NOT_FOUND,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower='未找到：库中未找到',
        phone='',
        reason='设备未找到，标记为丢失，不在任何人名下',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)
    api_client.add_operation_log(f"未找到标记丢失 {user['borrower_name']}", device.name, operator=user['borrower_name'], source="user")
    
    
    return jsonify({'success': True, 'message': '已标记为丢失'})


@app.route('/api/transfer-custodian', methods=['POST'])
@login_required
def api_transfer_custodian():
    """转让保管人API"""
    user = get_current_user()
    data = request.json
    
    # 重新加载数据以获取最新状态
    api_client.reload_data()
    
    device_id = data.get('device_id')
    new_custodian = data.get('new_custodian', '').strip()
    device = api_client.get_device_by_id(device_id)
    
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查当前用户是否为该设备的保管人
    if device.cabinet_number != user['borrower_name']:
        return jsonify({'success': False, 'message': '您不是该设备的保管人'})
    
    if not new_custodian:
        return jsonify({'success': False, 'message': '请选择新保管人'})
    
    # 检查不能转让给自己
    if new_custodian == user['borrower_name']:
        return jsonify({'success': False, 'message': '不能转让给自己'})
    
    # 查找新保管人信息
    target_user = None
    if '@' in new_custodian:
        # 通过邮箱查找
        target_user = api_client.get_user_by_email(new_custodian)
    else:
        # 通过姓名查找
        for u in api_client._users:
            if u.borrower_name == new_custodian:
                target_user = u
                break
    
    if not target_user:
        return jsonify({'success': False, 'message': '新保管人不存在'})
    
    original_custodian = device.cabinet_number
    
    # 转让保管人（修改 cabinet_number）
    device.cabinet_number = target_user.borrower_name
    
    api_client.update_device(device, source="user")
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.CUSTODIAN_CHANGE,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"转让保管人：{original_custodian}——>{new_custodian}",
        reason='设备转让保管人',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)
    api_client.add_operation_log(f"转让保管人 {original_custodian} -> {new_custodian}", device.name, operator=user['borrower_name'], source="user")
    
    
    # 发送通知给新保管人
    api_client.add_notification(
        user_id=target_user.id,
        user_name=target_user.borrower_name,
        title="设备保管人变更通知",
        content=f"设备「{device.name}」的保管人已从 {original_custodian} 转让给您",
        device_name=device.name,
        device_id=device.id,
        notification_type="info"
    )
    
    return jsonify({'success': True, 'message': '转让保管人成功'})


@app.route('/api/renew', methods=['POST'])
@login_required
def api_renew():
    """续借设备API"""
    user = get_current_user()
    data = request.json
    
    # 重新加载数据以获取最新状态
    api_client.reload_data()
    
    device_id = data.get('device_id')
    days = data.get('days', 1)
    new_return_date = data.get('new_return_date', '').strip()
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人或保管人
    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']
    
    if not is_borrower and not is_custodian:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人或保管人'})
    
    # 借用人只能在借出状态转借
    if is_borrower and device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
    # 检查是否逾期超过3天
    if device.expected_return_date:
        now = datetime.now()
        if now > device.expected_return_date:
            overdue_days = (now.date() - device.expected_return_date.date()).days
            if overdue_days > 3:
                return jsonify({'success': False, 'message': '无法续期，设备已逾期超过3天，请先归还后再借用'})
    
    # 计算新的预计归还日期
    if new_return_date:
        # 使用前端传递的完整日期时间
        from datetime import datetime as dt
        try:
            # 尝试解析完整格式 YYYY-MM-DD HH:MM:SS
            new_expected_return_date = dt.strptime(new_return_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # 兼容旧格式 YYYY-MM-DD，时间设为当前时间
            date_part = dt.strptime(new_return_date, '%Y-%m-%d')
            now = dt.now()
            new_expected_return_date = date_part.replace(hour=now.hour, minute=now.minute, second=now.second)
    else:
        # 长期借用，不设置归还日期（空字符串或None都表示长期借用）
        new_expected_return_date = None
    
    # 检查续期是否与预约冲突
    # 获取设备类型
    device_type = get_device_type_str(device)
    
    # 检查是否有预约与新的归还日期冲突（长期借用不检查冲突）
    if new_expected_return_date is not None:
        reservations = api_client._db.get_reservations_by_device(device_id, device_type)
        for reservation in reservations:
            # 只检查已同意或待确认的预约
            if reservation.status in [ReservationStatus.APPROVED.value,
                                       ReservationStatus.PENDING_CUSTODIAN.value,
                                       ReservationStatus.PENDING_BORROWER.value,
                                       ReservationStatus.PENDING_BOTH.value]:
                # 如果新的归还日期超过了预约开始时间，说明有冲突
                if new_expected_return_date > reservation.start_time:
                    # 检查是否是预约人自己续期自己的预约
                    if reservation.reserver_id == user['user_id']:
                        # 自己的预约，允许续期，但需要在预约到期时自动处理
                        continue
                    return jsonify({
                        'success': False,
                        'message': f"无法续期，该设备已被 {reservation.reserver_name} 预约，预约时间 {reservation.start_time.strftime('%Y-%m-%d %H:%M')} 至 {reservation.end_time.strftime('%Y-%m-%d %H:%M')}"
                    })
    
    # 更新设备的预计归还日期
    device.expected_return_date = new_expected_return_date
    
    api_client.update_device(device, source="user")
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.RENEW,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=user['borrower_name'],
        phone=device.phone,
        reason=f'续借 {days} 天' if new_expected_return_date else '续借为长期借用',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)
    api_client.add_operation_log(f"续借设备 {user['borrower_name']}, {days if new_expected_return_date else '长期'}天", device.name, operator=user['borrower_name'], source="user")
    
    
    # 通知保管人（如果存在且不是借用人自己）
    if device.cabinet_number and device.cabinet_number != user['borrower_name']:
        custodian_user = None
        for u in api_client._users:
            if u.borrower_name == device.cabinet_number:
                custodian_user = u
                break
        if custodian_user:
            return_date_str = device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else '长期借用'
            api_client.add_notification(
                user_id=custodian_user.id,
                user_name=custodian_user.borrower_name,
                title="设备借用续期通知",
                content=f"您保管的设备「{device.name}」已被借用人 {user['borrower_name']} 续期，新的预计归还日期：{return_date_str}",
                device_name=device.name,
                device_id=device.id,
                notification_type="info"
            )
    
    # 续借成功，发放积分奖励
    points_result = points_service.renew_reward(user['user_id'], device.name)
    points_message = ''
    points_change = 0
    if points_result['success']:
        points_message = f'，{points_result["message"]}'
        points_change = points_result.get('points_change', 0)

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    return_date_msg = device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else '长期借用'
    return jsonify({
        'success': True,
        'message': f'续借成功，新的预计归还日期: {return_date_msg}' + points_message,
        'points_added': points_change,
        'total_points': total_points
    })


# ==================== 通知API ====================

@app.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    """获取通知列表API"""
    user = get_current_user()
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'

    notifications = api_client.get_notifications(
        user_id=user['user_id'],
        user_name=user['borrower_name'],
        unread_only=unread_only
    )

    return jsonify({'notifications': [n.to_dict() for n in notifications]})


@app.route('/api/notifications/unread-count', methods=['GET'])
@login_required
def api_notification_unread_count():
    """获取未读通知数量API"""
    user = get_current_user()

    count = api_client.get_unread_count(
        user_id=user['user_id'],
        user_name=user['borrower_name']
    )

    return jsonify({'count': count})


@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    """标记通知为已读API"""
    success = api_client.mark_notification_read(notification_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '通知不存在'})


@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def api_mark_all_read():
    """标记所有通知为已读API"""
    user = get_current_user()

    count = api_client.mark_all_read(
        user_id=user['user_id'],
        user_name=user['borrower_name']
    )

    return jsonify({'success': True, 'count': count})


# ==================== 公告API ====================

@app.route('/api/announcements', methods=['GET'])
@login_required
def api_user_announcements():
    """获取公告列表API（用户端）"""
    # 普通公告
    normal_announcements = api_client.get_active_normal_announcements()
    # 特殊公告
    special_announcements = api_client.get_active_special_announcements()
    
    return jsonify({
        'success': True,
        'normal_announcements': [a.to_dict() for a in normal_announcements],
        'special_announcements': [a.to_dict() for a in special_announcements]
    })


# ==================== 用户排名API ====================

@app.route('/api/user-rankings', methods=['GET'])
@login_required
def api_user_rankings():
    """获取用户排名列表API"""
    ranking_type = request.args.get('type', 'borrow')  # 'borrow', 'return', 或 'points'

    if ranking_type not in ['borrow', 'return', 'points']:
        return jsonify({'success': False, 'message': '排名类型无效'})

    # 获取当前用户今天的点赞次数
    user = get_current_user()
    today_likes = api_client.get_user_today_likes(user['user_id'])
    remaining_likes = 5 - today_likes

    # 获取排名数据（都使用缓存）
    rankings = api_client.get_user_rankings(ranking_type)
    # 添加用户装备信息
    for r in rankings:
        equipment = get_user_equipment(r['user_id'])
        r['equipped_title'] = equipment.get('title')
        r['avatar_frame'] = equipment.get('avatar_frame')
    return jsonify({
        'success': True,
        'rankings': rankings,
        'remaining_likes': max(0, remaining_likes)
    })


@app.route('/api/user-like', methods=['POST'])
@login_required
def api_user_like():
    """用户点赞API"""
    data = request.get_json()
    to_user_id = data.get('to_user_id')

    if not to_user_id:
        return jsonify({'success': False, 'message': '请选择要点赞的用户'})

    user = get_current_user()
    success, message = api_client.add_like(user['user_id'], to_user_id)

    if success:
        # 点赞成功，发放积分奖励
        points_result = points_service.like_reward(user['user_id'])
        points_message = ''
        points_added = 0
        total_points = 0
        if points_result['success']:
            points_message = f'，{points_result["message"]}'
            points_added = points_result.get('points_change', 0)

        # 获取用户当前总积分
        user_points_data = api_client._db.get_user_points(user['user_id'])
        if user_points_data:
            total_points = user_points_data.points

        # 获取点赞后的点赞数
        like_count = api_client.get_user_like_count(to_user_id)
        return jsonify({
            'success': True,
            'message': message + points_message,
            'like_count': like_count,
            'points_added': points_added,
            'total_points': total_points
        })
    else:
        return jsonify({'success': False, 'message': message})


@app.route('/api/user/current-cursor', methods=['GET'])
@login_required
def api_user_current_cursor():
    """获取用户当前鼠标皮肤API"""
    user = get_current_user()
    full_user = api_client._db.get_user_by_id(user['user_id'])

    if not full_user or not full_user.current_cursor:
        return jsonify({'success': True, 'cursor_skin': None})

    # 获取鼠标皮肤详情
    cursor_item = api_client._db.get_shop_item_by_id(full_user.current_cursor)
    if cursor_item and cursor_item.icon:
        return jsonify({
            'success': True,
            'cursor_skin': cursor_item.icon,
            'cursor_name': cursor_item.name
        })

    return jsonify({'success': True, 'cursor_skin': None})


# ==================== 个人资料API ====================

@app.route('/pc/points')
@login_required
def pc_points_shop():
    """PC端积分商城页面"""
    api_client.reload_data()
    user = get_current_user()
    
    # 获取用户积分详情
    user_points = points_service.get_or_create_user_points(user['user_id'])
    points_rank = points_service.get_user_points_rank(user['user_id'])
    
    # 获取积分记录
    records = points_service.get_points_records(user['user_id'], limit=100)
    
    # 获取商品列表
    from common.models import ShopItemType, ShopItemSource
    shop_items = api_client._db.get_all_shop_items(only_active=True)
    
    # 获取用户已拥有的物品
    user_inventory = api_client._db.get_user_inventory(user['user_id'])
    owned_item_ids = {item.item_id for item in user_inventory}

    # 获取完整用户信息（用于检查当前装备的主题和鼠标皮肤）
    full_user = api_client._db.get_user_by_id(user['user_id'])
    current_theme_id = full_user.current_theme if full_user else ''
    current_cursor_id = full_user.current_cursor if full_user else ''

    # 标记已拥有的商品和装备状态
    for item in shop_items:
        item.owned = item.id in owned_item_ids
        # 如果是主题皮肤，检查是否正在使用
        if item.item_type and item.item_type.value == '主题皮肤':
            item.is_equipped = (item.id == current_theme_id)
        # 如果是鼠标皮肤，检查是否正在使用
        if item.item_type and item.item_type.value == '鼠标皮肤':
            item.is_equipped = (item.id == current_cursor_id)
    
    # 获取今日积分统计
    today = datetime.now().strftime('%Y-%m-%d')
    today_stats = {
        'daily_login': False,
        'like_count': 0,
        'search': False,
        'report_found': False,
        'report_fixed': False,
        'report_damaged': False,
        'report_lost': False,
    }
    
    from common.models import PointsTransactionType
    all_records = points_service.db.get_points_records(user['user_id'])
    for record in all_records:
        if record.create_time and record.create_time.strftime('%Y-%m-%d') == today:
            if record.transaction_type == PointsTransactionType.DAILY_LOGIN:
                today_stats['daily_login'] = True
            elif record.transaction_type == PointsTransactionType.LIKE:
                today_stats['like_count'] += 1
            elif record.transaction_type == PointsTransactionType.SEARCH:
                today_stats['search'] = True
            elif record.transaction_type == PointsTransactionType.REPORT_FOUND:
                today_stats['report_found'] = True
            elif record.transaction_type == PointsTransactionType.REPORT_FIXED:
                today_stats['report_fixed'] = True
            elif record.transaction_type == PointsTransactionType.REPORT_DAMAGED:
                today_stats['report_damaged'] = True
            elif record.transaction_type == PointsTransactionType.REPORT_LOST:
                today_stats['report_lost'] = True
    
    # 获取设备统计数据（用于侧边栏显示）
    stats = get_device_stats()
    
    return render_template('pc/points_shop.html',
                         user=user,
                         user_points=user_points,
                         points_rank=points_rank,
                         records=records,
                         shop_items=shop_items,
                         today_stats=today_stats,
                         active_nav='points_shop',
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


@app.route('/api/inventory/use', methods=['POST'])
@login_required
def api_use_inventory_item():
    """使用背包物品API"""
    try:
        data = request.get_json()
        inventory_id = data.get('inventory_id')
        
        if not inventory_id:
            return jsonify({'success': False, 'message': '物品ID不能为空'})
        
        user = get_current_user()
        user_id = user['user_id']
        
        # 获取背包物品
        inventory_item = api_client._db.get_inventory_item_by_id(inventory_id)
        if not inventory_item:
            return jsonify({'success': False, 'message': '物品不存在'})
        
        if inventory_item.user_id != user_id:
            return jsonify({'success': False, 'message': '无权操作该物品'})
        
        # 获取完整用户信息
        full_user = api_client._db.get_user_by_id(user_id)
        if not full_user:
            return jsonify({'success': False, 'message': '用户不存在'})
        
        from common.models import ShopItemType
        from datetime import datetime
        
        # 根据物品类型更新用户装备
        if inventory_item.item_type == ShopItemType.TITLE:
            # 先将同类型的其他物品设为未使用
            user_inventory = api_client._db.get_user_inventory(user_id, ShopItemType.TITLE.value)
            for inv in user_inventory:
                if inv.is_used:
                    api_client._db.update_inventory_item_status(inv.id, False)
            # 更新用户当前称号
            full_user.current_title = inventory_item.item_id
        elif inventory_item.item_type == ShopItemType.AVATAR_FRAME:
            # 先将同类型的其他物品设为未使用
            user_inventory = api_client._db.get_user_inventory(user_id, ShopItemType.AVATAR_FRAME.value)
            for inv in user_inventory:
                if inv.is_used:
                    api_client._db.update_inventory_item_status(inv.id, False)
            # 更新用户当前头像边框
            full_user.current_avatar_frame = inventory_item.item_id
        
        # 保存用户信息
        api_client._db.save_user(full_user)
        
        # 更新物品使用状态
        api_client._db.update_inventory_item_status(inventory_id, True, datetime.now())
        
        # 刷新api_client中的用户数据
        api_client.reload_data()
        
        item_type_name = '称号' if inventory_item.item_type == ShopItemType.TITLE else '头像边框'
        return jsonify({
            'success': True,
            'message': f'已装备 {inventory_item.item_name}',
            'item_type': item_type_name
        })
        
    except Exception as e:
        print(f"使用物品失败: {e}")
        return jsonify({'success': False, 'message': '使用失败，请重试'})


@app.route('/api/shop/buy', methods=['POST'])
@login_required
def api_shop_buy():
    """购买商品API"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')

        if not item_id:
            return jsonify({'success': False, 'message': '商品ID不能为空'})

        user = get_current_user()
        user_id = user['user_id']

        # 获取商品信息
        item = api_client._db.get_shop_item_by_id(item_id)
        if not item:
            return jsonify({'success': False, 'message': '商品不存在'})

        if not item.is_active:
            return jsonify({'success': False, 'message': '商品已下架'})

        # 检查用户是否已拥有该物品
        if api_client._db.has_item_in_inventory(user_id, item_id):
            return jsonify({'success': False, 'message': '您已拥有该物品'})

        # 获取用户积分
        user_points = points_service.get_or_create_user_points(user_id)

        # 检查积分是否足够
        if user_points.points < item.price:
            return jsonify({'success': False, 'message': '积分不足'})

        # 扣除积分
        success = points_service.add_points(
            user_id=user_id,
            points=-item.price,
            transaction_type=PointsTransactionType.SHOP_BUY,
            description=f'购买商品：{item.name}',
            related_id=item_id
        )

        if not success:
            return jsonify({'success': False, 'message': '积分扣除失败'})

        # 添加物品到背包
        from common.models import UserInventory, ShopItemSource
        import uuid
        inventory_item = UserInventory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            item_id=item.id,
            item_type=item.item_type,
            item_name=item.name,
            item_icon=item.icon,
            item_color=item.color,
            source=ShopItemSource.SHOP,
            is_used=False
        )
        api_client._db.add_to_inventory(inventory_item)

        return jsonify({
            'success': True,
            'message': f'成功购买 {item.name}',
            'item': {
                'id': item.id,
                'name': item.name,
                'type': item.item_type.value if item.item_type else ''
            }
        })

    except Exception as e:
        print(f"购买商品失败: {e}")
        return jsonify({'success': False, 'message': '购买失败，请重试'})


@app.route('/api/shop/equip', methods=['POST'])
@login_required
def api_shop_equip():
    """装备商品API（用于主题皮肤）"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')

        if not item_id:
            return jsonify({'success': False, 'message': '商品ID不能为空'})

        user = get_current_user()
        user_id = user['user_id']

        # 获取完整用户信息
        full_user = api_client._db.get_user_by_id(user_id)
        if not full_user:
            return jsonify({'success': False, 'message': '用户信息获取失败'})

        # 处理默认主题
        if item_id == 'default':
            # 恢复默认主题
            full_user.current_theme = ''
            api_client._db.save_user(full_user)

            return jsonify({
                'success': True,
                'message': '已恢复默认主题',
                'theme': 'default'
            })

        # 处理默认鼠标
        if item_id == 'default_cursor':
            # 恢复默认鼠标
            full_user.current_cursor = ''
            api_client._db.save_user(full_user)

            return jsonify({
                'success': True,
                'message': '已恢复默认鼠标',
                'cursor': 'default'
            })

        # 获取商品信息
        item = api_client._db.get_shop_item_by_id(item_id)
        if not item:
            return jsonify({'success': False, 'message': '商品不存在'})

        # 检查用户是否拥有该物品
        if not api_client._db.has_item_in_inventory(user_id, item_id):
            return jsonify({'success': False, 'message': '您未拥有该物品，请先购买'})

        # 根据商品类型进行装备
        if item.item_type and item.item_type.value == '主题皮肤':
            # 装备主题皮肤
            full_user.current_theme = item_id
            api_client._db.save_user(full_user)

            # 标记物品为已使用
            inventory_items = api_client._db.get_user_inventory(user_id)
            for inv_item in inventory_items:
                if inv_item.item_id == item_id:
                    api_client._db.update_inventory_item_status(
                        inv_item.id, True, datetime.now()
                    )

            return jsonify({
                'success': True,
                'message': f'成功应用主题：{item.name}',
                'theme': item.icon
            })
        elif item.item_type and item.item_type.value == '鼠标皮肤':
            # 装备鼠标皮肤
            full_user.current_cursor = item_id
            api_client._db.save_user(full_user)

            # 标记物品为已使用
            inventory_items = api_client._db.get_user_inventory(user_id)
            for inv_item in inventory_items:
                if inv_item.item_id == item_id:
                    api_client._db.update_inventory_item_status(
                        inv_item.id, True, datetime.now()
                    )

            return jsonify({
                'success': True,
                'message': f'成功应用鼠标皮肤：{item.name}',
                'cursor': item.icon
            })
        else:
            return jsonify({'success': False, 'message': '该商品类型不支持装备操作'})

    except Exception as e:
        print(f"装备商品失败: {e}")
        return jsonify({'success': False, 'message': '装备失败，请重试'})


@app.route('/pc/bounties')
@login_required
def pc_bounties():
    """PC端悬赏榜单页面"""
    api_client.reload_data()
    user = get_current_user()

    # 获取所有悬赏
    all_bounties = api_client._db.get_all_bounties()

    # 获取用户积分（显示当前剩余积分）
    user_points_data = points_service.get_or_create_user_points(user['user_id'])
    user_points = user_points_data.points if user_points_data else 0

    # 获取设备统计数据（用于侧边栏显示）
    stats = get_device_stats()

    return render_template('pc/bounties.html',
                         user=user,
                         user_points=user_points,
                         bounties=all_bounties,
                         active_nav='bounties',
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


@app.route('/api/bounties', methods=['GET'])
@login_required
def api_get_bounties():
    """获取悬赏列表API"""
    status = request.args.get('status', None)
    my_bounties = request.args.get('my_bounties', 'false').lower() == 'true'
    user = get_current_user()

    # 先自动取消所有过期悬赏
    expired_bounties = api_client._db.auto_cancel_expired_bounties()
    if expired_bounties:
        # 退还积分给发布人
        from common.models import PointsTransactionType
        from common.points_service import points_service
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

    if my_bounties:
        # 获取当前用户的悬赏
        bounties = api_client._db.get_bounties_by_publisher(user['user_id'])
    else:
        bounties = api_client._db.get_all_bounties(status=status)

    # 转换为字典列表
    bounty_list = []
    for bounty in bounties:
        bounty_dict = bounty.to_dict()
        # 添加发布人头像
        for u in api_client._users:
            if u.id == bounty.publisher_id:
                bounty_dict['publisher_avatar'] = u.avatar
                break
        # 添加认领人头像
        if bounty.claimer_id:
            for u in api_client._users:
                if u.id == bounty.claimer_id:
                    bounty_dict['claimer_avatar'] = u.avatar
                    break
        bounty_list.append(bounty_dict)

    return jsonify({'success': True, 'bounties': bounty_list})


@app.route('/api/devices/search', methods=['GET'])
@login_required
def api_search_devices():
    """搜索设备API（用于悬赏联想搜索）"""
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify({'success': True, 'devices': []})

    # 搜索设备
    all_devices = api_client._db.get_all_devices()
    matched_devices = []

    for device in all_devices:
        # 匹配设备名称、型号、SN码、IMEI等
        name_match = device.name and keyword.lower() in device.name.lower()
        model_match = device.model and keyword.lower() in device.model.lower()
        sn_match = (hasattr(device, 'sn') and device.sn and keyword.lower() in device.sn.lower())
        imei_match = (hasattr(device, 'imei') and device.imei and keyword.lower() in device.imei.lower())

        if name_match or model_match or sn_match or imei_match:
            matched_devices.append({
                'id': device.id,
                'name': device.name,
                'model': device.model,
                'device_type': device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
                'status': device.status.value if hasattr(device.status, 'value') else str(device.status),
                'cabinet_number': device.cabinet_number
            })

    # 最多返回10条结果
    return jsonify({'success': True, 'devices': matched_devices[:10]})


@app.route('/api/bounties', methods=['POST'])
@login_required
def api_create_bounty():
    """创建悬赏API"""
    user = get_current_user()
    data = request.json

    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    device_name = data.get('device_name', '').strip()
    device_id = data.get('device_id', '').strip()
    reward_points = int(data.get('reward_points', 10))

    # 验证数据
    if not title:
        return jsonify({'success': False, 'message': '请输入悬赏标题'})
    if not device_name:
        return jsonify({'success': False, 'message': '请输入要寻找的设备名称'})
    if reward_points < 1 or reward_points > 100:
        return jsonify({'success': False, 'message': '悬赏积分必须在1-100之间'})

    # 检查积分是否足够（发布悬赏需要10积分 + 悬赏积分）
    user_points = points_service.get_or_create_user_points(user['user_id'])
    total_cost = 10 + reward_points
    if user_points.points < total_cost:
        return jsonify({'success': False, 'message': f'积分不足，发布悬赏需要{total_cost}积分（发布费10积分 + 悬赏{reward_points}积分）'})

    # 如果提供了设备ID，验证设备是否存在
    device = None
    if device_id:
        device = api_client._db.get_device_by_id(device_id)
        if not device:
            return jsonify({'success': False, 'message': '设备不存在'})

    # 扣除发布悬赏的积分（发布费10积分 + 悬赏积分）
    from common.models import PointsTransactionType

    # 扣除发布费
    points_result = points_service.create_bounty_cost(user['user_id'], title, '')
    if not points_result['success']:
        return jsonify({'success': False, 'message': points_result['message']})

    # 扣除悬赏积分（冻结）
    if reward_points > 0:
        points_service.add_points(
            user_id=user['user_id'],
            points=-reward_points,
            transaction_type=PointsTransactionType.CREATE_BOUNTY,
            description=f'悬赏冻结积分: {title}',
            related_id=''
        )

    # 创建悬赏
    from common.models import Bounty, BountyStatus
    import uuid
    from datetime import datetime

    # 保存设备之前的状态
    device_previous_status = ""
    if device:
        device_previous_status = device.status.value if hasattr(device.status, 'value') else str(device.status)

    bounty = Bounty(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        publisher_id=user['user_id'],
        publisher_name=user['borrower_name'],
        reward_points=reward_points,
        status=BountyStatus.PENDING,
        device_name=device_name,
        device_id=device_id,
        device_previous_status=device_previous_status
    )

    api_client._db.save_bounty(bounty)

    # 添加设备借用记录
    if device:
        from common.models import Record, OperationType
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=get_device_type_str(device),
            operation_type=OperationType.CREATE_BOUNTY,
            operator=user['borrower_name'],
            operation_time=datetime.now(),
            borrower=user['borrower_name'],
            reason=f'发布悬赏：{title}',
            entry_source=EntrySource.USER.value
        )
        result = api_client._db.save_record(record)

        # 添加操作日志
        api_client._db.add_operation_log(
            operation="发布悬赏",
            device_name=device.name,
            operator=user['borrower_name']
        )

    # 更新积分记录中的related_id
    records = api_client._db.get_points_records(user['user_id'], limit=1)
    if records and records[0].transaction_type.value == '发布悬赏':
        records[0].related_id = bounty.id

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    return jsonify({
        'success': True,
        'message': '悬赏发布成功',
        'bounty_id': bounty.id,
        'points_added': -(10 + reward_points),  # 发布费 + 悬赏积分（负数表示扣除）
        'total_points': total_points
    })


@app.route('/api/bounties/<bounty_id>/found', methods=['POST'])
@login_required
def api_found_bounty(bounty_id):
    """找到设备API（任何人都可以提交找到设备）"""
    user = get_current_user()
    data = request.json
    finder_description = data.get('finder_description', '').strip()

    if not finder_description:
        return jsonify({'success': False, 'message': '请描述设备位置'})

    bounty = api_client._db.get_bounty_by_id(bounty_id)
    if not bounty:
        return jsonify({'success': False, 'message': '悬赏不存在'})

    if bounty.status.value != '待认领':
        return jsonify({'success': False, 'message': '该悬赏状态不正确'})

    # 不能找到自己发布的悬赏
    if bounty.publisher_id == user['user_id']:
        return jsonify({'success': False, 'message': '不能提交自己发布的悬赏'})

    # 更新悬赏状态为已找到
    from common.models import BountyStatus
    from datetime import datetime

    bounty.status = BountyStatus.FOUND
    bounty.claimer_id = user['user_id']
    bounty.claimer_name = user['borrower_name']
    bounty.claim_time = datetime.now()
    bounty.finder_description = finder_description
    api_client._db.save_bounty(bounty)

    # 通知发布人
    api_client.add_notification(
        user_id=bounty.publisher_id,
        user_name=bounty.publisher_name,
        title="悬赏有人找到设备",
        content=f"您发布的悬赏「{bounty.title}」已被 {user['borrower_name']} 找到，请确认",
        notification_type="info"
    )

    return jsonify({'success': True, 'message': '已通知悬赏人确认'})


@app.route('/api/bounties/<bounty_id>/confirm', methods=['POST'])
@login_required
def api_confirm_bounty(bounty_id):
    """确认悬赏完成API（发布人确认）"""
    user = get_current_user()
    data = request.json
    confirmed = data.get('confirmed', True)  # True=确认完成, False=未找到

    bounty = api_client._db.get_bounty_by_id(bounty_id)
    if not bounty:
        return jsonify({'success': False, 'message': '悬赏不存在'})

    if bounty.publisher_id != user['user_id']:
        return jsonify({'success': False, 'message': '只有发布人可以确认'})

    if bounty.status.value != '已找到':
        return jsonify({'success': False, 'message': '该悬赏状态不正确'})

    from common.models import BountyStatus, DeviceStatus, Record
    from datetime import datetime
    import uuid

    if confirmed:
        # 确认完成
        bounty.status = BountyStatus.COMPLETED
        bounty.complete_time = datetime.now()
        api_client._db.save_bounty(bounty)

        # 给找到人发放悬赏积分
        points_service.receive_bounty_reward(
            bounty.claimer_id,
            bounty.title,
            bounty.id,
            bounty.reward_points
        )

        # 如果关联了设备，将设备状态改为借出并转给发榜人
        if bounty.device_id:
            device = api_client._db.get_device_by_id(bounty.device_id)
            if device:
                # 更新设备状态为借出
                device.status = DeviceStatus.BORROWED
                device.borrower_id = bounty.publisher_id
                device.borrower_name = bounty.publisher_name
                device.loan_time = datetime.now()
                api_client._db.save_device(device)

                # 创建悬赏完成记录
                from common.models import OperationType
                record = Record(
                    id=str(uuid.uuid4()),
                    device_id=device.id,
                    device_name=device.name,
                    device_type=get_device_type_str(device),
                    operation_type=OperationType.COMPLETE_BOUNTY,
                    operator=user['borrower_name'],
                    operation_time=datetime.now(),
                    borrower=bounty.publisher_name,
                    reason=f'悬赏完成：{bounty.title}，获得设备',
                    entry_source=EntrySource.USER.value
                )
                result = api_client._db.save_record(record)

                # 添加操作日志
                api_client._db.add_operation_log(
                    operation="悬赏完成",
                    device_name=device.name,
                    operator=user['borrower_name']
                )

        # 通知找到人
        api_client.add_notification(
            user_id=bounty.claimer_id,
            user_name=bounty.claimer_name,
            title="悬赏完成",
            content=f"您找到的悬赏「{bounty.title}」已被确认，获得 {bounty.reward_points} 积分",
            notification_type="success"
        )

        return jsonify({'success': True, 'message': f'确认完成，{bounty.claimer_name} 已获得 {bounty.reward_points} 积分'})
    else:
        # 未找到，恢复悬赏状态为待认领
        bounty.status = BountyStatus.PENDING
        # 清除找到人信息但保留找到描述用于参考
        previous_finder = bounty.claimer_name
        bounty.claimer_id = ""
        bounty.claimer_name = ""
        bounty.claim_time = None
        api_client._db.save_bounty(bounty)

        # 通知找到人
        api_client.add_notification(
            user_id=bounty.claimer_id or "",
            user_name=previous_finder,
            title="悬赏未确认",
            content=f"您找到的悬赏「{bounty.title}」未被确认，悬赏已重新开放",
            notification_type="warning"
        )

        return jsonify({'success': True, 'message': '已标记为未找到，悬赏重新开放'})


@app.route('/api/bounties/<bounty_id>/cancel', methods=['POST'])
@login_required
def api_cancel_bounty(bounty_id):
    """取消悬赏API（发布人取消）"""
    user = get_current_user()

    bounty = api_client._db.get_bounty_by_id(bounty_id)
    if not bounty:
        return jsonify({'success': False, 'message': '悬赏不存在'})

    if bounty.publisher_id != user['user_id']:
        return jsonify({'success': False, 'message': '只有发布人可以取消'})

    if bounty.status.value != '待认领':
        return jsonify({'success': False, 'message': '只能取消待认领的悬赏'})

    # 退还发布悬赏的积分（10积分）和悬赏积分
    from common.models import PointsTransactionType

    # 退还发布费
    points_service.add_points(
        user_id=user['user_id'],
        points=10,
        transaction_type=PointsTransactionType.CREATE_BOUNTY,
        description=f'取消悬赏退还发布费: {bounty.title}',
        related_id=bounty.id
    )

    # 退还悬赏积分
    points_service.add_points(
        user_id=user['user_id'],
        points=bounty.reward_points,
        transaction_type=PointsTransactionType.RECEIVE_BOUNTY,
        description=f'取消悬赏退还悬赏积分: {bounty.title}',
        related_id=bounty.id
    )

    # 如果关联了设备，添加取消记录
    if bounty.device_id:
        device = api_client._db.get_device_by_id(bounty.device_id)
        if device:
            # 添加设备借用记录
            from common.models import Record, OperationType
            record = Record(
                id=str(uuid.uuid4()),
                device_id=device.id,
                device_name=device.name,
                device_type=get_device_type_str(device),
                operation_type=OperationType.CANCEL_BOUNTY,
                operator=user['borrower_name'],
                operation_time=datetime.now(),
                borrower=user['borrower_name'],
                reason=f'取消悬赏：{bounty.title}',
                entry_source=EntrySource.USER.value
            )
            result = api_client._db.save_record(record)

            # 添加操作日志
            api_client._db.add_operation_log(
                operation="取消悬赏",
                device_name=device.name,
                operator=user['borrower_name']
            )

    # 删除悬赏
    api_client._db.delete_bounty(bounty_id)

    return jsonify({'success': True, 'message': '悬赏已取消，积分已退还'})


@app.route('/pc/profile')
@login_required
def pc_profile():
    """PC端个人资料页面"""
    api_client.reload_data()
    user = get_current_user()

    # 获取完整用户信息（包含头像）
    full_user = None
    for u in api_client._users:
        if u.id == user['user_id']:
            full_user = u
            break

    # 获取用户背包物品
    from common.models import ShopItemType
    inventory = api_client._db.get_user_inventory(user['user_id'])

    inventory_titles = [item for item in inventory if item.item_type == ShopItemType.TITLE]
    inventory_frames = [item for item in inventory if item.item_type == ShopItemType.AVATAR_FRAME]
    inventory_themes = [item for item in inventory if item.item_type and item.item_type.value == '主题皮肤']
    inventory_cursors = [item for item in inventory if item.item_type and item.item_type.value == '鼠标皮肤']

    # 标记当前正在使用的主题
    current_theme_id = full_user.current_theme if full_user else ''
    for theme in inventory_themes:
        theme.is_used = (theme.item_id == current_theme_id)

    # 标记当前正在使用的鼠标皮肤
    current_cursor_id = full_user.current_cursor if full_user else ''
    for cursor in inventory_cursors:
        cursor.is_used = (cursor.item_id == current_cursor_id)

    # 获取当前主题图标
    current_theme = None
    if current_theme_id:
        theme_item = api_client._db.get_shop_item_by_id(current_theme_id)
        if theme_item:
            current_theme = theme_item.icon

    # 获取当前鼠标皮肤
    current_cursor = current_cursor_id if current_cursor_id else None

    # 获取设备统计数据（用于侧边栏显示）
    stats = get_device_stats()

    return render_template('pc/profile.html',
                         user=user,
                         full_user=full_user,
                         inventory=inventory,
                         inventory_titles=inventory_titles,
                         inventory_frames=inventory_frames,
                         inventory_themes=inventory_themes,
                         inventory_cursors=inventory_cursors,
                         current_theme=current_theme,
                         current_cursor=current_cursor,
                         hide_search=True,
                         **stats)


@app.route('/api/redeem-code', methods=['POST'])
@login_required
def api_redeem_code():
    """兑换码兑换积分API"""
    user = get_current_user()
    data = request.get_json()
    
    if not data or 'code' not in data or 'points' not in data:
        return jsonify({'success': False, 'message': '参数错误'})
    
    code = data['code']
    points = data['points']
    
    # 验证积分是否为正数
    if not isinstance(points, int) or points <= 0:
        return jsonify({'success': False, 'message': '无效的积分值'})
    
    try:
        # 添加积分到用户账户
        result = points_service.add_points(
            user_id=user['user_id'],
            points=points,
            transaction_type=PointsTransactionType.REDEEM_CODE,
            description=f'兑换码兑换: {code}'
        )

        # 获取更新后的总积分
        total_points = result.get('points', 0)
        
        return jsonify({
            'success': True,
            'message': f'成功兑换 {points} 积分',
            'total_points': total_points
        })
    except Exception as e:
        print(f"[ERROR] 兑换码兑换失败: {e}")
        return jsonify({'success': False, 'message': '兑换失败，请重试'})


@app.route('/api/upload-avatar', methods=['POST'])
@login_required
def api_upload_avatar():
    """上传头像API"""
    user = get_current_user()

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': '请选择要上传的图片'})

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': '请选择要上传的图片'})

    # 检查文件类型
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in allowed_extensions:
        return jsonify({'success': False, 'message': '只支持 png, jpg, jpeg, gif, webp 格式的图片'})

    try:
        from PIL import Image
        import io

        # 读取图片
        image = Image.open(file.stream)

        # 转换为RGB模式（处理RGBA、P模式等）
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        # 压缩图片到最大 300x300
        max_size = (300, 300)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # 生成文件名
        filename = f"avatar_{user['user_id']}_{int(datetime.now().timestamp())}.jpg"

        # 确保上传目录存在
        upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'avatars')
        os.makedirs(upload_dir, exist_ok=True)

        # 保存图片
        filepath = os.path.join(upload_dir, filename)
        image.save(filepath, 'JPEG', quality=85)

        # 更新用户头像路径
        avatar_url = f"/static/uploads/avatars/{filename}"

        # 查找并更新用户
        for u in api_client._users:
            if u.id == user['user_id']:
                u.avatar = avatar_url
                api_client._db.save_user(u)
                break

        return jsonify({
            'success': True,
            'message': '头像上传成功',
            'avatar_url': avatar_url
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'})


@app.route('/api/update-avatar', methods=['POST'])
@login_required
def api_update_avatar():
    """更新头像URL API（用于外部图片链接）"""
    user = get_current_user()
    data = request.json
    avatar_url = data.get('avatar_url', '').strip()

    if not avatar_url:
        return jsonify({'success': False, 'message': '头像URL不能为空'})

    # 查找并更新用户
    for u in api_client._users:
        if u.id == user['user_id']:
            u.avatar = avatar_url
            api_client._db.save_user(u)
            break

    return jsonify({
        'success': True,
        'message': '头像更新成功',
        'avatar_url': avatar_url
    })


@app.route('/api/update-signature', methods=['POST'])
@login_required
def api_update_signature():
    """更新个性签名API"""
    user = get_current_user()
    data = request.json
    signature = data.get('signature', '').strip()

    # 限制签名长度（最多100个字符）
    if len(signature) > 100:
        return jsonify({'success': False, 'message': '签名长度不能超过100个字符'})

    # 查找并更新用户
    full_user = None
    for u in api_client._users:
        if u.id == user['user_id']:
            u.signature = signature
            api_client._db.save_user(u)
            full_user = u
            break

    if full_user:
        return jsonify({
            'success': True,
            'message': '签名更新成功',
            'signature': signature
        })
    else:
        return jsonify({'success': False, 'message': '用户不存在'})


# ==================== 预约管理API ====================

@app.route('/api/reservations/create', methods=['POST'])
@login_required
def api_create_reservation():
    """创建预约API"""
    user = get_current_user()
    data = request.json
    
    device_id = data.get('device_id')
    device_type = data.get('device_type')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    reason = data.get('reason', '测试')
    
    if not device_id or not device_type:
        return jsonify({'success': False, 'message': '设备信息不完整'})
    
    if not start_time_str or not end_time_str:
        return jsonify({'success': False, 'message': '请选择预约时间'})
    
    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00').replace('+00:00', ''))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00').replace('+00:00', ''))
    except:
        return jsonify({'success': False, 'message': '时间格式错误'})
    
    success, result = api_client.create_reservation(
        device_id=device_id,
        device_type=device_type,
        reserver_id=user['user_id'],
        reserver_name=user['borrower_name'],
        start_time=start_time,
        end_time=end_time,
        reason=reason
    )
    
    if success:
        # 预约成功，发放积分奖励
        device = api_client.get_device_by_id(device_id)
        device_name = device.name if device else ''
        points_result = points_service.reserve_reward(user['user_id'], device_name)
        points_message = ''
        points_change = 0
        if points_result['success']:
            points_message = f'，{points_result["message"]}'
            points_change = points_result.get('points_change', 0)

        # 获取用户当前总积分
        total_points = get_user_total_points(user['user_id'])

        return jsonify({
            'success': True,
            'message': '预约成功' + points_message,
            'reservation': result.to_dict(),
            'points_added': points_change,
            'total_points': total_points
        })
    else:
        return jsonify({'success': False, 'message': result})


@app.route('/api/reservations/<reservation_id>/approve', methods=['POST'])
@login_required
def api_approve_reservation(reservation_id):
    """同意预约API"""
    user = get_current_user()
    data = request.json or {}
    approver_role = data.get('role', 'custodian')  # 'custodian' 或 'borrower'
    
    success, message = api_client.approve_reservation(
        reservation_id=reservation_id,
        approver_id=user['user_id'],
        approver_role=approver_role
    )
    
    return jsonify({'success': success, 'message': message})


@app.route('/api/reservations/<reservation_id>/reject', methods=['POST'])
@login_required
def api_reject_reservation(reservation_id):
    """拒绝预约API"""
    user = get_current_user()
    data = request.json or {}
    reason = data.get('reason', '')
    
    success, message = api_client.reject_reservation(
        reservation_id=reservation_id,
        rejected_by=user['borrower_name'],
        reason=reason
    )
    
    return jsonify({'success': success, 'message': message})


@app.route('/api/reservations/<reservation_id>/cancel', methods=['POST'])
@login_required
def api_cancel_reservation(reservation_id):
    """取消预约API"""
    user = get_current_user()
    data = request.json or {}
    reason = data.get('reason', '')
    
    success, message = api_client.cancel_reservation(
        reservation_id=reservation_id,
        cancelled_by=user['borrower_name'],
        reason=reason
    )
    
    return jsonify({'success': success, 'message': message})


@app.route('/api/reservations/<reservation_id>/delete', methods=['POST'])
@login_required
def api_delete_reservation(reservation_id):
    """删除预约API（仅已拒绝、已取消、已过期的可删除）"""
    user = get_current_user()
    
    success, message = api_client.delete_reservation(
        reservation_id=reservation_id,
        user_id=user['user_id']
    )
    
    return jsonify({'success': success, 'message': message})


@app.route('/api/reservations', methods=['GET'])
@login_required
def api_get_reservations():
    """获取我的预约列表API"""
    user = get_current_user()
    status = request.args.get('status')
    
    reservations = api_client.get_user_reservations(user['user_id'], status)
    
    return jsonify({
        'success': True,
        'reservations': [r.to_dict() for r in reservations]
    })


@app.route('/api/device/<device_id>/reservations', methods=['GET'])
@login_required
def api_get_device_reservations(device_id):
    """获取设备预约日历API"""
    device_type = request.args.get('device_type')
    
    # 获取设备信息
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'}), 404
    
    user = get_current_user()
    
    # 获取所有有效预约
    reservations = api_client.get_device_reservations(device_id, device_type, active_only=True)
    
    # 格式化预约数据
    reservation_list = []
    for r in reservations:
        reservation_list.append({
            'id': r.id,
            'reserver_name': r.reserver_name,
            'reserver_id': r.reserver_id,
            'start_time': r.start_time.strftime('%Y-%m-%d %H:%M:%S') if r.start_time else '',
            'end_time': r.end_time.strftime('%Y-%m-%d %H:%M:%S') if r.end_time else '',
            'status': r.status,
            'is_my_reservation': r.reserver_id == user['user_id']
        })
    
    # 当前借用信息
    current_borrow = None
    if device.status == DeviceStatus.BORROWED:
        current_borrow = {
            'borrower': device.borrower,
            'borrower_id': device.borrower_id,
            'start': device.borrow_time.strftime('%Y-%m-%d %H:%M:%S') if device.borrow_time else None,
            'end': device.expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.expected_return_date else None
        }
    
    return jsonify({
        'success': True,
        'reservations': reservation_list,
        'current_borrow': current_borrow
    })


@app.route('/api/device/<device_id>/pending-reservations')
@login_required
def api_get_device_pending_reservations(device_id):
    """获取设备待确认的预约（用于弹窗提示）"""
    user = get_current_user()
    device_type = request.args.get('device_type')
    
    # 获取设备信息
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'}), 404
    
    # 判断当前用户角色
    is_custodian = device.cabinet_number == user['borrower_name']
    is_borrower = device.borrower == user['borrower_name'] and device.status == DeviceStatus.BORROWED
    
    # 获取待确认的预约
    pending_reservations = []
    all_reservations = api_client.get_device_reservations(device_id, device_type)
    
    for r in all_reservations:
        # 保管人需要确认的预约
        if is_custodian and r.status in ['待保管人确认', '待2人确认'] and not r.custodian_approved:
            if r.custodian_id == user['user_id'] or (not r.custodian_id and device.cabinet_number == user['borrower_name']):
                pending_reservations.append({
                    'id': r.id,
                    'reserver_name': r.reserver_name,
                    'reserver_id': r.reserver_id,
                    'device_name': r.device_name,
                    'start_time': r.start_time.strftime('%Y-%m-%d %H:%M') if r.start_time else '',
                    'end_time': r.end_time.strftime('%Y-%m-%d %H:%M') if r.end_time else '',
                    'confirm_role': 'custodian'
                })
        
        # 借用人需要确认的预约
        if is_borrower and r.status in ['待借用人确认', '待2人确认'] and not r.borrower_approved:
            # 检查是否是当前借用人（通过ID或姓名匹配）
            is_current_borrower = (
                r.current_borrower_id == user['user_id'] or 
                (not r.current_borrower_id and device.borrower_id == user['user_id']) or
                r.current_borrower_name == user['borrower_name'] or
                device.borrower == user['borrower_name']
            )
            if is_current_borrower:
                pending_reservations.append({
                    'id': r.id,
                    'reserver_name': r.reserver_name,
                    'reserver_id': r.reserver_id,
                    'device_name': r.device_name,
                    'start_time': r.start_time.strftime('%Y-%m-%d %H:%M') if r.start_time else '',
                    'end_time': r.end_time.strftime('%Y-%m-%d %H:%M') if r.end_time else '',
                    'confirm_role': 'borrower'
                })
    
    return jsonify({
        'success': True,
        'reservations': pending_reservations
    })


@app.route('/api/my-pending-reservations')
@login_required
def api_get_my_pending_reservations():
    """获取所有需要当前用户确认的预约（用于首页弹窗）"""
    user = get_current_user()
    api_client.reload_data()
    
    pending_reservations = []
    
    # 获取所有设备
    all_devices = api_client.get_all_devices()
    
    for device in all_devices:
        # 检查用户是否是保管人
        is_custodian = device.cabinet_number == user['borrower_name']
        # 检查用户是否是借用人
        is_borrower = (device.borrower and user['borrower_name'] in device.borrower) and device.status == DeviceStatus.BORROWED
        
        if not is_custodian and not is_borrower:
            continue
        
        # 获取该设备的所有预约（包括待确认的）
        reservations = api_client.get_device_reservations(device.id, None, False)
        
        for r in reservations:
            # 保管人需要确认的预约
            if is_custodian and r.status in ['待保管人确认', '待2人确认'] and not r.custodian_approved:
                if r.custodian_id == user['user_id'] or (not r.custodian_id and device.cabinet_number == user['borrower_name']):
                    pending_reservations.append({
                        'id': r.id,
                        'reserver_name': r.reserver_name,
                        'reserver_id': r.reserver_id,
                        'device_id': device.id,
                        'device_name': device.name,
                        'device_type': get_device_type_str(device),
                        'start_time': r.start_time.strftime('%Y-%m-%d %H:%M') if r.start_time else '',
                        'end_time': r.end_time.strftime('%Y-%m-%d %H:%M') if r.end_time else '',
                        'confirm_role': 'custodian'
                    })
            
            # 借用人需要确认的预约
            if is_borrower and r.status in ['待借用人确认', '待2人确认'] and not r.borrower_approved:
                # 检查是否是当前借用人（通过ID或姓名匹配）
                is_current_borrower = (
                    r.current_borrower_id == user['user_id'] or 
                    r.current_borrower_name == user['borrower_name'] or
                    device.borrower == user['borrower_name']
                )
                if is_current_borrower:
                    pending_reservations.append({
                        'id': r.id,
                        'reserver_name': r.reserver_name,
                        'reserver_id': r.reserver_id,
                        'device_id': device.id,
                        'device_name': device.name,
                        'device_type': get_device_type_str(device),
                        'start_time': r.start_time.strftime('%Y-%m-%d %H:%M') if r.start_time else '',
                        'end_time': r.end_time.strftime('%Y-%m-%d %H:%M') if r.end_time else '',
                        'confirm_role': 'borrower'
                    })
    
    return jsonify({
        'success': True,
        'reservations': pending_reservations
    })


@app.route('/pc/my-reservations')
@login_required
def pc_my_reservations():
    """我的预约列表页面"""
    api_client.reload_data()
    user = get_current_user()
    
    # 获取用户的所有预约
    reservations = api_client.get_user_reservations(user['user_id'])
    
    # 获取设备统计数据
    stats = get_device_stats()
    
    return render_template('pc/my_reservations.html',
                         user=user,
                         reservations=reservations,
                         hide_search=True,
                         current_theme=get_current_theme_icon(user['user_id']),
                         **stats)


# ==================== 转借API（支持强制转借）====================

@app.route('/api/transfer', methods=['POST'])
@login_required
def api_transfer():
    """转借设备API（支持强制转借）"""
    user = get_current_user()
    data = request.json
    
    # 重新加载数据以获取最新状态
    api_client.reload_data()
    
    device_id = data.get('device_id')
    device_type = data.get('device_type')
    transfer_to = data.get('transfer_to')
    remark = data.get('remark', '')
    force = data.get('force', False)  # 是否强制转借
    
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    # 检查是否是当前借用人或保管人
    is_borrower = device.borrower == user['borrower_name']
    is_custodian = device.cabinet_number == user['borrower_name']
    
    if not is_borrower and not is_custodian:
        return jsonify({'success': False, 'message': '您不是该设备的当前借用人或保管人'})
    
    # 借用人只能在借出状态转借
    if is_borrower and device.status != DeviceStatus.BORROWED:
        return jsonify({'success': False, 'message': '设备状态异常'})
    
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
    
    # 检查不能转借给自己
    if transfer_to == user['borrower_name']:
        return jsonify({'success': False, 'message': '不能转借给自己'})
    
    # 检查转借对象借用数量限制
    user_borrowed_count = 0
    all_devices = api_client.get_all_devices()
    for d in all_devices:
        if d.borrower == transfer_to and d.status == DeviceStatus.BORROWED:
            user_borrowed_count += 1
    
    borrow_limit = 10
    if user_borrowed_count >= borrow_limit:
        return jsonify({'success': False, 'message': f'{transfer_to}已借用 {user_borrowed_count} 台设备，达到上限 ({borrow_limit}台)，无法接收设备'})
    
    # 检查预约冲突
    if not force:
        conflict_check = api_client.check_transfer_conflict(device_id)
        if conflict_check['has_conflict']:
            r = conflict_check['reservations'][0]
            return jsonify({
                'success': False,
                'code': 'RESERVATION_CONFLICT',
                'message': f'该设备已被 {r.reserver_name} 预约借用',
                'conflict_info': {
                    'reserver_name': r.reserver_name,
                    'reserver_id': r.reserver_id,
                    'start_time': r.start_time.strftime('%Y-%m-%d %H:%M'),
                    'end_time': r.end_time.strftime('%Y-%m-%d %H:%M'),
                    'reservation_id': r.id
                }
            }), 409
    
    # 强制转借：取消相关预约
    if force:
        cancelled_count = api_client.cancel_reservations_due_to_transfer(
            device_id=device_id,
            transfer_to=transfer_to,
            cancelled_by=user['borrower_name']
        )
    
    # 保存原借用人信息
    original_borrower = device.borrower
    
    # 更新设备信息
    device.borrower = transfer_to
    device.phone = ''  # 转借时清空手机号，由接收人自行填写
    device.previous_borrower = original_borrower
    device.status = DeviceStatus.BORROWED
    device.lost_time = None  # 清除丢失时间
    device.entry_source = EntrySource.USER.value
    device.expected_return_date = datetime.now() + timedelta(days=1)  # 转借后预计归还时间刷新为当前时间+1天
    
    api_client.update_device(device, source="user")
    
    # 添加记录
    record = Record(
        id=str(uuid.uuid4()),
        device_id=device.id,
        device_name=device.name,
        device_type=get_device_type_str(device),
        operation_type=OperationType.TRANSFER,
        operator=user['borrower_name'],
        operation_time=datetime.now(),
        borrower=f"被转借：{original_borrower or '保管人'}——>{transfer_to}",
        phone='',
        reason=remark or '用户转借',
        entry_source=EntrySource.USER.value
    )
    api_client._db.save_record(record)
    
    # 给转借对象增加借用次数
    for u in api_client._users:
        if u.borrower_name == transfer_to:
            u.borrow_count += 1
            api_client._db.save_user(u)
            break
    
    api_client.add_operation_log(f"转借设备 {original_borrower or '保管人'} -> {transfer_to}", device.name, operator=user['borrower_name'], source="user")
    
    # 通知转借对象
    api_client.add_notification(
        user_id=target_user.id,
        user_name=target_user.borrower_name,
        title="设备转借通知",
        content=f"设备「{device.name}」已被 {user['borrower_name']} 转借给您",
        device_name=device.name,
        device_id=device.id,
        notification_type="info"
    )
    
    # 通知原借用人（如果存在且不是当前用户）
    if original_borrower and original_borrower != user['borrower_name']:
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
                content=f"您借用的设备「{device.name}」已被 {user['borrower_name']} 转借给 {transfer_to}",
                device_name=device.name,
                device_id=device.id,
                notification_type="warning"
            )
    
    # 通知保管人（如果存在且不是相关人）
    if device.cabinet_number and device.cabinet_number != original_borrower and device.cabinet_number != user['borrower_name']:
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
                content=f"您保管的设备「{device.name}」已被 {user['borrower_name']} 从 {original_borrower or '保管人'} 转借给 {transfer_to}",
                device_name=device.name,
                device_id=device.id,
                notification_type="info"
            )
    
    message = '转借成功'
    if force:
        message = '强制转借成功，已取消相关预约'

    # 转借成功，发放积分奖励
    points_result = points_service.transfer_reward(user['user_id'], device.name)
    points_change = 0
    if points_result['success']:
        message += f'，{points_result["message"]}'
        points_change = points_result.get('points_change', 0)

    # 获取用户当前总积分
    total_points = get_user_total_points(user['user_id'])

    return jsonify({
        'success': True,
        'message': message,
        'points_added': points_change,
        'total_points': total_points
    })


# ==================== 定时任务 ====================

def process_reservations_job():
    """定时任务：处理预约（每分钟执行）"""
    try:
        with app.app_context():
            api_client.process_reservations_schedule()
    except Exception as e:
        print(f"定时任务执行失败: {e}")


def send_overdue_reminder_job():
    """定时任务：发送逾期3天提醒邮件（每天执行）"""
    try:
        with app.app_context():
            api_client.send_overdue_email_reminders()
    except Exception as e:
        print(f"发送逾期提醒邮件失败: {e}")


def send_reservation_pending_reminder_job():
    """定时任务：发送预约待确认提醒邮件（每小时执行）"""
    try:
        with app.app_context():
            api_client.send_reservation_pending_email_reminders()
    except Exception as e:
        print(f"发送预约待确认提醒邮件失败: {e}")


def auto_deduct_overdue_points_job():
    """定时任务：自动扣除逾期设备积分（每小时执行）"""
    try:
        with app.app_context():
            from datetime import datetime
            from common.models import DeviceStatus

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查逾期设备并扣除积分...")

            # 获取所有借用中的设备
            all_devices = api_client._db.get_all_devices()
            borrowed_devices = [d for d in all_devices if d.status == DeviceStatus.BORROWED and d.borrower and d.expected_return_date]

            deducted_count = 0
            for device in borrowed_devices:
                # 检查是否逾期
                now = datetime.now()
                if now > device.expected_return_date:
                    time_diff = now - device.expected_return_date
                    # 逾期超过1分钟才算逾期
                    if time_diff.total_seconds() > 60:
                        # 查找借用人
                        borrower_user = None
                        for u in api_client._users:
                            if u.borrower_name == device.borrower:
                                borrower_user = u
                                break

                        if borrower_user:
                            # 检查今天是否已经扣除过该设备的逾期积分
                            today = now.strftime('%Y-%m-%d')
                            records = api_client._db.get_points_records(borrower_user.id)
                            already_deducted_today = False

                            for record in records:
                                if record.transaction_type == PointsTransactionType.OVERDUE:
                                    # 检查是否是今天扣除的，并且是否是同一设备
                                    if record.create_time and record.create_time.strftime('%Y-%m-%d') == today:
                                        if record.related_id == device.id:
                                            already_deducted_today = True
                                            break

                            if not already_deducted_today:
                                # 扣除逾期积分
                                points_result = points_service.overdue_penalty(borrower_user.id, device.name, device.id)
                                if points_result['success']:
                                    deducted_count += 1
                                    print(f"  ✓ 已扣除 {borrower_user.borrower_name} 的逾期积分 -15分 (设备: {device.name})")

                                    # 发送通知给借用人
                                    api_client.add_notification(
                                        user_id=borrower_user.id,
                                        user_name=borrower_user.borrower_name,
                                        title="逾期积分扣除通知",
                                        content=f"您借用的设备「{device.name}」已逾期，已自动扣除15积分",
                                        device_name=device.name,
                                        device_id=device.id,
                                        notification_type="error"
                                    )

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 逾期积分扣除完成，共处理 {deducted_count} 个设备")

    except Exception as e:
        print(f"自动扣除逾期积分失败: {e}")
        import traceback
        traceback.print_exc()


# 初始化定时任务
scheduler = None
if APSCHEDULER_AVAILABLE:
    scheduler = BackgroundScheduler()
    # 添加任务前先移除已存在的同名任务（防止重复添加）
    try:
        scheduler.remove_job('process_reservations')
    except:
        pass
    try:
        scheduler.remove_job('send_overdue_reminders')
    except:
        pass
    try:
        scheduler.remove_job('send_reservation_pending_reminders')
    except:
        pass
    try:
        scheduler.remove_job('auto_deduct_overdue_points')
    except:
        pass

    # 每分钟执行一次预约处理
    scheduler.add_job(process_reservations_job, 'interval', minutes=1, id='process_reservations')
    # 每5分钟检查并发送逾期提醒邮件（需要精确到10分钟的提醒）
    scheduler.add_job(send_overdue_reminder_job, 'interval', minutes=5, id='send_overdue_reminders')
    # 每30分钟检查并发送预约待确认提醒邮件
    scheduler.add_job(send_reservation_pending_reminder_job, 'interval', minutes=30, id='send_reservation_pending_reminders')
    # 每小时检查并自动扣除逾期积分
    scheduler.add_job(auto_deduct_overdue_points_job, 'interval', minutes=60, id='auto_deduct_overdue_points')
    scheduler.start()
    print("✓ 定时任务已启动：每分钟处理预约、每5分钟检查逾期提醒、每30分钟检查预约确认提醒、每小时自动扣除逾期积分")


@app.route('/api/stats/borrow-return', methods=['GET'])
@login_required
def api_borrow_return_stats():
    """获取借出归还统计数据API - 用于折线图展示"""
    try:
        range_type = request.args.get('range', 'day')  # day, month, year
        
        # 获取所有记录
        all_records = api_client.get_records()
        
        # 根据时间范围确定日期格式和天数
        if range_type == 'day':
            # 按小时统计今日数据
            labels = [f'{h:02d}:00' for h in range(24)]
            borrow_data = [0] * 24
            return_data = [0] * 24
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            for record in all_records:
                try:
                    record_date = record.operation_time.strftime('%Y-%m-%d')
                    if record_date == today:
                        hour = record.operation_time.hour
                        op_type = record.operation_type
                        # 处理枚举类型或字符串类型
                        op_value = op_type.value if hasattr(op_type, 'value') else str(op_type)
                        if op_value in ['借出', '强制借出']:
                            borrow_data[hour] += 1
                        elif op_value in ['归还', '强制归还']:
                            return_data[hour] += 1
                except Exception as rec_err:
                    print(f'处理记录时出错: {rec_err}')
                    continue
            
            return jsonify({
                'success': True,
                'labels': labels,
                'borrow': borrow_data,
                'return': return_data
            })
        
        elif range_type == 'month':
            # 按天统计本月数据
            now = datetime.now()
            year = now.year
            month = now.month
            
            # 获取当月天数
            _, days_in_month = calendar.monthrange(year, month)
            
            labels = [f'{i+1}日' for i in range(days_in_month)]
            borrow_data = [0] * days_in_month
            return_data = [0] * days_in_month
            
            for record in all_records:
                try:
                    record_time = record.operation_time
                    if record_time.year == year and record_time.month == month:
                        day = record_time.day - 1  # 转换为0-based索引
                        op_type = record.operation_type
                        op_value = op_type.value if hasattr(op_type, 'value') else str(op_type)
                        if op_value in ['借出', '强制借出']:
                            borrow_data[day] += 1
                        elif op_value in ['归还', '强制归还']:
                            return_data[day] += 1
                except Exception as rec_err:
                    print(f'处理记录时出错: {rec_err}')
                    continue
            
            return jsonify({
                'success': True,
                'labels': labels,
                'borrow': borrow_data,
                'return': return_data
            })
        
        elif range_type == 'year':
            # 按月份统计本年数据
            now = datetime.now()
            year = now.year
            
            labels = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
            borrow_data = [0] * 12
            return_data = [0] * 12
            
            for record in all_records:
                try:
                    record_time = record.operation_time
                    if record_time.year == year:
                        month = record_time.month - 1  # 转换为0-based索引
                        op_type = record.operation_type
                        op_value = op_type.value if hasattr(op_type, 'value') else str(op_type)
                        if op_value in ['借出', '强制借出']:
                            borrow_data[month] += 1
                        elif op_value in ['归还', '强制归还']:
                            return_data[month] += 1
                except Exception as rec_err:
                    print(f'处理记录时出错: {rec_err}')
                    continue
            
            return jsonify({
                'success': True,
                'labels': labels,
                'borrow': borrow_data,
                'return': return_data
            })
        
        else:
            return jsonify({'success': False, 'message': '无效的时间范围参数'}), 400
            
    except Exception as e:
        import traceback
        print(f'获取借出归还统计数据失败: {e}')
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': f'获取统计数据失败: {str(e)}'}), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message='页面未找到'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message='服务器内部错误'), 500


# ========== 设备图片和附件API ==========

# 上传目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, 'images')
ATTACHMENT_FOLDER = os.path.join(UPLOAD_FOLDER, 'attachments')

# 确保上传目录存在
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(ATTACHMENT_FOLDER, exist_ok=True)

# 存储图片和附件数据（使用JSON文件存储）
DEVICE_MEDIA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'device_media.json')
os.makedirs(os.path.dirname(DEVICE_MEDIA_FILE), exist_ok=True)

def load_device_media():
    """加载设备媒体数据"""
    if os.path.exists(DEVICE_MEDIA_FILE):
        try:
            with open(DEVICE_MEDIA_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except (json.JSONDecodeError, IOError):
            pass
    return {'images': {}, 'attachments': {}}

def save_device_media(data):
    """保存设备媒体数据"""
    with open(DEVICE_MEDIA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_device_images(device_id):
    """获取设备的图片列表"""
    media = load_device_media()
    images = media.get('images', {}).get(device_id, [])
    # 按上传时间倒序排列
    images.sort(key=lambda x: x.get('upload_time', ''), reverse=True)
    return images

def get_device_attachments(device_id):
    """获取设备的附件列表"""
    media = load_device_media()
    attachments = media.get('attachments', {}).get(device_id, [])
    # 按上传时间倒序排列
    attachments.sort(key=lambda x: x.get('upload_time', ''), reverse=True)
    return attachments

@app.route('/api/device/images/upload', methods=['POST'])
@login_required
def api_upload_device_images():
    """上传设备图片"""
    user = get_current_user()
    device_id = request.form.get('device_id')
    device_type = request.form.get('device_type')
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    # 检查设备是否存在
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    files = request.files.getlist('images')
    if not files:
        return jsonify({'success': False, 'message': '请选择要上传的图片'})
    
    max_size = 200 * 1024 * 1024  # 200MB
    uploaded = []
    media = load_device_media()
    
    if 'images' not in media:
        media['images'] = {}
    if device_id not in media['images']:
        media['images'][device_id] = []
    
    for file in files:
        if file.filename == '':
            continue
        
        # 检查文件大小
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        if size > max_size:
            continue
        
        # 生成唯一文件名
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            ext = '.jpg'
        
        filename = f"{uuid.uuid4().hex}{ext}"
        device_folder = os.path.join(IMAGE_FOLDER, device_id)
        os.makedirs(device_folder, exist_ok=True)
        filepath = os.path.join(device_folder, filename)
        
        # 保存文件
        file.save(filepath)
        
        # 构建URL
        url = f'/uploads/images/{device_id}/{filename}'
        
        # 保存记录
        image_data = {
            'id': str(uuid.uuid4()),
            'device_id': device_id,
            'device_type': device_type,
            'filename': file.filename,
            'url': url,
            'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'uploader': user['borrower_name']
        }
        media['images'][device_id].append(image_data)
        uploaded.append(image_data)
    
    save_device_media(media)
    
    return jsonify({
        'success': True,
        'message': f'成功上传 {len(uploaded)} 张图片',
        'images': uploaded
    })

@app.route('/api/device/images/<image_id>/delete', methods=['POST'])
@login_required
def api_delete_device_image(image_id):
    """删除设备图片"""
    user = get_current_user()
    data = request.json or {}
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    media = load_device_media()
    images = media.get('images', {}).get(device_id, [])
    
    # 查找图片
    image = None
    for img in images:
        if img['id'] == image_id:
            image = img
            break
    
    if not image:
        return jsonify({'success': False, 'message': '图片不存在'})
    
    # 检查权限（只有上传者或管理员可以删除）
    if image.get('uploader') != user['borrower_name'] and not user.get('is_admin'):
        return jsonify({'success': False, 'message': '您没有权限删除此图片'})
    
    # 删除文件
    try:
        filepath = os.path.join(UPLOAD_FOLDER, '..', image['url'].lstrip('/'))
        filepath = os.path.abspath(filepath)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"删除图片文件失败: {e}")
    
    # 从记录中移除
    media['images'][device_id] = [img for img in images if img['id'] != image_id]
    save_device_media(media)
    
    return jsonify({'success': True, 'message': '删除成功'})

@app.route('/api/device/attachments/upload', methods=['POST'])
@login_required
def api_upload_device_attachments():
    """上传设备附件"""
    user = get_current_user()
    device_id = request.form.get('device_id')
    device_type = request.form.get('device_type')
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    # 检查设备是否存在
    device = api_client.get_device_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'message': '设备不存在'})
    
    files = request.files.getlist('attachments')
    if not files:
        return jsonify({'success': False, 'message': '请选择要上传的附件'})
    
    max_size = 200 * 1024 * 1024  # 200MB
    uploaded = []
    media = load_device_media()
    
    if 'attachments' not in media:
        media['attachments'] = {}
    if device_id not in media['attachments']:
        media['attachments'][device_id] = []
    
    for file in files:
        if file.filename == '':
            continue
        
        # 检查文件大小
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        if size > max_size:
            continue
        
        # 生成唯一文件名
        ext = os.path.splitext(file.filename)[1].lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        device_folder = os.path.join(ATTACHMENT_FOLDER, device_id)
        os.makedirs(device_folder, exist_ok=True)
        filepath = os.path.join(device_folder, filename)
        
        # 保存文件
        file.save(filepath)
        
        # 构建URL
        url = f'/uploads/attachments/{device_id}/{filename}'
        
        # 保存记录
        attachment_data = {
            'id': str(uuid.uuid4()),
            'device_id': device_id,
            'device_type': device_type,
            'filename': file.filename,
            'url': url,
            'size': size,
            'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'uploader': user['borrower_name']
        }
        media['attachments'][device_id].append(attachment_data)
        uploaded.append(attachment_data)
    
    save_device_media(media)
    
    return jsonify({
        'success': True,
        'message': f'成功上传 {len(uploaded)} 个附件',
        'attachments': uploaded
    })

@app.route('/api/device/attachments/<attachment_id>/delete', methods=['POST'])
@login_required
def api_delete_device_attachment(attachment_id):
    """删除设备附件"""
    user = get_current_user()
    data = request.json or {}
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    media = load_device_media()
    attachments = media.get('attachments', {}).get(device_id, [])
    
    # 查找附件
    attachment = None
    for att in attachments:
        if att['id'] == attachment_id:
            attachment = att
            break
    
    if not attachment:
        return jsonify({'success': False, 'message': '附件不存在'})
    
    # 检查权限（只有上传者或管理员可以删除）
    if attachment.get('uploader') != user['borrower_name'] and not user.get('is_admin'):
        return jsonify({'success': False, 'message': '您没有权限删除此附件'})
    
    # 删除文件
    try:
        filepath = os.path.join(UPLOAD_FOLDER, '..', attachment['url'].lstrip('/'))
        filepath = os.path.abspath(filepath)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"删除附件文件失败: {e}")
    
    # 从记录中移除
    media['attachments'][device_id] = [att for att in attachments if att['id'] != attachment_id]
    save_device_media(media)
    
    return jsonify({'success': True, 'message': '删除成功'})

@app.route('/api/device/attachments/batch-download', methods=['POST'])
@login_required
def api_batch_download_attachments():
    """批量下载附件（打包成ZIP）"""
    import zipfile
    import io
    
    data = request.json or {}
    device_id = data.get('device_id')
    attachment_ids = data.get('attachment_ids', [])
    
    if not device_id or not attachment_ids:
        return jsonify({'success': False, 'message': '参数错误'}), 400
    
    media = load_device_media()
    attachments = media.get('attachments', {}).get(device_id, [])
    
    # 筛选要下载的附件
    selected_attachments = []
    for att in attachments:
        if att['id'] in attachment_ids:
            selected_attachments.append(att)
    
    if not selected_attachments:
        return jsonify({'success': False, 'message': '未找到要下载的附件'}), 404
    
    # 创建ZIP文件
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for att in selected_attachments:
            filepath = os.path.join(UPLOAD_FOLDER, '..', att['url'].lstrip('/'))
            filepath = os.path.abspath(filepath)
            if os.path.exists(filepath):
                zf.write(filepath, att['filename'])
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'attachments_{device_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    )

# 静态文件服务 - 上传的文件
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """提供上传的文件访问"""
    return send_from_directory(UPLOAD_FOLDER, filename)


# ========== 每日转盘 API ==========

@app.route('/api/wheel/status', methods=['GET'])
@login_required
def api_wheel_status():
    """获取转盘状态"""
    from common.wheel_service import wheel_service
    user_id = session.get('user_id')
    status = wheel_service.get_wheel_status(user_id)
    return jsonify({'success': True, **status})


@app.route('/api/wheel/spin', methods=['POST'])
@login_required
def api_wheel_spin():
    """执行转盘抽奖"""
    from common.wheel_service import wheel_service
    user_id = session.get('user_id')
    result = wheel_service.spin(user_id)
    return jsonify(result)


@app.route('/api/wheel/records', methods=['GET'])
@login_required
def api_wheel_records():
    """获取用户抽奖记录"""
    from common.wheel_service import wheel_service
    user_id = session.get('user_id')
    records = wheel_service.db.get_wheel_records_by_user(user_id, limit=50)
    return jsonify({'success': True, 'records': records})


@app.route('/api/wheel/hidden-titles', methods=['GET'])
@login_required
def api_wheel_hidden_titles():
    """获取用户获得的隐藏称号"""
    from common.wheel_service import wheel_service
    user_id = session.get('user_id')
    titles = wheel_service.get_user_hidden_titles(user_id)
    return jsonify({'success': True, 'titles': titles})


if __name__ == '__main__':
    print(f"用户服务启动在端口 {USER_SERVICE_PORT}")
    try:
        # threaded=True 启用多线程支持高并发
        app.run(debug=False, host='0.0.0.0', port=USER_SERVICE_PORT, threaded=True)
    finally:
        # 关闭定时任务
        if scheduler:
            scheduler.shutdown()
            print("定时任务已关闭")

