# -*- coding: utf-8 -*-
"""
数据客户端
从SQLite数据库读取和保存数据
"""
import uuid
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, ViewRecord, Notification, Announcement, UserLike, Reservation, AdminOperationLog
from .models import DeviceStatus, DeviceType, OperationType, EntrySource, Admin, ReservationStatus
from .db_store import DatabaseStore, get_db_transaction
from .email_sender import email_sender

# 创建邮件发送线程池
email_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="email_sender")

# 创建全局 DatabaseStore 实例
_db_store = DatabaseStore()


class APIClient:
    """API 客户端单例类"""
    _instance = None
    _initialized = False

    # 类属性 - 始终存在
    _current_admin: str = "管理员"

    # 排行榜缓存
    _rankings_cache: Dict[str, Any] = {
        'borrow': None,
        'return': None,
        'points': None,
        'last_update': None
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not APIClient._initialized:
            self._current_admin = "管理员"
            self._db = _db_store
            APIClient._initialized = True

    def _should_update_rankings_cache(self) -> bool:
        """检查是否需要更新排行榜缓存（每天0点后更新）"""
        if self._rankings_cache['last_update'] is None:
            return True

        now = datetime.now()
        last_update = self._rankings_cache['last_update']

        # 如果上次更新是昨天或更早，需要更新（到了新的一天）
        if now.date() > last_update.date():
            return True

        return False

    def _update_rankings_cache(self):
        """更新排行榜缓存"""
        self._rankings_cache['borrow'] = self._calculate_rankings('borrow')
        self._rankings_cache['return'] = self._calculate_rankings('return')
        self._rankings_cache['points'] = self._calculate_points_rankings()
        self._rankings_cache['last_update'] = datetime.now()

        # 发放排行榜前十积分奖励
        self._distribute_ranking_rewards()

    def _calculate_rankings(self, ranking_type: str = 'borrow') -> List[dict]:
        """计算排行榜数据（内部方法）"""
        valid_users = [u for u in self._db.get_all_users() if not u.is_frozen and not u.is_deleted]

        if ranking_type == 'borrow':
            sorted_users = sorted(valid_users, key=lambda x: x.borrow_count, reverse=True)
            titles = self.BORROW_TITLES
        else:
            sorted_users = sorted(valid_users, key=lambda x: x.return_count, reverse=True)
            titles = self.RETURN_TITLES

        rankings = []
        for i, user in enumerate(sorted_users):
            rank = i + 1
            count = user.borrow_count if ranking_type == 'borrow' else user.return_count

            if rank <= 10:
                title = titles[i] if i < len(titles) else titles[-1]
            else:
                title = None

            star_level = self.get_star_level(count)
            like_count = self.get_user_like_count(user.id)

            rankings.append({
                'rank': rank,
                'user_id': user.id,
                'user_name': user.borrower_name,
                'avatar': user.avatar,
                'signature': user.signature,
                'count': count,
                'title': title,
                'star_level': star_level,
                'like_count': like_count
            })

        return rankings

    def _calculate_points_rankings(self) -> List[dict]:
        """计算积分排行榜数据"""
        from .points_service import points_service

        # 获取积分排行数据（使用 points_service 的逻辑）
        rankings = points_service.get_points_rankings(limit=100)

        # 添加点赞数
        for ranking in rankings:
            ranking['like_count'] = self.get_user_like_count(ranking['user_id'])

        return rankings

    def _distribute_ranking_rewards(self):
        """发放排行榜前十积分奖励"""
        from .points_service import points_service
        from .models import PointsTransactionType
        
        # 获取借用和归还排行榜
        borrow_rankings = self._rankings_cache.get('borrow', [])
        return_rankings = self._rankings_cache.get('return', [])
        
        # 发放借用排行榜奖励
        for ranking in borrow_rankings[:10]:
            user_id = ranking['user_id']
            rank = ranking['rank']
            
            # 检查今天是否已经发放过该排行榜奖励
            today = datetime.now().strftime('%Y-%m-%d')
            records = self._db.get_points_records(user_id)
            already_rewarded = False
            
            for record in records:
                if record.transaction_type == PointsTransactionType.RANKING_REWARD:
                    if record.create_time:
                        record_date = record.create_time.strftime('%Y-%m-%d') if isinstance(record.create_time, datetime) else str(record.create_time)[:10]
                        if record_date == today and '借用' in record.description:
                            already_rewarded = True
                            break
            
            if not already_rewarded:
                points_service.ranking_reward(user_id, rank, '借用排行')
        
        # 发放归还排行榜奖励
        for ranking in return_rankings[:10]:
            user_id = ranking['user_id']
            rank = ranking['rank']
            
            # 检查今天是否已经发放过该排行榜奖励
            today = datetime.now().strftime('%Y-%m-%d')
            records = self._db.get_points_records(user_id)
            already_rewarded = False
            
            for record in records:
                if record.transaction_type == PointsTransactionType.RANKING_REWARD:
                    if record.create_time:
                        record_date = record.create_time.strftime('%Y-%m-%d') if isinstance(record.create_time, datetime) else str(record.create_time)[:10]
                        if record_date == today and '归还' in record.description:
                            already_rewarded = True
                            break
            
            if not already_rewarded:
                points_service.ranking_reward(user_id, rank, '归还排行')

    @property
    def _users(self):
        """兼容属性：返回所有用户列表"""
        return self._db.get_all_users()

    @_users.setter
    def _users(self, value):
        """兼容属性：设置用户列表（不执行任何操作，仅保持兼容）"""
        pass

    @property
    def _car_machines(self):
        """兼容属性：返回所有车机设备"""
        return self._db.get_all_devices(device_type='车机')

    @property
    def _instruments(self):
        """兼容属性：返回所有仪表设备"""
        return self._db.get_all_devices(device_type='仪表')

    @property
    def _phones(self):
        """兼容属性：返回所有手机设备"""
        return self._db.get_all_devices(device_type='手机')

    @property
    def _sim_cards(self):
        """兼容属性：返回所有手机卡设备"""
        return self._db.get_all_devices(device_type='手机卡')

    @property
    def _other_devices(self):
        """兼容属性：返回所有其它设备"""
        return self._db.get_all_devices(device_type='其它设备')

    @property
    def _records(self):
        """兼容属性：返回所有记录"""
        return self._db.get_all_records()

    @property
    def _remarks(self):
        """兼容属性：返回所有备注"""
        return self._db.get_remarks()

    @property
    def _operation_logs(self):
        """兼容属性：返回所有操作日志"""
        return []

    @property
    def _view_records(self):
        """兼容属性：返回所有查看记录"""
        return []

    @property
    def _admins(self):
        """兼容属性：返回所有管理员"""
        return []

    @property
    def _notifications(self):
        """兼容属性：返回所有通知"""
        return self._db.get_notifications_by_user('')

    @property
    def _announcements(self):
        """兼容属性：返回所有公告"""
        return self._db.get_all_announcements()

    @property
    def _user_likes(self):
        """兼容属性：返回所有用户点赞"""
        return []

    def _safe_print(self, message):
        """安全打印，处理Windows控制台编码问题"""
        try:
            print(message)
        except OSError:
            pass

    def _get_device_type_str(self, device: Device) -> str:
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
        return device.device_type.value if hasattr(device, 'device_type') else "未知"

    def _get_default_status_for_device(self, device) -> DeviceStatus:
        """根据设备类型获取默认状态（在库/保管中）"""
        if device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]:
            return DeviceStatus.IN_CUSTODY
        return DeviceStatus.IN_STOCK

    def _is_available_for_borrow(self, device) -> bool:
        """检查设备是否可借用（在库或保管中）"""
        return device.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]

    # ==================== 认证相关 ====================
    
    def verify_admin(self, username: str, password: str) -> bool:
        """验证管理员账号密码"""
        # 1. 检查传统管理员表
        admin = self._db.get_admin_by_username(username)
        if admin and admin.password == password:
            return True
        
        # 2. 检查被指定为管理员的用户（通过借用人名称或邮箱登录）
        user = self._db.get_user_by_email(username)
        if user and user.is_admin and not user.is_frozen and user.password == password:
            return True
        
        # 3. 尝试用借用人名称查找
        for user in self._db.get_all_users():
            if user.borrower_name == username and user.is_admin and not user.is_frozen and user.password == password:
                return True
        
        return False
    
    def is_user_admin(self, borrower_name: str) -> bool:
        """检查指定用户是否为管理员"""
        # 特殊管理员用户名（后台登录的管理员）
        if borrower_name in ['管理员', 'admin']:
            return True
        # 检查用户是否为管理员
        for user in self._db.get_all_users():
            if user.borrower_name == borrower_name and user.is_admin:
                return True
        return False
    
    def set_current_admin(self, admin_name: str):
        """设置当前管理员"""
        self._current_admin = admin_name
    
    def get_current_admin(self) -> str:
        """获取当前管理员"""
        return self._current_admin
    
    def verify_user_login(self, email: str, password: str) -> Optional[User]:
        """验证用户登录"""
        user = self._db.get_user_by_email(email)
        if user and user.password == password:
            if user.is_frozen:
                return None  # 账号已冻结
            return user
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return self._db.get_user_by_email(email)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self._db.get_user_by_id(user_id)

    def get_user_by_borrower_name(self, borrower_name: str) -> Optional[User]:
        """根据借用人名称获取用户"""
        for user in self._db.get_all_users():
            if user.borrower_name == borrower_name:
                return user
        return None

    def update_user_borrower_name(self, user_id: str, borrower_name: str) -> bool:
        """更新用户借用人名称"""
        # 检查借用人名称是否已存在
        for user in self._db.get_all_users():
            if user.borrower_name == borrower_name and user.id != user_id:
                return False  # 名称已存在
        
        user = self._db.get_user_by_id(user_id)
        if user:
            user.borrower_name = borrower_name
            self._db.save_user(user)
            return True
        return False
    
    def register_user(self, email: str, password: str, borrower_name: str) -> tuple[bool, str]:
        """注册用户
        
        Returns:
            (成功, 错误信息) 或 (成功, 用户)
        """
        # 检查邮箱是否已存在
        existing_user = self._db.get_user_by_email(email)
        if existing_user:
            return False, "邮箱已被注册"
        
        # 检查用户名是否已存在
        for user in self._db.get_all_users():
            if user.borrower_name == borrower_name:
                return False, "用户名已被使用"
        
        # 创建新用户
        new_user = User(
            id=str(uuid.uuid4()),
            email=email,
            password=password,
            borrower_name=borrower_name,
            borrow_count=0,
            is_frozen=False,
            is_first_login=True,
            create_time=datetime.now()
        )
        
        self._db.save_user(new_user)
        return True, "注册成功"
    
    # ==================== 设备管理 ====================
    
    def get_all_devices(self, device_type: Optional[str] = None) -> List[Device]:
        """获取所有设备，按创建时间倒序排列（最新的在前面）"""
        devices = self._db.get_all_devices(device_type=device_type)
        # 按创建时间倒序排列，最新的设备排在最前面
        return sorted(devices, key=lambda d: d.create_time if d.create_time else datetime.min, reverse=True)
    
    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """根据ID获取设备"""
        return self._db.get_device_by_id(device_id)
    
    def get_device_by_name(self, device_name: str) -> Optional[Device]:
        """根据名称获取设备"""
        all_devices = self._db.get_all_devices()
        for device in all_devices:
            if device.name == device_name:
                return device
        return None
    
    def add_device(self, device: Device) -> bool:
        """新增设备"""
        # 检查设备名是否唯一
        all_devices = self._db.get_all_devices()
        for d in all_devices:
            if d.name == device.name:
                return False
        
        self._db.save_device(device)
        
        # 添加操作日志
        self.add_operation_log(f"新增设备", device.name)
        return True
    
    def update_device(self, device: Device, source: str = "admin") -> bool:
        """更新设备信息

        Args:
            device: 设备对象
            source: 操作来源，admin-管理员操作，user-用户端操作
        """
        existing = self._db.get_device_by_id(device.id)
        if existing:
            self._db.save_device(device)
            self.add_operation_log(f"更新设备信息", device.name, source=source)
            return True
        return False
    
    def delete_device(self, device_id: str) -> bool:
        """软删除设备"""
        device = self._db.get_device_by_id(device_id)
        if device:
            # 取消所有有效预约
            device_type = self._get_device_type_str(device)
            self._cancel_reservations_on_device_delete(device_id, device_type, device.name)
            
            device.is_deleted = True
            self._db.save_device(device)
            self.add_operation_log(f"删除设备", device.name)
            return True
        return False
    
    def _cancel_reservations_on_device_delete(self, device_id: str, device_type: str, device_name: str):
        """设备删除时取消所有有效预约"""
        reservations = self._db.get_reservations_by_device(device_id, device_type)
        now = datetime.now()
        
        for reservation in reservations:
            # 只处理未完成的预约
            if reservation.status in [
                ReservationStatus.PENDING_CUSTODIAN.value,
                ReservationStatus.PENDING_BORROWER.value,
                ReservationStatus.PENDING_BOTH.value,
                ReservationStatus.APPROVED.value
            ]:
                # 更新预约状态为已取消
                reservation.status = ReservationStatus.CANCELLED.value
                reservation.cancel_time = now
                reservation.cancel_reason = "设备已被删除"
                self._db.save_reservation(reservation)
                
                # 通知预约人
                self._notify_reservation_cancelled_due_to_device_delete(reservation, device_name)
    
    def _notify_reservation_cancelled_due_to_device_delete(self, reservation: Reservation, device_name: str):
        """通知预约人设备删除导致预约取消"""
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约已取消",
            content=f"您预约的设备「{device_name}」已被删除，预约已自动取消",
            device_name=device_name,
            device_id=reservation.device_id,
            notification_type="warning"
        )
    
    # ==================== 录入登记/强制归还 ====================
    
    def force_borrow(self, device_id: str, borrower: str, phone: str,
                     location: str, reason: str, expected_return_date: datetime,
                     remark: str = "") -> bool:
        """强制借出（管理员录入）"""
        device = self.get_device_by_id(device_id)
        if not device or not self._is_available_for_borrow(device):
            return False

        # 查找用户ID
        borrower_id = ""
        for user in self._db.get_all_users():
            if user.borrower_name == borrower:
                borrower_id = user.id
                break

        device.status = DeviceStatus.BORROWED
        device.borrower = borrower
        device.borrower_id = borrower_id
        device.phone = phone
        device.borrow_time = datetime.now()
        device.location = location
        device.reason = reason
        device.entry_source = EntrySource.ADMIN.value
        device.expected_return_date = expected_return_date
        device.admin_operator = self._current_admin

        # 保存设备
        self._db.save_device(device)
        
        # 添加记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=self._get_device_type_str(device),
            operation_type=OperationType.FORCE_BORROW,
            operator=self._current_admin,
            operation_time=datetime.now(),
            borrower=borrower,
            phone=phone,
            reason=reason,
            entry_source=EntrySource.ADMIN.value,
            remark=remark
        )
        self._db.save_record(record)
        
        # 更新用户借用次数
        for user in self._db.get_all_users():
            if user.borrower_name == borrower:
                user.borrow_count += 1
                self._db.save_user(user)
                break

        # 添加操作日志
        self.add_operation_log(f"强制借出登记: {borrower}", device.name)
        return True
    
    def force_return(self, device_id: str, return_person: str, return_location: str,
                     return_reason: str, remark: str = "") -> bool:
        """强制归还"""
        device = self.get_device_by_id(device_id)
        if not device or device.status != DeviceStatus.BORROWED:
            return False
        
        borrower = device.borrower

        # 清空借用信息，根据设备类型设置默认状态
        device.status = self._get_default_status_for_device(device)
        device.borrower = ""
        device.borrower_id = ""
        device.phone = ""
        device.borrow_time = None
        device.location = ""
        device.reason = ""
        device.entry_source = ""
        device.expected_return_date = None
        
        # 保存设备
        self._db.save_device(device)
        
        # 添加记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=self._get_device_type_str(device),
            operation_type=OperationType.FORCE_RETURN,
            operator=self._current_admin,
            operation_time=datetime.now(),
            borrower=return_person,
            reason=return_reason,
            entry_source=EntrySource.ADMIN.value,
            remark=remark
        )
        self._db.save_record(record)
        
        # 更新原借用人的归还次数
        if borrower:
            for user in self._db.get_all_users():
                if user.borrower_name == borrower:
                    user.return_count += 1
                    self._db.save_user(user)
                    break
        
        # 添加操作日志
        self.add_operation_log(f"强制归还: {borrower} -> {return_person}", device.name)
        return True
    
    def transfer_device(self, device_id: str, transfer_to: str, location: str,
                        reason: str, expected_return_date: datetime,
                        remark: str = "") -> bool:
        """转借设备（管理员操作）"""
        device = self.get_device_by_id(device_id)
        if not device or device.status != DeviceStatus.BORROWED:
            return False
        
        original_borrower = device.borrower

        # 获取转借人的信息
        transfer_email = ""
        transfer_user_id = ""
        for user in self._db.get_all_users():
            if user.borrower_name == transfer_to:
                transfer_email = user.email
                transfer_user_id = user.id
                break

        # 更新设备信息
        device.borrower = transfer_to
        device.borrower_id = transfer_user_id
        device.location = location
        device.reason = reason
        device.expected_return_date = expected_return_date
        
        # 保存设备
        self._db.save_device(device)
        
        # 添加记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=self._get_device_type_str(device),
            operation_type=OperationType.TRANSFER,
            operator=self._current_admin,
            operation_time=datetime.now(),
            borrower=f"转借：{original_borrower}——>{transfer_to}",
            reason=reason,
            entry_source=EntrySource.ADMIN.value,
            remark=remark
        )
        self._db.save_record(record)

        # 更新新借用人的借用次数
        for user in self._db.get_all_users():
            if user.borrower_name == transfer_to:
                user.borrow_count += 1
                self._db.save_user(user)
                break

        # 更新原借用人的归还次数（转借视为原借用人归还）
        if original_borrower:
            for user in self._db.get_all_users():
                if user.borrower_name == original_borrower:
                    user.return_count += 1
                    self._db.save_user(user)
                    break

        # 添加操作日志
        self.add_operation_log(f"转借：{original_borrower}——>{transfer_to}", device.name)
        return True
    
    # ==================== 记录查询 ====================
    
    def get_records(self, device_type: Optional[str] = None,
                    device_name: Optional[str] = None,
                    operation_type: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: int = None) -> List[Record]:
        """查询记录"""
        records = self._db.get_all_records(limit=limit)

        if device_type:
            records = [r for r in records if r.device_type == device_type]
        if device_name:
            records = [r for r in records if device_name in r.device_name]
        if operation_type:
            records = [r for r in records if r.operation_type.value == operation_type]
        if start_time:
            if isinstance(start_time, datetime):
                start_dt = start_time
            else:
                from datetime import datetime as dt
                start_dt = dt.combine(start_time, dt.min.time())
            records = [r for r in records if r.operation_time >= start_dt]
        if end_time:
            if isinstance(end_time, datetime):
                end_dt = end_time
            else:
                from datetime import datetime as dt
                end_dt = dt.combine(end_time, dt.max.time())
            records = [r for r in records if r.operation_time <= end_dt]
        
        return sorted(records, key=lambda x: x.operation_time, reverse=True)
    
    # ==================== 人员管理 ====================
    
    def get_all_users(self) -> List[User]:
        """获取所有用户"""
        return self._db.get_all_users()
    
    def freeze_user(self, user_id: str) -> bool:
        """冻结用户"""
        user = self._db.get_user_by_id(user_id)
        if user:
            user.is_frozen = True
            self._db.save_user(user)
            self.add_operation_log(f"冻结用户", user.borrower_name)
            return True
        return False
    
    def unfreeze_user(self, user_id: str) -> bool:
        """解冻用户"""
        user = self._db.get_user_by_id(user_id)
        if user:
            user.is_frozen = False
            self._db.save_user(user)
            self.add_operation_log(f"解冻用户", user.borrower_name)
            return True
        return False

    def set_user_admin(self, user_id: str) -> bool:
        """设置用户为管理员"""
        user = self._db.get_user_by_id(user_id)
        if user:
            user.is_admin = True
            self._db.save_user(user)
            self.add_operation_log(f"设置管理员", user.borrower_name)
            return True
        return False

    def cancel_user_admin(self, user_id: str) -> bool:
        """取消用户管理员权限"""
        user = self._db.get_user_by_id(user_id)
        if user:
            user.is_admin = False
            self._db.save_user(user)
            self.add_operation_log(f"取消管理员", user.borrower_name)
            return True
        return False

    def set_user_admin_flag(self, user_id: str, is_admin: bool) -> bool:
        """设置用户管理员标志"""
        user = self._db.get_user_by_id(user_id)
        if user:
            user.is_admin = is_admin
            self._db.save_user(user)
            action = "设置管理员" if is_admin else "取消管理员"
            self.add_operation_log(action, user.borrower_name)
            return True
        return False

    # ==================== 后台管理功能 ====================
    
    def verify_admin_login(self, username: str, password: str) -> Optional[dict]:
        """验证管理员登录"""
        # 1. 检查传统管理员表
        admin = self._db.get_admin_by_username(username)
        if admin and admin.password == password:
            return {
                'id': admin.id,
                'name': admin.username,
                'username': admin.username
            }
        
        # 2. 检查被指定为管理员的用户（通过借用人名称或邮箱登录）
        for user in self._db.get_all_users():
            if user.is_admin and not user.is_frozen:
                if (user.borrower_name == username or user.email == username) and user.password == password:
                    return {
                        'id': user.id,
                        'name': user.borrower_name,
                        'username': user.borrower_name
                    }
        
        return None
    
    def get_users(self) -> List[User]:
        """获取所有用户列表"""
        return self._db.get_all_users()
    
    def get_device(self, device_id: str) -> Optional[Device]:
        """根据ID获取设备"""
        return self._db.get_device_by_id(device_id)
    
    def get_device_records(self, device_id: str, device_type: str = None, limit: int = 10) -> List[Record]:
        """获取设备的操作记录"""
        records = self._db.get_records_by_device(device_id)
        if device_type:
            records = [r for r in records if r.device_type == device_type]
        return sorted(records, key=lambda x: x.operation_time, reverse=True)[:limit]
    
    def create_device(self, device_type, device_name: str, model: str = '', 
                     cabinet: str = '', status: str = '在库', remarks: str = '',
                     asset_number: str = '', purchase_amount: float = 0.0,
                     **kwargs) -> Device:
        """创建新设备"""
        device_id = str(uuid.uuid4())
        device_status = DeviceStatus(status) if status else DeviceStatus.IN_STOCK
        
        create_time = datetime.now()
        if device_type == DeviceType.PHONE or str(device_type) == 'DeviceType.PHONE':
            device = Phone(
                id=device_id,
                name=device_name,
                model=model,
                cabinet_number=cabinet,
                status=device_status,
                remark=remarks,
                asset_number=asset_number,
                purchase_amount=purchase_amount,
                sn=kwargs.get('sn', ''),
                imei=kwargs.get('imei', ''),
                system_version=kwargs.get('system_version', ''),
                carrier=kwargs.get('carrier', ''),
                create_time=create_time
            )
        elif device_type == DeviceType.INSTRUMENT or str(device_type) == 'DeviceType.INSTRUMENT':
            device = Instrument(
                id=device_id,
                name=device_name,
                model=model,
                cabinet_number=cabinet,
                status=device_status,
                remark=remarks,
                asset_number=asset_number,
                purchase_amount=purchase_amount,
                create_time=create_time
            )
        elif device_type == DeviceType.SIM_CARD or str(device_type) == 'DeviceType.SIM_CARD':
            device = SimCard(
                id=device_id,
                name=device_name,
                model=model,
                cabinet_number=cabinet,
                status=device_status,
                remark=remarks,
                asset_number=asset_number,
                purchase_amount=purchase_amount,
                carrier=kwargs.get('carrier', ''),
                create_time=create_time
            )
        elif device_type == DeviceType.OTHER_DEVICE or str(device_type) == 'DeviceType.OTHER_DEVICE':
            device = OtherDevice(
                id=device_id,
                name=device_name,
                model=model,
                cabinet_number=cabinet,
                status=device_status,
                remark=remarks,
                asset_number=asset_number,
                purchase_amount=purchase_amount,
                create_time=create_time
            )
        else:
            device = CarMachine(
                id=device_id,
                name=device_name,
                model=model,
                cabinet_number=cabinet,
                status=device_status,
                remark=remarks,
                asset_number=asset_number,
                purchase_amount=purchase_amount,
                create_time=create_time
            )
        
        try:
            self._db.save_device(device)
        except Exception as e:
            print(f"[DEBUG] create_device - save_device error: {e}")
            import traceback
            print(f"[DEBUG] create_device - traceback: {traceback.format_exc()}")
            raise
        self.add_operation_log("创建设备", device_name)
        return device
    
    def update_device_by_id(self, device_id: str, data: dict, operator: str = '管理员') -> bool:
        """通过ID更新设备信息"""
        device = self.get_device(device_id)
        if not device:
            return False

        # 保存原始状态和保管人
        original_status = device.status
        original_custodian = device.cabinet_number
        original_borrower = device.borrower

        # 检查是否改为报废状态
        is_scrapped = data.get('status') == '报废'
        was_borrowed = device.status == DeviceStatus.BORROWED

        # 追踪哪些字段发生了变化
        status_changed = False
        custodian_changed = False

        if 'device_name' in data:
            device.name = data['device_name']
        if 'device_type' in data:
            # 更新设备类型
            device_type_str = data['device_type']
            if isinstance(device_type_str, str):
                # 根据中文值获取枚举类型
                new_device_type = None
                for dt in DeviceType:
                    if dt.value == device_type_str:
                        new_device_type = dt
                        break
                if new_device_type and new_device_type != device.device_type:
                    # 设备类型发生变化，根据新类型和借用人状态自动调整状态
                    device.device_type = new_device_type
                    # 判断是否为车机/仪表类型
                    is_car_or_instrument = new_device_type in [DeviceType.CAR_MACHINE, DeviceType.INSTRUMENT]
                    # 判断是否有借出人
                    has_borrower = device.borrower and device.borrower.strip()
                    if has_borrower:
                        # 有借出人，状态设为借出
                        if device.status != DeviceStatus.BORROWED:
                            original_status = device.status
                            device.status = DeviceStatus.BORROWED
                            status_changed = True
                    else:
                        # 无借出人，根据设备类型设置默认状态
                        if is_car_or_instrument:
                            # 车机/仪表：在库
                            if device.status != DeviceStatus.IN_STOCK:
                                original_status = device.status
                                device.status = DeviceStatus.IN_STOCK
                                status_changed = True
                        else:
                            # 手机/手机卡/其它设备：保管中
                            if device.status != DeviceStatus.IN_CUSTODY:
                                original_status = device.status
                                device.status = DeviceStatus.IN_CUSTODY
                                status_changed = True
        if 'model' in data:
            device.model = data['model']
        if 'cabinet' in data:
            device.cabinet_number = data['cabinet']
            if device.cabinet_number != original_custodian:
                custodian_changed = True
            # 根据保管人名称查找并更新custodian_id
            if device.cabinet_number:
                for user in self._users:
                    if user.borrower_name == device.cabinet_number:
                        device.custodian_id = user.id
                        break
                else:
                    device.custodian_id = ""
            else:
                device.custodian_id = ""
        if 'status' in data:
            new_status = DeviceStatus(data['status'])
            if new_status != original_status:
                status_changed = True
                device.status = new_status
                
                # 如果状态变为损坏、丢失、报废或封存，取消相关预约
                if new_status in [DeviceStatus.DAMAGED, DeviceStatus.LOST, 
                                  DeviceStatus.SCRAPPED, DeviceStatus.SEALED]:
                    cancelled_count = self.cancel_reservations_by_device_status_change(
                        device_id, new_status.value, operator
                    )
                    if cancelled_count > 0:
                        self.add_operation_log(
                            f"设备状态变更为{new_status.value}，取消{cancelled_count}个预约", 
                            device.name
                        )
        if 'remarks' in data:
            device.remark = data['remarks']
        if 'jira_address' in data:
            device.jira_address = data['jira_address']
        if 'borrower' in data:
            device.borrower = data['borrower']

        # 手机特有字段
        if 'sn' in data:
            device.sn = data['sn']
        if 'imei' in data:
            device.imei = data['imei']
        if 'system_version' in data:
            device.system_version = data['system_version']
        if 'carrier' in data:
            device.carrier = data['carrier']
        if 'asset_number' in data:
            device.asset_number = data['asset_number']
        if 'purchase_amount' in data:
            device.purchase_amount = float(data['purchase_amount']) if data['purchase_amount'] else 0.0

        # 车机特有字段
        if 'software_version' in data:
            device.software_version = data['software_version']
        if 'hardware_version' in data:
            device.hardware_version = data['hardware_version']

        # 车机和仪表特有字段（JIRA地址后）
        if 'project_attribute' in data:
            device.project_attribute = data['project_attribute']
        if 'connection_method' in data:
            device.connection_method = data['connection_method']
        if 'os_version' in data:
            device.os_version = data['os_version']
        if 'os_platform' in data:
            device.os_platform = data['os_platform']
        if 'product_name' in data:
            device.product_name = data['product_name']
        if 'screen_orientation' in data:
            device.screen_orientation = data['screen_orientation']
        if 'screen_resolution' in data:
            device.screen_resolution = data['screen_resolution']

        # 添加状态变更记录（不包括报废，报废有单独处理）
        if status_changed and not is_scrapped:
            notify_user = device.borrower or original_borrower or device.cabinet_number or original_custodian
            record = Record(
                id=str(uuid.uuid4()),
                device_id=device.id,
                device_name=device.name,
                device_type=self._get_device_type_str(device),
                operation_type=OperationType.STATUS_CHANGE,
                operator=operator,
                operation_time=datetime.now(),
                borrower=notify_user,
                reason=f'管理员将状态从{original_status.value}改成了{device.status.value}',
                remark=''
            )
            self._db.save_record(record)

        # 添加保管人变更记录
        if custodian_changed:
            record = Record(
                id=str(uuid.uuid4()),
                device_id=device.id,
                device_name=device.name,
                device_type=self._get_device_type_str(device),
                operation_type=OperationType.CUSTODIAN_CHANGE,
                operator=operator,
                operation_time=datetime.now(),
                borrower=device.borrower,
                reason=f'管理员将保管人更改成{device.cabinet_number}',
                remark=f'原保管人: {original_custodian}'
            )
            self._db.save_record(record)

        # 如果设备被报废且之前是借出状态，清空借用人信息并添加报废记录
        if is_scrapped and was_borrowed and original_borrower:
            device.borrower = ''
            device.phone = ''
            device.borrow_time = None
            device.expected_return_date = None
            device.location = ''
            device.reason = ''

            record = Record(
                id=str(uuid.uuid4()),
                device_id=device.id,
                device_name=device.name,
                device_type=self._get_device_type_str(device),
                operation_type=OperationType.SCRAP,
                operator=operator,
                operation_time=datetime.now(),
                borrower=original_borrower,
                reason='设备被管理员报废'
            )
            self._db.save_record(record)
            self.add_operation_log(f"报废设备(原借用人: {original_borrower})", device.name)
            self.notify_status_change(
                device_id=device.id,
                device_name=device.name,
                borrower=original_borrower,
                new_status='报废',
                operator=operator
            )
        else:
            if status_changed:
                self.add_operation_log(f"状态变更: {original_status.value} -> {device.status.value}", device.name)
                if original_borrower:
                    self.notify_status_change(
                        device_id=device.id,
                        device_name=device.name,
                        borrower=original_borrower,
                        new_status=device.status.value,
                        operator=operator
                    )
                if device.cabinet_number and device.cabinet_number != original_borrower:
                    custodian_user = None
                    for user in self._db.get_all_users():
                        if user.borrower_name == device.cabinet_number:
                            custodian_user = user
                            break
                    if custodian_user:
                        self.add_notification(
                            user_id=custodian_user.id,
                            user_name=custodian_user.borrower_name,
                            title=f"设备{device.status.value}通知",
                            content=f"您保管的设备「{device.name}」已被管理员设置为「{device.status.value}」状态。",
                            device_name=device.name,
                            device_id=device.id,
                            notification_type="warning"
                        )
            elif custodian_changed:
                self.add_operation_log(f"保管人变更: {original_custodian} -> {device.cabinet_number}", device.name)
                if original_custodian and original_custodian != device.cabinet_number:
                    for user in self._db.get_all_users():
                        if user.borrower_name == original_custodian:
                            self.add_notification(
                                user_id=user.id,
                                user_name=user.borrower_name,
                                title="设备保管人变更通知",
                                content=f"您保管的设备「{device.name}」的保管人已变更为 {device.cabinet_number or '无'}。",
                                device_name=device.name,
                                device_id=device.id,
                                notification_type="warning"
                            )
                            break
                if device.cabinet_number and device.cabinet_number != original_custodian:
                    for user in self._db.get_all_users():
                        if user.borrower_name == device.cabinet_number:
                            self.add_notification(
                                user_id=user.id,
                                user_name=user.borrower_name,
                                title="设备保管人变更通知",
                                content=f"您已成为设备「{device.name}」的保管人。",
                                device_name=device.name,
                                device_id=device.id,
                                notification_type="success"
                            )
                            break
                if device.borrower:
                    for user in self._db.get_all_users():
                        if user.borrower_name == device.borrower:
                            self.add_notification(
                                user_id=user.id,
                                user_name=user.borrower_name,
                                title="设备保管人变更通知",
                                content=f"您借用的设备「{device.name}」的保管人已变更为 {device.cabinet_number or '无'}。",
                                device_name=device.name,
                                device_id=device.id,
                                notification_type="info"
                            )
                            break
            else:
                self.add_operation_log("编辑设备", device.name)

        self._db.save_device(device)
        return True
    
    def create_user(self, borrower_name: str, 
                   email: str = '', password: str = '', is_admin: bool = False) -> User:
        """创建新用户"""
        # 检查邮箱是否已存在（如果提供了邮箱）
        if email:
            existing_user = self._db.get_user_by_email(email)
            if existing_user:
                raise ValueError("邮箱已被注册")
        
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            email=email,
            password=password or '123456',
            borrower_name=borrower_name,
            is_admin=is_admin,
            is_first_login=True,
            create_time=datetime.now()
        )
        self._db.save_user(user)
        self.add_operation_log("创建用户", borrower_name)
        return user
    
    def update_user(self, user_id: str, data: dict) -> bool:
        """更新用户信息"""
        user = self._db.get_user_by_id(user_id)
        if user:
            old_borrower_name = user.borrower_name
            
            if 'name' in data:
                user.borrower_name = data['name']
            if 'email' in data:
                user.email = data['email']
            if 'password' in data and data['password']:
                user.password = data['password']
            if 'is_admin' in data:
                user.is_admin = data['is_admin']
            if 'is_first_login' in data:
                user.is_first_login = data['is_first_login']
            
            self._db.save_user(user)
            
            # 如果借用人名称发生变化，同步更新设备表中的借用人和保管人
            if 'name' in data and old_borrower_name and old_borrower_name != data['name']:
                self._sync_device_borrower_name(old_borrower_name, data['name'])
            
            self.add_operation_log("编辑用户", user.borrower_name)
            return True
        return False
    
    def _sync_device_borrower_name(self, old_name: str, new_name: str):
        """同步更新设备表中的借用人和保管人名称"""
        all_devices = self.get_all_devices()
        for device in all_devices:
            need_save = False
            # 更新借用人
            if device.borrower == old_name:
                device.borrower = new_name
                need_save = True
            # 更新保管人
            if device.cabinet_number == old_name:
                device.cabinet_number = new_name
                need_save = True
            # 更新上一个借用人
            if device.previous_borrower == old_name:
                device.previous_borrower = new_name
                need_save = True
            
            if need_save:
                self._db.save_device(device)
    
    def get_user_borrowed_devices(self, borrower_name: str) -> list:
        """获取用户当前借用的所有设备（通过名称）"""
        borrowed_devices = []
        all_devices = self.get_all_devices()
        for device in all_devices:
            if device.borrower == borrower_name and device.status == DeviceStatus.BORROWED:
                borrowed_devices.append(device)
        return borrowed_devices

    def get_user_borrowed_devices_by_id(self, borrower_id: str) -> list:
        """获取用户当前借用的所有设备（通过用户ID）"""
        borrowed_devices = []
        all_devices = self.get_all_devices()

        # 获取用户信息以获取borrower_name
        user = self._db.get_user_by_id(borrower_id)
        user_name = user.borrower_name if user else ""

        for device in all_devices:
            if device.status == DeviceStatus.BORROWED:
                # 检查borrower_id匹配，或者通过borrower名称匹配用户
                if device.borrower_id == borrower_id:
                    borrowed_devices.append(device)
                elif user_name and device.borrower == user_name:
                    borrowed_devices.append(device)
        return borrowed_devices

    def get_user_custodian_devices_by_id(self, custodian_id: str) -> list:
        """获取用户保管的所有设备（通过用户ID）"""
        custodian_devices = []
        all_devices = self.get_all_devices()

        # 获取用户信息以获取borrower_name
        user = self._db.get_user_by_id(custodian_id)
        user_name = user.borrower_name if user else ""

        for device in all_devices:
            # 检查custodian_id匹配，或者通过cabinet_number匹配用户名称
            if device.custodian_id == custodian_id:
                custodian_devices.append(device)
            elif user_name and device.cabinet_number == user_name:
                custodian_devices.append(device)
        return custodian_devices

    def delete_user(self, user_id: str) -> tuple[bool, str]:
        """删除用户（逻辑删除）

        Returns:
            (成功, 消息)
        """
        user = self._db.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"

        # 检查用户是否有借用的设备
        borrowed_devices = self.get_user_borrowed_devices_by_id(user_id)
        if borrowed_devices:
            device_names = [d.name for d in borrowed_devices[:5]]  # 最多显示5个设备名
            device_list = ", ".join(device_names)
            if len(borrowed_devices) > 5:
                device_list += f" 等共{len(borrowed_devices)}个设备"
            return False, f"该用户还有未归还的借用设备：{device_list}，请归还后再删除用户"

        # 检查用户是否有保管的设备
        custodian_devices = self.get_user_custodian_devices_by_id(user_id)
        if custodian_devices:
            device_names = [d.name for d in custodian_devices[:5]]  # 最多显示5个设备名
            device_list = ", ".join(device_names)
            if len(custodian_devices) > 5:
                device_list += f" 等共{len(custodian_devices)}个设备"
            return False, f"该用户还有保管中的设备：{device_list}，请移交后再删除用户"

        # 处理用户的预约记录
        self._handle_user_reservations_on_delete(user_id, user.borrower_name)

        user.is_deleted = True
        self._db.save_user(user)
        self.add_operation_log("删除用户", user.borrower_name)
        return True, "删除成功"
    
    def _handle_user_reservations_on_delete(self, user_id: str, user_name: str):
        """用户删除时处理其预约记录"""
        # 获取用户的所有预约
        reservations = self._db.get_reservations_by_reserver(user_id)
        
        for reservation in reservations:
            # 只处理未完成的预约
            if reservation.status in [
                ReservationStatus.PENDING_CUSTODIAN.value,
                ReservationStatus.PENDING_BORROWER.value,
                ReservationStatus.PENDING_BOTH.value,
                ReservationStatus.APPROVED.value
            ]:
                # 取消预约
                reservation.status = ReservationStatus.CANCELLED.value
                reservation.cancelled_by = "system"
                reservation.cancelled_at = datetime.now()
                reservation.cancel_reason = f"预约人 {user_name} 已被删除"
                reservation.updated_at = datetime.now()
                self._db.save_reservation(reservation)
                
                # 通知相关人（保管人或当前借用人）
                if reservation.custodian_id:
                    self.add_notification(
                        user_id=reservation.custodian_id,
                        user_name="",
                        title="预约已取消",
                        content=f"用户 {user_name} 预约的 {reservation.device_name} 已因其账号被删除而自动取消",
                        device_name=reservation.device_name,
                        device_id=reservation.device_id,
                        notification_type="info"
                    )
                if reservation.current_borrower_id:
                    self.add_notification(
                        user_id=reservation.current_borrower_id,
                        user_name=reservation.current_borrower_name,
                        title="预约已取消",
                        content=f"用户 {user_name} 对您借用设备的预约已因其账号被删除而自动取消",
                        device_name=reservation.device_name,
                        device_id=reservation.device_id,
                        notification_type="info"
                    )
    
    def reset_user_password(self, user_id: str) -> bool:
        """重置用户密码为初始密码123456，并设置为首次登录状态"""
        user = self._db.get_user_by_id(user_id)
        if user:
            user.password = '123456'
            user.is_first_login = True
            self._db.save_user(user)
            self.add_operation_log("重置密码", user.borrower_name)
            return True
        return False
    
    def change_user_password(self, user_id: str, new_password: str) -> bool:
        """用户修改密码"""
        user = self._db.get_user_by_id(user_id)
        if user:
            user.password = new_password
            user.is_first_login = False  # 修改密码后不再是首次登录
            self._db.save_user(user)
            return True
        return False
    
    def borrow_device(self, device_id: str, borrower: str, days: int = 1,
                     remarks: str = '', operator: str = '管理员', entry_source: str = None) -> bool:
        """借出设备"""
        device = self.get_device(device_id)
        if not device:
            return False

        # 封存状态设备无法借用
        if device.status == DeviceStatus.SEALED:
            raise ValueError('封存状态的设备无法借用')

        # 检查是否是邮箱，如果是则通过邮箱查找用户获取borrower_name
        actual_borrower = borrower
        borrower_id = ""
        if '@' in borrower:
            user = self.get_user_by_email(borrower)
            if not user:
                raise ValueError(f'未找到邮箱为 {borrower} 的用户')
            actual_borrower = user.borrower_name
            borrower_id = user.id
        else:
            # 通过名称查找用户ID
            for user in self._db.get_all_users():
                if user.borrower_name == borrower:
                    borrower_id = user.id
                    break

        # 检查用户借用数量限制（管理员借出也要检查）
        user_borrowed_count = 0
        all_devices = self.get_all_devices()
        for d in all_devices:
            if d.borrower == actual_borrower and d.status == DeviceStatus.BORROWED:
                user_borrowed_count += 1

        borrow_limit = 10  # 最大借用数量
        if user_borrowed_count >= borrow_limit:
            raise ValueError(f'{actual_borrower}已超出可借设备上限，请归还后再借')

        # 计算预计归还时间：当前时间 + 天数
        now = datetime.now()
        expected_return = now + timedelta(days=days)

        device.borrower = actual_borrower
        device.borrower_id = borrower_id
        device.status = DeviceStatus.BORROWED
        device.borrow_time = now
        device.expected_return_date = expected_return

        # 保存设备
        self._db.save_device(device)

        # 确定录入来源
        if entry_source is None:
            entry_source = EntrySource.ADMIN.value if operator != borrower else EntrySource.USER.value

        # 创建记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device_id,
            device_name=device.name,
            device_type=device.device_type.value,
            operation_type=OperationType.BORROW,
            operator=operator,
            operation_time=datetime.now(),
            borrower=actual_borrower,
            reason=remarks,
            entry_source=entry_source,
            remark=remarks
        )
        self._db.save_record(record)

        # 更新用户借用次数
        for user in self._db.get_all_users():
            if user.borrower_name == borrower:
                user.borrow_count += 1
                self._db.save_user(user)
                break

        self.add_operation_log("录入登记", device.name)
        return True
    
    def return_device(self, device_id: str, operator: str = '管理员', entry_source: str = None) -> bool:
        """归还设备"""
        device = self.get_device(device_id)
        if not device:
            return False

        borrower = device.borrower
        device.borrower = ''
        device.borrower_id = ''
        device.cabinet_number = 'A01'  # 默认柜号
        device.status = self._get_default_status_for_device(device)
        device.borrow_time = None
        device.expected_return_date = None

        # 保存设备
        self._db.save_device(device)

        # 确定录入来源
        if entry_source is None:
            entry_source = EntrySource.ADMIN.value if operator != borrower else EntrySource.USER.value

        # 创建记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device_id,
            device_name=device.name,
            device_type=device.device_type.value,
            operation_type=OperationType.RETURN,
            operator=operator,
            operation_time=datetime.now(),
            borrower=borrower,
            entry_source=entry_source
        )
        self._db.save_record(record)

        # 更新用户归还次数
        if borrower:
            for user in self._db.get_all_users():
                if user.borrower_name == borrower:
                    user.return_count += 1
                    self._db.save_user(user)
                    break

        self.add_operation_log("强制归还", device.name)

        # 发送通知
        if borrower:
            self.notify_return(
                device_id=device_id,
                device_name=device.name,
                borrower=borrower,
                operator=operator
            )

        return True

    # ==================== 备注管理 ====================
    
    def get_remarks(self, device_id: Optional[str] = None, device_type: str = None,
                    exclude_inappropriate: bool = False) -> List[UserRemark]:
        """获取备注列表"""
        if device_id:
            remarks = self._db.get_remarks_by_device(device_id)
        else:
            # 获取所有备注
            remarks = self._db.get_all_remarks()

        if device_type:
            remarks = [r for r in remarks if r.device_type == device_type]
        if exclude_inappropriate:
            remarks = [r for r in remarks if not r.is_inappropriate]
        return remarks
    
    def delete_remark(self, remark_id: str) -> bool:
        """删除备注"""
        self._db.delete_remark(remark_id)
        return True

    def mark_inappropriate(self, remark_id: str) -> bool:
        """标记不当备注"""
        return self._db.mark_remark_inappropriate(remark_id, True)

    def unmark_inappropriate(self, remark_id: str) -> bool:
        """取消不当备注标记"""
        return self._db.mark_remark_inappropriate(remark_id, False)
    
    # ==================== 操作日志 ====================
    
    def get_operation_logs(self, limit: int = 50) -> List[OperationLog]:
        """获取操作日志"""
        logs = self._db.get_all_operation_logs()
        return sorted(logs, key=lambda x: x.operation_time, reverse=True)[:limit]
    
    def add_operation_log(self, operation_content: str, device_info: str, operator: str = None, source: str = "admin"):
        """添加操作日志

        Args:
            operation_content: 操作内容
            device_info: 设备信息
            operator: 操作人，如果不传则使用当前管理员
            source: 操作来源，admin-管理员操作，user-用户端操作
        """
        log = OperationLog(
            id=str(uuid.uuid4()),
            operation_time=datetime.now(),
            operator=operator if operator else self._current_admin,
            operation_content=operation_content,
            device_info=device_info,
            source=source
        )
        self._db.save_operation_log(log)
    
    def get_admin_logs(self, limit: int = 100) -> List[dict]:
        """获取管理员操作日志（用于后台管理）"""
        logs = self.get_operation_logs(limit * 2)
        result = []
        for log in logs:
            # 只显示管理员操作（source="admin"）
            # 注意：对于旧数据（source为NULL），需要检查操作人是否为管理员
            if log.source == "user":
                continue
            # 对于 source="admin" 或旧数据（source=None），检查操作人是否为管理员
            if not self.is_user_admin(log.operator):
                continue
            result.append({
                'id': log.id,
                'time': log.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
                'admin_name': log.operator,
                'action_type': self._categorize_action(log.operation_content),
                'details': f"{log.operation_content}: {log.device_info}",
                'ip': ''
            })
            if len(result) >= limit:
                break
        return result
    
    def _categorize_action(self, content: str) -> str:
        """将操作内容分类"""
        if '借出' in content or '录入登记' in content:
            return '借出'
        elif '归还' in content or '强制归还' in content:
            return '归还'
        elif '转借' in content:
            return '转借'
        elif '编辑' in content or '修改' in content:
            return '编辑'
        elif '删除' in content:
            return '删除'
        elif '新增' in content or '添加' in content or '创建' in content:
            return '新增'
        elif '冻结' in content or '解冻' in content:
            return '用户管理'
        elif '管理员' in content:
            return '权限管理'
        else:
            return '其他'

    # ==================== 后台管理操作日志 ====================

    def add_admin_operation_log(self, admin_id: str, admin_name: str, action_type: str,
                                 action_name: str, target_type: str, target_id: str = "",
                                 target_name: str = "", description: str = "",
                                 ip_address: str = "", user_agent: str = "",
                                 request_method: str = "", request_path: str = "",
                                 request_params: str = "", result: str = "SUCCESS",
                                 error_message: str = "") -> bool:
        """添加后台管理操作日志

        Args:
            admin_id: 管理员ID
            admin_name: 管理员名称
            action_type: 操作类型
            action_name: 操作名称
            target_type: 操作对象类型
            target_id: 操作对象ID
            target_name: 操作对象名称
            description: 操作描述
            ip_address: IP地址
            user_agent: 浏览器UA
            request_method: HTTP方法
            request_path: 请求路径
            request_params: 请求参数
            result: 操作结果
            error_message: 错误信息
        """
        log = AdminOperationLog(
            id=str(uuid.uuid4()),
            operation_time=datetime.now(),
            admin_id=admin_id,
            admin_name=admin_name,
            action_type=action_type,
            action_name=action_name,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            request_params=request_params,
            result=result,
            error_message=error_message
        )
        return self._db.save_admin_operation_log(log)

    def get_admin_operation_logs(self, limit: int = 100, offset: int = 0,
                                  admin_id: str = None, action_type: str = None,
                                  target_type: str = None, result: str = None,
                                  start_time: datetime = None, end_time: datetime = None) -> List[AdminOperationLog]:
        """获取后台管理操作日志列表"""
        return self._db.get_admin_operation_logs(
            limit=limit, offset=offset,
            admin_id=admin_id, action_type=action_type,
            target_type=target_type, result=result,
            start_time=start_time, end_time=end_time
        )

    def get_admin_operation_logs_count(self, admin_id: str = None, action_type: str = None,
                                        target_type: str = None, result: str = None,
                                        start_time: datetime = None, end_time: datetime = None) -> int:
        """获取后台管理操作日志总数"""
        return self._db.get_admin_operation_logs_count(
            admin_id=admin_id, action_type=action_type,
            target_type=target_type, result=result,
            start_time=start_time, end_time=end_time
        )

    def get_admin_operation_logs_for_display(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """获取后台管理操作日志（用于前端展示）"""
        logs = self._db.get_admin_operation_logs(limit=limit, offset=offset)
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'time': log.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
                'admin_name': log.admin_name,
                'action_type': log.action_type,
                'action_name': log.action_name,
                'target_type': log.target_type,
                'target_name': log.target_name,
                'description': log.description,
                'ip': log.ip_address,
                'result': log.result,
            })
        return result

    def clear_old_admin_operation_logs(self, days: int = 90) -> int:
        """清理指定天数之前的后台管理操作日志"""
        return self._db.clear_admin_operation_logs(days=days)

    # ==================== 通知功能 ====================

    def get_notifications(self, user_id: str = None, user_name: str = None, unread_only: bool = False) -> List[Notification]:
        """获取通知列表"""
        if user_id:
            notifications = self._db.get_notifications_by_user(user_id)
        else:
            # 获取所有通知需要额外实现
            notifications = []
        
        if unread_only:
            notifications = [n for n in notifications if not n.is_read]
        
        return sorted(notifications, key=lambda x: x.create_time, reverse=True)

    def get_unread_count(self, user_id: str = None, user_name: str = None) -> int:
        """获取未读通知数量"""
        if user_id:
            notifications = self._db.get_notifications_by_user(user_id)
            return len([n for n in notifications if not n.is_read])
        return 0

    def add_notification(self, user_id: str, user_name: str, title: str, content: str,
                         device_name: str = "", device_id: str = "",
                         notification_type: str = "info") -> Notification:
        """添加通知"""
        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            user_name=user_name,
            title=title,
            content=content,
            device_name=device_name,
            device_id=device_id,
            is_read=False,
            notification_type=notification_type
        )
        self._db.save_notification(notification)
        return notification

    def mark_notification_read(self, notification_id: str) -> bool:
        """标记通知为已读"""
        self._db.mark_notification_as_read(notification_id)
        return True

    def mark_all_read(self, user_id: str = None, user_name: str = None) -> int:
        """标记用户所有通知为已读，返回标记数量"""
        if user_id:
            notifications = self._db.get_notifications_by_user(user_id)
            count = 0
            for notification in notifications:
                if not notification.is_read:
                    self._db.mark_notification_as_read(notification.id)
                    count += 1
            return count
        return 0

    def delete_notification(self, notification_id: str) -> bool:
        """删除通知"""
        # 需要在db_store中添加删除方法
        return True

    def notify_borrow(self, device_id: str, device_name: str, borrower: str, operator: str):
        """通知用户设备已借出"""
        for user in self._db.get_all_users():
            if user.borrower_name == borrower:
                content = f"操作员 {operator} 已将设备「{device_name}」借出给您，请注意按时归还。"
                self.add_notification(
                    user_id=user.id,
                    user_name=borrower,
                    title="设备借出通知",
                    content=content,
                    device_name=device_name,
                    device_id=device_id,
                    notification_type="success"
                )
                break

    def notify_return(self, device_id: str, device_name: str, borrower: str, operator: str):
        """通知用户设备已归还（强制归还）"""
        for user in self._db.get_all_users():
            if user.borrower_name == borrower:
                content = f"操作员 {operator} 已将您借用的设备「{device_name}」强制归还。"
                self.add_notification(
                    user_id=user.id,
                    user_name=borrower,
                    title="设备强制归还通知",
                    content=content,
                    device_name=device_name,
                    device_id=device_id,
                    notification_type="warning"
                )
                break

    def notify_transfer(self, device_id: str, device_name: str, original_borrower: str, new_borrower: str, operator: str):
        """通知相关用户设备已转借"""
        # 通知原借用人（排除操作人自己）
        if original_borrower and original_borrower != operator:
            for user in self._db.get_all_users():
                if user.borrower_name == original_borrower:
                    content = f"您借用的设备「{device_name}」已被 {operator} 转借给 {new_borrower}。"
                    self.add_notification(
                        user_id=user.id,
                        user_name=original_borrower,
                        title="设备转借通知",
                        content=content,
                        device_name=device_name,
                        device_id=device_id,
                        notification_type="warning"
                    )
                    break

        # 通知新借用人
        for user in self._db.get_all_users():
            if user.borrower_name == new_borrower:
                content = f"{operator} 已将设备「{device_name}」转借给您。"
                self.add_notification(
                    user_id=user.id,
                    user_name=new_borrower,
                    title="设备转借通知",
                    content=content,
                    device_name=device_name,
                    device_id=device_id,
                    notification_type="success"
                )
                break

    def notify_status_change(self, device_id: str, device_name: str, borrower: str, new_status: str, operator: str):
        """通知用户设备状态变更"""
        for user in self._db.get_all_users():
            if user.borrower_name == borrower:
                status_desc = {
                    "已损坏": "损坏",
                    "丢失": "丢失",
                    "已寄出": "寄出",
                    "维修中": "维修",
                    "报废": "报废"
                }.get(new_status, new_status)

                notification_type = "error" if new_status in ["已损坏", "丢失"] else "warning"
                content = f"操作员 {operator} 将您借用的设备「{device_name}」状态更改为「{new_status}」。"

                self.add_notification(
                    user_id=user.id,
                    user_name=borrower,
                    title=f"设备{status_desc}通知",
                    content=content,
                    device_name=device_name,
                    device_id=device_id,
                    notification_type=notification_type
                )
                break

    def notify_overdue_reminder(self, device_id: str, device_name: str, borrower: str, operator: str):
        """通知用户设备逾期归还提醒"""
        for user in self._db.get_all_users():
            if user.borrower_name == borrower:
                content = f"您借用的设备「{device_name}」已逾期，请及时归还。如有问题请联系管理员。"
                self.add_notification(
                    user_id=user.id,
                    user_name=borrower,
                    title="设备逾期归还提醒",
                    content=content,
                    device_name=device_name,
                    device_id=device_id,
                    notification_type="warning"
                )
                break

    def reload_data(self):
        """重新加载数据（用于网页端刷新）- 数据库模式下无需重新加载"""
        pass
    
    # ==================== 查看记录 ====================
    
    def add_view_record(self, device_id: str, viewer: str, device_type: str = ""):
        """添加查看记录"""
        self._db.save_view_record(device_id, device_type, viewer)

    def get_view_records(self, device_id: str, device_type: str = None, limit: int = 20) -> List[ViewRecord]:
        """获取设备的查看记录"""
        records = self._db.get_view_records_by_device(device_id)
        if device_type:
            records = [r for r in records if r.get('device_type') == device_type]
        
        # 转换为ViewRecord对象
        view_records = []
        for r in records[:limit]:
            view_time = r.get('view_time', '')
            if view_time:
                # 处理带微秒的格式
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        view_time = datetime.strptime(view_time, fmt)
                        break
                    except:
                        continue
                else:
                    view_time = datetime.now()
            else:
                view_time = datetime.now()
            view_records.append(ViewRecord(
                id=r.get('id', ''),
                device_id=r.get('device_id', ''),
                device_type=r.get('device_type', ''),
                viewer=r.get('viewer', ''),
                view_time=view_time
            ))
        return view_records

    # ==================== 公告管理 ====================

    def get_announcements(self, announcement_type: str = None, active_only: bool = False) -> List[Announcement]:
        """获取公告列表"""
        announcements = self._db.get_all_announcements(active_only=False)
        
        if active_only:
            announcements = [a for a in announcements if a.is_active]
        
        if announcement_type:
            announcements = [a for a in announcements if a.announcement_type == announcement_type]
        
        return sorted(announcements, key=lambda x: (x.sort_order, -x.create_time.timestamp() if x.create_time else 0))

    def get_active_normal_announcements(self) -> List[Announcement]:
        """获取上架的普通公告列表（按排序显示）"""
        announcements = self._db.get_all_announcements(active_only=True)
        announcements = [a for a in announcements if a.announcement_type == 'normal']
        return sorted(announcements, key=lambda x: (x.sort_order, -x.create_time.timestamp() if x.create_time else 0))

    def get_active_special_announcements(self) -> List[Announcement]:
        """获取上架的特殊公告列表（最多3条）"""
        announcements = self._db.get_all_announcements(active_only=True)
        announcements = [a for a in announcements if a.announcement_type == 'special']
        announcements = sorted(announcements, key=lambda x: (x.sort_order, -x.create_time.timestamp() if x.create_time else 0))
        return announcements[:3]

    def get_announcement_by_id(self, announcement_id: str) -> Optional[Announcement]:
        """根据ID获取公告"""
        for announcement in self._db.get_all_announcements(active_only=False):
            if announcement.id == announcement_id:
                return announcement
        return None

    def create_announcement(self, title: str, content: str, announcement_type: str = 'normal', 
                           sort_order: int = None, creator: str = '') -> Announcement:
        """创建公告"""
        all_announcements = self._db.get_all_announcements(active_only=False)
        
        if sort_order is None:
            if all_announcements:
                sort_order = max(a.sort_order for a in all_announcements) + 1
            else:
                sort_order = 0
        
        announcement = Announcement(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            announcement_type=announcement_type,
            is_active=True,
            sort_order=sort_order,
            creator=creator,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        self._db.save_announcement(announcement)
        
        # 如果是特殊公告，检查是否超过3条
        if announcement_type == 'special':
            active_special = [a for a in self._db.get_all_announcements(active_only=True) 
                            if a.announcement_type == 'special']
            if len(active_special) > 3:
                active_special_sorted = sorted(active_special, key=lambda x: x.create_time or datetime.min)
                for old_announcement in active_special_sorted[:-3]:
                    old_announcement.is_active = False
                    old_announcement.update_time = datetime.now()
                    self._db.save_announcement(old_announcement)
        
        return announcement

    def update_announcement(self, announcement_id: str, data: dict) -> Optional[Announcement]:
        """更新公告"""
        announcement = self.get_announcement_by_id(announcement_id)
        if not announcement:
            return None
        
        if 'title' in data:
            announcement.title = data['title']
        if 'content' in data:
            announcement.content = data['content']
        if 'announcement_type' in data:
            announcement.announcement_type = data['announcement_type']
        if 'sort_order' in data:
            announcement.sort_order = data['sort_order']
        
        announcement.update_time = datetime.now()
        
        # 如果更新为特殊公告，检查是否超过3条
        if announcement.announcement_type == 'special' and announcement.is_active:
            active_special = [a for a in self._db.get_all_announcements(active_only=True) 
                            if a.announcement_type == 'special']
            if len(active_special) > 3:
                active_special_sorted = sorted(active_special, key=lambda x: x.create_time or datetime.min)
                for old_announcement in active_special_sorted[:-3]:
                    if old_announcement.id != announcement_id:
                        old_announcement.is_active = False
                        old_announcement.update_time = datetime.now()
                        self._db.save_announcement(old_announcement)
        
        self._db.save_announcement(announcement)
        return announcement

    def toggle_announcement_status(self, announcement_id: str) -> Optional[Announcement]:
        """切换公告上架/下架状态"""
        announcement = self.get_announcement_by_id(announcement_id)
        if not announcement:
            return None
        
        announcement.is_active = not announcement.is_active
        announcement.update_time = datetime.now()
        self._db.save_announcement(announcement)
        return announcement

    def delete_announcement(self, announcement_id: str) -> bool:
        """删除公告"""
        # 需要在db_store中添加删除方法
        return True

    def force_show_announcement(self, announcement_id: str) -> Optional[Announcement]:
        """再次公告 - 增加版本号让用户重新看到弹窗"""
        announcement = self.get_announcement_by_id(announcement_id)
        if not announcement:
            return None
        
        announcement.force_show_version += 1
        announcement.update_time = datetime.now()
        self._db.save_announcement(announcement)
        return announcement

    def move_announcement(self, announcement_id: str, direction: str) -> Optional[dict]:
        """移动公告顺序 - 上移或下移"""
        announcement = self.get_announcement_by_id(announcement_id)
        if not announcement:
            return None
        
        all_announcements = self._db.get_all_announcements(active_only=False)
        sorted_announcements = sorted(
            all_announcements, 
            key=lambda x: (x.sort_order, -x.create_time.timestamp() if x.create_time else 0)
        )
        
        try:
            current_index = sorted_announcements.index(announcement)
        except ValueError:
            return None
        
        if direction == 'up' and current_index == 0:
            return None
        if direction == 'down' and current_index == len(sorted_announcements) - 1:
            return None
        
        if direction == 'up':
            target_index = current_index - 1
        else:
            target_index = current_index + 1
        
        target_announcement = sorted_announcements[target_index]
        
        if announcement.sort_order == target_announcement.sort_order:
            for i, a in enumerate(sorted_announcements):
                a.sort_order = i
        
        announcement.sort_order, target_announcement.sort_order = \
            target_announcement.sort_order, announcement.sort_order
        
        announcement.update_time = datetime.now()
        target_announcement.update_time = datetime.now()
        
        self._db.save_announcement(announcement)
        self._db.save_announcement(target_announcement)
        
        return {'announcement_title': announcement.title}

    # ==================== 用户排名和点赞功能 ====================

    BORROW_TITLES = [
        "👑 借物真神", "⚔️ 借物至尊", "🔥 借物霸主", "⚡ 借物狂魔", "💀 借物死神",
        "🌟 借物王者", "🗡️ 借物战将", "🛡️ 借物勇士", "🏹 借物猎手", "🎯 借物先锋"
    ]

    RETURN_TITLES = [
        "👑 归还真神", "🔱 归还至尊", "⚜️ 归还圣者", "🛡️ 归还战神", "⚔️ 归还统领",
        "🏆 归还大师", "🌟 归还精英", "💎 归还卫士", "🎯 归还能手", "⭐ 守信先锋"
    ]

    def get_star_level(self, count: int) -> int:
        """根据次数获取星级（1-7星）"""
        if count >= 1001:
            return 7
        elif count >= 501:
            return 6
        elif count >= 201:
            return 5
        elif count >= 101:
            return 4
        elif count >= 51:
            return 3
        elif count >= 11:
            return 2
        else:
            return 1

    def get_user_rankings(self, ranking_type: str = 'borrow') -> List[dict]:
        """获取用户排名列表（使用缓存，每天0点后自动更新）"""
        # 检查是否需要更新缓存
        if self._should_update_rankings_cache():
            self._update_rankings_cache()

        # 返回缓存数据
        if ranking_type == 'points':
            cache_key = 'points'
        else:
            cache_key = 'borrow' if ranking_type == 'borrow' else 'return'
        rankings = self._rankings_cache.get(cache_key, []) or []

        # 实时更新签名（签名可能经常变化，从最新用户数据中获取）
        users_map = {u.id: u for u in self._db.get_all_users()}
        for ranking in rankings:
            user = users_map.get(ranking['user_id'])
            if user:
                ranking['signature'] = user.signature

        return rankings

    def get_user_like_count(self, user_id: str) -> int:
        """获取用户的被点赞数"""
        likes = self._db.get_user_likes_to_user(user_id)
        return len(likes)

    def get_user_today_likes(self, from_user_id: str) -> int:
        """获取用户今天已点赞的次数"""
        today = datetime.now().strftime("%Y-%m-%d")
        likes = self._db.get_user_likes_by_user(from_user_id)
        return len([like for like in likes 
                   if like.from_user_id == from_user_id and like.create_date == today])

    def add_like(self, from_user_id: str, to_user_id: str) -> tuple:
        """添加点赞"""
        if from_user_id == to_user_id:
            return False, "不能给自己点赞"
        
        today = datetime.now().strftime("%Y-%m-%d")
        likes = self._db.get_user_likes_by_user(from_user_id)
        existing_like = [like for like in likes 
                        if like.from_user_id == from_user_id 
                        and like.to_user_id == to_user_id 
                        and like.create_date == today]
        if existing_like:
            return False, "今天已经点赞过该用户"
        
        today_likes = self.get_user_today_likes(from_user_id)
        if today_likes >= 5:
            return False, "今天点赞次数已达上限（5次）"
        
        like = UserLike(
            id=str(uuid.uuid4()),
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            create_date=today,
            create_time=datetime.now()
        )
        self._db.save_user_like(like)
        
        return True, "点赞成功"

    # ==================== 预约管理 ====================

    def check_reservation_conflict(self, device_id: str, device_type: str, 
                                   start_time: datetime, end_time: datetime,
                                   exclude_id: str = None,
                                   current_user_id: str = None) -> tuple:
        """
        检查预约时间冲突
        返回: (has_conflict, conflict_info)
        current_user_id: 当前用户ID，如果是自己的预约则不视为冲突
        """
        # 1. 检查与现有预约的冲突
        existing_reservations = self._db.get_reservations_by_device(
            device_id, device_type, active_only=True
        )
        
        for r in existing_reservations:
            if exclude_id and r.id == exclude_id:
                continue
            # 如果是当前用户自己的预约，不视为冲突
            if current_user_id and r.reserver_id == current_user_id:
                continue
            # 时间重叠检测
            if not (end_time <= r.start_time or start_time >= r.end_time):
                return True, {
                    "type": "reservation",
                    "conflict_with": r.reserver_name,
                    "reserver_id": r.reserver_id,
                    "start_time": r.start_time,
                    "end_time": r.end_time
                }
        
        # 2. 检查与当前借用的冲突（借用中设备）
        device = self._db.get_device_by_id(device_id)
        if device and device.status == DeviceStatus.BORROWED:
            # 如果是当前借用人自己，不视为冲突
            if current_user_id and device.borrower_id == current_user_id:
                return False, None
            # 如果有预计归还时间，检查是否重叠
            if device.expected_return_date:
                if start_time < device.expected_return_date:
                    return True, {
                        "type": "current_borrow",
                        "conflict_with": device.borrower,
                        "borrower_id": device.borrower_id,
                        "end_time": device.expected_return_date
                    }
        
        return False, None

    def create_reservation(self, device_id: str, device_type: str,
                          reserver_id: str, reserver_name: str,
                          start_time: datetime, end_time: datetime,
                          reason: str = "") -> tuple:
        """
        创建预约
        返回: (success, result_or_message)
        """
        # 获取设备信息
        device = self._db.get_device_by_id(device_id)
        if not device:
            return False, "设备不存在"
        
        # 检查设备状态
        if device.status == DeviceStatus.SCRAPPED:
            return False, "该设备已报废，无法预约"
        if device.status == DeviceStatus.DAMAGED:
            return False, "该设备已损坏，无法预约"
        if device.status == DeviceStatus.LOST:
            return False, "该设备已丢失，无法预约"
        if device.status == DeviceStatus.SEALED:
            return False, "该设备已封存，无法预约"
        
        # 检查设备是否逾期（借用中且逾期的设备不能预约）
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            if datetime.now() > device.expected_return_date:
                return False, "该设备已逾期，需要原借用人归还后才能预约"
        
        # 检查用户是否正在借用该设备（自己借用自己预约的情况）
        if device.status == DeviceStatus.BORROWED and device.borrower_id == reserver_id:
            # 用户正在借用该设备，将预约转为续期意图
            # 检查预约时间是否在当前借用之后
            if start_time > device.borrow_time:
                # 允许创建预约，但标记为自动续期类型
                pass  # 继续创建预约流程
        
        # 检查时间冲突（只检查与现有预约的冲突，借用中设备可以预约）
        has_conflict, conflict_info = self.check_reservation_conflict(
            device_id, device_type, start_time, end_time, current_user_id=reserver_id
        )
        if has_conflict:
            if conflict_info["type"] == "reservation":
                return False, (
                    f"当前时段已被预约，需要让 {conflict_info['conflict_with']} "
                    f"取消借用或更改预约借用时段"
                )
            # 借用中设备不阻止预约，后面会处理确认流程
        
        # 确定预约状态
        status = ReservationStatus.APPROVED.value
        custodian_id = device.custodian_id if hasattr(device, 'custodian_id') else ""
        current_borrower_id = ""
        current_borrower_name = ""
        
        if device.status == DeviceStatus.IN_CUSTODY:
            # 保管中设备 - 需要保管人确认
            status = ReservationStatus.PENDING_CUSTODIAN.value
        elif device.status == DeviceStatus.BORROWED:
            # 借用中设备
            current_borrower_id = device.borrower_id
            current_borrower_name = device.borrower
            
            # 检查时间是否重合
            if device.expected_return_date and start_time < device.expected_return_date:
                # 时间重合，需要当前借用人确认
                if custodian_id:
                    # 有保管人，需要双方确认
                    status = ReservationStatus.PENDING_BOTH.value
                else:
                    # 无保管人，只需要借用人确认
                    status = ReservationStatus.PENDING_BORROWER.value
            else:
                # 时间不重合，无需确认
                status = ReservationStatus.APPROVED.value
        
        # 创建预约
        reservation = Reservation(
            id=str(uuid.uuid4()),
            device_id=device_id,
            device_type=device_type,
            device_name=device.name,
            reserver_id=reserver_id,
            reserver_name=reserver_name,
            start_time=start_time,
            end_time=end_time,
            status=status,
            custodian_id=custodian_id,
            current_borrower_id=current_borrower_id,
            current_borrower_name=current_borrower_name,
            reason=reason
        )
        
        self._db.save_reservation(reservation)
        
        # 发送通知
        if status == ReservationStatus.PENDING_CUSTODIAN.value:
            # 通知保管人
            self._notify_custodian_reservation_pending(reservation)
        elif status == ReservationStatus.PENDING_BORROWER.value:
            # 通知当前借用人
            self._notify_borrower_reservation_pending(reservation)
        elif status == ReservationStatus.PENDING_BOTH.value:
            # 通知保管人和借用人
            self._notify_custodian_reservation_pending(reservation)
            self._notify_borrower_reservation_pending(reservation)
        
        return True, reservation

    def approve_reservation(self, reservation_id: str, approver_id: str, 
                           approver_role: str) -> tuple:
        """
        同意预约
        approver_role: 'custodian' 或 'borrower'
        返回: (success, message)
        """
        reservation = self._db.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在"
        
        if reservation.status in [ReservationStatus.CANCELLED.value, 
                                  ReservationStatus.REJECTED.value,
                                  ReservationStatus.EXPIRED.value]:
            return False, "该预约已失效"
        
        if reservation.status == ReservationStatus.APPROVED.value:
            return False, "该预约已被同意"
        
        now = datetime.now()
        
        if approver_role == 'custodian':
            # 保管人同意
            if reservation.custodian_approved:
                return False, "您已同意过该预约"
            
            reservation.custodian_approved = True
            reservation.custodian_approved_at = now
            
            # 更新状态
            if reservation.status == ReservationStatus.PENDING_CUSTODIAN.value:
                reservation.status = ReservationStatus.APPROVED.value
            elif reservation.status == ReservationStatus.PENDING_BOTH.value:
                if reservation.borrower_approved:
                    reservation.status = ReservationStatus.APPROVED.value
                else:
                    reservation.status = ReservationStatus.PENDING_BORROWER.value
        
        elif approver_role == 'borrower':
            # 借用人同意
            if reservation.borrower_approved:
                return False, "您已同意过该预约"
            
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
        self._db.save_reservation(reservation)
        
        # 如果已同意，通知预约人
        if reservation.status == ReservationStatus.APPROVED.value:
            self._notify_reserver_reservation_approved(reservation)
        
        return True, "同意成功"

    def reject_reservation(self, reservation_id: str, rejected_by: str, 
                          reason: str = "") -> tuple:
        """
        拒绝预约
        返回: (success, message)
        """
        reservation = self._db.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在"
        
        if reservation.status in [ReservationStatus.CANCELLED.value, 
                                  ReservationStatus.REJECTED.value,
                                  ReservationStatus.EXPIRED.value]:
            return False, "该预约已失效"
        
        reservation.status = ReservationStatus.REJECTED.value
        reservation.rejected_by = rejected_by
        reservation.rejected_at = datetime.now()
        reservation.updated_at = datetime.now()
        
        self._db.save_reservation(reservation)
        
        # 通知预约人
        self._notify_reserver_reservation_rejected(reservation, rejected_by)
        
        return True, "拒绝成功"

    def cancel_reservation(self, reservation_id: str, cancelled_by: str,
                          reason: str = "") -> tuple:
        """
        取消预约
        返回: (success, message)
        """
        reservation = self._db.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在"
        
        if reservation.status in [ReservationStatus.CANCELLED.value, 
                                  ReservationStatus.REJECTED.value,
                                  ReservationStatus.EXPIRED.value,
                                  ReservationStatus.CONVERTED.value]:
            return False, "该预约已无法取消"
        
        reservation.status = ReservationStatus.CANCELLED.value
        reservation.cancelled_by = cancelled_by
        reservation.cancelled_at = datetime.now()
        reservation.cancel_reason = reason
        reservation.updated_at = datetime.now()
        
        self._db.save_reservation(reservation)
        
        return True, "取消成功"

    def delete_reservation(self, reservation_id: str, user_id: str) -> tuple:
        """
        删除预约（仅已拒绝、已取消、已过期的可删除）
        返回: (success, message)
        """
        reservation = self._db.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在"
        
        # 只能删除自己的预约
        if reservation.reserver_id != user_id:
            return False, "只能删除自己的预约"
        
        if reservation.status not in [ReservationStatus.REJECTED.value,
                                      ReservationStatus.CANCELLED.value,
                                      ReservationStatus.EXPIRED.value]:
            return False, "只能删除已拒绝、已取消或过期的预约"
        
        self._db.delete_reservation(reservation_id)
        return True, "删除成功"

    def get_device_reservations(self, device_id: str, device_type: str = None,
                                active_only: bool = False) -> List[Reservation]:
        """获取设备的预约列表"""
        return self._db.get_reservations_by_device(device_id, device_type, active_only=active_only)

    def get_user_reservations(self, user_id: str, status: str = None) -> List[Reservation]:
        """获取用户的预约列表"""
        return self._db.get_reservations_by_reserver(user_id, status)

    def get_pending_reservations_for_user(self, user_id: str, role: str) -> List[Reservation]:
        """获取用户需要处理的预约"""
        if role == 'custodian':
            return self._db.get_reservations_by_custodian(user_id, pending_only=True)
        elif role == 'borrower':
            return self._db.get_reservations_by_borrower(user_id, pending_only=True)
        return []

    def convert_reservation_to_borrow(self, reservation_id: str) -> tuple:
        """
        将预约转为借用（定时任务调用）
        返回: (success, message)
        """
        reservation = self._db.get_reservation_by_id(reservation_id)
        if not reservation:
            return False, "预约不存在"
        
        if reservation.status != ReservationStatus.APPROVED.value:
            return False, "预约状态不正确"
        
        if reservation.converted_to_borrow:
            return False, "该预约已转为借用"
        
        # 获取设备
        device = self._db.get_device_by_id(reservation.device_id)
        if not device:
            return False, "设备不存在"
        
        # 检查设备状态
        if device.status == DeviceStatus.BORROWED:
            # 如果当前借用人就是预约人，自动续期
            if device.borrower_id == reservation.reserver_id:
                # 自动续期：只更新预计归还时间
                device.expected_return_date = reservation.end_time
                self._db.save_device(device)
                
                # 更新预约状态
                reservation.converted_to_borrow = True
                reservation.converted_at = datetime.now()
                reservation.status = ReservationStatus.CONVERTED.value
                reservation.updated_at = datetime.now()
                self._db.save_reservation(reservation)
                
                # 创建续期记录
                record = Record(
                    id=str(uuid.uuid4()),
                    device_id=device.id,
                    device_name=device.name,
                    device_type=device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
                    operation_type=OperationType.RENEW,
                    operator=reservation.reserver_name,
                    operation_time=datetime.now(),
                    borrower=reservation.reserver_name,
                    reason=f"预约自动续期至 {reservation.end_time.strftime('%Y-%m-%d %H:%M')}",
                    entry_source="预约自动续期"
                )
                self._db.save_record(record)
                
                # 通知用户续期成功
                self.add_notification(
                    user_id=reservation.reserver_id,
                    user_name=reservation.reserver_name,
                    title="预约自动续期成功",
                    content=f"您预约的 {reservation.device_name} 已自动续期，借用时间延长至 {reservation.end_time.strftime('%Y-%m-%d %H:%M')}",
                    device_name=reservation.device_name,
                    device_id=reservation.device_id,
                    notification_type="success"
                )
                
                return True, "预约自动续期成功"
            else:
                # 设备被其他人借用，无法转换
                # 通知预约人
                self._notify_reserver_device_not_available(reservation)
                reservation.status = ReservationStatus.CANCELLED.value
                reservation.cancel_reason = "设备已被他人借用，无法转为借用"
                reservation.updated_at = datetime.now()
                self._db.save_reservation(reservation)
                return False, "设备已被他人借用"
        
        # 执行借用（设备未被借用的情况）
        device.status = DeviceStatus.BORROWED
        device.borrower = reservation.reserver_name
        device.borrower_id = reservation.reserver_id
        device.borrow_time = datetime.now()
        device.expected_return_date = reservation.end_time
        device.reason = reservation.reason
        device.entry_source = "预约借用"
        
        self._db.save_device(device)
        
        # 更新预约状态
        reservation.converted_to_borrow = True
        reservation.converted_at = datetime.now()
        reservation.status = ReservationStatus.CONVERTED.value
        reservation.updated_at = datetime.now()
        self._db.save_reservation(reservation)
        
        # 创建借还记录 - 修改借用人和原因显示
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device.id,
            device_name=device.name,
            device_type=device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
            operation_type=OperationType.BORROW,
            operator=reservation.reserver_name,
            operation_time=datetime.now(),
            borrower=f"自动借用：{reservation.reserver_name}",
            reason=f"预约时间已到，原预约借用",
            entry_source="预约借用"
        )
        self._db.save_record(record)
        
        # 通知预约人
        self._notify_reserver_reservation_converted(reservation)
        
        # 通知原借用人（如果设备之前有借用人）
        if reservation.current_borrower_id and reservation.current_borrower_id != reservation.reserver_id:
            self._notify_original_borrower_reservation_converted(reservation, device)
        
        # 通知保管人（如果存在）
        if reservation.custodian_id:
            self._notify_custodian_reservation_converted(reservation, device)
        
        return True, "转为借用成功"

    def expire_reservation(self, reservation_id: str) -> bool:
        """将预约标记为过期（定时任务调用）"""
        reservation = self._db.get_reservation_by_id(reservation_id)
        if not reservation:
            return False
        
        if reservation.status in [ReservationStatus.PENDING_CUSTODIAN.value,
                                  ReservationStatus.PENDING_BORROWER.value,
                                  ReservationStatus.PENDING_BOTH.value]:
            reservation.status = ReservationStatus.EXPIRED.value
            reservation.updated_at = datetime.now()
            self._db.save_reservation(reservation)
            
            # 通知预约人
            self._notify_reserver_reservation_expired(reservation)
            return True
        
        return False

    def cancel_reservations_by_device_status_change(self, device_id: str, 
                                                     new_status: str,
                                                     operator: str) -> int:
        """
        设备状态变更时取消相关预约（损坏、丢失、报废、封存等）
        返回取消的预约数量
        """
        if new_status not in [DeviceStatus.DAMAGED.value, DeviceStatus.LOST.value,
                              DeviceStatus.SCRAPPED.value, DeviceStatus.SEALED.value]:
            return 0
        
        reservations = self._db.get_reservations_by_device(device_id, active_only=True)
        cancelled_count = 0
        
        for r in reservations:
            if r.status in [ReservationStatus.APPROVED.value,
                           ReservationStatus.PENDING_CUSTODIAN.value,
                           ReservationStatus.PENDING_BORROWER.value,
                           ReservationStatus.PENDING_BOTH.value]:
                r.status = ReservationStatus.CANCELLED.value
                r.cancelled_by = "system"
                r.cancelled_at = datetime.now()
                r.cancel_reason = f"设备已{new_status}，无法预约"
                r.updated_at = datetime.now()
                self._db.save_reservation(r)
                
                # 通知预约人
                self._notify_reserver_reservation_cancelled_by_status(r, new_status)
                cancelled_count += 1
        
        return cancelled_count

    def check_transfer_conflict(self, device_id: str) -> dict:
        """
        检查转借时是否有预约冲突
        返回: {'has_conflict': bool, 'reservations': list}
        冲突定义：任何已同意或待确认的预约，且预约时间包含当前时间或与转借后借用时间重叠
        """
        now = datetime.now()
        reservations = self._db.get_reservations_by_device(device_id)
        
        conflict_reservations = []
        for r in reservations:
            # 跳过已取消、已拒绝、已过期、已转借用的预约
            if r.status in [ReservationStatus.CANCELLED.value,
                           ReservationStatus.REJECTED.value,
                           ReservationStatus.EXPIRED.value,
                           ReservationStatus.CONVERTED.value]:
                continue
            
            # 检查预约时间是否与当前时间重叠（即预约正在进行中或即将开始）
            # 转借后新借用人预计借用1天，所以检查当前时间是否在预约时间内
            # 或者预约开始时间在转借后的借用期内
            if r.start_time <= now <= r.end_time:
                # 当前正在进行中的预约
                conflict_reservations.append(r)
            elif r.start_time > now:
                # 未来的预约
                conflict_reservations.append(r)
        
        return {
            'has_conflict': len(conflict_reservations) > 0,
            'reservations': conflict_reservations
        }

    def cancel_reservations_due_to_transfer(self, device_id: str, 
                                           transfer_to: str,
                                           cancelled_by: str) -> int:
        """
        强制转借时取消相关预约
        返回取消的预约数量
        """
        now = datetime.now()
        device = self._db.get_device_by_id(device_id)
        reservations = self._db.get_reservations_by_device(device_id)
        
        cancelled_count = 0
        for r in reservations:
            # 取消已同意的未来预约
            if r.status == ReservationStatus.APPROVED.value and r.start_time > now:
                r.status = ReservationStatus.CANCELLED.value
                r.cancelled_by = cancelled_by
                r.cancelled_at = datetime.now()
                r.cancel_reason = f"设备被强制转借给{transfer_to}，预约自动取消"
                r.updated_at = datetime.now()
                self._db.save_reservation(r)
                
                # 通知预约人
                self._notify_reserver_reservation_cancelled_by_transfer(r, transfer_to)
                
                # 记录操作日志
                self.add_operation_log(
                    f"强制转借取消预约",
                    f"设备: {r.device_name}, 预约人: {r.reserver_name}, 转借给: {transfer_to}"
                )
                cancelled_count += 1
            
            # 拒绝待确认的预约
            elif r.status in [ReservationStatus.PENDING_CUSTODIAN.value,
                             ReservationStatus.PENDING_BORROWER.value,
                             ReservationStatus.PENDING_BOTH.value]:
                r.status = ReservationStatus.REJECTED.value
                r.rejected_by = cancelled_by
                r.rejected_at = datetime.now()
                r.updated_at = datetime.now()
                self._db.save_reservation(r)
                
                # 通知预约人
                self._notify_reserver_reservation_rejected(r, cancelled_by, 
                    reason=f"设备已被强制转借给{transfer_to}")
                
                # 记录操作日志
                self.add_operation_log(
                    f"强制转借拒绝预约",
                    f"设备: {r.device_name}, 预约人: {r.reserver_name}, 转借给: {transfer_to}"
                )
                cancelled_count += 1
        
        # 通知保管人（如果设备有保管人）
        if device and hasattr(device, 'custodian_id') and device.custodian_id:
            custodian_user = None
            for u in self._users:
                if u.id == device.custodian_id:
                    custodian_user = u
                    break
            if custodian_user and custodian_user.borrower_name != cancelled_by:
                self.add_notification(
                    user_id=custodian_user.id,
                    user_name=custodian_user.borrower_name,
                    title="设备强制转借通知",
                    content=f"您保管的设备「{device.name}」已被强制转借给 {transfer_to}，相关预约已自动取消",
                    device_name=device.name,
                    device_id=device.id,
                    notification_type="warning"
                )
        
        return cancelled_count

    # ==================== 预约通知方法 ====================

    def _notify_custodian_reservation_pending(self, reservation: Reservation):
        """通知保管人有待确认的预约"""
        if not reservation.custodian_id:
            return
        
        self.add_notification(
            user_id=reservation.custodian_id,
            user_name="",
            title="设备预约申请",
            content=(
                f"{reservation.reserver_name} 预约了 {reservation.device_name}，"
                f"预约时间：{reservation.start_time.strftime('%Y-%m-%d %H:%M')} 至 "
                f"{reservation.end_time.strftime('%Y-%m-%d %H:%M')}，"
                f"请确认是否同意"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="warning"
        )
        reservation.custodian_notified = True
        self._db.save_reservation(reservation)

    def _notify_borrower_reservation_pending(self, reservation: Reservation):
        """通知当前借用人有待确认的预约"""
        user_id = reservation.current_borrower_id
        user_name = reservation.current_borrower_name
        
        # 如果 borrower_id 为空，尝试通过 borrower_name 查找用户
        if not user_id and user_name:
            for user in self._db.get_all_users():
                if user.borrower_name == user_name:
                    user_id = user.id
                    break
        
        if not user_id:
            return
        
        self.add_notification(
            user_id=user_id,
            user_name=user_name,
            title="设备预约申请",
            content=(
                f"{reservation.reserver_name} 预约了 {reservation.device_name}，"
                f"与您当前借用时间重合，请确认是否同意"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="warning"
        )
        reservation.borrower_notified = True
        self._db.save_reservation(reservation)

    def _notify_reserver_reservation_approved(self, reservation: Reservation):
        """通知预约人预约已同意"""
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约已同意",
            content=(
                f"您预约的 {reservation.device_name} 已被同意，"
                f"将在预约时间自动转为借用"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="success"
        )

    def _notify_reserver_reservation_rejected(self, reservation: Reservation, 
                                              rejected_by: str, reason: str = ""):
        """通知预约人预约被拒绝"""
        content = f"您预约的 {reservation.device_name} 已被 {rejected_by} 拒绝"
        if reason:
            content += f"，原因：{reason}"
        
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约被拒绝",
            content=content,
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="error"
        )

    def _notify_reserver_reservation_expired(self, reservation: Reservation):
        """通知预约人预约已过期"""
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约已过期",
            content=(
                f"您预约的 {reservation.device_name} 因未及时处理已过期，"
                f"如需借用请重新预约"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="warning"
        )

    def _notify_reserver_reservation_converted(self, reservation: Reservation):
        """通知预约人预约已转为借用"""
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约已转为借用",
            content=(
                f"您预约的 {reservation.device_name} 已自动转为借用，"
                f"借用时间至 {reservation.end_time.strftime('%Y-%m-%d %H:%M')}"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="success"
        )

    def _notify_reserver_device_not_available(self, reservation: Reservation):
        """通知预约人设备不可用"""
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约取消",
            content=(
                f"您预约的 {reservation.device_name} 因设备仍在借用中，"
                f"无法按时转为借用，预约已自动取消"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="error"
        )

    def _notify_reserver_reservation_cancelled_by_status(self, reservation: Reservation,
                                                         new_status: str):
        """通知预约人因设备状态变更被取消"""
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约已取消",
            content=f"您预约的 {reservation.device_name} 因设备已{new_status}而自动取消",
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="error"
        )

    def _notify_reserver_reservation_cancelled_by_transfer(self, reservation: Reservation,
                                                           transfer_to: str):
        """通知预约人因设备被转借被取消"""
        self.add_notification(
            user_id=reservation.reserver_id,
            user_name=reservation.reserver_name,
            title="预约已被取消",
            content=(
                f"您预约的 {reservation.device_name} 因设备被转借给 {transfer_to} "
                f"而自动取消，原预约时间：{reservation.start_time.strftime('%Y-%m-%d %H:%M')} 至 "
                f"{reservation.end_time.strftime('%Y-%m-%d %H:%M')}"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="error"
        )

    def _notify_original_borrower_reservation_converted(self, reservation: Reservation, device):
        """通知原借用人预约已转为借用（自动转借给预约人）"""
        self.add_notification(
            user_id=reservation.current_borrower_id,
            user_name=reservation.current_borrower_name,
            title="设备自动转借通知",
            content=(
                f"{reservation.device_name} 设备预约时间已到，"
                f"已自动转借给 {reservation.reserver_name}"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="info"
        )

    def _notify_custodian_reservation_converted(self, reservation: Reservation, device):
        """通知保管人预约已转为借用"""
        self.add_notification(
            user_id=reservation.custodian_id,
            user_name="",
            title="设备自动转借通知",
            content=(
                f"{reservation.device_name} 设备预约时间已到，"
                f"已自动转借给 {reservation.reserver_name}"
            ),
            device_name=reservation.device_name,
            device_id=reservation.device_id,
            notification_type="info"
        )

    def process_reservations_schedule(self):
        """
        定时任务：处理预约
        1. 将到期的已同意预约转为借用
        2. 将过期的待确认预约标记为过期
        3. 清理已结束超过7天的预约记录
        """
        now = datetime.now()
        
        # 1. 处理到期的已同意预约
        pending_convert = self._db.get_pending_reservations_to_convert()
        for r in pending_convert:
            try:
                self.convert_reservation_to_borrow(r.id)
            except Exception as e:
                print(f"转换预约失败 {r.id}: {e}")
        
        # 2. 处理过期的待确认预约
        expired_pending = self._db.get_expired_pending_reservations()
        for r in expired_pending:
            try:
                self.expire_reservation(r.id)
            except Exception as e:
                print(f"标记预约过期失败 {r.id}: {e}")
        
        # 3. 清理已结束超过7天的预约记录
        try:
            self._cleanup_old_reservations()
        except Exception as e:
            print(f"清理旧预约记录失败: {e}")
    
    def _cleanup_old_reservations(self):
        """清理已结束超过7天的预约记录"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=7)
        
        # 获取需要清理的预约（已结束超过7天的）
        reservations_to_cleanup = self._db.get_reservations_to_cleanup(cutoff_date)
        
        cleanup_count = 0
        for r in reservations_to_cleanup:
            try:
                self._db.delete_reservation(r.id)
                cleanup_count += 1
            except Exception as e:
                print(f"删除旧预约记录失败 {r.id}: {e}")
        
        if cleanup_count > 0:
            print(f"已清理 {cleanup_count} 条旧预约记录")
    
    def send_overdue_email_reminders(self):
        """
        发送逾期提醒邮件
        逻辑：
        1. 逾期前1小时发送第一次提醒
        2. 逾期前10分钟发送第二次提醒
        3. 逾期后每24小时发送一次提醒
        4. 如果借用时间小于1小时，只在逾期前10分钟发送一次
        """
        from datetime import timedelta

        all_devices = self.get_all_devices()
        now = datetime.now()

        for device in all_devices:
            if (device.status == DeviceStatus.BORROWED and
                device.expected_return_date and
                device.borrower_id):

                user = self._db.get_user_by_id(device.borrower_id)
                if not user or not user.email:
                    continue

                # 计算借用时长（从借出到预计归还的时间）
                if device.borrow_time:
                    borrow_duration = device.expected_return_date - device.borrow_time
                    borrow_duration_hours = borrow_duration.total_seconds() / 3600
                else:
                    borrow_duration_hours = 24  # 默认24小时

                # 计算距离逾期的时间差
                time_until_overdue = device.expected_return_date - now
                minutes_until_overdue = time_until_overdue.total_seconds() / 60

                # 计算已逾期的时间
                if now > device.expected_return_date:
                    overdue_duration = now - device.expected_return_date
                    overdue_hours = overdue_duration.total_seconds() / 3600
                else:
                    overdue_hours = 0

                should_send = False
                email_type = None
                email_content = None

                # 情况1：借用时间小于1小时，只在逾期前10分钟发送
                if borrow_duration_hours < 1:
                    if 5 <= minutes_until_overdue <= 10:
                        # 检查是否已经发送过10分钟提醒
                        if not self._db.has_email_sent_within_hours(
                            user.id, 'overdue_10min', device.id):
                            should_send = True
                            email_type = 'overdue_10min'
                            email_content = f"设备 {device.name} 将在10分钟内逾期"

                else:
                    # 情况2：借用时间大于等于1小时

                    # 逾期前1小时提醒
                    if 55 <= minutes_until_overdue <= 60:
                        if not self._db.has_email_sent_within_hours(
                            user.id, 'overdue_1hour', device.id):
                            should_send = True
                            email_type = 'overdue_1hour'
                            email_content = f"设备 {device.name} 将在1小时内逾期"

                    # 逾期前10分钟提醒
                    elif 5 <= minutes_until_overdue <= 10:
                        if not self._db.has_email_sent_within_hours(
                            user.id, 'overdue_10min', device.id):
                            should_send = True
                            email_type = 'overdue_10min'
                            email_content = f"设备 {device.name} 将在10分钟内逾期"

                    # 逾期后每24小时提醒
                    elif overdue_hours > 0:
                        # 检查是否是24小时的整数倍（允许5分钟误差）
                        hours_mod = overdue_hours % 24
                        if hours_mod <= 0.5 or hours_mod >= 23.5:
                            if not self._db.has_email_sent_today(
                                user.id, 'overdue_daily', device.id):
                                should_send = True
                                email_type = 'overdue_daily'
                                email_content = f"设备 {device.name} 已逾期{int(overdue_hours)}小时"

                if should_send and email_type:
                    self._send_overdue_email_async(
                        user, device, email_type, email_content
                    )

    def _send_overdue_email_async(self, user, device, email_type: str, content: str):
        """异步发送逾期提醒邮件"""
        def send_email():
            try:
                # 计算逾期信息
                now = datetime.now()
                if now > device.expected_return_date:
                    overdue_days = (now.date() - device.expected_return_date.date()).days
                    overdue_hours = int((now - device.expected_return_date).total_seconds() // 3600)
                else:
                    overdue_days = 0
                    overdue_hours = 0

                # 根据邮件类型确定提醒类型
                if email_type == 'overdue_1hour':
                    reminder_type = '1hour'
                elif email_type == 'overdue_10min':
                    reminder_type = '10min'
                else:
                    reminder_type = 'daily'

                devices_data = [{
                    'name': device.name,
                    'device_type': self._get_device_type_str(device),
                    'overdue_days': overdue_days if overdue_days > 0 else 1
                }]

                success = email_sender.send_overdue_reminder(
                    to_email=user.email,
                    borrower_name=user.borrower_name,
                    devices=devices_data,
                    reminder_type=reminder_type
                )

                if success:
                    # 记录邮件发送日志
                    self._db.save_email_log(
                        user_id=user.id,
                        user_email=user.email,
                        email_type=email_type,
                        related_id=device.id,
                        related_type='device',
                        status='sent',
                        content=content
                    )
                    print(f"逾期提醒邮件发送成功: {user.email} - {email_type}")
                else:
                    print(f"逾期提醒邮件发送失败: {user.email} - {email_type}")

            except Exception as e:
                print(f"发送逾期提醒邮件失败 {user.email}: {e}")

        email_executor.submit(send_email)
    
    def send_reservation_pending_email_reminders(self):
        """
        发送预约待确认提醒邮件
        逻辑：
        1. 预约创建后立即发送邮件
        2. 如果未处理，每24小时后发送一次提醒
        """
        from datetime import timedelta

        # 获取所有待确认的预约
        pending_reservations = []

        # 待保管人确认
        pending_reservations.extend(
            self._db.get_reservations_by_status(ReservationStatus.PENDING_CUSTODIAN.value)
        )

        # 待借用人确认
        pending_reservations.extend(
            self._db.get_reservations_by_status(ReservationStatus.PENDING_BORROWER.value)
        )

        # 待2人确认
        pending_reservations.extend(
            self._db.get_reservations_by_status(ReservationStatus.PENDING_BOTH.value)
        )

        # 去重：使用预约ID去重
        seen_ids = set()
        unique_reservations = []
        for r in pending_reservations:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_reservations.append(r)

        for reservation in unique_reservations:
            try:
                # 根据状态确定需要通知谁
                if reservation.status == ReservationStatus.PENDING_CUSTODIAN.value:
                    # 通知保管人
                    if reservation.custodian_id:
                        custodian = self._db.get_user_by_id(reservation.custodian_id)
                        if custodian and custodian.email:
                            self._send_reservation_email_if_needed(
                                custodian, reservation, 'custodian'
                            )

                elif reservation.status == ReservationStatus.PENDING_BORROWER.value:
                    # 通知当前借用人
                    if reservation.current_borrower_id:
                        borrower = self._db.get_user_by_id(reservation.current_borrower_id)
                        if borrower and borrower.email:
                            self._send_reservation_email_if_needed(
                                borrower, reservation, 'borrower'
                            )

                elif reservation.status == ReservationStatus.PENDING_BOTH.value:
                    # 通知双方
                    # 通知保管人
                    if reservation.custodian_id:
                        custodian = self._db.get_user_by_id(reservation.custodian_id)
                        if custodian and custodian.email:
                            self._send_reservation_email_if_needed(
                                custodian, reservation, 'custodian'
                            )

                    # 通知借用人
                    if reservation.current_borrower_id:
                        borrower = self._db.get_user_by_id(reservation.current_borrower_id)
                        if borrower and borrower.email:
                            self._send_reservation_email_if_needed(
                                borrower, reservation, 'borrower'
                            )

            except Exception as e:
                print(f"发送预约待确认提醒邮件失败 {reservation.id}: {e}")

    def _send_reservation_email_if_needed(self, user, reservation, role: str):
        """
        检查并发送预约邮件
        逻辑：
        1. 如果从未发送过，立即发送
        2. 如果已发送过，每24小时发送一次
        """
        email_type = f'reservation_pending_{role}'

        # 检查是否已经发送过
        last_sent = self._db.get_last_email_sent_time(user.id, email_type, reservation.id)

        should_send = False
        if not last_sent:
            # 从未发送过，立即发送
            should_send = True
        else:
            # 检查是否已经过了24小时
            time_since_last = datetime.now() - last_sent
            if time_since_last.total_seconds() >= 24 * 3600:
                should_send = True

        if should_send:
            self._send_reservation_email_async(user, reservation, role, email_type)

    def _send_reservation_email_async(self, user, reservation, role: str, email_type: str):
        """异步发送预约提醒邮件"""
        def send_email():
            try:
                success = email_sender.send_reservation_pending_reminder(
                    to_email=user.email,
                    recipient_name=user.borrower_name,
                    device_name=reservation.device_name,
                    device_type=reservation.device_type,
                    start_time=reservation.start_time,
                    end_time=reservation.end_time,
                    reserver_name=reservation.reserver_name,
                    role=role
                )

                if success:
                    # 记录邮件发送日志
                    content = f"预约确认提醒：{reservation.reserver_name} 预约了 {reservation.device_name}"
                    self._db.save_email_log(
                        user_id=user.id,
                        user_email=user.email,
                        email_type=email_type,
                        related_id=reservation.id,
                        related_type='reservation',
                        status='sent',
                        content=content
                    )
                    print(f"预约确认提醒邮件发送成功: {user.email} - {role}")
                else:
                    print(f"预约确认提醒邮件发送失败: {user.email} - {role}")

            except Exception as e:
                print(f"发送预约确认提醒邮件失败 {user.email}: {e}")

        email_executor.submit(send_email)


# 全局 API 客户端实例
api_client = APIClient()
