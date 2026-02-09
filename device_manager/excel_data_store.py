# -*- coding: utf-8 -*-
"""
Excel 数据存储模块
从本地Excel文件读取和保存数据
"""
import os
import pandas as pd
from datetime import datetime
from typing import List, Optional

from models import Device, CarMachine, Phone, Record, UserRemark, User, OperationLog, Admin
from models import DeviceStatus, DeviceType, OperationType, EntrySource

# Excel文件路径
EXCEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'excel_templates')
CAR_FILE = os.path.join(EXCEL_DIR, '车机表.xlsx')
PHONE_FILE = os.path.join(EXCEL_DIR, '手机表.xlsx')
RECORD_FILE = os.path.join(EXCEL_DIR, '记录表.xlsx')
REMARK_FILE = os.path.join(EXCEL_DIR, '用户备注表.xlsx')
USER_FILE = os.path.join(EXCEL_DIR, '用户表.xlsx')
OPERATION_LOG_FILE = os.path.join(EXCEL_DIR, '操作日志表.xlsx')
VIEW_RECORD_FILE = os.path.join(EXCEL_DIR, '查看记录表.xlsx')
ADMIN_FILE = os.path.join(EXCEL_DIR, '管理员表.xlsx')


class ExcelDataStore:
    """Excel数据存储类"""
    
    @staticmethod
    def load_car_machines() -> List[CarMachine]:
        """从Excel加载车机数据"""
        devices = []
        if not os.path.exists(CAR_FILE):
            return devices
        
        try:
            df = pd.read_excel(CAR_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('设备ID')):
                    continue
                
                # 处理可能为NaN的字符串字段
                def safe_str(val):
                    if pd.isna(val) or str(val).lower() == 'nan':
                        return ''
                    return str(val)
                
                device = CarMachine(
                    id=str(row['设备ID']),
                    name=str(row['设备名']),
                    model=safe_str(row.get('型号', '')),
                    cabinet_number=safe_str(row.get('柜号', '')),
                    status=DeviceStatus(row['状态']) if pd.notna(row.get('状态')) else DeviceStatus.IN_STOCK,
                    remark=safe_str(row.get('备注', '')),
                    is_deleted=str(row.get('是否删除', '否')) == '是',
                )
                
                # 借用信息
                if pd.notna(row.get('借用人')):
                    device.borrower = safe_str(row['借用人'])
                if pd.notna(row.get('手机号')):
                    device.phone = safe_str(row['手机号'])
                if pd.notna(row.get('借用时间')):
                    try:
                        device.borrow_time = pd.to_datetime(row['借用时间'])
                    except:
                        pass
                if pd.notna(row.get('借用地点')):
                    device.location = safe_str(row['借用地点'])
                if pd.notna(row.get('借用原因')):
                    device.reason = safe_str(row['借用原因'])
                if pd.notna(row.get('录入者')):
                    device.entry_source = safe_str(row['录入者'])
                if pd.notna(row.get('预计归还日期')):
                    try:
                        device.expected_return_date = pd.to_datetime(row['预计归还日期'])
                    except:
                        pass
                # 丢失/损坏信息
                if pd.notna(row.get('丢失时间')):
                    try:
                        device.lost_time = pd.to_datetime(row['丢失时间'])
                    except:
                        pass
                if pd.notna(row.get('损坏原因')):
                    device.damage_reason = str(row['损坏原因'])
                if pd.notna(row.get('损坏时间')):
                    try:
                        device.damage_time = pd.to_datetime(row['损坏时间'])
                    except:
                        pass
                if pd.notna(row.get('上一个借用人')):
                    device.previous_borrower = str(row['上一个借用人'])
                
                if not device.is_deleted:
                    devices.append(device)
        except Exception as e:
            print(f"加载车机数据失败: {e}")
        
        return devices
    
    @staticmethod
    def load_phones() -> List[Phone]:
        """从Excel加载手机数据"""
        devices = []
        if not os.path.exists(PHONE_FILE):
            return devices
        
        try:
            df = pd.read_excel(PHONE_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('设备ID')):
                    continue
                
                # 处理可能为NaN的字符串字段
                def safe_str(val):
                    if pd.isna(val) or str(val).lower() == 'nan':
                        return ''
                    return str(val)
                
                device = Phone(
                    id=str(row['设备ID']),
                    name=str(row['设备名']),
                    model=safe_str(row.get('型号', '')),
                    cabinet_number=safe_str(row.get('保管人', '')),
                    status=DeviceStatus(row['状态']) if pd.notna(row.get('状态')) else DeviceStatus.IN_STOCK,
                    remark=safe_str(row.get('备注', '')),
                    is_deleted=str(row.get('是否删除', '否')) == '是',
                )
                
                # 借用信息
                if pd.notna(row.get('借用人')):
                    device.borrower = safe_str(row['借用人'])
                if pd.notna(row.get('手机号')):
                    device.phone = safe_str(row['手机号'])
                if pd.notna(row.get('借用时间')):
                    try:
                        device.borrow_time = pd.to_datetime(row['借用时间'])
                    except:
                        pass
                if pd.notna(row.get('借用地点')):
                    device.location = safe_str(row['借用地点'])
                if pd.notna(row.get('借用原因')):
                    device.reason = safe_str(row['借用原因'])
                if pd.notna(row.get('录入者')):
                    device.entry_source = safe_str(row['录入者'])
                if pd.notna(row.get('预计归还日期')):
                    try:
                        device.expected_return_date = pd.to_datetime(row['预计归还日期'])
                    except:
                        pass
                # 丢失/损坏信息
                if pd.notna(row.get('丢失时间')):
                    try:
                        device.lost_time = pd.to_datetime(row['丢失时间'])
                    except:
                        pass
                if pd.notna(row.get('损坏原因')):
                    device.damage_reason = str(row['损坏原因'])
                if pd.notna(row.get('损坏时间')):
                    try:
                        device.damage_time = pd.to_datetime(row['损坏时间'])
                    except:
                        pass
                if pd.notna(row.get('上一个借用人')):
                    device.previous_borrower = str(row['上一个借用人'])
                
                if not device.is_deleted:
                    devices.append(device)
        except Exception as e:
            print(f"加载手机数据失败: {e}")
        
        return devices
    
    @staticmethod
    def save_car_machines(devices: List[CarMachine]):
        """保存车机数据到Excel"""
        data = []
        for device in devices:
            data.append({
                '设备ID': device.id,
                '设备名': device.name,
                '型号': device.model,
                '柜号': device.cabinet_number,
                '状态': device.status.value,
                '备注': device.remark,
                '借用人': device.borrower,
                '手机号': device.phone,
                '借用时间': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                '借用地点': device.location,
                '借用原因': device.reason,
                '录入者': device.entry_source,
                '预计归还日期': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else '',
                '是否删除': '是' if device.is_deleted else '否',
                '丢失时间': device.lost_time.strftime('%Y-%m-%d %H:%M') if device.lost_time else '',
                '损坏原因': device.damage_reason,
                '损坏时间': device.damage_time.strftime('%Y-%m-%d %H:%M') if device.damage_time else '',
                '上一个借用人': device.previous_borrower,
            })
        
        df = pd.DataFrame(data)
        df.to_excel(CAR_FILE, index=False)
    
    @staticmethod
    def save_phones(devices: List[Phone]):
        """保存手机数据到Excel"""
        data = []
        for device in devices:
            data.append({
                '设备ID': device.id,
                '设备名': device.name,
                '型号': device.model,
                '保管人': device.cabinet_number,
                '状态': device.status.value,
                '备注': device.remark,
                '借用人': device.borrower,
                '手机号': device.phone,
                '借用时间': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                '借用地点': device.location,
                '借用原因': device.reason,
                '录入者': device.entry_source,
                '预计归还日期': device.expected_return_date.strftime('%Y-%m-%d') if device.expected_return_date else '',
                '是否删除': '是' if device.is_deleted else '否',
                '丢失时间': device.lost_time.strftime('%Y-%m-%d %H:%M') if device.lost_time else '',
                '损坏原因': device.damage_reason,
                '损坏时间': device.damage_time.strftime('%Y-%m-%d %H:%M') if device.damage_time else '',
                '上一个借用人': device.previous_borrower,
            })
        
        df = pd.DataFrame(data)
        df.to_excel(PHONE_FILE, index=False)
    
    @staticmethod
    def load_records() -> List[Record]:
        """从Excel加载记录"""
        records = []
        if not os.path.exists(RECORD_FILE):
            return records
        
        try:
            df = pd.read_excel(RECORD_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('记录ID')):
                    continue
                
                try:
                    # 处理可能为NaN的字符串字段
                    def safe_str(val):
                        if pd.isna(val) or str(val).lower() == 'nan':
                            return ''
                        return str(val)
                    
                    record = Record(
                        id=str(row['记录ID']),
                        device_id=str(row['设备ID']),
                        device_name=str(row['设备名']),
                        device_type=str(row['设备类型']),
                        operation_type=OperationType(row['操作类型']),
                        operator=str(row['操作人']),
                        operation_time=pd.to_datetime(row['操作时间']),
                        borrower=safe_str(row.get('借用人', '')),
                        phone=safe_str(row.get('手机号', '')),
                        reason=safe_str(row.get('原因', '')),
                        entry_source=safe_str(row.get('录入者', '')),
                        remark=safe_str(row.get('备注', '')),
                    )
                    records.append(record)
                except Exception as e:
                    print(f"解析记录失败: {e}")
                    continue
        except Exception as e:
            print(f"加载记录失败: {e}")
        
        return records
    
    @staticmethod
    def save_records(records: List[Record]):
        """保存记录到Excel"""
        data = []
        for record in records:
            data.append({
                '记录ID': record.id,
                '设备ID': record.device_id,
                '设备名': record.device_name,
                '设备类型': record.device_type,
                '操作类型': record.operation_type.value,
                '操作人': record.operator,
                '操作时间': record.operation_time.strftime('%Y-%m-%d %H:%M:%S'),
                '借用人': record.borrower,
                '手机号': record.phone,
                '原因': record.reason,
                '录入者': record.entry_source,
                '备注': record.remark,
            })
        
        df = pd.DataFrame(data)
        df.to_excel(RECORD_FILE, index=False)
    
    @staticmethod
    def load_remarks() -> List[UserRemark]:
        """从Excel加载备注"""
        remarks = []
        if not os.path.exists(REMARK_FILE):
            return remarks
        
        try:
            df = pd.read_excel(REMARK_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('备注ID')):
                    continue
                
                try:
                    remark = UserRemark(
                        id=str(row['备注ID']),
                        device_id=str(row['设备ID']),
                        content=str(row['备注内容']),
                        creator=str(row['创建人']),
                        create_time=pd.to_datetime(row['创建时间']),
                    )
                    remark.is_inappropriate = str(row.get('是否不当', '否')) == '是'
                    remarks.append(remark)
                except Exception as e:
                    print(f"解析备注失败: {e}")
                    continue
        except Exception as e:
            print(f"加载备注失败: {e}")
        
        return remarks
    
    @staticmethod
    def save_remarks(remarks: List[UserRemark]):
        """保存备注到Excel"""
        data = []
        for remark in remarks:
            data.append({
                '备注ID': remark.id,
                '设备ID': remark.device_id,
                '设备名': '',  # 可从设备表关联
                '备注内容': remark.content,
                '创建人': remark.creator,
                '创建时间': remark.create_time.strftime('%Y-%m-%d %H:%M'),
                '是否不当': '是' if remark.is_inappropriate else '否',
            })
        
        df = pd.DataFrame(data)
        df.to_excel(REMARK_FILE, index=False)
    
    @staticmethod
    def load_users() -> List[User]:
        """从Excel加载用户"""
        users = []
        if not os.path.exists(USER_FILE):
            return users
        
        try:
            df = pd.read_excel(USER_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('用户ID')):
                    continue
                
                try:
                    create_time = None
                    if pd.notna(row.get('注册时间')):
                        create_time = pd.to_datetime(row['注册时间'])
                    
                    user = User(
                        id=str(row['用户ID']),
                        wechat_name=str(row['微信名']),
                        phone=str(row['手机号']),
                        password=str(row.get('密码', '123456')),
                        borrower_name=str(row.get('借用人', '')),
                        borrow_count=int(row.get('借用次数', 0)),
                        is_frozen=str(row.get('状态', '正常')) == '已冻结',
                        is_admin=str(row.get('是否管理员', '否')) == '是',
                        create_time=create_time,
                    )
                    users.append(user)
                except Exception as e:
                    print(f"解析用户失败: {e}")
                    continue
        except Exception as e:
            print(f"加载用户失败: {e}")
        
        return users
    
    @staticmethod
    def save_users(users: List[User]):
        """保存用户到Excel"""
        data = []
        for user in users:
            data.append({
                '用户ID': user.id,
                '微信名': user.wechat_name,
                '手机号': user.phone,
                '密码': user.password,
                '借用人': user.borrower_name,
                '借用次数': user.borrow_count,
                '状态': '已冻结' if user.is_frozen else '正常',
                '是否管理员': '是' if user.is_admin else '否',
                '注册时间': user.create_time.strftime('%Y-%m-%d') if user.create_time else '',
            })
        
        df = pd.DataFrame(data)
        df.to_excel(USER_FILE, index=False)

    @staticmethod
    def load_operation_logs() -> List[OperationLog]:
        """从Excel加载操作日志"""
        logs = []
        if not os.path.exists(OPERATION_LOG_FILE):
            return logs
        
        try:
            df = pd.read_excel(OPERATION_LOG_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('日志ID')):
                    continue
                
                try:
                    log = OperationLog(
                        id=str(row['日志ID']),
                        operation_time=pd.to_datetime(row['操作时间']),
                        operator=str(row['操作人']),
                        operation_content=str(row['操作内容']),
                        device_info=str(row['设备信息'])
                    )
                    logs.append(log)
                except Exception as e:
                    print(f"解析操作日志失败: {e}")
                    continue
        except Exception as e:
            print(f"加载操作日志失败: {e}")
        
        return logs
    
    @staticmethod
    def save_operation_logs(logs: List[OperationLog]):
        """保存操作日志到Excel"""
        data = []
        for log in logs:
            data.append({
                '日志ID': log.id,
                '操作时间': log.operation_time.strftime('%Y-%m-%d %H:%M'),
                '操作人': log.operator,
                '操作内容': log.operation_content,
                '设备信息': log.device_info,
            })
        
        df = pd.DataFrame(data)
        df.to_excel(OPERATION_LOG_FILE, index=False)

    @staticmethod
    def load_view_records() -> List:
        """从Excel加载查看记录"""
        from models import ViewRecord
        records = []
        if not os.path.exists(VIEW_RECORD_FILE):
            return records
        
        try:
            df = pd.read_excel(VIEW_RECORD_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('记录ID')):
                    continue
                
                try:
                    record = ViewRecord(
                        id=str(row['记录ID']),
                        device_id=str(row['设备ID']),
                        viewer=str(row['查看人']),
                        view_time=pd.to_datetime(row['查看时间'])
                    )
                    records.append(record)
                except Exception as e:
                    print(f"解析查看记录失败: {e}")
                    continue
        except Exception as e:
            print(f"加载查看记录失败: {e}")
        
        return records
    
    @staticmethod
    def save_view_records(records: List):
        """保存查看记录到Excel"""
        data = []
        for record in records:
            data.append({
                '记录ID': record.id,
                '设备ID': record.device_id,
                '查看人': record.viewer,
                '查看时间': record.view_time.strftime('%Y-%m-%d %H:%M'),
            })
        
        df = pd.DataFrame(data)
        df.to_excel(VIEW_RECORD_FILE, index=False)

    @staticmethod
    def load_admins() -> List[Admin]:
        """从Excel加载管理员列表"""
        admins = []
        if not os.path.exists(ADMIN_FILE):
            return admins
        
        try:
            df = pd.read_excel(ADMIN_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('管理员ID')):
                    continue
                
                try:
                    create_time = None
                    if pd.notna(row.get('创建时间')):
                        create_time = pd.to_datetime(row['创建时间'])
                    
                    admin = Admin(
                        id=str(row['管理员ID']),
                        username=str(row['账号']),
                        password=str(row['密码']),
                        create_time=create_time
                    )
                    admins.append(admin)
                except Exception as e:
                    print(f"解析管理员失败: {e}")
                    continue
        except Exception as e:
            print(f"加载管理员失败: {e}")
        
        return admins
    
    @staticmethod
    def save_admins(admins: List[Admin]):
        """保存管理员列表到Excel"""
        data = []
        for admin in admins:
            data.append({
                '管理员ID': admin.id,
                '账号': admin.username,
                '密码': admin.password,
                '创建时间': admin.create_time.strftime('%Y-%m-%d %H:%M') if admin.create_time else '',
            })
        
        df = pd.DataFrame(data)
        df.to_excel(ADMIN_FILE, index=False)
