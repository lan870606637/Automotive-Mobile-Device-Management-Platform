# -*- coding: utf-8 -*-
"""
Excel 数据存储模块
从本地Excel文件读取和保存数据
"""
import os
import pandas as pd
from datetime import datetime
from typing import List, Optional

from .models import Device, CarMachine, Instrument, Phone, SimCard, OtherDevice, Record, UserRemark, User, OperationLog, Admin, Notification
from .models import DeviceStatus, DeviceType, OperationType, EntrySource

# Excel文件路径
EXCEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'excel_templates')
CAR_FILE = os.path.join(EXCEL_DIR, '车机表.xlsx')
INSTRUMENT_FILE = os.path.join(EXCEL_DIR, '仪表表.xlsx')
PHONE_FILE = os.path.join(EXCEL_DIR, '手机表.xlsx')
SIM_CARD_FILE = os.path.join(EXCEL_DIR, '手机卡表.xlsx')
OTHER_DEVICE_FILE = os.path.join(EXCEL_DIR, '其它设备表.xlsx')
RECORD_FILE = os.path.join(EXCEL_DIR, '记录表.xlsx')
REMARK_FILE = os.path.join(EXCEL_DIR, '用户备注表.xlsx')
USER_FILE = os.path.join(EXCEL_DIR, '用户表.xlsx')
OPERATION_LOG_FILE = os.path.join(EXCEL_DIR, '操作日志表.xlsx')
VIEW_RECORD_FILE = os.path.join(EXCEL_DIR, '查看记录表.xlsx')
ADMIN_FILE = os.path.join(EXCEL_DIR, '管理员表.xlsx')
NOTIFICATION_FILE = os.path.join(EXCEL_DIR, '通知表.xlsx')


