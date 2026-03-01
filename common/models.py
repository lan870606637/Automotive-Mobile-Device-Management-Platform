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
    CREATE_BOUNTY = "发布悬赏"
    CANCEL_BOUNTY = "取消悬赏"
    COMPLETE_BOUNTY = "悬赏完成"


class EntrySource(Enum):
    """录入来源"""
    ADMIN = "管理员录入"
    USER = "用户自助"


class ReservationStatus(Enum):
    """预约状态"""
    PENDING_CUSTODIAN = "待保管人确认"
    PENDING_BORROWER = "待借用人确认"
    PENDING_BOTH = "待2人确认"
    APPROVED = "已同意"
    REJECTED = "已拒绝"
    CANCELLED = "已取消"
    EXPIRED = "已过期"
    CONVERTED = "已转借用"


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

    # 资产信息
    asset_number: str = ""  # 固定资产编号
    purchase_amount: float = 0.0  # 购买金额（元）

    # 丢失/损坏信息
    lost_time: Optional[datetime] = None
    damage_reason: str = ""
    damage_time: Optional[datetime] = None
    previous_borrower: str = ""  # 上一个借用人
    previous_status: str = ""  # 丢失/损坏前的状态（用于恢复）
    
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
            previous_status=data.get('previous_status', ''),
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
            screen_resolution=data.get('screen_resolution', ''),
            asset_number=data.get('asset_number', ''),
            purchase_amount=float(data.get('purchase_amount', 0)) if data.get('purchase_amount') else 0.0
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
            "expected_return_date": self.expected_return_date.strftime("%Y-%m-%d %H:%M:%S") if self.expected_return_date else "",
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
    avatar: str = ""          # 头像URL或路径
    signature: str = ""       # 个性签名
    borrow_count: int = 0     # 借用次数
    return_count: int = 0     # 归还次数
    is_frozen: bool = False   # 是否冻结
    is_admin: bool = False    # 是否为管理员
    is_deleted: bool = False  # 是否已删除
    is_first_login: bool = True  # 是否首次登录（需要修改密码）
    create_time: Optional[datetime] = None
    
    # 装扮相关
    current_title: str = ""       # 当前使用的称号ID
    current_avatar_frame: str = ""  # 当前使用的头像边框ID
    current_theme: str = ""       # 当前使用的主题皮肤ID
    
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
            avatar=data.get('avatar', ''),
            signature=data.get('signature', ''),
            borrow_count=int(data.get('borrow_count', 0)),
            return_count=int(data.get('return_count', 0)),
            is_frozen=bool(data.get('is_frozen', 0)),
            is_admin=bool(data.get('is_admin', 0)),
            is_deleted=bool(data.get('is_deleted', 0)),
            is_first_login=bool(data.get('is_first_login', 1)),
            create_time=parse_datetime(data.get('create_time')),
            current_title=data.get('current_title', ''),
            current_avatar_frame=data.get('current_avatar_frame', ''),
            current_theme=data.get('current_theme', '')
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "password": self.password,
            "borrower_name": self.borrower_name,
            "avatar": self.avatar,
            "signature": self.signature,
            "borrow_count": self.borrow_count,
            "return_count": self.return_count,
            "is_frozen": "已冻结" if self.is_frozen else "正常",
            "is_admin": "是" if self.is_admin else "否",
            "is_first_login": self.is_first_login,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
            "current_title": self.current_title,
            "current_avatar_frame": self.current_avatar_frame,
            "current_theme": self.current_theme,
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


