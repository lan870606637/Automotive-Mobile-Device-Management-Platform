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
    BORROWED = "借出"
    SHIPPED = "已寄出"
    DAMAGED = "已损坏"
    LOST = "丢失"
    SCRAPPED = "报废"


class DeviceType(Enum):
    """设备类型"""
    CAR_MACHINE = "车机"
    PHONE = "手机"


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
    CUSTODIAN_CHANGE = "保管人变更"
    NOT_FOUND = "借用人未找到"
    RENEW = "借用续期"


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
    is_deleted: bool = False
    
    # 借用信息
    borrower: str = ""
    phone: str = ""
    borrow_time: Optional[datetime] = None
    location: str = ""
    reason: str = ""
    entry_source: str = ""
    expected_return_date: Optional[datetime] = None
    admin_operator: str = ""  # 管理员录入/转借时的操作人
    
    # 丢失/损坏信息
    lost_time: Optional[datetime] = None
    damage_reason: str = ""
    damage_time: Optional[datetime] = None
    previous_borrower: str = ""  # 上一个借用人
    
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
        }


@dataclass
class CarMachine(Device):
    """车机设备"""
    def __init__(self, **kwargs):
        kwargs['device_type'] = DeviceType.CAR_MACHINE
        super().__init__(**kwargs)


@dataclass
class Phone(Device):
    """手机设备"""
    def __init__(self, **kwargs):
        kwargs['device_type'] = DeviceType.PHONE
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
    content: str
    creator: str
    create_time: datetime
    is_inappropriate: bool = False
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
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
    viewer: str
    view_time: datetime
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "viewer": self.viewer,
            "view_time": self.view_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