class ExcelDataStore:
    """Excel数据存储类"""

    @staticmethod
    def _safe_print(message):
        """安全打印，处理Windows控制台编码问题"""
        try:
            print(message)
        except OSError:
            # 如果打印失败（如编码问题），忽略错误
            pass

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

                create_time = None
                if pd.notna(row.get('创建时间')):
                    try:
                        create_time = pd.to_datetime(row['创建时间'])
                    except:
                        pass
                device = CarMachine(
                    id=str(row['设备ID']),
                    name=str(row['设备名']),
                    model=safe_str(row.get('型号', '')),
                    cabinet_number=safe_str(row.get('柜号', '')),
                    status=DeviceStatus(row['状态']) if pd.notna(row.get('状态')) else DeviceStatus.IN_STOCK,
                    remark=safe_str(row.get('备注', '')),
                    jira_address=safe_str(row.get('JIRA地址', '')),
                    is_deleted=str(row.get('是否删除', '否')) == '是',
                    create_time=create_time,
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
                # 车机特有信息
                if pd.notna(row.get('软件版本')):
                    device.software_version = safe_str(row['软件版本'])
                if pd.notna(row.get('芯片型号')):
                    device.hardware_version = safe_str(row['芯片型号'])
                # 车机和仪表共有字段（JIRA地址后）
                if pd.notna(row.get('项目属性')):
                    device.project_attribute = safe_str(row['项目属性'])
                if pd.notna(row.get('连接方式')):
                    device.connection_method = safe_str(row['连接方式'])
                if pd.notna(row.get('系统版本')):
                    device.os_version = safe_str(row['系统版本'])
                if pd.notna(row.get('系统平台')):
                    device.os_platform = safe_str(row['系统平台'])
                if pd.notna(row.get('产品名称')):
                    device.product_name = safe_str(row['产品名称'])
                if pd.notna(row.get('屏幕方向')):
                    device.screen_orientation = safe_str(row['屏幕方向'])
                if pd.notna(row.get('车机分辨率')):
                    device.screen_resolution = safe_str(row['车机分辨率'])
                # 寄出信息
                if pd.notna(row.get('寄出时间')):
                    try:
                        device.ship_time = pd.to_datetime(row['寄出时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出备注')):
                    device.ship_remark = str(row['寄出备注'])
                if pd.notna(row.get('寄出人')):
                    device.ship_by = str(row['寄出人'])
                if pd.notna(row.get('寄出前借用人')):
                    device.pre_ship_borrower = str(row['寄出前借用人'])
                if pd.notna(row.get('寄出前借用时间')):
                    try:
                        device.pre_ship_borrow_time = pd.to_datetime(row['寄出前借用时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出前预计归还')):
                    try:
                        device.pre_ship_expected_return_date = pd.to_datetime(row['寄出前预计归还'])
                    except:
                        pass
                
                if not device.is_deleted:
                    devices.append(device)
        except Exception as e:
            ExcelDataStore._safe_print(f"加载车机数据失败: {e}")
        
        return devices

    @staticmethod
    def load_instruments() -> List[Instrument]:
        """从Excel加载仪表数据（与车机表结构一致）"""
        devices = []
        if not os.path.exists(INSTRUMENT_FILE):
            return devices
        
        try:
            df = pd.read_excel(INSTRUMENT_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('设备ID')):
                    continue
                
                def safe_str(val):
                    if pd.isna(val) or str(val).lower() == 'nan':
                        return ''
                    return str(val)
                
                create_time = None
                if pd.notna(row.get('创建时间')):
                    try:
                        create_time = pd.to_datetime(row['创建时间'])
                    except:
                        pass
                device = Instrument(
                    id=str(row['设备ID']),
                    name=str(row['设备名']),
                    model=safe_str(row.get('型号', '')),
                    cabinet_number=safe_str(row.get('柜号', '')),
                    status=DeviceStatus(row['状态']) if pd.notna(row.get('状态')) else DeviceStatus.IN_STOCK,
                    remark=safe_str(row.get('备注', '')),
                    jira_address=safe_str(row.get('JIRA地址', '')),
                    is_deleted=str(row.get('是否删除', '否')) == '是',
                    create_time=create_time,
                )
                
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
                # 仪表特有字段（与车机一致）
                if pd.notna(row.get('软件版本')):
                    device.software_version = safe_str(row['软件版本'])
                if pd.notna(row.get('芯片型号')):
                    device.hardware_version = safe_str(row['芯片型号'])
                # 车机和仪表共有字段（JIRA地址后）
                if pd.notna(row.get('项目属性')):
                    device.project_attribute = safe_str(row['项目属性'])
                if pd.notna(row.get('连接方式')):
                    device.connection_method = safe_str(row['连接方式'])
                if pd.notna(row.get('系统版本')):
                    device.os_version = safe_str(row['系统版本'])
                if pd.notna(row.get('系统平台')):
                    device.os_platform = safe_str(row['系统平台'])
                if pd.notna(row.get('产品名称')):
                    device.product_name = safe_str(row['产品名称'])
                if pd.notna(row.get('寄出时间')):
                    try:
                        device.ship_time = pd.to_datetime(row['寄出时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出备注')):
                    device.ship_remark = str(row['寄出备注'])
                if pd.notna(row.get('寄出人')):
                    device.ship_by = str(row['寄出人'])
                if pd.notna(row.get('寄出前借用人')):
                    device.pre_ship_borrower = str(row['寄出前借用人'])
                if pd.notna(row.get('寄出前借用时间')):
                    try:
                        device.pre_ship_borrow_time = pd.to_datetime(row['寄出前借用时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出前预计归还')):
                    try:
                        device.pre_ship_expected_return_date = pd.to_datetime(row['寄出前预计归还'])
                    except:
                        pass
                
                if not device.is_deleted:
                    devices.append(device)
        except Exception as e:
            ExcelDataStore._safe_print(f"加载仪表数据失败: {e}")
        
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
                
                # 手机默认状态为保管中，如果Excel中是'在库'则转换为'保管中'
                status_value = row['状态'] if pd.notna(row.get('状态')) else None
                if status_value == '在库':
                    status_value = '保管中'
                create_time = None
                if pd.notna(row.get('创建时间')):
                    try:
                        create_time = pd.to_datetime(row['创建时间'])
                    except:
                        pass
                device = Phone(
                    id=str(row['设备ID']),
                    name=str(row['设备名']),
                    model=safe_str(row.get('型号', '')),
                    cabinet_number=safe_str(row.get('保管人', '')),
                    status=DeviceStatus(status_value) if status_value else DeviceStatus.IN_CUSTODY,
                    remark=safe_str(row.get('备注', '')),
                    jira_address=safe_str(row.get('JIRA地址', '')),
                    is_deleted=str(row.get('是否删除', '否')) == '是',
                    create_time=create_time,
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
                # 手机特有信息
                if pd.notna(row.get('SN码')):
                    device.sn = safe_str(row['SN码'])
                if pd.notna(row.get('系统版本')):
                    device.system_version = safe_str(row['系统版本'])
                if pd.notna(row.get('IMEI')):
                    device.imei = safe_str(row['IMEI'])
                if pd.notna(row.get('运营商')):
                    device.carrier = safe_str(row['运营商'])
                # 寄出信息
                if pd.notna(row.get('寄出时间')):
                    try:
                        device.ship_time = pd.to_datetime(row['寄出时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出备注')):
                    device.ship_remark = str(row['寄出备注'])
                if pd.notna(row.get('寄出人')):
                    device.ship_by = str(row['寄出人'])
                if pd.notna(row.get('寄出前借用人')):
                    device.pre_ship_borrower = str(row['寄出前借用人'])
                if pd.notna(row.get('寄出前借用时间')):
                    try:
                        device.pre_ship_borrow_time = pd.to_datetime(row['寄出前借用时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出前预计归还')):
                    try:
                        device.pre_ship_expected_return_date = pd.to_datetime(row['寄出前预计归还'])
                    except:
                        pass
                
                if not device.is_deleted:
                    devices.append(device)
        except Exception as e:
            ExcelDataStore._safe_print(f"加载手机数据失败: {e}")
        
        return devices

    @staticmethod
    def load_sim_cards() -> List[SimCard]:
        """从Excel加载手机卡数据（与手机表结构一致，但型号字段对应号码）"""
        devices = []
        if not os.path.exists(SIM_CARD_FILE):
            return devices
        
        try:
            df = pd.read_excel(SIM_CARD_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('设备ID')):
                    continue
                
                def safe_str(val):
                    if pd.isna(val) or str(val).lower() == 'nan':
                        return ''
                    return str(val)
                
                # 手机卡默认状态为保管中，如果Excel中是'在库'则转换为'保管中'
                status_value = row['状态'] if pd.notna(row.get('状态')) else None
                if status_value == '在库':
                    status_value = '保管中'
                create_time = None
                if pd.notna(row.get('创建时间')):
                    try:
                        create_time = pd.to_datetime(row['创建时间'])
                    except:
                        pass
                device = SimCard(
                    id=str(row['设备ID']),
                    name=str(row['设备名']),
                    model=safe_str(row.get('号码', '')),
                    cabinet_number=safe_str(row.get('保管人', '')),
                    status=DeviceStatus(status_value) if status_value else DeviceStatus.IN_CUSTODY,
                    remark=safe_str(row.get('备注', '')),
                    jira_address=safe_str(row.get('JIRA地址', '')),
                    is_deleted=str(row.get('是否删除', '否')) == '是',
                    create_time=create_time,
                )
                
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
                # 仪表特有字段（与车机一致）
                if pd.notna(row.get('软件版本')):
                    device.software_version = safe_str(row['软件版本'])
                if pd.notna(row.get('芯片型号')):
                    device.hardware_version = safe_str(row['芯片型号'])
                # 车机和仪表共有字段（JIRA地址后）
                if pd.notna(row.get('项目属性')):
                    device.project_attribute = safe_str(row['项目属性'])
                if pd.notna(row.get('连接方式')):
                    device.connection_method = safe_str(row['连接方式'])
                if pd.notna(row.get('系统版本')):
                    device.os_version = safe_str(row['系统版本'])
                if pd.notna(row.get('系统平台')):
                    device.os_platform = safe_str(row['系统平台'])
                if pd.notna(row.get('产品名称')):
                    device.product_name = safe_str(row['产品名称'])
                if pd.notna(row.get('寄出时间')):
                    try:
                        device.ship_time = pd.to_datetime(row['寄出时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出备注')):
                    device.ship_remark = str(row['寄出备注'])
                if pd.notna(row.get('寄出人')):
                    device.ship_by = str(row['寄出人'])
                if pd.notna(row.get('寄出前借用人')):
                    device.pre_ship_borrower = str(row['寄出前借用人'])
                if pd.notna(row.get('寄出前借用时间')):
                    try:
                        device.pre_ship_borrow_time = pd.to_datetime(row['寄出前借用时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出前预计归还')):
                    try:
                        device.pre_ship_expected_return_date = pd.to_datetime(row['寄出前预计归还'])
                    except:
                        pass
                
                if not device.is_deleted:
                    devices.append(device)
        except Exception as e:
            ExcelDataStore._safe_print(f"加载手机卡数据失败: {e}")
        
        return devices

    @staticmethod
    def load_other_devices() -> List[OtherDevice]:
        """从Excel加载其它设备数据（与手机表结构一致）"""
        devices = []
        if not os.path.exists(OTHER_DEVICE_FILE):
            return devices
        
        try:
            df = pd.read_excel(OTHER_DEVICE_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('设备ID')):
                    continue
                
                def safe_str(val):
                    if pd.isna(val) or str(val).lower() == 'nan':
                        return ''
                    return str(val)
                
                # 其它设备默认状态为保管中，如果Excel中是'在库'则转换为'保管中'
                status_value = row['状态'] if pd.notna(row.get('状态')) else None
                if status_value == '在库':
                    status_value = '保管中'
                create_time = None
                if pd.notna(row.get('创建时间')):
                    try:
                        create_time = pd.to_datetime(row['创建时间'])
                    except:
                        pass
                device = OtherDevice(
                    id=str(row['设备ID']),
                    name=str(row['设备名']),
                    model=safe_str(row.get('型号', '')),
                    cabinet_number=safe_str(row.get('保管人', '')),
                    status=DeviceStatus(status_value) if status_value else DeviceStatus.IN_CUSTODY,
                    remark=safe_str(row.get('备注', '')),
                    jira_address=safe_str(row.get('JIRA地址', '')),
                    is_deleted=str(row.get('是否删除', '否')) == '是',
                    create_time=create_time,
                )
                
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
                # 仪表特有字段（与车机一致）
                if pd.notna(row.get('软件版本')):
                    device.software_version = safe_str(row['软件版本'])
                if pd.notna(row.get('芯片型号')):
                    device.hardware_version = safe_str(row['芯片型号'])
                # 车机和仪表共有字段（JIRA地址后）
                if pd.notna(row.get('项目属性')):
                    device.project_attribute = safe_str(row['项目属性'])
                if pd.notna(row.get('连接方式')):
                    device.connection_method = safe_str(row['连接方式'])
                if pd.notna(row.get('系统版本')):
                    device.os_version = safe_str(row['系统版本'])
                if pd.notna(row.get('系统平台')):
                    device.os_platform = safe_str(row['系统平台'])
                if pd.notna(row.get('产品名称')):
                    device.product_name = safe_str(row['产品名称'])
                if pd.notna(row.get('寄出时间')):
                    try:
                        device.ship_time = pd.to_datetime(row['寄出时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出备注')):
                    device.ship_remark = str(row['寄出备注'])
                if pd.notna(row.get('寄出人')):
                    device.ship_by = str(row['寄出人'])
                if pd.notna(row.get('寄出前借用人')):
                    device.pre_ship_borrower = str(row['寄出前借用人'])
                if pd.notna(row.get('寄出前借用时间')):
                    try:
                        device.pre_ship_borrow_time = pd.to_datetime(row['寄出前借用时间'])
                    except:
                        pass
                if pd.notna(row.get('寄出前预计归还')):
                    try:
                        device.pre_ship_expected_return_date = pd.to_datetime(row['寄出前预计归还'])
                    except:
                        pass
                
                if not device.is_deleted:
                    devices.append(device)
        except Exception as e:
            ExcelDataStore._safe_print(f"加载其它设备数据失败: {e}")
        
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
                'JIRA地址': device.jira_address,
                '创建时间': device.create_time.strftime('%Y-%m-%d %H:%M:%S') if device.create_time else '',
                '借用人': device.borrower,
                '手机号': device.phone,
                '借用时间': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                '借用地点': device.location,
                '借用原因': device.reason,
                '录入者': device.entry_source,
                '预计归还日期': device.expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.expected_return_date else '',
                '是否删除': '是' if device.is_deleted else '否',
                '丢失时间': device.lost_time.strftime('%Y-%m-%d %H:%M') if device.lost_time else '',
                '损坏原因': device.damage_reason,
                '损坏时间': device.damage_time.strftime('%Y-%m-%d %H:%M') if device.damage_time else '',
                '上一个借用人': device.previous_borrower,
                '软件版本': device.software_version,
                '芯片型号': device.hardware_version,
                '项目属性': device.project_attribute,
                '连接方式': device.connection_method,
                '系统版本': device.os_version,
                '系统平台': device.os_platform,
                '产品名称': device.product_name,
                '屏幕方向': device.screen_orientation,
                '车机分辨率': device.screen_resolution,
                '寄出时间': device.ship_time.strftime('%Y-%m-%d %H:%M') if device.ship_time else '',
                '寄出备注': device.ship_remark,
                '寄出人': device.ship_by,
                '寄出前借用人': device.pre_ship_borrower,
                '寄出前借用时间': device.pre_ship_borrow_time.strftime('%Y-%m-%d %H:%M') if device.pre_ship_borrow_time else '',
                '寄出前预计归还': device.pre_ship_expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.pre_ship_expected_return_date else '',
            })

        df = pd.DataFrame(data)
        df.to_excel(CAR_FILE, index=False)

    @staticmethod
    def save_instruments(devices: List[Instrument]):
        """保存仪表数据到Excel（与车机表结构一致）"""
        data = []
        for device in devices:
            data.append({
                '设备ID': device.id,
                '设备名': device.name,
                '型号': device.model,
                '柜号': device.cabinet_number,
                '状态': device.status.value,
                '备注': device.remark,
                'JIRA地址': device.jira_address,
                '创建时间': device.create_time.strftime('%Y-%m-%d %H:%M:%S') if device.create_time else '',
                '借用人': device.borrower,
                '手机号': device.phone,
                '借用时间': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                '借用地点': device.location,
                '借用原因': device.reason,
                '录入者': device.entry_source,
                '预计归还日期': device.expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.expected_return_date else '',
                '是否删除': '是' if device.is_deleted else '否',
                '丢失时间': device.lost_time.strftime('%Y-%m-%d %H:%M') if device.lost_time else '',
                '损坏原因': device.damage_reason,
                '损坏时间': device.damage_time.strftime('%Y-%m-%d %H:%M') if device.damage_time else '',
                '上一个借用人': device.previous_borrower,
                '软件版本': device.software_version,
                '芯片型号': device.hardware_version,
                '项目属性': device.project_attribute,
                '连接方式': device.connection_method,
                '系统版本': device.os_version,
                '系统平台': device.os_platform,
                '产品名称': device.product_name,
                '屏幕方向': device.screen_orientation,
                '车机分辨率': device.screen_resolution,
                '寄出时间': device.ship_time.strftime('%Y-%m-%d %H:%M') if device.ship_time else '',
                '寄出备注': device.ship_remark,
                '寄出人': device.ship_by,
                '寄出前借用人': device.pre_ship_borrower,
                '寄出前借用时间': device.pre_ship_borrow_time.strftime('%Y-%m-%d %H:%M') if device.pre_ship_borrow_time else '',
                '寄出前预计归还': device.pre_ship_expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.pre_ship_expected_return_date else '',
            })

        df = pd.DataFrame(data)
        df.to_excel(INSTRUMENT_FILE, index=False)

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
                'JIRA地址': device.jira_address,
                '创建时间': device.create_time.strftime('%Y-%m-%d %H:%M:%S') if device.create_time else '',
                '借用人': device.borrower,
                '手机号': device.phone,
                '借用时间': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                '借用地点': device.location,
                '借用原因': device.reason,
                '录入者': device.entry_source,
                '预计归还日期': device.expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.expected_return_date else '',
                '是否删除': '是' if device.is_deleted else '否',
                '丢失时间': device.lost_time.strftime('%Y-%m-%d %H:%M') if device.lost_time else '',
                '损坏原因': device.damage_reason,
                '损坏时间': device.damage_time.strftime('%Y-%m-%d %H:%M') if device.damage_time else '',
                '上一个借用人': device.previous_borrower,
                'SN码': device.sn,
                '系统版本': device.system_version,
                'IMEI': device.imei,
                '运营商': device.carrier,
                '寄出时间': device.ship_time.strftime('%Y-%m-%d %H:%M') if device.ship_time else '',
                '寄出备注': device.ship_remark,
                '寄出人': device.ship_by,
                '寄出前借用人': device.pre_ship_borrower,
                '寄出前借用时间': device.pre_ship_borrow_time.strftime('%Y-%m-%d %H:%M') if device.pre_ship_borrow_time else '',
                '寄出前预计归还': device.pre_ship_expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.pre_ship_expected_return_date else '',
            })

        df = pd.DataFrame(data)
        df.to_excel(PHONE_FILE, index=False)

    @staticmethod
    def save_sim_cards(devices: List[SimCard]):
        """保存手机卡数据到Excel（与手机表一致，但型号字段改为号码）"""
        data = []
        for device in devices:
            data.append({
                '设备ID': device.id,
                '设备名': device.name,
                '号码': device.model,
                '保管人': device.cabinet_number,
                '状态': device.status.value,
                '备注': device.remark,
                'JIRA地址': device.jira_address,
                '创建时间': device.create_time.strftime('%Y-%m-%d %H:%M:%S') if device.create_time else '',
                '借用人': device.borrower,
                '手机号': device.phone,
                '借用时间': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                '借用地点': device.location,
                '借用原因': device.reason,
                '录入者': device.entry_source,
                '预计归还日期': device.expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.expected_return_date else '',
                '是否删除': '是' if device.is_deleted else '否',
                '丢失时间': device.lost_time.strftime('%Y-%m-%d %H:%M') if device.lost_time else '',
                '损坏原因': device.damage_reason,
                '损坏时间': device.damage_time.strftime('%Y-%m-%d %H:%M') if device.damage_time else '',
                '上一个借用人': device.previous_borrower,
                '软件版本': device.software_version,
                '芯片型号': device.hardware_version,
                '寄出时间': device.ship_time.strftime('%Y-%m-%d %H:%M') if device.ship_time else '',
                '寄出备注': device.ship_remark,
                '寄出人': device.ship_by,
                '寄出前借用人': device.pre_ship_borrower,
                '寄出前借用时间': device.pre_ship_borrow_time.strftime('%Y-%m-%d %H:%M') if device.pre_ship_borrow_time else '',
                '寄出前预计归还': device.pre_ship_expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.pre_ship_expected_return_date else '',
            })

        df = pd.DataFrame(data)
        df.to_excel(SIM_CARD_FILE, index=False)

    @staticmethod
    def save_other_devices(devices: List[OtherDevice]):
        """保存其它设备数据到Excel（与手机表结构一致）"""
        data = []
        for device in devices:
            data.append({
                '设备ID': device.id,
                '设备名': device.name,
                '型号': device.model,
                '保管人': device.cabinet_number,
                '状态': device.status.value,
                '备注': device.remark,
                'JIRA地址': device.jira_address,
                '创建时间': device.create_time.strftime('%Y-%m-%d %H:%M:%S') if device.create_time else '',
                '借用人': device.borrower,
                '手机号': device.phone,
                '借用时间': device.borrow_time.strftime('%Y-%m-%d %H:%M') if device.borrow_time else '',
                '借用地点': device.location,
                '借用原因': device.reason,
                '录入者': device.entry_source,
                '预计归还日期': device.expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.expected_return_date else '',
                '是否删除': '是' if device.is_deleted else '否',
                '丢失时间': device.lost_time.strftime('%Y-%m-%d %H:%M') if device.lost_time else '',
                '损坏原因': device.damage_reason,
                '损坏时间': device.damage_time.strftime('%Y-%m-%d %H:%M') if device.damage_time else '',
                '上一个借用人': device.previous_borrower,
                '软件版本': device.software_version,
                '芯片型号': device.hardware_version,
                '寄出时间': device.ship_time.strftime('%Y-%m-%d %H:%M') if device.ship_time else '',
                '寄出备注': device.ship_remark,
                '寄出人': device.ship_by,
                '寄出前借用人': device.pre_ship_borrower,
                '寄出前借用时间': device.pre_ship_borrow_time.strftime('%Y-%m-%d %H:%M') if device.pre_ship_borrow_time else '',
                '寄出前预计归还': device.pre_ship_expected_return_date.strftime('%Y-%m-%d %H:%M:%S') if device.pre_ship_expected_return_date else '',
            })

        df = pd.DataFrame(data)
        df.to_excel(OTHER_DEVICE_FILE, index=False)
    
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
                    ExcelDataStore._safe_print(f"解析记录失败: {e}")
                    continue
        except Exception as e:
            ExcelDataStore._safe_print(f"加载记录失败: {e}")
        
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
                    ExcelDataStore._safe_print(f"解析备注失败: {e}")
                    continue
        except Exception as e:
            ExcelDataStore._safe_print(f"加载备注失败: {e}")
        
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
                    ExcelDataStore._safe_print(f"解析用户失败: {e}")
                    continue
        except Exception as e:
            ExcelDataStore._safe_print(f"加载用户失败: {e}")
        
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
                    ExcelDataStore._safe_print(f"解析操作日志失败: {e}")
                    continue
        except Exception as e:
            ExcelDataStore._safe_print(f"加载操作日志失败: {e}")
        
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
        from .models import ViewRecord
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
                        device_type=str(row.get('设备类型', '')),
                        viewer=str(row['查看人']),
                        view_time=pd.to_datetime(row['查看时间'])
                    )
                    records.append(record)
                except Exception as e:
                    ExcelDataStore._safe_print(f"解析查看记录失败: {e}")
                    continue
        except Exception as e:
            ExcelDataStore._safe_print(f"加载查看记录失败: {e}")
        
        return records
    
    @staticmethod
    def save_view_records(records: List):
        """保存查看记录到Excel"""
        data = []
        for record in records:
            data.append({
                '记录ID': record.id,
                '设备ID': record.device_id,
                '设备类型': record.device_type,
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
                    ExcelDataStore._safe_print(f"解析管理员失败: {e}")
                    continue
        except Exception as e:
            ExcelDataStore._safe_print(f"加载管理员失败: {e}")

        return admins

    @staticmethod
    def load_notifications() -> List[Notification]:
        """从Excel加载通知列表"""
        notifications = []
        if not os.path.exists(NOTIFICATION_FILE):
            return notifications

        try:
            df = pd.read_excel(NOTIFICATION_FILE)
            for _, row in df.iterrows():
                if pd.isna(row.get('通知ID')):
                    continue

                try:
                    create_time = None
                    if pd.notna(row.get('创建时间')):
                        create_time = pd.to_datetime(row['创建时间'])

                    notification = Notification(
                        id=str(row['通知ID']),
                        user_id=str(row['用户ID']),
                        user_name=str(row.get('用户名', '')),
                        title=str(row.get('标题', '')),
                        content=str(row.get('内容', '')),
                        device_name=str(row.get('设备名', '')),
                        device_id=str(row.get('设备ID', '')),
                        is_read=str(row.get('是否已读', '否')) == '是',
                        create_time=create_time,
                        notification_type=str(row.get('通知类型', 'info'))
                    )
                    notifications.append(notification)
                except Exception as e:
                    ExcelDataStore._safe_print(f"解析通知失败: {e}")
                    continue
        except Exception as e:
            ExcelDataStore._safe_print(f"加载通知失败: {e}")

        return notifications

    @staticmethod
    def save_notifications(notifications: List[Notification]):
        """保存通知列表到Excel"""
        data = []
        for notification in notifications:
            data.append({
                '通知ID': notification.id,
                '用户ID': notification.user_id,
                '用户名': notification.user_name,
                '标题': notification.title,
                '内容': notification.content,
                '设备名': notification.device_name,
                '设备ID': notification.device_id,
                '是否已读': '是' if notification.is_read else '否',
                '创建时间': notification.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                '通知类型': notification.notification_type,
            })

        df = pd.DataFrame(data)
        df.to_excel(NOTIFICATION_FILE, index=False)
    
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