@dataclass
class Reservation:
    """预约记录"""
    id: str
    device_id: str
    device_type: str
    device_name: str
    reserver_id: str
    reserver_name: str
    start_time: datetime
    end_time: datetime
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # 确认相关
    custodian_approved: bool = False
    custodian_approved_at: Optional[datetime] = None
    borrower_approved: bool = False
    borrower_approved_at: Optional[datetime] = None
    
    # 通知相关
    custodian_notified: bool = False
    borrower_notified: bool = False
    
    # 取消/拒绝信息
    cancelled_by: str = ""
    cancelled_at: Optional[datetime] = None
    cancel_reason: str = ""
    rejected_by: str = ""
    rejected_at: Optional[datetime] = None
    
    # 转为借用记录
    converted_to_borrow: bool = False
    converted_at: Optional[datetime] = None
    
    # 相关人ID（用于借用中设备的预约）
    custodian_id: str = ""
    current_borrower_id: str = ""
    current_borrower_name: str = ""
    
    # 借用原因
    reason: str = ""
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Reservation':
        """从字典创建预约对象"""
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
            device_id=data.get('device_id', ''),
            device_type=data.get('device_type', ''),
            device_name=data.get('device_name', ''),
            reserver_id=data.get('reserver_id', ''),
            reserver_name=data.get('reserver_name', ''),
            start_time=parse_datetime(data.get('start_time')),
            end_time=parse_datetime(data.get('end_time')),
            status=data.get('status', ReservationStatus.PENDING_CUSTODIAN.value),
            created_at=parse_datetime(data.get('created_at')),
            updated_at=parse_datetime(data.get('updated_at')),
            custodian_approved=bool(data.get('custodian_approved', 0)),
            custodian_approved_at=parse_datetime(data.get('custodian_approved_at')),
            borrower_approved=bool(data.get('borrower_approved', 0)),
            borrower_approved_at=parse_datetime(data.get('borrower_approved_at')),
            custodian_notified=bool(data.get('custodian_notified', 0)),
            borrower_notified=bool(data.get('borrower_notified', 0)),
            cancelled_by=data.get('cancelled_by', ''),
            cancelled_at=parse_datetime(data.get('cancelled_at')),
            cancel_reason=data.get('cancel_reason', ''),
            rejected_by=data.get('rejected_by', ''),
            rejected_at=parse_datetime(data.get('rejected_at')),
            converted_to_borrow=bool(data.get('converted_to_borrow', 0)),
            converted_at=parse_datetime(data.get('converted_at')),
            custodian_id=data.get('custodian_id', ''),
            current_borrower_id=data.get('current_borrower_id', ''),
            current_borrower_name=data.get('current_borrower_name', ''),
            reason=data.get('reason', '')
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "device_name": self.device_name,
            "reserver_id": self.reserver_id,
            "reserver_name": self.reserver_name,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else "",
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else "",
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else "",
            "custodian_approved": self.custodian_approved,
            "custodian_approved_at": self.custodian_approved_at.strftime("%Y-%m-%d %H:%M:%S") if self.custodian_approved_at else "",
            "borrower_approved": self.borrower_approved,
            "borrower_approved_at": self.borrower_approved_at.strftime("%Y-%m-%d %H:%M:%S") if self.borrower_approved_at else "",
            "custodian_notified": self.custodian_notified,
            "borrower_notified": self.borrower_notified,
            "cancelled_by": self.cancelled_by,
            "cancelled_at": self.cancelled_at.strftime("%Y-%m-%d %H:%M:%S") if self.cancelled_at else "",
            "cancel_reason": self.cancel_reason,
            "rejected_by": self.rejected_by,
            "rejected_at": self.rejected_at.strftime("%Y-%m-%d %H:%M:%S") if self.rejected_at else "",
            "converted_to_borrow": self.converted_to_borrow,
            "converted_at": self.converted_at.strftime("%Y-%m-%d %H:%M:%S") if self.converted_at else "",
            "custodian_id": self.custodian_id,
            "current_borrower_id": self.current_borrower_id,
            "current_borrower_name": self.current_borrower_name,
            "reason": self.reason
        }


@dataclass
class DeviceImage:
    """设备图片"""
    id: str
    device_id: str
    device_type: str
    filename: str
    url: str
    upload_time: datetime
    uploader: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceImage':
        """从字典创建设备图片对象"""
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
            filename=data.get('filename', ''),
            url=data.get('url', ''),
            upload_time=parse_datetime(data.get('upload_time')),
            uploader=data.get('uploader', '')
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "filename": self.filename,
            "url": self.url,
            "upload_time": self.upload_time.strftime("%Y-%m-%d %H:%M:%S") if self.upload_time else "",
            "uploader": self.uploader
        }


@dataclass
class DeviceAttachment:
    """设备附件"""
    id: str
    device_id: str
    device_type: str
    filename: str
    url: str
    size: int
    upload_time: datetime
    uploader: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceAttachment':
        """从字典创建设备附件对象"""
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
            filename=data.get('filename', ''),
            url=data.get('url', ''),
            size=int(data.get('size', 0)),
            upload_time=parse_datetime(data.get('upload_time')),
            uploader=data.get('uploader', '')
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "filename": self.filename,
            "url": self.url,
            "size": self.size,
            "size_formatted": self.format_size(),
            "upload_time": self.upload_time.strftime("%Y-%m-%d %H:%M:%S") if self.upload_time else "",
            "uploader": self.uploader
        }
    
    def format_size(self) -> str:
        """格式化文件大小"""
        size = self.size
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f}GB"


