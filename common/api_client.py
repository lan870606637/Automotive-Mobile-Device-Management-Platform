# -*- coding: utf-8 -*-
"""
数据客户端
从SQLite数据库读取和保存数据
"""
import uuid
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, ViewRecord, Notification, Announcement, UserLike
from .models import DeviceStatus, DeviceType, OperationType, EntrySource, Admin
from .db_store import DatabaseStore, get_db_transaction

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
        """检查是否需要更新排行榜缓存（每天12点后更新）"""
        if self._rankings_cache['last_update'] is None:
            return True

        now = datetime.now()
        last_update = self._rankings_cache['last_update']

        # 如果上次更新是昨天或更早，且现在过了12点，需要更新
        if now.date() > last_update.date():
            return True

        # 如果上次更新在今天12点之前，且现在过了12点，需要更新
        noon_today = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now >= noon_today and last_update < noon_today:
            return True

        return False

    def _update_rankings_cache(self):
        """更新排行榜缓存"""
        self._rankings_cache['borrow'] = self._calculate_rankings('borrow')
        self._rankings_cache['return'] = self._calculate_rankings('return')
        self._rankings_cache['last_update'] = datetime.now()

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
                'count': count,
                'title': title,
                'star_level': star_level,
                'like_count': like_count
            })

        return rankings

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
    
    def update_device(self, device: Device) -> bool:
        """更新设备信息"""
        existing = self._db.get_device_by_id(device.id)
        if existing:
            self._db.save_device(device)
            self.add_operation_log(f"更新设备信息", device.name)
            return True
        return False
    
    def delete_device(self, device_id: str) -> bool:
        """软删除设备"""
        device = self._db.get_device_by_id(device_id)
        if device:
            device.is_deleted = True
            self._db.save_device(device)
            self.add_operation_log(f"删除设备", device.name)
            return True
        return False
    
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
                     cabinet: str = '', status: str = '在库', remarks: str = '') -> Device:
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
                create_time=create_time
            )
        
        self._db.save_device(device)
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

        user.is_deleted = True
        self._db.save_user(user)
        self.add_operation_log("删除用户", user.borrower_name)
        return True, "删除成功"
    
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
    
    def add_operation_log(self, operation_content: str, device_info: str):
        """添加操作日志"""
        log = OperationLog(
            id=str(uuid.uuid4()),
            operation_time=datetime.now(),
            operator=self._current_admin,
            operation_content=operation_content,
            device_info=device_info
        )
        self._db.save_operation_log(log)
    
    def get_admin_logs(self, limit: int = 100) -> List[dict]:
        """获取管理员操作日志（用于后台管理）"""
        logs = self.get_operation_logs(limit)
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'time': log.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
                'admin_name': log.operator,
                'action_type': self._categorize_action(log.operation_content),
                'details': f"{log.operation_content}: {log.device_info}",
                'ip': ''
            })
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
        "⚔️ 借物至尊", "🔥 借物霸主", "⚡ 借物狂魔", "💀 借物死神", "🌟 借物王者",
        "🗡️ 借物战将", "🛡️ 借物勇士", "🏹 借物猎手", "🎯 借物先锋", "🔥 借物新星"
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
        """获取用户排名列表（使用缓存，每天12点后自动更新）"""
        # 检查是否需要更新缓存
        if self._should_update_rankings_cache():
            self._update_rankings_cache()

        # 返回缓存数据
        cache_key = 'borrow' if ranking_type == 'borrow' else 'return'
        return self._rankings_cache.get(cache_key, []) or []

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


# 全局 API 客户端实例
api_client = APIClient()
