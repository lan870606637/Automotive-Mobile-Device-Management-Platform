# -*- coding: utf-8 -*-
"""
Excel 数据客户端
从本地Excel文件读取和保存数据
"""
import uuid
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, ViewRecord, Notification, Announcement
from .models import DeviceStatus, DeviceType, OperationType, EntrySource, Admin
from .excel_data_store import ExcelDataStore


class APIClient:
    """API 客户端单例类"""
    _instance = None
    _initialized = False
    
    # 类属性 - 始终存在
    _current_admin: str = "管理员"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not APIClient._initialized:
            self._current_admin = "管理员"
            self._load_data()
            APIClient._initialized = True

    def _safe_print(self, message):
        """安全打印，处理Windows控制台编码问题"""
        try:
            print(message)
        except OSError:
            # 如果打印失败（如编码问题），忽略错误
            pass

    def _save_data(self):
        """保存数据到Excel文件"""
        try:
            ExcelDataStore.save_car_machines(self._car_machines)
            ExcelDataStore.save_instruments(self._instruments)
            ExcelDataStore.save_phones(self._phones)
            ExcelDataStore.save_sim_cards(self._sim_cards)
            ExcelDataStore.save_other_devices(self._other_devices)
            ExcelDataStore.save_records(self._records)
            ExcelDataStore.save_remarks(self._remarks)
            ExcelDataStore.save_users(self._users)
            ExcelDataStore.save_operation_logs(self._operation_logs)
            ExcelDataStore.save_view_records(self._view_records)
            ExcelDataStore.save_notifications(self._notifications)
            ExcelDataStore.save_announcements(self._announcements)
        except PermissionError as e:
            self._safe_print(f"警告: Excel文件被占用，无法保存数据: {e}")
            self._safe_print("请关闭所有打开的Excel文件后重试")
        except Exception as e:
            self._safe_print(f"保存数据失败: {e}")
    
    def _load_data(self):
        """从Excel文件加载数据"""
        try:
            # 从Excel加载数据
            self._car_machines = ExcelDataStore.load_car_machines()
            self._instruments = ExcelDataStore.load_instruments()
            self._phones = ExcelDataStore.load_phones()
            self._sim_cards = ExcelDataStore.load_sim_cards()
            self._other_devices = ExcelDataStore.load_other_devices()
            self._records = ExcelDataStore.load_records()
            self._remarks = ExcelDataStore.load_remarks()
            self._users = ExcelDataStore.load_users()
            
            # 如果没有数据，使用默认数据
            if not self._car_machines and not self._instruments and not self._phones and not self._sim_cards and not self._other_devices:
                self._safe_print("Excel文件为空，使用默认数据")
                self._init_mock_data()
                self._save_data()
            else:
                self._safe_print(f"从Excel加载: 车机{len(self._car_machines)}台, 仪表{len(self._instruments)}台, 手机{len(self._phones)}台, 手机卡{len(self._sim_cards)}张, 其它设备{len(self._other_devices)}台, 记录{len(self._records)}条")
                self._safe_print(f"从Excel加载: 用户{len(self._users)}个")
                # 如果用户列表为空，使用默认用户数据
                if not self._users:
                    self._safe_print("用户表为空，初始化默认用户")
                    self._init_default_users()
                    self._save_data()
            
            # 从Excel加载操作日志
            self._operation_logs = ExcelDataStore.load_operation_logs()
            self._safe_print(f"从Excel加载: 操作日志{len(self._operation_logs)}条")
            
            # 从Excel加载查看记录
            self._view_records = ExcelDataStore.load_view_records()
            self._safe_print(f"从Excel加载: 查看记录{len(self._view_records)}条")
            
            # 从Excel加载管理员列表
            self._admins = ExcelDataStore.load_admins()
            self._safe_print(f"从Excel加载: 管理员{len(self._admins)}个")
            # 如果没有管理员，创建默认管理员
            if not self._admins:
                default_admin = Admin(
                    id=str(uuid.uuid4()),
                    username="admin",
                    password="admin123",
                    create_time=datetime.now()
                )
                self._admins = [default_admin]
                ExcelDataStore.save_admins(self._admins)
                self._safe_print("已创建默认管理员: admin / admin123")

            # 从Excel加载通知列表
            self._notifications = ExcelDataStore.load_notifications()
            self._safe_print(f"从Excel加载: 通知{len(self._notifications)}条")

            # 从Excel加载公告列表
            self._announcements = ExcelDataStore.load_announcements()
            self._safe_print(f"从Excel加载: 公告{len(self._announcements)}条")

        except Exception as e:
            # 通知加载失败时使用空列表，不影响其他数据加载
            self._notifications = []
            self._announcements = []
            self._safe_print(f"加载数据失败: {e}")
    
    def _device_to_dict(self, device: Device) -> dict:
        """设备转字典"""
        return {
            'id': device.id,
            'name': device.name,
            'device_type': device.device_type.value,
            'model': device.model,
            'cabinet_number': device.cabinet_number,
            'status': device.status.value,
            'remark': device.remark,
            'jira_address': device.jira_address,
            'is_deleted': device.is_deleted,
            'create_time': device.create_time.isoformat() if device.create_time else None,
            'borrower': device.borrower,
            'phone': device.phone,
            'borrow_time': device.borrow_time.isoformat() if device.borrow_time else None,
            'location': device.location,
            'reason': device.reason,
            'entry_source': device.entry_source,
            'expected_return_date': device.expected_return_date.isoformat() if device.expected_return_date else None,
            # 车机和仪表特有字段（JIRA地址后）
            'project_attribute': device.project_attribute,
            'connection_method': device.connection_method,
            'os_version': device.os_version,
            'os_platform': device.os_platform,
            'product_name': device.product_name,
            'screen_orientation': device.screen_orientation,
            'screen_resolution': device.screen_resolution,
            # 寄出信息
            'ship_time': device.ship_time.isoformat() if device.ship_time else None,
            'ship_remark': device.ship_remark,
            'ship_by': device.ship_by,
            # 寄出前借用信息（用于还原）
            'pre_ship_borrower': device.pre_ship_borrower,
            'pre_ship_borrow_time': device.pre_ship_borrow_time.isoformat() if device.pre_ship_borrow_time else None,
            'pre_ship_expected_return_date': device.pre_ship_expected_return_date.isoformat() if device.pre_ship_expected_return_date else None,
        }
    
    def _dict_to_device(self, data: dict, cls) -> Device:
        """字典转设备"""
        create_time = None
        if data.get('create_time'):
            create_time = datetime.fromisoformat(data['create_time'])
        device = cls(
            id=data['id'],
            name=data['name'],
            model=data.get('model', ''),
            cabinet_number=data.get('cabinet_number', ''),
            status=DeviceStatus(data['status']) if data.get('status') else DeviceStatus.IN_STOCK,
            remark=data.get('remark', ''),
            jira_address=data.get('jira_address', ''),
            is_deleted=data.get('is_deleted', False),
            create_time=create_time,
        )
        device.borrower = data.get('borrower', '')
        device.phone = data.get('phone', '')
        if data.get('borrow_time'):
            device.borrow_time = datetime.fromisoformat(data['borrow_time'])
        device.location = data.get('location', '')
        device.reason = data.get('reason', '')
        device.entry_source = data.get('entry_source', '')
        if data.get('expected_return_date'):
            device.expected_return_date = datetime.fromisoformat(data['expected_return_date'])
        # 寄出信息
        device.ship_remark = data.get('ship_remark', '')
        device.ship_by = data.get('ship_by', '')
        if data.get('ship_time'):
            device.ship_time = datetime.fromisoformat(data['ship_time'])
        # 寄出前借用信息（用于还原）
        device.pre_ship_borrower = data.get('pre_ship_borrower', '')
        if data.get('pre_ship_borrow_time'):
            device.pre_ship_borrow_time = datetime.fromisoformat(data['pre_ship_borrow_time'])
        if data.get('pre_ship_expected_return_date'):
            device.pre_ship_expected_return_date = datetime.fromisoformat(data['pre_ship_expected_return_date'])
        return device
    
    def _record_to_dict(self, record: Record) -> dict:
        """记录转字典"""
        return {
            'id': record.id,
            'device_id': record.device_id,
            'device_name': record.device_name,
            'device_type': record.device_type,
            'operation_type': record.operation_type.value,
            'operator': record.operator,
            'operation_time': record.operation_time.isoformat(),
            'borrower': record.borrower,
            'phone': record.phone,
            'reason': record.reason,
            'entry_source': record.entry_source,
            'remark': record.remark,
        }
    
    def _dict_to_record(self, data: dict) -> Record:
        """字典转记录"""
        return Record(
            id=data['id'],
            device_id=data['device_id'],
            device_name=data['device_name'],
            device_type=data['device_type'],
            operation_type=OperationType(data['operation_type']),
            operator=data['operator'],
            operation_time=datetime.fromisoformat(data['operation_time']),
            borrower=data.get('borrower', ''),
            phone=data.get('phone', ''),
            reason=data.get('reason', ''),
            entry_source=data.get('entry_source', ''),
            remark=data.get('remark', ''),
        )
    
    def _remark_to_dict(self, remark: UserRemark) -> dict:
        """备注转字典"""
        return {
            'id': remark.id,
            'device_id': remark.device_id,
            'content': remark.content,
            'creator': remark.creator,
            'create_time': remark.create_time.isoformat(),
            'is_inappropriate': remark.is_inappropriate,
        }
    
    def _dict_to_remark(self, data: dict) -> UserRemark:
        """字典转备注"""
        remark = UserRemark(
            id=data['id'],
            device_id=data['device_id'],
            device_type=data.get('device_type', ''),
            content=data['content'],
            creator=data['creator'],
            create_time=datetime.fromisoformat(data['create_time']),
        )
        remark.is_inappropriate = data.get('is_inappropriate', False)
        return remark
    
    def _user_to_dict(self, user: User) -> dict:
        """用户转字典"""
        return {
            'id': user.id,
            'wechat_name': user.wechat_name,
            'phone': user.phone,
            'borrow_count': user.borrow_count,
            'is_frozen': user.is_frozen,
            'create_time': user.create_time.isoformat() if user.create_time else None,
        }
    
    def _dict_to_user(self, data: dict) -> User:
        """字典转用户"""
        create_time = None
        if data.get('create_time'):
            create_time = datetime.fromisoformat(data['create_time'])
        return User(
            id=data['id'],
            wechat_name=data['wechat_name'],
            phone=data['phone'],
            borrow_count=data.get('borrow_count', 0),
            is_frozen=data.get('is_frozen', False),
            create_time=create_time,
        )
    
    def _log_to_dict(self, log: OperationLog) -> dict:
        """日志转字典"""
        return {
            'id': log.id,
            'operation_time': log.operation_time.isoformat(),
            'operator': log.operator,
            'operation_content': log.operation_content,
            'device_info': log.device_info,
        }
    
    def _dict_to_log(self, data: dict) -> OperationLog:
        """字典转日志"""
        return OperationLog(
            id=data['id'],
            operation_time=datetime.fromisoformat(data['operation_time']),
            operator=data['operator'],
            operation_content=data['operation_content'],
            device_info=data['device_info'],
        )

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
        return "未知"

    def _init_default_users(self):
        """初始化默认用户数据"""
        self._users: List[User] = [
            User(id=str(uuid.uuid4()), wechat_name="张三", phone="13800138001", borrower_name="张三", password="123456", borrow_count=5, create_time=datetime.now() - timedelta(days=30)),
            User(id=str(uuid.uuid4()), wechat_name="李四", phone="13800138002", borrower_name="李四", password="123456", borrow_count=3, create_time=datetime.now() - timedelta(days=20)),
            User(id=str(uuid.uuid4()), wechat_name="王五", phone="13800138003", borrower_name="王五", password="123456", borrow_count=8, create_time=datetime.now() - timedelta(days=45)),
            User(id=str(uuid.uuid4()), wechat_name="赵六", phone="13800138004", borrower_name="赵六", password="123456", borrow_count=2, is_frozen=True, create_time=datetime.now() - timedelta(days=10)),
        ]

    def _init_mock_data(self):
        """初始化默认数据"""
        self._car_machines: List[CarMachine] = [
            CarMachine(
                id=str(uuid.uuid4()),
                name="车机-001",
                model="Model X1",
                cabinet_number="A-01",
                status=DeviceStatus.IN_STOCK,
                remark="测试用车机"
            ),
            CarMachine(
                id=str(uuid.uuid4()),
                name="车机-002",
                model="Model X2",
                cabinet_number="A-02",
                status=DeviceStatus.BORROWED,
                borrower="张三",
                phone="13800138001",
                borrow_time=datetime.now() - timedelta(days=2),
                location="研发中心",
                reason="功能测试",
                entry_source=EntrySource.USER.value,
                expected_return_date=datetime.now() + timedelta(days=5)
            ),
            CarMachine(
                id=str(uuid.uuid4()),
                name="车机-003",
                model="Model X3",
                cabinet_number="A-03",
                status=DeviceStatus.BORROWED,
                borrower="李四",
                phone="13800138002",
                borrow_time=datetime.now() - timedelta(days=1),
                location="实验室",
                reason="开发调试",
                entry_source=EntrySource.ADMIN.value,
                expected_return_date=datetime.now() + timedelta(days=3)
            ),
        ]
        
        self._phones: List[Phone] = [
            Phone(
                id=str(uuid.uuid4()),
                name="手机-001",
                model="iPhone 15",
                cabinet_number="B-01",
                status=DeviceStatus.IN_STOCK,
                remark="iOS测试机"
            ),
            Phone(
                id=str(uuid.uuid4()),
                name="手机-002",
                model="Samsung S24",
                cabinet_number="B-02",
                status=DeviceStatus.BORROWED,
                borrower="王五",
                phone="13800138003",
                borrow_time=datetime.now() - timedelta(days=3),
                location="会议室",
                reason="演示",
                entry_source=EntrySource.USER.value,
                expected_return_date=datetime.now() + timedelta(days=1)
            ),
        ]
        
        self._users: List[User] = [
            User(id=str(uuid.uuid4()), wechat_name="张三", phone="13800138001", borrower_name="张三", borrow_count=5, create_time=datetime.now() - timedelta(days=30)),
            User(id=str(uuid.uuid4()), wechat_name="李四", phone="13800138002", borrower_name="李四", borrow_count=3, create_time=datetime.now() - timedelta(days=20)),
            User(id=str(uuid.uuid4()), wechat_name="王五", phone="13800138003", borrower_name="王五", borrow_count=8, create_time=datetime.now() - timedelta(days=45)),
            User(id=str(uuid.uuid4()), wechat_name="赵六", phone="13800138004", borrower_name="赵六", borrow_count=2, is_frozen=True, create_time=datetime.now() - timedelta(days=10)),
        ]
        
        self._records: List[Record] = [
            Record(
                id=str(uuid.uuid4()),
                device_id=self._car_machines[1].id,
                device_name=self._car_machines[1].name,
                device_type="车机",
                operation_type=OperationType.BORROW,
                operator="张三",
                operation_time=datetime.now() - timedelta(days=2),
                borrower="张三",
                phone="13800138001",
                reason="功能测试",
                entry_source=EntrySource.USER.value
            ),
            Record(
                id=str(uuid.uuid4()),
                device_id=self._car_machines[2].id,
                device_name=self._car_machines[2].name,
                device_type="车机",
                operation_type=OperationType.FORCE_BORROW,
                operator="管理员",
                operation_time=datetime.now() - timedelta(days=1),
                borrower="李四",
                phone="13800138002",
                reason="开发调试",
                entry_source=EntrySource.ADMIN.value
            ),
        ]
        
        self._remarks: List[UserRemark] = [
            UserRemark(
                id=str(uuid.uuid4()),
                device_id=self._car_machines[0].id,
                content="屏幕有轻微划痕",
                creator="张三",
                create_time=datetime.now() - timedelta(days=5)
            ),
            UserRemark(
                id=str(uuid.uuid4()),
                device_id=self._car_machines[1].id,
                content="电池续航正常",
                creator="李四",
                create_time=datetime.now() - timedelta(days=3)
            ),
        ]
        
        self._operation_logs: List[OperationLog] = [
            OperationLog(
                id=str(uuid.uuid4()),
                operation_time=datetime.now() - timedelta(days=2),
                operator="管理员",
                operation_content="设备借出登记",
                device_info="车机-002"
            ),
            OperationLog(
                id=str(uuid.uuid4()),
                operation_time=datetime.now() - timedelta(days=1),
                operator="管理员",
                operation_content="强制借出登记",
                device_info="车机-003"
            ),
            OperationLog(
                id=str(uuid.uuid4()),
                operation_time=datetime.now() - timedelta(hours=5),
                operator="管理员",
                operation_content="新增设备",
                device_info="手机-002"
            ),
        ]
        
        # 查看记录
        self._view_records: List[ViewRecord] = []
    
    # ==================== 认证相关 ====================
    
    def verify_admin(self, username: str, password: str) -> bool:
        """验证管理员账号密码"""
        # 1. 检查传统管理员表
        for admin in self._admins:
            if admin.username == username and admin.password == password:
                return True
        
        # 2. 检查被指定为管理员的用户（通过借用人名称或手机号登录）
        for user in self._users:
            if user.is_admin and not user.is_frozen:
                # 支持借用人名称或手机号作为账号
                if (user.borrower_name == username or user.phone == username) and user.password == password:
                    return True
        
        return False
    
    def is_user_admin(self, borrower_name: str) -> bool:
        """检查指定用户是否为管理员"""
        for user in self._users:
            if user.borrower_name == borrower_name and user.is_admin:
                return True
        return False
    
    def set_current_admin(self, admin_name: str):
        """设置当前管理员"""
        self._current_admin = admin_name
    
    def get_current_admin(self) -> str:
        """获取当前管理员"""
        return self._current_admin
    
    def verify_user_login(self, phone: str, password: str) -> Optional[User]:
        """验证用户登录"""
        for user in self._users:
            if user.phone == phone and user.password == password:
                if user.is_frozen:
                    return None  # 账号已冻结
                return user
        return None
    
    def get_user_by_phone(self, phone: str) -> Optional[User]:
        """根据手机号获取用户"""
        for user in self._users:
            if user.phone == phone:
                return user
        return None
    
    def update_user_borrower_name(self, user_id: str, borrower_name: str) -> bool:
        """更新用户借用人名称"""
        # 检查借用人名称是否已存在
        for user in self._users:
            if user.borrower_name == borrower_name and user.id != user_id:
                return False  # 名称已存在
        
        for user in self._users:
            if user.id == user_id:
                user.borrower_name = borrower_name
                self._save_data()
                return True
        return False
    
    def register_user(self, phone: str, password: str, borrower_name: str) -> tuple[bool, str]:
        """注册用户
        
        Returns:
            (成功, 错误信息) 或 (成功, 用户)
        """
        # 检查手机号是否已存在
        for user in self._users:
            if user.phone == phone:
                return False, "手机号已被注册"
        
        # 检查用户名是否已存在
        for user in self._users:
            if user.borrower_name == borrower_name:
                return False, "用户名已被使用"
        
        # 创建新用户
        new_user = User(
            id=str(uuid.uuid4()),
            wechat_name=borrower_name,
            phone=phone,
            password=password,
            borrower_name=borrower_name,
            borrow_count=0,
            is_frozen=False,
            create_time=datetime.now()
        )
        
        self._users.append(new_user)
        self._save_data()
        return True, "注册成功"
    
    # ==================== 设备管理 ====================
    
    def get_all_devices(self, device_type: Optional[str] = None) -> List[Device]:
        """获取所有设备，按创建时间倒序排列（最新的在前面）"""
        devices = []
        if device_type is None or device_type == "车机":
            devices.extend([d for d in self._car_machines if not d.is_deleted])
        if device_type is None or device_type == "仪表":
            devices.extend([d for d in self._instruments if not d.is_deleted])
        if device_type is None or device_type == "手机":
            devices.extend([d for d in self._phones if not d.is_deleted])
        if device_type is None or device_type == "手机卡":
            devices.extend([d for d in self._sim_cards if not d.is_deleted])
        if device_type is None or device_type == "其它设备":
            devices.extend([d for d in self._other_devices if not d.is_deleted])
        # 按创建时间倒序排列，最新的设备排在最前面
        return sorted(devices, key=lambda d: d.create_time if d.create_time else datetime.min, reverse=True)
    
    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """根据ID获取设备"""
        for device in self._car_machines + self._instruments + self._phones + self._sim_cards + self._other_devices:
            if device.id == device_id and not device.is_deleted:
                return device
        return None
    
    def get_device_by_name(self, device_name: str) -> Optional[Device]:
        """根据名称获取设备"""
        for device in self._car_machines + self._instruments + self._phones + self._sim_cards + self._other_devices:
            if device.name == device_name and not device.is_deleted:
                return device
        return None
    
    def add_device(self, device: Device) -> bool:
        """新增设备"""
        # 检查设备名是否唯一
        all_devices = self._car_machines + self._instruments + self._phones + self._sim_cards + self._other_devices
        for d in all_devices:
            if d.name == device.name and not d.is_deleted:
                return False
        
        if isinstance(device, CarMachine):
            self._car_machines.append(device)
        elif isinstance(device, Instrument):
            self._instruments.append(device)
        elif isinstance(device, Phone):
            self._phones.append(device)
        elif isinstance(device, SimCard):
            self._sim_cards.append(device)
        elif isinstance(device, OtherDevice):
            self._other_devices.append(device)
        
        # 添加操作日志
        self.add_operation_log(f"新增设备", device.name)
        self._save_data()
        return True
    
    def update_device(self, device: Device) -> bool:
        """更新设备信息"""
        if isinstance(device, CarMachine):
            devices = self._car_machines
        elif isinstance(device, Instrument):
            devices = self._instruments
        elif isinstance(device, Phone):
            devices = self._phones
        elif isinstance(device, SimCard):
            devices = self._sim_cards
        elif isinstance(device, OtherDevice):
            devices = self._other_devices
        else:
            return False
        
        for i, d in enumerate(devices):
            if d.id == device.id:
                devices[i] = device
                self.add_operation_log(f"更新设备信息", device.name)
                self._save_data()
                return True
        return False
    
    def delete_device(self, device_id: str) -> bool:
        """软删除设备"""
        for device in self._car_machines + self._instruments + self._phones + self._sim_cards + self._other_devices:
            if device.id == device_id:
                device.is_deleted = True
                self.add_operation_log(f"删除设备", device.name)
                self._save_data()
                return True
        return False
    
    # ==================== 录入登记/强制归还 ====================
    
    def _get_default_status_for_device(self, device) -> DeviceStatus:
        """根据设备类型获取默认状态（在库/保管中）"""
        from .models import DeviceType
        if device.device_type in [DeviceType.PHONE, DeviceType.SIM_CARD, DeviceType.OTHER_DEVICE]:
            return DeviceStatus.IN_CUSTODY
        return DeviceStatus.IN_STOCK
    
    def _is_available_for_borrow(self, device) -> bool:
        """检查设备是否可借用（在库或保管中）"""
        return device.status in [DeviceStatus.IN_STOCK, DeviceStatus.IN_CUSTODY]
    
    def force_borrow(self, device_id: str, borrower: str, phone: str, 
                     location: str, reason: str, expected_return_date: datetime,
                     remark: str = "") -> bool:
        """强制借出（管理员录入）"""
        device = self.get_device_by_id(device_id)
        if not device or not self._is_available_for_borrow(device):
            return False
        
        device.status = DeviceStatus.BORROWED
        device.borrower = borrower
        device.phone = phone
        device.borrow_time = datetime.now()
        device.location = location
        device.reason = reason
        device.entry_source = EntrySource.ADMIN.value
        device.expected_return_date = expected_return_date
        device.admin_operator = self._current_admin  # 记录录入管理员
        
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
            remark=remark
        )
        self._records.append(record)
        
        # 添加操作日志
        self.add_operation_log(f"强制借出登记: {borrower}", device.name)
        self._save_data()
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
        device.phone = ""
        device.borrow_time = None
        device.location = ""
        device.reason = ""
        device.entry_source = ""
        device.expected_return_date = None
        
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
            remark=remark
        )
        self._records.append(record)
        
        # 添加操作日志
        self.add_operation_log(f"强制归还: {borrower} -> {return_person}", device.name)
        self._save_data()
        return True
    
    def transfer_device(self, device_id: str, transfer_to: str, location: str,
                        reason: str, expected_return_date: datetime,
                        remark: str = "") -> bool:
        """转借设备（管理员操作）"""
        device = self.get_device_by_id(device_id)
        if not device or device.status != DeviceStatus.BORROWED:
            return False
        
        original_borrower = device.borrower
        
        # 获取转借人的手机号
        transfer_phone = ""
        for user in self._users:
            if user.borrower_name == transfer_to:
                transfer_phone = user.phone
                break
        
        # 更新设备信息
        device.borrower = transfer_to
        device.phone = transfer_phone
        device.location = location
        device.reason = reason
        device.expected_return_date = expected_return_date
        
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
            phone=transfer_phone,
            reason=reason,
            entry_source=EntrySource.ADMIN.value,
            remark=remark
        )
        self._records.append(record)
        
        # 添加操作日志
        self.add_operation_log(f"转借：{original_borrower}——>{transfer_to}", device.name)
        self._save_data()
        return True
    
    # ==================== 记录查询 ====================
    
    def get_records(self, device_type: Optional[str] = None,
                    device_name: Optional[str] = None,
                    operation_type: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None) -> List[Record]:
        """查询记录"""
        records = self._records
        
        if device_type:
            records = [r for r in records if r.device_type == device_type]
        if device_name:
            records = [r for r in records if device_name in r.device_name]
        if operation_type:
            records = [r for r in records if r.operation_type.value == operation_type]
        if start_time:
            # 将 start_time 转换为 datetime 以便比较
            if isinstance(start_time, datetime):
                start_dt = start_time
            else:
                from datetime import datetime as dt
                start_dt = dt.combine(start_time, dt.min.time())
            records = [r for r in records if r.operation_time >= start_dt]
        if end_time:
            # 将 end_time 转换为 datetime 以便比较
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
        return self._users
    
    def freeze_user(self, user_id: str) -> bool:
        """冻结用户"""
        for user in self._users:
            if user.id == user_id:
                user.is_frozen = True
                self.add_operation_log(f"冻结用户", user.wechat_name)
                self._save_data()
                return True
        return False
    
    def unfreeze_user(self, user_id: str) -> bool:
        """解冻用户"""
        for user in self._users:
            if user.id == user_id:
                user.is_frozen = False
                self.add_operation_log(f"解冻用户", user.wechat_name)
                self._save_data()
                return True
        return False

    def set_user_admin(self, user_id: str) -> bool:
        """设置用户为管理员"""
        for user in self._users:
            if user.id == user_id:
                user.is_admin = True
                self.add_operation_log(f"设置管理员", user.wechat_name)
                self._save_data()
                return True
        return False

    def cancel_user_admin(self, user_id: str) -> bool:
        """取消用户管理员权限"""
        for user in self._users:
            if user.id == user_id:
                user.is_admin = False
                self.add_operation_log(f"取消管理员", user.wechat_name)
                self._save_data()
                return True
        return False

    def set_user_admin_flag(self, user_id: str, is_admin: bool) -> bool:
        """设置用户管理员标志"""
        for user in self._users:
            if user.id == user_id:
                user.is_admin = is_admin
                action = "设置管理员" if is_admin else "取消管理员"
                self.add_operation_log(action, user.wechat_name)
                self._save_data()
                return True
        return False

    # ==================== 后台管理功能 ====================
    
    def verify_admin_login(self, username: str, password: str) -> Optional[dict]:
        """验证管理员登录"""
        for admin in self._admins:
            if admin.username == username and admin.password == password:
                return {
                    'id': admin.id,
                    'name': admin.username,
                    'username': admin.username
                }
        return None
    
    def get_users(self) -> List[User]:
        """获取所有用户列表"""
        return [u for u in self._users if not u.is_deleted]
    
    def get_device(self, device_id: str) -> Optional[Device]:
        """根据ID获取设备"""
        for device in self._car_machines + self._instruments + self._phones + self._sim_cards + self._other_devices:
            if device.id == device_id and not device.is_deleted:
                return device
        return None
    
    def get_device_records(self, device_id: str, device_type: str = None, limit: int = 10) -> List[Record]:
        """获取设备的操作记录"""
        if device_type:
            records = [r for r in self._records if r.device_id == device_id and r.device_type == device_type]
        else:
            records = [r for r in self._records if r.device_id == device_id]
        return sorted(records, key=lambda x: x.operation_time, reverse=True)[:limit]
    
    def create_device(self, device_type, device_name: str, model: str = '', 
                     cabinet: str = '', status: str = '在库', remarks: str = '') -> Device:
        """创建新设备"""
        from .models import DeviceStatus, CarMachine, Instrument, Phone, SimCard, OtherDevice
        
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
            self._phones.append(device)
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
            self._instruments.append(device)
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
            self._sim_cards.append(device)
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
            self._other_devices.append(device)
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
            self._car_machines.append(device)
        
        self.add_operation_log("创建设备", device_name)
        self._save_data()
        return device
    
    def update_device_by_id(self, device_id: str, data: dict, operator: str = '管理员') -> bool:
        """通过ID更新设备信息"""
        from datetime import datetime
        from .models import Record, OperationType

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
        if 'model' in data:
            device.model = data['model']
        if 'cabinet' in data:
            device.cabinet_number = data['cabinet']
            if device.cabinet_number != original_custodian:
                custodian_changed = True
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
            # 确定应该接收通知的用户：优先借用人，其次是保管人
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
            self._records.append(record)

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
            self._records.append(record)

        # 如果设备被报废且之前是借出状态，清空借用人信息并添加报废记录
        if is_scrapped and was_borrowed and original_borrower:
            # 清空借用人信息
            device.borrower = ''
            device.phone = ''
            device.borrow_time = None
            device.expected_return_date = None
            device.location = ''
            device.reason = ''

            # 添加报废记录
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
            self._records.append(record)
            self.add_operation_log(f"报废设备(原借用人: {original_borrower})", device.name)
            # 发送通知
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
                # 如果设备状态变更，且有借用人，发送通知
                if original_borrower:
                    self.notify_status_change(
                        device_id=device.id,
                        device_name=device.name,
                        borrower=original_borrower,
                        new_status=device.status.value,
                        operator=operator
                    )
                # 如果是保管人变更，也通知保管人
                elif device.cabinet_number and device.cabinet_number != original_custodian:
                    self.notify_status_change(
                        device_id=device.id,
                        device_name=device.name,
                        borrower=device.cabinet_number,
                        new_status=device.status.value,
                        operator=operator
                    )
            elif custodian_changed:
                self.add_operation_log(f"保管人变更: {original_custodian} -> {device.cabinet_number}", device.name)
            else:
                self.add_operation_log("编辑设备", device.name)

        self._save_data()
        return True
    
    def create_user(self, borrower_name: str, wechat_name: str = '', 
                   phone: str = '', password: str = '', is_admin: bool = False) -> User:
        """创建新用户"""
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            borrower_name=borrower_name,
            wechat_name=wechat_name,
            phone=phone,
            password=password,
            is_admin=is_admin,
            create_time=datetime.now()
        )
        self._users.append(user)
        self.add_operation_log("创建用户", borrower_name)
        self._save_data()
        return user
    
    def update_user(self, user_id: str, data: dict) -> bool:
        """更新用户信息"""
        for user in self._users:
            if user.id == user_id:
                if 'name' in data:
                    user.borrower_name = data['name']
                if 'weixin_name' in data:
                    user.wechat_name = data['weixin_name']
                if 'phone' in data:
                    user.phone = data['phone']
                if 'password' in data and data['password']:
                    user.password = data['password']
                if 'is_admin' in data:
                    user.is_admin = data['is_admin']
                
                self.add_operation_log("编辑用户", user.borrower_name)
                self._save_data()
                return True
        return False
    
    def delete_user(self, user_id: str) -> bool:
        """删除用户（逻辑删除）"""
        for user in self._users:
            if user.id == user_id:
                user.is_deleted = True
                self.add_operation_log("删除用户", user.borrower_name)
                self._save_data()
                return True
        return False
    
    def borrow_device(self, device_id: str, borrower: str, days: int = 1,
                     remarks: str = '', operator: str = '管理员') -> bool:
        """借出设备"""
        device = self.get_device(device_id)
        if not device:
            return False

        # 封存状态设备无法借用
        if device.status == DeviceStatus.SEALED:
            raise ValueError('封存状态的设备无法借用')

        # 检查用户借用数量限制（管理员借出也要检查）
        user_borrowed_count = 0
        all_devices = self.get_all_devices()
        for d in all_devices:
            if d.borrower == borrower and d.status == DeviceStatus.BORROWED:
                user_borrowed_count += 1

        borrow_limit = 10  # 最大借用数量
        if user_borrowed_count >= borrow_limit:
            # 抛出异常以便调用方处理
            raise ValueError(f'{borrower}已超出可借设备上限，请归还后再借')

        # 计算预计归还时间：当前时间 + 天数
        now = datetime.now()
        expected_return = now + timedelta(days=days)

        device.borrower = borrower
        # 借出时保持原柜号不变
        device.status = DeviceStatus.BORROWED
        device.borrow_time = now
        device.expected_return_date = expected_return

        # 创建记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device_id,
            device_name=device.name,
            device_type=device.device_type.value,
            operation_type=OperationType.BORROW,
            operator=operator,
            operation_time=datetime.now(),
            borrower=borrower,
            reason=remarks,
            remark=remarks
        )
        self._records.append(record)

        # 更新用户借用次数
        for user in self._users:
            if user.borrower_name == borrower:
                user.borrow_count += 1
                break

        self.add_operation_log("录入登记", device.name)
        self._save_data()
        return True
    
    def return_device(self, device_id: str, operator: str = '管理员') -> bool:
        """归还设备"""
        device = self.get_device(device_id)
        if not device:
            return False

        borrower = device.borrower
        device.borrower = ''
        device.cabinet_number = 'A01'  # 默认柜号
        # 根据设备类型设置默认状态（在库或保管中）
        device.status = self._get_default_status_for_device(device)
        device.borrow_time = None
        device.expected_return_date = None

        # 创建记录
        record = Record(
            id=str(uuid.uuid4()),
            device_id=device_id,
            device_name=device.name,
            device_type=device.device_type.value,
            operation_type=OperationType.RETURN,
            operator=operator,
            operation_time=datetime.now(),
            borrower=borrower
        )
        self._records.append(record)

        self.add_operation_log("强制归还", device.name)
        self._save_data()

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
    
    def get_remarks(self, device_id: Optional[str] = None, device_type: str = None) -> List[UserRemark]:
        """获取备注列表"""
        if device_id:
            if device_type:
                return [r for r in self._remarks if r.device_id == device_id and r.device_type == device_type]
            return [r for r in self._remarks if r.device_id == device_id]
        return self._remarks
    
    def delete_remark(self, remark_id: str) -> bool:
        """删除备注"""
        for i, remark in enumerate(self._remarks):
            if remark.id == remark_id:
                del self._remarks[i]
                self.add_operation_log(f"删除备注", f"备注ID: {remark_id}")
                self._save_data()
                return True
        return False
    
    def mark_inappropriate(self, remark_id: str) -> bool:
        """标记不当备注"""
        for remark in self._remarks:
            if remark.id == remark_id:
                remark.is_inappropriate = True
                self._save_data()
                return True
        return False
    
    # ==================== 操作日志 ====================
    
    def get_operation_logs(self, limit: int = 50) -> List[OperationLog]:
        """获取操作日志"""
        return sorted(self._operation_logs, key=lambda x: x.operation_time, reverse=True)[:limit]
    
    def add_operation_log(self, operation_content: str, device_info: str):
        """添加操作日志"""
        log = OperationLog(
            id=str(uuid.uuid4()),
            operation_time=datetime.now(),
            operator=self._current_admin,
            operation_content=operation_content,
            device_info=device_info
        )
        self._operation_logs.append(log)
        self._save_data()
    
    def get_admin_logs(self, limit: int = 100) -> List[dict]:
        """获取管理员操作日志（用于后台管理）"""
        logs = sorted(self._operation_logs, key=lambda x: x.operation_time, reverse=True)[:limit]
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'time': log.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
                'admin_name': log.operator,
                'action_type': self._categorize_action(log.operation_content),
                'details': f"{log.operation_content}: {log.device_info}",
                'ip': ''  # IP地址需要在外部记录
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
        notifications = []
        for notification in self._notifications:
            # 过滤条件
            if user_id and notification.user_id != user_id:
                continue
            if user_name and notification.user_name != user_name:
                continue
            if unread_only and notification.is_read:
                continue
            notifications.append(notification)

        # 按创建时间倒序排列
        return sorted(notifications, key=lambda x: x.create_time, reverse=True)

    def get_unread_count(self, user_id: str = None, user_name: str = None) -> int:
        """获取未读通知数量"""
        count = 0
        for notification in self._notifications:
            if notification.is_read:
                continue
            if user_id and notification.user_id != user_id:
                continue
            if user_name and notification.user_name != user_name:
                continue
            count += 1
        return count

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
        self._notifications.append(notification)
        self._save_data()
        return notification

    def mark_notification_read(self, notification_id: str) -> bool:
        """标记通知为已读"""
        for notification in self._notifications:
            if notification.id == notification_id:
                notification.is_read = True
                self._save_data()
                return True
        return False

    def mark_all_read(self, user_id: str = None, user_name: str = None) -> int:
        """标记用户所有通知为已读，返回标记数量"""
        count = 0
        for notification in self._notifications:
            if notification.is_read:
                continue
            if user_id and notification.user_id != user_id:
                continue
            if user_name and notification.user_name != user_name:
                continue
            notification.is_read = True
            count += 1
        if count > 0:
            self._save_data()
        return count

    def delete_notification(self, notification_id: str) -> bool:
        """删除通知"""
        for i, notification in enumerate(self._notifications):
            if notification.id == notification_id:
                del self._notifications[i]
                self._save_data()
                return True
        return False

    def notify_borrow(self, device_id: str, device_name: str, borrower: str, operator: str):
        """通知用户设备已借出"""
        # 查找用户ID
        user_id = None
        for user in self._users:
            if user.borrower_name == borrower:
                user_id = user.id
                break

        if user_id:
            content = f"操作员 {operator} 已将设备「{device_name}」借出给您，请注意按时归还。"
            self.add_notification(
                user_id=user_id,
                user_name=borrower,
                title="设备借出通知",
                content=content,
                device_name=device_name,
                device_id=device_id,
                notification_type="success"
            )

    def notify_return(self, device_id: str, device_name: str, borrower: str, operator: str):
        """通知用户设备已归还（强制归还）"""
        # 查找用户ID
        user_id = None
        for user in self._users:
            if user.borrower_name == borrower:
                user_id = user.id
                break

        if user_id:
            content = f"操作员 {operator} 已将您借用的设备「{device_name}」强制归还。"
            self.add_notification(
                user_id=user_id,
                user_name=borrower,
                title="设备强制归还通知",
                content=content,
                device_name=device_name,
                device_id=device_id,
                notification_type="warning"
            )

    def notify_transfer(self, device_id: str, device_name: str, original_borrower: str, new_borrower: str, operator: str):
        """通知相关用户设备已转借"""
        # 通知原借用人
        original_user_id = None
        for user in self._users:
            if user.borrower_name == original_borrower:
                original_user_id = user.id
                break

        if original_user_id:
            content = f"您借用的设备「{device_name}」已被 {operator} 转借给 {new_borrower}。"
            self.add_notification(
                user_id=original_user_id,
                user_name=original_borrower,
                title="设备转借通知",
                content=content,
                device_name=device_name,
                device_id=device_id,
                notification_type="warning"
            )

        # 通知新借用人
        new_user_id = None
        for user in self._users:
            if user.borrower_name == new_borrower:
                new_user_id = user.id
                break

        if new_user_id:
            content = f"操作员 {operator} 已将设备「{device_name}」转借给您。"
            self.add_notification(
                user_id=new_user_id,
                user_name=new_borrower,
                title="设备转借通知",
                content=content,
                device_name=device_name,
                device_id=device_id,
                notification_type="success"
            )

    def notify_status_change(self, device_id: str, device_name: str, borrower: str, new_status: str, operator: str):
        """通知用户设备状态变更"""
        # 查找用户ID
        user_id = None
        for user in self._users:
            if user.borrower_name == borrower:
                user_id = user.id
                break

        if user_id:
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
                user_id=user_id,
                user_name=borrower,
                title=f"设备{status_desc}通知",
                content=content,
                device_name=device_name,
                device_id=device_id,
                notification_type=notification_type
            )

    def reload_data(self):
        """重新加载数据（用于网页端刷新）"""
        self._load_data()
    
    # ==================== 查看记录 ====================
    
    def add_view_record(self, device_id: str, viewer: str, device_type: str = ""):
        """添加查看记录"""
        record = ViewRecord(
            id=str(uuid.uuid4()),
            device_id=device_id,
            device_type=device_type,
            viewer=viewer,
            view_time=datetime.now()
        )
        self._view_records.append(record)
        # 只保留最近100条查看记录
        if len(self._view_records) > 100:
            self._view_records = self._view_records[-100:]
        self._save_data()

    def get_view_records(self, device_id: str, device_type: str = None, limit: int = 20) -> List[ViewRecord]:
        """获取设备的查看记录"""
        if device_type:
            records = [r for r in self._view_records if r.device_id == device_id and r.device_type == device_type]
        else:
            records = [r for r in self._view_records if r.device_id == device_id]
        return sorted(records, key=lambda x: x.view_time, reverse=True)[:limit]

    # ==================== 公告管理 ====================

    def get_announcements(self, announcement_type: str = None, active_only: bool = False) -> List[Announcement]:
        """获取公告列表
        
        Args:
            announcement_type: 公告类型过滤 (None=全部, 'normal'=普通, 'special'=特殊)
            active_only: 是否只获取上架的公告
        """
        announcements = self._announcements
        
        if active_only:
            announcements = [a for a in announcements if a.is_active]
        
        if announcement_type:
            announcements = [a for a in announcements if a.announcement_type == announcement_type]
        
        # 按排序字段排序，然后按创建时间倒序
        return sorted(announcements, key=lambda x: (x.sort_order, -x.create_time.timestamp() if x.create_time else 0))

    def get_active_normal_announcements(self) -> List[Announcement]:
        """获取上架的普通公告列表（按排序显示）"""
        announcements = [a for a in self._announcements if a.is_active and a.announcement_type == 'normal']
        return sorted(announcements, key=lambda x: (x.sort_order, -x.create_time.timestamp() if x.create_time else 0))

    def get_active_special_announcements(self) -> List[Announcement]:
        """获取上架的特殊公告列表（最多3条）"""
        announcements = [a for a in self._announcements if a.is_active and a.announcement_type == 'special']
        # 按排序字段排序，然后按创建时间倒序，取前3条
        announcements = sorted(announcements, key=lambda x: (x.sort_order, -x.create_time.timestamp() if x.create_time else 0))
        return announcements[:3]

    def get_announcement_by_id(self, announcement_id: str) -> Optional[Announcement]:
        """根据ID获取公告"""
        for announcement in self._announcements:
            if announcement.id == announcement_id:
                return announcement
        return None

    def create_announcement(self, title: str, content: str, announcement_type: str = 'normal', 
                           sort_order: int = 0, creator: str = '') -> Announcement:
        """创建公告"""
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
        self._announcements.append(announcement)
        
        # 如果是特殊公告，检查是否超过3条，超过则下架最旧的
        if announcement_type == 'special':
            active_special = [a for a in self._announcements if a.is_active and a.announcement_type == 'special']
            if len(active_special) > 3:
                # 按创建时间排序，下架最旧的
                active_special_sorted = sorted(active_special, key=lambda x: x.create_time or datetime.min)
                for old_announcement in active_special_sorted[:-3]:
                    old_announcement.is_active = False
                    old_announcement.update_time = datetime.now()
        
        self._save_data()
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
            active_special = [a for a in self._announcements if a.is_active and a.announcement_type == 'special']
            if len(active_special) > 3:
                active_special_sorted = sorted(active_special, key=lambda x: x.create_time or datetime.min)
                for old_announcement in active_special_sorted[:-3]:
                    if old_announcement.id != announcement_id:
                        old_announcement.is_active = False
                        old_announcement.update_time = datetime.now()
        
        self._save_data()
        return announcement

    def toggle_announcement_status(self, announcement_id: str) -> Optional[Announcement]:
        """切换公告上架/下架状态"""
        announcement = self.get_announcement_by_id(announcement_id)
        if not announcement:
            return None
        
        announcement.is_active = not announcement.is_active
        announcement.update_time = datetime.now()
        self._save_data()
        return announcement

    def delete_announcement(self, announcement_id: str) -> bool:
        """删除公告"""
        announcement = self.get_announcement_by_id(announcement_id)
        if not announcement:
            return False
        
        self._announcements.remove(announcement)
        self._save_data()
        return True

    def force_show_announcement(self, announcement_id: str) -> Optional[Announcement]:
        """再次公告 - 增加版本号让用户重新看到弹窗"""
        announcement = self.get_announcement_by_id(announcement_id)
        if not announcement:
            return None
        
        # 增加版本号
        announcement.force_show_version += 1
        announcement.update_time = datetime.now()
        self._save_data()
        return announcement


# 全局 API 客户端实例
api_client = APIClient()