class PointsTransactionType(Enum):
    """积分交易类型"""
    FIRST_LOGIN = "首次登录"
    DAILY_LOGIN = "每日登录"
    BORROW = "借用设备"
    RETURN = "归还设备"
    OVERDUE = "逾期归还"
    CREATE_BOUNTY = "发布悬赏"
    COMPLETE_BOUNTY = "完成悬赏"
    RECEIVE_BOUNTY = "获得悬赏"
    RANKING_REWARD = "排行榜奖励"
    LIKE = "点赞"
    SEARCH = "搜索设备"
    REPORT_FOUND = "我已找到"
    REPORT_FIXED = "我已修好"
    REPORT_DAMAGED = "损坏报备"
    REPORT_LOST = "丢失报备"
    TRANSFER = "转借设备"
    RENEW = "续期"
    RESERVE = "预约设备"
    SHOP_BUY = "购买商品"


@dataclass
class UserPoints:
    """用户积分"""
    id: str
    user_id: str
    points: int = 0  # 当前积分，可以为负
    total_earned: int = 0  # 累计获得积分
    total_spent: int = 0  # 累计消费积分
    update_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.update_time is None:
            self.update_time = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UserPoints':
        """从字典创建用户积分对象"""
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
            user_id=data.get('user_id', ''),
            points=int(data.get('points', 0)),
            total_earned=int(data.get('total_earned', 0)),
            total_spent=int(data.get('total_spent', 0)),
            update_time=parse_datetime(data.get('update_time'))
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "points": self.points,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "update_time": self.update_time.strftime("%Y-%m-%d %H:%M:%S") if self.update_time else "",
        }


@dataclass
class PointsRecord:
    """积分记录"""
    id: str
    user_id: str
    transaction_type: PointsTransactionType
    points_change: int  # 正数为获得，负数为扣除
    points_after: int  # 变动后的积分
    description: str = ""
    related_id: str = ""  # 相关记录ID（如设备ID、悬赏ID等）
    create_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.create_time is None:
            self.create_time = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PointsRecord':
        """从字典创建积分记录对象"""
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
        
        # 确定交易类型
        trans_type_str = data.get('transaction_type', '首次登录')
        if isinstance(trans_type_str, PointsTransactionType):
            trans_type = trans_type_str
        else:
            try:
                trans_type = PointsTransactionType(trans_type_str)
            except Exception as e:
                # 如果转换失败，尝试通过值查找
                trans_type = None
                for pt in PointsTransactionType:
                    if pt.value == trans_type_str:
                        trans_type = pt
                        break
                if trans_type is None:
                    trans_type = PointsTransactionType.FIRST_LOGIN
        
        return cls(
            id=data.get('id', ''),
            user_id=data.get('user_id', ''),
            transaction_type=trans_type,
            points_change=int(data.get('points_change', 0)),
            points_after=int(data.get('points_after', 0)),
            description=data.get('description', ''),
            related_id=data.get('related_id', ''),
            create_time=parse_datetime(data.get('create_time'))
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "transaction_type": self.transaction_type.value if isinstance(self.transaction_type, PointsTransactionType) else str(self.transaction_type),
            "points_change": self.points_change,
            "points_after": self.points_after,
            "description": self.description,
            "related_id": self.related_id,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
        }


class BountyStatus(Enum):
    """悬赏状态"""
    PENDING = "待认领"
    FOUND = "已找到"  # 有人找到设备，等待悬赏人确认
    COMPLETED = "已完成"
    CANCELLED = "已取消"


