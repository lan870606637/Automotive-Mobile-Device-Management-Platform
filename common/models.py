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
    borrower: str = ""
    phone: str = ""
    borrow_time: Optional[datetime] = None
    location: str = ""
    reason: str = ""
    entry_source: str = ""
    expected_return_date: Optional[datetime] = None
    admin_operator: str = ""  # 管理员录入/转借时的操作人

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
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type.value,
            "model": self.model,
            "cabinet_number": self.cabinet_number,
            "status": self.status.value,
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "operation_type": self.operation_type.value,
            "operator": self.operator,
            "operation_time": self.operation_time.strftime("%Y-%m-%d %H:%M:%S"),
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
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "content": self.content,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_inappropriate": "是" if self.is_inappropriate else "否",
        }


@dataclass
class User:
    """用户信息"""
    id: str
    wechat_name: str
    phone: str
    password: str = "123456"  # 默认密码
    borrower_name: str = ""   # 借用人名称（必填，唯一）
    borrow_count: int = 0
    is_frozen: bool = False
    is_admin: bool = False    # 是否为管理员
    is_deleted: bool = False  # 是否已删除
    create_time: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "wechat_name": self.wechat_name,
            "phone": self.phone,
            "password": self.password,
            "borrower_name": self.borrower_name,
            "borrow_count": self.borrow_count,
            "is_frozen": "已冻结" if self.is_frozen else "正常",
            "is_admin": "是" if self.is_admin else "否",
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
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "operation_time": self.operation_time.strftime("%Y-%m-%d %H:%M:%S"),
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_type": self.device_type,
            "viewer": self.viewer,
            "view_time": self.view_time.strftime("%Y-%m-%d %H:%M:%S"),
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
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
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
