# -*- coding: utf-8 -*-
"""
数据模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class DeviceStatus(Enum):
    """设备状态"""
    IN_STOCK = "在库"
    IN_CUSTODY = "保管中"  # 手机、手机卡、其它设备使用
    BORROWED = "借出"
    SHIPPED = "已寄出"
    DAMAGED = "已损坏"
    LOST = "丢失"
    SCRAPPED = "报废"
    CIRCULATING = "流通"
    NO_CABINET = "无柜号"
    SEALED = "封存"


class DeviceType(Enum):
    """设备类型"""
    CAR_MACHINE = "车机"
    INSTRUMENT = "仪表"
    PHONE = "手机"
    SIM_CARD = "手机卡"
    OTHER_DEVICE = "其它设备"


class OperationType(Enum):
    """操作类型"""
    BORROW = "借出"
    RETURN = "归还"
    FORCE_BORROW = "强制借出"
    FORCE_RETURN = "强制归还"
    TRANSFER = "转借"
    REPORT_LOST = "丢失报备"
    REPORT_DAMAGE = "损坏报备"
    FOUND = "找回"
    REPAIRED = "修复"
    SCRAP = "报废"
    CUSTODIAN_CHANGE = "保管人变更"
    NOT_FOUND = "借用人未找到"
    RENEW = "借用续期"
    SHIP = "寄出"
    STATUS_CHANGE = "状态变更"
    BATCH_IMPORT = "批量导入"


class EntrySource(Enum):
    """录入来源"""
    ADMIN = "管理员录入"
    USER = "用户自助"


@dataclass
class Device:
    """设备基础类"""
    id: str
    name: str
    device_type: DeviceType
    model: str
    cabinet_number: str
    status: DeviceStatus = DeviceStatus.IN_STOCK
    remark: str = ""
    jira_address: str = ""  # JIRA地址，如：NAV-2890
    is_deleted: bool = False
    create_time: Optional[datetime] = None  # 创建时间
    
    # 借用信息
    borrower: str = ""  # 借用人名称（显示用）
    borrower_id: str = ""  # 借用人ID（关联用户表）
    phone: str = ""
    borrow_time: Optional[datetime] = None
    location: str = ""
    reason: str = ""
    entry_source: str = ""
    expected_return_date: Optional[datetime] = None
    admin_operator: str = ""  # 管理员录入/转借时的操作人

    # 保管信息
    custodian_id: str = ""  # 保管人ID（关联用户表）

    # 寄出信息
    ship_time: Optional[datetime] = None
    ship_remark: str = ""
    ship_by: str = ""

    # 寄出前借用信息（用于还原）
    pre_ship_borrower: str = ""
    pre_ship_phone: str = ""
    pre_ship_borrow_time: Optional[datetime] = None
    pre_ship_expected_return_date: Optional[datetime] = None
    pre_ship_reason: str = ""
    
    # 丢失/损坏信息
    lost_time: Optional[datetime] = None
    damage_reason: str = ""
    damage_time: Optional[datetime] = None
    previous_borrower: str = ""  # 上一个借用人
    
    # 手机特有信息
    sn: str = ""  # SN码（设备序列号）
    system_version: str = ""  # 系统版本
    imei: str = ""  # IMEI号
    carrier: str = ""  # 运营商（移动/联通/电信）

    # 车机特有信息
    software_version: str = ""  # 软件版本
    hardware_version: str = ""  # 芯片型号

    # 车机和仪表特有信息（JIRA地址后的字段）
    project_attribute: str = ""  # 项目属性
    connection_method: str = ""  # 连接方式
    os_version: str = ""  # 系统版本
    os_platform: str = ""  # 系统平台
    product_name: str = ""  # 产品名称
    screen_orientation: str = ""  # 屏幕方向
    screen_resolution: str = ""  # 车机分辨率
    
    def __post_init__(self):
        """初始化后，如果没有设置创建时间，则设置为当前时间"""
        if self.create_time is None:
            self.create_time = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Device':
        """从字典创建设备对象"""
        from datetime import datetime
        
        def parse_datetime(val):
            if val is None or val == '':
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return None
        
        # 确定设备类型
        device_type_str = data.get('device_type', '')
        if isinstance(device_type_str, DeviceType):
            device_type = device_type_str
        else:
            device_type = None
            # 首先尝试通过枚举名称匹配（如 CAR_MACHINE）
            try:
                device_type = DeviceType(device_type_str)
            except (ValueError, KeyError):
                pass
            
            # 如果失败，尝试通过枚举值匹配（如 车机）
            if device_type is None:
                for dt in DeviceType:
                    if dt.value == device_type_str:
                        device_type = dt
                        break
            
            # 如果仍然失败，默认使用车机
            if device_type is None:
                device_type = DeviceType.CAR_MACHINE
        
        # 确定状态
        status_str = data.get('status', '在库')
        if isinstance(status_str, DeviceStatus):
            status = status_str
        else:
            try:
                status = DeviceStatus(status_str)
            except:
                status = DeviceStatus.IN_STOCK
        
        # 创建基础设备对象
        device = cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            device_type=device_type,
            model=data.get('model', ''),
            cabinet_number=data.get('cabinet_number', ''),
            status=status,
            remark=data.get('remark', ''),
            jira_address=data.get('jira_address', ''),
            is_deleted=bool(data.get('is_deleted', 0)),
            create_time=parse_datetime(data.get('create_time')),
            borrower=data.get('borrower', ''),
            borrower_id=data.get('borrower_id', ''),
            phone=data.get('phone', ''),
            borrow_time=parse_datetime(data.get('borrow_time')),
            location=data.get('location', ''),
            reason=data.get('reason', ''),
            entry_source=data.get('entry_source', ''),
            expected_return_date=parse_datetime(data.get('expected_return_date')),
            admin_operator=data.get('admin_operator', ''),
            custodian_id=data.get('custodian_id', ''),
            ship_time=parse_datetime(data.get('ship_time')),
            ship_remark=data.get('ship_remark', ''),
            ship_by=data.get('ship_by', ''),
            pre_ship_borrower=data.get('pre_ship_borrower', ''),
            pre_ship_phone=data.get('pre_ship_phone', ''),
            pre_ship_borrow_time=parse_datetime(data.get('pre_ship_borrow_time')),
            pre_ship_expected_return_date=parse_datetime(data.get('pre_ship_expected_return_date')),
            pre_ship_reason=data.get('pre_ship_reason', ''),
            lost_time=parse_datetime(data.get('lost_time')),
            damage_reason=data.get('damage_reason', ''),
            damage_time=parse_datetime(data.get('damage_time')),
            previous_borrower=data.get('previous_borrower', ''),
            sn=data.get('sn', ''),
            system_version=data.get('system_version', ''),
            imei=data.get('imei', ''),
            carrier=data.get('carrier', ''),
            software_version=data.get('software_version', ''),
            hardware_version=data.get('hardware_version', ''),
            project_attribute=data.get('project_attribute', ''),
            connection_method=data.get('connection_method', ''),
            os_version=data.get('os_version', ''),
            os_platform=data.get('os_platform', ''),
            product_name=data.get('product_name', ''),
            screen_orientation=data.get('screen_orientation', ''),
            screen_resolution=data.get('screen_resolution', '')
        )
        return device

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type.value if isinstance(self.device_type, DeviceType) else str(self.device_type),
            "model": self.model,
            "cabinet_number": self.cabinet_number,
            "status": self.status.value if isinstance(self.status, DeviceStatus) else str(self.status),
            "remark": self.remark,
            "borrower": self.borrower,
            "phone": self.phone,
            "borrow_time": self.borrow_time.strftime("%Y-%m-%d %H:%M:%S") if self.borrow_time else "",
            "location": self.location,
            "reason": self.reason,
            "entry_source": self.entry_source,
            "expected_return_date": self.expected_return_date.strftime("%Y-%m-%d") if self.expected_return_date else "",
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
        }


@dataclass
class CarMachine(Device):
    """车机设备"""
    def __init__(self, **kwargs):
        kwargs['device_type'] = DeviceType.CAR_MACHINE
        super().__init__(**kwargs)


@dataclass
class Instrument(Device):
    """仪表设备"""
    def __init__(self, **kwargs):
        kwargs['device_type'] = DeviceType.INSTRUMENT
        super().__init__(**kwargs)


@dataclass
class Phone(Device):
    """手机设备"""
    def __init__(self, **kwargs):
        kwargs['device_type'] = DeviceType.PHONE
        super().__init__(**kwargs)


@dataclass
class SimCard(Device):
    """手机卡设备"""
    def __init__(self, **kwargs):
        kwargs['device_type'] = DeviceType.SIM_CARD
        super().__init__(**kwargs)


@dataclass
class OtherDevice(Device):
    """其它设备"""
    def __init__(self, **kwargs):
        kwargs['device_type'] = DeviceType.OTHER_DEVICE
        super().__init__(**kwargs)


@dataclass
class Record:
    """借还记录"""
    id: str
    device_id: str
    device_name: str
    device_type: str
    operation_type: OperationType
    operator: str
    operation_time: datetime
    borrower: str = ""
    phone: str = ""
    reason: str = ""
    entry_source: str = ""
    remark: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> 'Record':
        """从字典创建记录对象"""
        from datetime import datetime
        
        def parse_datetime(val):
            if val is None or val == '':
                return datetime.now()
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return datetime.now()
        
        # 确定操作类型
        op_type_str = data.get('operation_type', '借出')
        if isinstance(op_type_str, OperationType):
            op_type = op_type_str
        else:
            try:
                op_type = OperationType(op_type_str)
            except:
                op_type = OperationType.BORROW
        
        return cls(
            id=data.get('id', ''),
            device_id=data.get('device_id', ''),
            device_name=data.get('device_name', ''),
            device_type=data.get('device_type', ''),
            operation_type=op_type,
            operator=data.get('operator', ''),
            operation_time=parse_datetime(data.get('operation_time')),
            borrower=data.get('borrower', ''),
            phone=data.get('phone', ''),
            reason=data.get('reason', ''),
            entry_source=data.get('entry_source', ''),
            remark=data.get('remark', '')
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "operation_type": self.operation_type.value if isinstance(self.operation_type, OperationType) else str(self.operation_type),
            "operator": self.operator,
            "operation_time": self.operation_time.strftime("%Y-%m-%d %H:%M:%S") if self.operation_time else "",
            "borrower": self.borrower,
            "phone": self.phone,
            "reason": self.reason,
            "entry_source": self.entry_source,
            "remark": self.remark,
        }


@dataclass
class UserRemark:
    """用户备注"""
    id: str
    device_id: str
    device_type: str
    content: str
    creator: str
    create_time: datetime
    is_inappropriate: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UserRemark':
        """从字典创建备注对象"""
        from datetime import datetime
        
        def parse_datetime(val):
            if val is None or val == '':
                return datetime.now()
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return datetime.now()
        
        return cls(
            id=data.get('id', ''),
            device_id=data.get('device_id', ''),
            device_type=data.get('device_type', ''),
            content=data.get('content', ''),
            creator=data.get('creator', ''),
            create_time=parse_datetime(data.get('create_time')),
            is_inappropriate=bool(data.get('is_inappropriate', 0))
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "content": self.content,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
            "is_inappropriate": "是" if self.is_inappropriate else "否",
        }


@dataclass
class User:
    """用户信息"""
    id: str
    email: str                # 邮箱（用于登录，唯一）
    password: str = "123456"  # 默认密码
    borrower_name: str = ""   # 借用人名称（必填，唯一）
    borrow_count: int = 0     # 借用次数
    return_count: int = 0     # 归还次数
    is_frozen: bool = False   # 是否冻结
    is_admin: bool = False    # 是否为管理员
    is_deleted: bool = False  # 是否已删除
    is_first_login: bool = True  # 是否首次登录（需要修改密码）
    create_time: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """从字典创建用户对象"""
        from datetime import datetime
        
        def parse_datetime(val):
            if val is None or val == '':
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return None
        
        return cls(
            id=data.get('id', ''),
            email=data.get('email', ''),
            password=data.get('password', '123456'),
            borrower_name=data.get('borrower_name', ''),
            borrow_count=int(data.get('borrow_count', 0)),
            return_count=int(data.get('return_count', 0)),
            is_frozen=bool(data.get('is_frozen', 0)),
            is_admin=bool(data.get('is_admin', 0)),
            is_deleted=bool(data.get('is_deleted', 0)),
            is_first_login=bool(data.get('is_first_login', 1)),
            create_time=parse_datetime(data.get('create_time'))
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "password": self.password,
            "borrower_name": self.borrower_name,
            "borrow_count": self.borrow_count,
            "return_count": self.return_count,
            "is_frozen": "已冻结" if self.is_frozen else "正常",
            "is_admin": "是" if self.is_admin else "否",
            "is_first_login": self.is_first_login,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
        }


@dataclass
class UserLike:
    """用户点赞记录"""
    id: str
    from_user_id: str       # 点赞用户ID
    to_user_id: str         # 被点赞用户ID
    create_date: str        # 点赞日期（YYYY-MM-DD）
    create_time: datetime   # 点赞时间

    @classmethod
    def from_dict(cls, data: dict) -> 'UserLike':
        """从字典创建用户点赞对象"""
        from datetime import datetime

        def parse_datetime(val):
            if val is None or val == '':
                return datetime.now()
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return datetime.now()

        return cls(
            id=data.get('id', ''),
            from_user_id=data.get('from_user_id', ''),
            to_user_id=data.get('to_user_id', ''),
            create_date=data.get('create_date', ''),
            create_time=parse_datetime(data.get('create_time'))
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "create_date": self.create_date,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
        }


@dataclass
class OperationLog:
    """操作日志"""
    id: str
    operation_time: datetime
    operator: str
    operation_content: str
    device_info: str

    @classmethod
    def from_dict(cls, data: dict) -> 'OperationLog':
        """从字典创建操作日志对象"""
        from datetime import datetime

        def parse_datetime(val):
            if val is None or val == '':
                return datetime.now()
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return datetime.now()

        return cls(
            id=data.get('id', ''),
            operation_time=parse_datetime(data.get('operation_time')),
            operator=data.get('operator', ''),
            operation_content=data.get('operation_content', ''),
            device_info=data.get('device_info', '')
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "operation_time": self.operation_time.strftime("%Y-%m-%d %H:%M:%S") if self.operation_time else "",
            "operator": self.operator,
            "operation_content": self.operation_content,
            "device_info": self.device_info,
        }


@dataclass
class Admin:
    """管理员信息"""
    id: str
    username: str
    password: str
    create_time: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Admin':
        """从字典创建管理员对象"""
        from datetime import datetime
        
        def parse_datetime(val):
            if val is None or val == '':
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return None
        
        return cls(
            id=data.get('id', ''),
            username=data.get('username', ''),
            password=data.get('password', ''),
            create_time=parse_datetime(data.get('create_time'))
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "password": self.password,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
        }


@dataclass
class ViewRecord:
    """查看记录"""
    id: str
    device_id: str
    device_type: str
    viewer: str
    view_time: datetime

    @classmethod
    def from_dict(cls, data: dict) -> 'ViewRecord':
        """从字典创建查看记录对象"""
        from datetime import datetime

        def parse_datetime(val):
            if val is None or val == '':
                return datetime.now()
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return datetime.now()

        return cls(
            id=data.get('id', ''),
            device_id=data.get('device_id', ''),
            device_type=data.get('device_type', ''),
            viewer=data.get('viewer', ''),
            view_time=parse_datetime(data.get('view_time'))
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "viewer": self.viewer,
            "view_time": self.view_time.strftime("%Y-%m-%d %H:%M:%S") if self.view_time else "",
        }


@dataclass
class Notification:
    """通知消息"""
    id: str
    user_id: str  # 接收通知的用户ID
    user_name: str  # 接收通知的用户名（用于快速查找）
    title: str  # 通知标题
    content: str  # 通知内容
    device_name: str = ""  # 相关设备名称
    device_id: str = ""  # 相关设备ID
    is_read: bool = False  # 是否已读
    create_time: datetime = None  # 创建时间
    notification_type: str = "info"  # 通知类型：info, warning, error, success

    def __post_init__(self):
        if self.create_time is None:
            self.create_time = datetime.now()

    @classmethod
    def from_dict(cls, data: dict) -> 'Notification':
        """从字典创建通知对象"""
        from datetime import datetime
        
        def parse_datetime(val):
            if val is None or val == '':
                return datetime.now()
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return datetime.now()
        
        return cls(
            id=data.get('id', ''),
            user_id=data.get('user_id', ''),
            user_name=data.get('user_name', ''),
            title=data.get('title', ''),
            content=data.get('content', ''),
            device_name=data.get('device_name', ''),
            device_id=data.get('device_id', ''),
            is_read=bool(data.get('is_read', 0)),
            create_time=parse_datetime(data.get('create_time')),
            notification_type=data.get('notification_type', 'info')
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "title": self.title,
            "content": self.content,
            "device_name": self.device_name,
            "device_id": self.device_id,
            "is_read": self.is_read,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
            "notification_type": self.notification_type,
        }


@dataclass
class Announcement:
    """公告"""
    id: str
    title: str  # 公告标题
    content: str  # 公告内容
    announcement_type: str = "normal"  # 公告类型：normal(普通), special(特殊)
    is_active: bool = True  # 是否上架
    sort_order: int = 0  # 排序顺序（数字越小越靠前）
    creator: str = ""  # 创建人
    create_time: Optional[datetime] = None  # 创建时间
    update_time: Optional[datetime] = None  # 更新时间
    force_show_version: int = 0  # 强制显示版本号，增加后用户会重新看到弹窗

    def __post_init__(self):
        if self.create_time is None:
            self.create_time = datetime.now()

    @classmethod
    def from_dict(cls, data: dict) -> 'Announcement':
        """从字典创建公告对象"""
        from datetime import datetime
        
        def parse_datetime(val):
            if val is None or val == '':
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                    try:
                        return datetime.strptime(val, fmt)
                    except:
                        continue
            return None
        
        return cls(
            id=data.get('id', ''),
            title=data.get('title', ''),
            content=data.get('content', ''),
            announcement_type=data.get('announcement_type', 'normal'),
            is_active=bool(data.get('is_active', 1)),
            sort_order=int(data.get('sort_order', 0)),
            creator=data.get('creator', ''),
            create_time=parse_datetime(data.get('create_time')),
            update_time=parse_datetime(data.get('update_time')),
            force_show_version=int(data.get('force_show_version', 0))
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "announcement_type": self.announcement_type,
            "is_active": "是" if self.is_active else "否",
            "sort_order": self.sort_order,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
            "update_time": self.update_time.strftime("%Y-%m-%d %H:%M:%S") if self.update_time else "",
            "force_show_version": self.force_show_version,
        }