@dataclass
class Bounty:
    """悬赏任务"""
    id: str
    title: str  # 悬赏标题
    description: str  # 悬赏描述
    publisher_id: str  # 发布人ID
    publisher_name: str  # 发布人名称
    reward_points: int  # 悬赏积分
    status: BountyStatus = BountyStatus.PENDING
    device_name: str = ""  # 要找的设备名称/型号
    device_id: str = ""  # 关联的设备ID
    device_previous_status: str = ""  # 设备发布悬赏前的状态
    create_time: Optional[datetime] = None
    claim_time: Optional[datetime] = None
    complete_time: Optional[datetime] = None
    claimer_id: str = ""  # 认领人ID
    claimer_name: str = ""  # 认领人名称
    finder_description: str = ""  # 找到设备的描述
    
    def __post_init__(self):
        if self.create_time is None:
            self.create_time = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Bounty':
        """从字典创建悬赏对象"""
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
        
        # 确定状态
        status_str = data.get('status', '待认领')
        if isinstance(status_str, BountyStatus):
            status = status_str
        else:
            try:
                status = BountyStatus(status_str)
            except:
                status = BountyStatus.PENDING
        
        return cls(
            id=data.get('id', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            publisher_id=data.get('publisher_id', ''),
            publisher_name=data.get('publisher_name', ''),
            reward_points=int(data.get('reward_points', 0)),
            status=status,
            device_name=data.get('device_name', ''),
            device_id=data.get('device_id', ''),
            device_previous_status=data.get('device_previous_status', ''),
            create_time=parse_datetime(data.get('create_time')),
            claim_time=parse_datetime(data.get('claim_time')),
            complete_time=parse_datetime(data.get('complete_time')),
            claimer_id=data.get('claimer_id', ''),
            claimer_name=data.get('claimer_name', ''),
            finder_description=data.get('finder_description', '')
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "publisher_id": self.publisher_id,
            "publisher_name": self.publisher_name,
            "reward_points": self.reward_points,
            "status": self.status.value if isinstance(self.status, BountyStatus) else str(self.status),
            "device_name": self.device_name,
            "device_id": self.device_id,
            "device_previous_status": self.device_previous_status,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
            "claim_time": self.claim_time.strftime("%Y-%m-%d %H:%M:%S") if self.claim_time else "",
            "complete_time": self.complete_time.strftime("%Y-%m-%d %H:%M:%S") if self.complete_time else "",
            "claimer_id": self.claimer_id,
            "claimer_name": self.claimer_name,
            "finder_description": self.finder_description,
        }


class ShopItemType(Enum):
    """积分商城商品类型"""
    TITLE = "称号"
    AVATAR_FRAME = "头像边框"
    THEME = "主题皮肤"


class ShopItemSource(Enum):
    """商品来源类型"""
    SHOP = "积分商城"
    ACHIEVEMENT = "成就奖励"
    RANDOM = "随机获得"
    EVENT = "活动获得"


@dataclass
class ShopItem:
    """积分商城商品"""
    id: str
    name: str
    description: str
    item_type: ShopItemType
    price: int
    icon: str = ""  # 图标/样式标识
    color: str = ""  # 颜色主题
    is_active: bool = True
    sort_order: int = 0
    create_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.create_time is None:
            self.create_time = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ShopItem':
        """从字典创建商品对象"""
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
        
        # 确定商品类型
        item_type_str = data.get('item_type', '称号')
        if isinstance(item_type_str, ShopItemType):
            item_type = item_type_str
        else:
            try:
                item_type = ShopItemType(item_type_str)
            except:
                item_type = ShopItemType.TITLE
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            item_type=item_type,
            price=int(data.get('price', 0)),
            icon=data.get('icon', ''),
            color=data.get('color', ''),
            is_active=bool(data.get('is_active', 1)),
            sort_order=int(data.get('sort_order', 0)),
            create_time=parse_datetime(data.get('create_time'))
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "item_type": self.item_type.value if isinstance(self.item_type, ShopItemType) else str(self.item_type),
            "price": self.price,
            "icon": self.icon,
            "color": self.color,
            "is_active": "是" if self.is_active else "否",
            "sort_order": self.sort_order,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
        }


@dataclass
class UserInventory:
    """用户背包/物品"""
    id: str
    user_id: str
    item_id: str
    item_type: ShopItemType
    item_name: str
    item_icon: str
    item_color: str
    source: ShopItemSource
    is_used: bool = False
    acquire_time: Optional[datetime] = None
    use_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.acquire_time is None:
            self.acquire_time = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UserInventory':
        """从字典创建背包物品对象"""
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
        
        # 确定商品类型
        item_type_str = data.get('item_type', '称号')
        if isinstance(item_type_str, ShopItemType):
            item_type = item_type_str
        else:
            try:
                item_type = ShopItemType(item_type_str)
            except:
                item_type = ShopItemType.TITLE
        
        # 确定来源类型
        source_str = data.get('source', '积分商城')
        if isinstance(source_str, ShopItemSource):
            source = source_str
        else:
            try:
                source = ShopItemSource(source_str)
            except:
                source = ShopItemSource.SHOP
        
        return cls(
            id=data.get('id', ''),
            user_id=data.get('user_id', ''),
            item_id=data.get('item_id', ''),
            item_type=item_type,
            item_name=data.get('item_name', ''),
            item_icon=data.get('item_icon', ''),
            item_color=data.get('item_color', ''),
            source=source,
            is_used=bool(data.get('is_used', 0)),
            acquire_time=parse_datetime(data.get('acquire_time')),
            use_time=parse_datetime(data.get('use_time'))
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item_id": self.item_id,
            "item_type": self.item_type.value if isinstance(self.item_type, ShopItemType) else str(self.item_type),
            "item_name": self.item_name,
            "item_icon": self.item_icon,
            "item_color": self.item_color,
            "source": self.source.value if isinstance(self.source, ShopItemSource) else str(self.source),
            "is_used": "使用中" if self.is_used else "未使用",
            "acquire_time": self.acquire_time.strftime("%Y-%m-%d %H:%M:%S") if self.acquire_time else "",
            "use_time": self.use_time.strftime("%Y-%m-%d %H:%M:%S") if self.use_time else "",
        }
