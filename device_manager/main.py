# -*- coding: utf-8 -*-
"""
车载测试设备管理系统 - 后台管理端
使用 PySide6 实现
"""
import sys
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QTabWidget, QDialog, QMessageBox, QFormLayout, QComboBox,
    QDateEdit, QTextEdit, QGroupBox, QSplitter, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QAbstractItemView, QMenu,
    QSystemTrayIcon, QStatusBar, QToolBar, QFrame, QSizePolicy,
    QCheckBox, QRadioButton, QButtonGroup, QFileDialog, QInputDialog,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QFont, QColor, QBrush

from models import Device, CarMachine, Phone, DeviceStatus, DeviceType, OperationType, EntrySource, User
from api_client import api_client
from excel_data_store import ExcelDataStore


class LoginDialog(QDialog):
    """登录对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理员登录")
        self.setFixedSize(400, 200)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("车载测试设备管理系统")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3;")
        layout.addWidget(title)
        
        # 表单
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入管理员账号")
        self.username_input.setText("admin")
        form_layout.addRow("账号:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("密码:", self.password_input)
        
        layout.addLayout(form_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.login_btn = QPushButton("登录")
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 30px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.login_btn.clicked.connect(self.on_login)
        btn_layout.addStretch()
        btn_layout.addWidget(self.login_btn)
        layout.addLayout(btn_layout)
    
    def on_login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入账号和密码")
            return
        
        if api_client.verify_admin(username, password):
            api_client.set_current_admin(username)
            self.accept()
        else:
            QMessageBox.warning(self, "登录失败", "账号或密码错误")


class DeviceEditDialog(QDialog):
    """设备编辑对话框"""
    def __init__(self, device=None, device_type=None, parent=None):
        super().__init__(parent)
        self.device = device
        self.device_type = device_type
        self.setWindowTitle("编辑设备" if device else "新增设备")
        self.setFixedSize(450, 350)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        # 设备类型
        self.type_combo = QComboBox()
        self.type_combo.addItems(["车机", "手机"])
        if self.device:
            self.type_combo.setCurrentText("车机" if isinstance(self.device, CarMachine) else "手机")
        elif self.device_type:
            self.type_combo.setCurrentText(self.device_type)
        form_layout.addRow("设备类型:", self.type_combo)
        
        # 设备名
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("请输入设备名（唯一）")
        if self.device:
            self.name_input.setText(self.device.name)
        form_layout.addRow("设备名*:", self.name_input)
        
        # 型号
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("请输入型号")
        if self.device:
            self.model_input.setText(self.device.model)
        form_layout.addRow("型号:", self.model_input)
        
        # 柜号
        self.cabinet_input = QLineEdit()
        self.cabinet_input.setPlaceholderText("请输入存放柜号")
        if self.device:
            self.cabinet_input.setText(self.device.cabinet_number)
        form_layout.addRow("柜号*:", self.cabinet_input)
        
        # 备注
        self.remark_input = QTextEdit()
        self.remark_input.setMaximumHeight(80)
        self.remark_input.setPlaceholderText("请输入备注信息")
        if self.device:
            self.remark_input.setText(self.device.remark)
        form_layout.addRow("备注:", self.remark_input)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px;")
        save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def on_save(self):
        name = self.name_input.text().strip()
        model = self.model_input.text().strip()
        cabinet = self.cabinet_input.text().strip()
        remark = self.remark_input.toPlainText().strip()
        device_type = self.type_combo.currentText()
        
        if not name or not cabinet:
            QMessageBox.warning(self, "警告", "设备名和柜号为必填项")
            return
        
        if self.device:
            # 检查设备名是否修改且新名称是否已存在
            if name != self.device.name:
                all_devices = api_client._car_machines + api_client._phones
                for d in all_devices:
                    if d.name == name and d.id != self.device.id:
                        QMessageBox.warning(self, "警告", "该设备名已存在，请更换")
                        return
            
            # 检查设备类型是否改变
            original_type = "车机" if isinstance(self.device, CarMachine) else "手机"
            if device_type != original_type:
                # 设备类型改变，需要创建新设备并删除旧设备
                import uuid
                reply = QMessageBox.question(
                    self, "确认",
                    f"确定要将设备类型从 {original_type} 改为 {device_type} 吗？\n这会创建一个新设备并保留原设备的所有借用记录。",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
                
                # 创建新设备
                if device_type == "车机":
                    new_device = CarMachine(
                        id=str(uuid.uuid4()),
                        name=name,
                        model=model,
                        cabinet_number=cabinet,
                        remark=remark,
                        status=self.device.status
                    )
                else:
                    new_device = Phone(
                        id=str(uuid.uuid4()),
                        name=name,
                        model=model,
                        cabinet_number=cabinet,
                        remark=remark,
                        status=self.device.status
                    )
                
                # 复制借用信息
                new_device.borrower = self.device.borrower
                new_device.phone = self.device.phone
                new_device.borrow_time = self.device.borrow_time
                new_device.location = self.device.location
                new_device.reason = self.device.reason
                new_device.entry_source = self.device.entry_source
                new_device.expected_return_date = self.device.expected_return_date
                
                # 添加新设备并删除旧设备
                if device_type == "车机":
                    api_client._car_machines.append(new_device)
                    # 从手机列表中删除旧设备
                    api_client._phones = [d for d in api_client._phones if d.id != self.device.id]
                else:
                    api_client._phones.append(new_device)
                    # 从车机列表中删除旧设备
                    api_client._car_machines = [d for d in api_client._car_machines if d.id != self.device.id]
                
                api_client.add_operation_log(f"修改设备类型: {original_type}->{device_type}, 名称:{self.device.name}->{name}", name)
                api_client._save_data()
                QMessageBox.information(self, "成功", "设备类型已修改")
                self.accept()
            else:
                # 仅更新设备信息
                self.device.name = name
                self.device.model = model
                self.device.cabinet_number = cabinet
                self.device.remark = remark
                if api_client.update_device(self.device):
                    QMessageBox.information(self, "成功", "设备信息已更新")
                    self.accept()
                else:
                    QMessageBox.warning(self, "失败", "更新设备信息失败")
        else:
            # 新增设备
            import uuid
            if device_type == "车机":
                new_device = CarMachine(
                    id=str(uuid.uuid4()),
                    name=name,
                    model=model,
                    cabinet_number=cabinet,
                    remark=remark
                )
            else:
                new_device = Phone(
                    id=str(uuid.uuid4()),
                    name=name,
                    model=model,
                    cabinet_number=cabinet,
                    remark=remark
                )
            
            if api_client.add_device(new_device):
                QMessageBox.information(self, "成功", "设备已添加")
                self.accept()
            else:
                QMessageBox.warning(self, "失败", "设备名已存在，请更换")


class ForceBorrowDialog(QDialog):
    """强制借出（录入登记）对话框"""
    def __init__(self, device, parent=None):
        super().__init__(parent)
        self.device = device
        self.setWindowTitle(f"录入登记 - {device.name}")
        self.setFixedSize(500, 450)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 设备信息
        info_group = QGroupBox("设备信息")
        info_layout = QFormLayout()
        info_layout.addRow("设备名:", QLabel(self.device.name))
        info_layout.addRow("型号:", QLabel(self.device.model))
        info_layout.addRow("柜号:", QLabel(self.device.cabinet_number))
        info_layout.addRow("当前状态:", QLabel(self.device.status.value))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        if self.device.status == DeviceStatus.BORROWED:
            QMessageBox.warning(self, "警告", "该设备已被借出，无法再次登记")
            self.reject()
            return
        
        # 登记信息
        borrow_group = QGroupBox("借用登记信息")
        form_layout = QFormLayout()
        
        # 借用人搜索联想输入
        self.borrower_input = QLineEdit()
        self.borrower_input.setPlaceholderText("输入姓名搜索...")
        form_layout.addRow("借用人*:", self.borrower_input)
        
        # 建议列表
        self.suggestions_list = QListWidget()
        self.suggestions_list.setMaximumHeight(150)
        self.suggestions_list.hide()
        form_layout.addRow("", self.suggestions_list)
        
        # 加载所有用户用于搜索
        self.all_users = [(u.borrower_name, u.phone) for u in api_client.get_all_users() if u.borrower_name]
        self.selected_borrower = ""
        
        # 连接信号
        self.borrower_input.textChanged.connect(self.on_borrower_search)
        self.suggestions_list.itemClicked.connect(self.on_suggestion_selected)
        
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("请输入手机号")
        self.phone_input.setReadOnly(True)
        form_layout.addRow("手机号:", self.phone_input)
        
        # 借用原因
        self.reason_combo = QComboBox()
        self.reason_combo.addItems(["测试", "开发", "演示", "出差", "其他"])
        self.reason_combo.setEditable(True)
        form_layout.addRow("借用原因:", self.reason_combo)
        
        # 预计归还日期
        self.return_date = QDateEdit()
        self.return_date.setCalendarPopup(True)
        self.return_date.setDate(datetime.now() + timedelta(days=1))
        form_layout.addRow("预计归还日期:", self.return_date)
        
        # 备注
        self.remark_input = QTextEdit()
        self.remark_input.setMaximumHeight(60)
        form_layout.addRow("录入备注:", self.remark_input)
        
        borrow_group.setLayout(form_layout)
        layout.addWidget(borrow_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("确认录入登记")
        confirm_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 20px;")
        confirm_btn.clicked.connect(self.on_confirm)
        btn_layout.addWidget(confirm_btn)
        
        layout.addLayout(btn_layout)
    
    def on_borrower_search(self, text):
        """搜索借用人"""
        keyword = text.strip().lower()
        self.suggestions_list.clear()
        
        if keyword:
            matched = [(name, phone) for name, phone in self.all_users 
                      if keyword in name.lower() or keyword in phone]
            
            if matched:
                for name, phone in matched:
                    item = QListWidgetItem(f"{name} ({phone})")
                    item.setData(Qt.UserRole, name)
                    self.suggestions_list.addItem(item)
                self.suggestions_list.show()
            else:
                self.suggestions_list.hide()
        else:
            self.suggestions_list.hide()
    
    def on_suggestion_selected(self, item):
        """选择建议项"""
        self.selected_borrower = item.data(Qt.UserRole)
        self.borrower_input.setText(self.selected_borrower)
        
        # 填充手机号
        for name, phone in self.all_users:
            if name == self.selected_borrower:
                self.phone_input.setText(phone)
                break
        
        self.suggestions_list.hide()
    
    def on_confirm(self):
        borrower = self.selected_borrower or self.borrower_input.text().strip()
        
        phone = self.phone_input.text().strip()
        reason = self.reason_combo.currentText().strip()
        return_date = self.return_date.date().toPython()
        remark = self.remark_input.toPlainText().strip()
        
        if not borrower:
            QMessageBox.warning(self, "警告", "借用人不能为空")
            return
        
        if api_client.force_borrow(
            self.device.id, borrower, phone, "", reason,
            return_date, remark
        ):
            QMessageBox.information(self, "成功", "录入登记成功")
            self.accept()
        else:
            QMessageBox.warning(self, "失败", "录入登记失败")


class ForceReturnDialog(QDialog):
    """强制归还对话框"""
    def __init__(self, device, parent=None):
        super().__init__(parent)
        self.device = device
        self.setWindowTitle(f"强制归还 - {device.name}")
        self.setFixedSize(500, 400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 设备信息
        info_group = QGroupBox("当前借用信息")
        info_layout = QFormLayout()
        info_layout.addRow("设备名:", QLabel(self.device.name))
        info_layout.addRow("借用人:", QLabel(self.device.borrower))
        info_layout.addRow("录入者:", QLabel(self.device.entry_source))
        info_layout.addRow("借用时间:", QLabel(
            self.device.borrow_time.strftime("%Y-%m-%d %H:%M") if self.device.borrow_time else ""
        ))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 归还信息
        return_group = QGroupBox("归还信息")
        form_layout = QFormLayout()
        
        self.return_person_input = QLineEdit()
        self.return_person_input.setText(self.device.borrower)
        form_layout.addRow("归还人:", self.return_person_input)
        
        # 归还原因
        self.reason_combo = QComboBox()
        self.reason_combo.addItems(["正常归还", "设备收回", "转借他人", "其他"])
        form_layout.addRow("归还原因:", self.reason_combo)
        
        # 备注
        self.remark_input = QTextEdit()
        self.remark_input.setMaximumHeight(60)
        self.remark_input.setPlaceholderText("请输入备注信息")
        form_layout.addRow("备注:", self.remark_input)
        
        return_group.setLayout(form_layout)
        layout.addWidget(return_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("确认强制归还")
        confirm_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 8px 20px;")
        confirm_btn.clicked.connect(self.on_confirm)
        btn_layout.addWidget(confirm_btn)
        
        layout.addLayout(btn_layout)
    
    def on_confirm(self):
        return_person = self.return_person_input.text().strip()
        reason = self.reason_combo.currentText()
        remark = self.remark_input.toPlainText().strip()
        
        reply = QMessageBox.question(
            self, "确认", 
            f"确定要强制归还设备 {self.device.name} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if api_client.force_return(
                self.device.id, return_person, "", reason, remark
            ):
                QMessageBox.information(self, "成功", "强制归还成功")
                self.accept()
            else:
                QMessageBox.warning(self, "失败", "强制归还失败")


class TransferDialog(QDialog):
    """转借对话框"""
    def __init__(self, device, parent=None):
        super().__init__(parent)
        self.device = device
        self.setWindowTitle(f"转借设备 - {device.name}")
        self.setFixedSize(500, 450)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 当前借用信息
        info_group = QGroupBox("当前借用信息")
        info_layout = QFormLayout()
        info_layout.addRow("设备名:", QLabel(self.device.name))
        info_layout.addRow("当前借用人:", QLabel(self.device.borrower))
        info_layout.addRow("借用时间:", QLabel(self.device.borrow_time.strftime("%Y-%m-%d %H:%M") if self.device.borrow_time else "-"))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 转借信息
        transfer_group = QGroupBox("转借信息")
        form_layout = QFormLayout()
        
        # 转借给（搜索联想输入）
        self.transfer_to_input = QLineEdit()
        self.transfer_to_input.setPlaceholderText("输入姓名搜索...")
        form_layout.addRow("转借给:", self.transfer_to_input)
        
        # 建议列表
        self.suggestions_list = QListWidget()
        self.suggestions_list.setMaximumHeight(150)
        self.suggestions_list.hide()
        form_layout.addRow("", self.suggestions_list)
        
        # 加载所有用户用于搜索
        self.all_users = [(u.borrower_name, u.phone) for u in api_client.get_all_users() 
                         if u.borrower_name and u.borrower_name != self.device.borrower]
        self.selected_transfer_to = ""
        
        # 连接信号
        self.transfer_to_input.textChanged.connect(self.on_transfer_search)
        self.suggestions_list.itemClicked.connect(self.on_transfer_suggestion_selected)
        
        # 保管地点/位置
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("请输入保管地点")
        form_layout.addRow("保管地点*:", self.location_input)
        
        # 转借原因
        self.reason_combo = QComboBox()
        self.reason_combo.setEditable(True)
        self.reason_combo.addItems(["项目需要", "工作交接", "临时借用", "其他"])
        form_layout.addRow("转借原因*:", self.reason_combo)
        
        # 预计归还日期
        self.return_date = QDateEdit()
        self.return_date.setCalendarPopup(True)
        self.return_date.setDate(self.device.expected_return_date if self.device.expected_return_date else datetime.now() + timedelta(days=1))
        form_layout.addRow("预计归还日期:", self.return_date)
        
        # 备注
        self.remark_input = QTextEdit()
        self.remark_input.setPlaceholderText("可选：添加转借备注")
        self.remark_input.setMaximumHeight(80)
        form_layout.addRow("备注:", self.remark_input)
        
        transfer_group.setLayout(form_layout)
        layout.addWidget(transfer_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("确认转借")
        confirm_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 20px;")
        confirm_btn.clicked.connect(self.on_confirm)
        btn_layout.addWidget(confirm_btn)
        
        layout.addLayout(btn_layout)
    
    def on_transfer_search(self, text):
        """搜索转借人"""
        keyword = text.strip().lower()
        self.suggestions_list.clear()
        
        if keyword:
            matched = [(name, phone) for name, phone in self.all_users 
                      if keyword in name.lower() or keyword in phone]
            
            if matched:
                for name, phone in matched:
                    item = QListWidgetItem(f"{name} ({phone})")
                    item.setData(Qt.UserRole, name)
                    self.suggestions_list.addItem(item)
                self.suggestions_list.show()
            else:
                self.suggestions_list.hide()
        else:
            self.suggestions_list.hide()
    
    def on_transfer_suggestion_selected(self, item):
        """选择建议项"""
        self.selected_transfer_to = item.data(Qt.UserRole)
        self.transfer_to_input.setText(self.selected_transfer_to)
        self.suggestions_list.hide()
    
    def on_confirm(self):
        transfer_to = self.selected_transfer_to or self.transfer_to_input.text().strip()
        
        location = self.location_input.text().strip()
        reason = self.reason_combo.currentText().strip()
        return_date = self.return_date.date().toPyDate()
        remark = self.remark_input.toPlainText().strip()
        
        if not transfer_to:
            QMessageBox.warning(self, "警告", "请输入转借人")
            return
        
        if not location:
            QMessageBox.warning(self, "警告", "保管人不能为空")
            return
        
        if not reason:
            QMessageBox.warning(self, "警告", "转借原因不能为空")
            return
        
        reply = QMessageBox.question(
            self, "确认",
            f"确定要将设备 {self.device.name} 从 {self.device.borrower} 转借给 {transfer_to} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if api_client.transfer_device(
                self.device.id, transfer_to, location, reason,
                return_date, remark
            ):
                QMessageBox.information(self, "成功", "转借成功")
                self.accept()
            else:
                QMessageBox.warning(self, "失败", "转借失败")


class RecordQueryDialog(QDialog):
    """记录查询对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("记录查询与导出")
        self.resize(900, 600)
        self.setup_ui()
        self.load_records()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 筛选条件
        filter_group = QGroupBox("筛选条件")
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("设备类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["全部", "车机", "手机"])
        filter_layout.addWidget(self.type_combo)
        
        filter_layout.addWidget(QLabel("设备名:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("输入设备名关键字")
        filter_layout.addWidget(self.name_input)
        
        filter_layout.addWidget(QLabel("操作类型:"))
        self.op_combo = QComboBox()
        self.op_combo.addItems(["全部", "借出", "归还", "强制借出", "强制归还", "转借"])
        filter_layout.addWidget(self.op_combo)
        
        filter_layout.addWidget(QLabel("开始日期:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(datetime.now() - timedelta(days=30))
        filter_layout.addWidget(self.start_date)
        
        filter_layout.addWidget(QLabel("结束日期:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(datetime.now())
        filter_layout.addWidget(self.end_date)
        
        self.query_btn = QPushButton("查询")
        self.query_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.query_btn.clicked.connect(self.load_records)
        filter_layout.addWidget(self.query_btn)
        
        self.export_btn = QPushButton("导出Excel")
        self.export_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.export_btn.clicked.connect(self.export_records)
        filter_layout.addWidget(self.export_btn)
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # 记录表格
        self.record_table = QTableWidget()
        self.record_table.setColumnCount(9)
        self.record_table.setHorizontalHeaderLabels([
            "操作时间", "设备类型", "设备名", "操作类型", "操作人",
            "借用人", "手机号", "原因", "备注"
        ])
        self.record_table.horizontalHeader().setStretchLastSection(True)
        self.record_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.record_table.setAlternatingRowColors(True)
        layout.addWidget(self.record_table)
    
    def load_records(self):
        """加载记录"""
        device_type = self.type_combo.currentText()
        device_name = self.name_input.text().strip()
        operation_type = self.op_combo.currentText()
        start_time = self.start_date.date().toPython()
        end_time = self.end_date.date().toPython() + timedelta(days=1)
        
        if device_type == "全部":
            device_type = None
        if not device_name:
            device_name = None
        if operation_type == "全部":
            operation_type = None
        
        records = api_client.get_records(
            device_type=device_type,
            device_name=device_name,
            operation_type=operation_type,
            start_time=start_time,
            end_time=end_time
        )
        
        self.record_table.setRowCount(len(records))
        
        for i, record in enumerate(records):
            self.record_table.setItem(i, 0, QTableWidgetItem(record.operation_time.strftime("%Y-%m-%d %H:%M")))
            self.record_table.setItem(i, 1, QTableWidgetItem(record.device_type))
            self.record_table.setItem(i, 2, QTableWidgetItem(record.device_name))
            self.record_table.setItem(i, 3, QTableWidgetItem(record.operation_type.value))
            self.record_table.setItem(i, 4, QTableWidgetItem(record.operator))
            self.record_table.setItem(i, 5, QTableWidgetItem(record.borrower))
            self.record_table.setItem(i, 6, QTableWidgetItem(record.phone))
            self.record_table.setItem(i, 7, QTableWidgetItem(record.reason))
            self.record_table.setItem(i, 8, QTableWidgetItem(record.remark))
    
    def export_records(self):
        """导出记录到Excel"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存Excel文件", f"借还记录_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        
        if file_path:
            try:
                import pandas as pd
                
                records = []
                for row in range(self.record_table.rowCount()):
                    record = {
                        "操作时间": self.record_table.item(row, 0).text(),
                        "设备类型": self.record_table.item(row, 1).text(),
                        "设备名": self.record_table.item(row, 2).text(),
                        "操作类型": self.record_table.item(row, 3).text(),
                        "操作人": self.record_table.item(row, 4).text(),
                        "借用人": self.record_table.item(row, 5).text(),
                        "手机号": self.record_table.item(row, 6).text(),
                        "原因": self.record_table.item(row, 7).text(),
                        "备注": self.record_table.item(row, 8).text(),
                    }
                    records.append(record)
                
                df = pd.DataFrame(records)
                df.to_excel(file_path, index=False)
                
                QMessageBox.information(self, "成功", f"记录已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", str(e))


class DeviceManager(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("车载测试设备管理系统 - 后台管理端")
        self.resize(1400, 900)
        self.setup_ui()
        self.update_filter_options()
        self.load_devices()
        self.load_operation_logs()
        self.load_overdue_devices()
        self.start_auto_refresh()
    
    def setup_ui(self):
        # 创建菜单栏
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 设备管理菜单
        device_menu = menubar.addMenu("设备管理")
        add_device_action = QAction("新增设备", self)
        add_device_action.triggered.connect(self.on_add_device)
        device_menu.addAction(add_device_action)
        
        # 用户管理菜单
        user_menu = menubar.addMenu("用户管理")
        user_mgmt_action = QAction("用户管理", self)
        user_mgmt_action.triggered.connect(self.on_user_management)
        user_menu.addAction(user_mgmt_action)
        
        # 记录查询菜单
        record_menu = menubar.addMenu("记录查询")
        query_record_action = QAction("记录查询与导出", self)
        query_record_action.triggered.connect(self.on_query_records)
        record_menu.addAction(query_record_action)
        
        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        refresh_action = QAction("立即刷新", self)
        refresh_action.triggered.connect(self.refresh_data)
        settings_menu.addAction(refresh_action)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建分割器
        main_splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(main_splitter)
        
        # 上半部分：设备列表和详情
        top_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(top_splitter)
        
        # 左侧：设备树形列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 筛选区域
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("设备列表"))
        
        # 搜索框 - 模糊搜索设备名、借用人、柜号
        self.device_search_input = QLineEdit()
        self.device_search_input.setPlaceholderText("模糊搜索设备名/借用人/柜号...")
        self.device_search_input.setMaximumWidth(180)
        self.device_search_input.textChanged.connect(self.on_device_search)
        filter_layout.addWidget(self.device_search_input)
        
        # 状态筛选
        filter_layout.addWidget(QLabel("状态:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部", "在库", "借出", "已寄出", "已损坏", "丢失", "报废"])
        self.status_filter.currentTextChanged.connect(self.on_device_search)
        filter_layout.addWidget(self.status_filter)
        
        # 借用人筛选
        filter_layout.addWidget(QLabel("借用人:"))
        self.borrower_filter = QComboBox()
        self.borrower_filter.setEditable(True)
        self.borrower_filter.setMinimumWidth(100)
        self.borrower_filter.currentTextChanged.connect(self.on_device_search)
        filter_layout.addWidget(self.borrower_filter)
        
        # 柜号/保管人筛选
        filter_layout.addWidget(QLabel("柜号/保管人:"))
        self.cabinet_filter = QComboBox()
        self.cabinet_filter.setEditable(True)
        self.cabinet_filter.setMinimumWidth(100)
        self.cabinet_filter.currentTextChanged.connect(self.on_device_search)
        filter_layout.addWidget(self.cabinet_filter)
        
        # 过期筛选
        filter_layout.addWidget(QLabel("过期:"))
        self.overdue_filter = QComboBox()
        self.overdue_filter.addItems(["全部", "已过期", "未过期"])
        self.overdue_filter.currentTextChanged.connect(self.on_device_search)
        filter_layout.addWidget(self.overdue_filter)
        
        # 重置按钮
        self.reset_filter_btn = QPushButton("重置")
        self.reset_filter_btn.setStyleSheet("background-color: #757575; color: white;")
        self.reset_filter_btn.clicked.connect(self.on_reset_filters)
        filter_layout.addWidget(self.reset_filter_btn)
        
        filter_layout.addStretch()
        
        self.add_device_btn = QPushButton("+ 新增")
        self.add_device_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.add_device_btn.clicked.connect(self.on_add_device)
        filter_layout.addWidget(self.add_device_btn)
        
        left_layout.addLayout(filter_layout)
        
        self.device_tree = QTreeWidget()
        self.device_tree.setHeaderLabels(["设备名", "状态", "借用人", "柜号/保管人", "逾期"])
        self.device_tree.setColumnWidth(0, 150)
        self.device_tree.setColumnWidth(1, 80)
        self.device_tree.setColumnWidth(3, 100)
        self.device_tree.setColumnWidth(4, 60)
        self.device_tree.currentItemChanged.connect(self.on_device_selected)
        self.device_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.device_tree.customContextMenuRequested.connect(self.show_device_context_menu)
        left_layout.addWidget(self.device_tree)
        
        top_splitter.addWidget(left_widget)
        
        # 右侧：设备详情面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 详情面板
        self.detail_group = QGroupBox("设备详情")
        detail_layout = QFormLayout()
        
        self.detail_name = QLabel("-")
        self.detail_type = QLabel("-")
        self.detail_model = QLabel("-")
        self.detail_cabinet = QLabel("-")
        self.detail_status = QLabel("-")
        self.detail_borrower = QLabel("-")
        self.detail_phone = QLabel("-")
        self.detail_reason = QLabel("-")
        self.detail_entry = QLabel("-")
        self.detail_remark = QLabel("-")
        # 动态信息标签（根据状态显示不同内容）
        self.detail_dynamic_label1 = QLabel("")
        self.detail_dynamic_value1 = QLabel("-")
        self.detail_dynamic_label2 = QLabel("")
        self.detail_dynamic_value2 = QLabel("-")

        detail_layout.addRow("设备名:", self.detail_name)
        detail_layout.addRow("设备类型:", self.detail_type)
        detail_layout.addRow("型号:", self.detail_model)
        self.cabinet_label = QLabel("柜号:")
        detail_layout.addRow(self.cabinet_label, self.detail_cabinet)
        detail_layout.addRow("状态:", self.detail_status)
        detail_layout.addRow("借用人:", self.detail_borrower)
        detail_layout.addRow("手机号:", self.detail_phone)
        detail_layout.addRow("借用原因:", self.detail_reason)
        detail_layout.addRow("录入者:", self.detail_entry)
        detail_layout.addRow(self.detail_dynamic_label1, self.detail_dynamic_value1)
        detail_layout.addRow(self.detail_dynamic_label2, self.detail_dynamic_value2)
        detail_layout.addRow("备注:", self.detail_remark)
        
        self.detail_group.setLayout(detail_layout)
        right_layout.addWidget(self.detail_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.edit_btn = QPushButton("编辑设备")
        self.edit_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.edit_btn.clicked.connect(self.on_edit_device)
        btn_layout.addWidget(self.edit_btn)
        
        self.borrow_btn = QPushButton("录入登记")
        self.borrow_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.borrow_btn.clicked.connect(self.on_force_borrow)
        btn_layout.addWidget(self.borrow_btn)
        
        self.transfer_btn = QPushButton("转借")
        self.transfer_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.transfer_btn.clicked.connect(self.on_transfer)
        btn_layout.addWidget(self.transfer_btn)
        
        self.return_btn = QPushButton("强制归还")
        self.return_btn.setStyleSheet("background-color: #FF5722; color: white;")
        self.return_btn.clicked.connect(self.on_force_return)
        btn_layout.addWidget(self.return_btn)
        
        self.delete_btn = QPushButton("删除设备")
        self.delete_btn.setStyleSheet("background-color: #F44336; color: white;")
        self.delete_btn.clicked.connect(self.on_delete_device)
        btn_layout.addWidget(self.delete_btn)
        
        right_layout.addLayout(btn_layout)
        
        top_splitter.addWidget(right_widget)
        top_splitter.setSizes([500, 500])
        
        # 下半部分：左右分割布局
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # 左半边：操作日志和过期未还（使用标签页）
        bottom_left_tab = QTabWidget()
        
        # 操作日志标签页
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["操作时间", "操作人", "操作内容"])
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.setAlternatingRowColors(True)
        log_layout.addWidget(self.log_table)
        bottom_left_tab.addTab(log_widget, "操作日志")
        
        # 过期未还标签页
        overdue_widget = QWidget()
        overdue_layout = QVBoxLayout(overdue_widget)
        overdue_layout.setContentsMargins(0, 0, 0, 0)
        
        self.overdue_table = QTableWidget()
        self.overdue_table.setColumnCount(5)
        self.overdue_table.setHorizontalHeaderLabels(["设备名", "借用人", "借用时间", "预计归还", "超时天数"])
        self.overdue_table.horizontalHeader().setStretchLastSection(True)
        self.overdue_table.setAlternatingRowColors(True)
        overdue_layout.addWidget(self.overdue_table)
        bottom_left_tab.addTab(overdue_widget, "过期未还")
        
        bottom_splitter.addWidget(bottom_left_tab)
        self.bottom_left_tab = bottom_left_tab
        
        # 右半边：借还记录、用户备注、查看记录（三个标签页）
        bottom_right_tab = QTabWidget()
        
        # 设备借还记录标签页
        record_widget = QWidget()
        record_layout = QVBoxLayout(record_widget)
        record_layout.setContentsMargins(0, 0, 0, 0)
        
        self.device_record_table = QTableWidget()
        self.device_record_table.setColumnCount(3)
        self.device_record_table.setHorizontalHeaderLabels(["时间", "操作类型", "借用人"])
        self.device_record_table.horizontalHeader().setStretchLastSection(True)
        self.device_record_table.setAlternatingRowColors(True)
        record_layout.addWidget(self.device_record_table)
        bottom_right_tab.addTab(record_widget, "借还记录")
        
        # 用户备注标签页
        remark_widget = QWidget()
        remark_layout = QVBoxLayout(remark_widget)
        remark_layout.setContentsMargins(0, 0, 0, 0)
        
        self.device_remark_table = QTableWidget()
        self.device_remark_table.setColumnCount(3)
        self.device_remark_table.setHorizontalHeaderLabels(["时间", "创建人", "内容"])
        self.device_remark_table.horizontalHeader().setStretchLastSection(True)
        self.device_remark_table.setAlternatingRowColors(True)
        remark_layout.addWidget(self.device_remark_table)
        bottom_right_tab.addTab(remark_widget, "用户备注")
        
        # 查看记录标签页
        view_widget = QWidget()
        view_layout = QVBoxLayout(view_widget)
        view_layout.setContentsMargins(0, 0, 0, 0)
        
        self.device_view_table = QTableWidget()
        self.device_view_table.setColumnCount(3)
        self.device_view_table.setHorizontalHeaderLabels(["时间", "查看人", "设备"])
        self.device_view_table.horizontalHeader().setStretchLastSection(True)
        self.device_view_table.setAlternatingRowColors(True)
        view_layout.addWidget(self.device_view_table)
        bottom_right_tab.addTab(view_widget, "查看记录")
        
        bottom_splitter.addWidget(bottom_right_tab)
        bottom_splitter.setSizes([500, 500])
        
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setSizes([500, 500])
        
        # 状态栏
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(f"当前管理员: {api_client.get_current_admin()} | 系统就绪")
    
    def get_overdue_days(self, device):
        """计算设备逾期天数"""
        if device.status == DeviceStatus.BORROWED and device.expected_return_date:
            from datetime import datetime, date
            today = datetime.now().date()
            # 兼容 date 和 datetime 两种类型
            if isinstance(device.expected_return_date, datetime):
                expected_date = device.expected_return_date.date()
            else:
                expected_date = device.expected_return_date
            if today > expected_date:
                return (today - expected_date).days
        return 0
    
    def update_filter_options(self):
        """更新筛选下拉框选项"""
        all_devices = api_client.get_all_devices()
        
        # 获取所有借用人
        borrowers = sorted(set([d.borrower for d in all_devices if d.borrower]))
        current_borrower = self.borrower_filter.currentText()
        self.borrower_filter.clear()
        self.borrower_filter.addItem("全部")
        self.borrower_filter.addItems(borrowers)
        self.borrower_filter.setCurrentText(current_borrower if current_borrower in borrowers else "全部")
        
        # 获取所有柜号/保管人
        cabinets = sorted(set([d.cabinet_number for d in all_devices if d.cabinet_number]))
        current_cabinet = self.cabinet_filter.currentText()
        self.cabinet_filter.clear()
        self.cabinet_filter.addItem("全部")
        self.cabinet_filter.addItems(cabinets)
        self.cabinet_filter.setCurrentText(current_cabinet if current_cabinet in cabinets else "全部")
    
    def load_devices(self):
        """加载设备列表到树形控件"""
        self.device_tree.clear()
        
        # 获取筛选条件
        keyword = self.device_search_input.text().strip().lower()
        status_filter = self.status_filter.currentText()
        borrower_filter = self.borrower_filter.currentText()
        cabinet_filter = self.cabinet_filter.currentText()
        overdue_filter = self.overdue_filter.currentText()
        
        # 车机分类
        car_item = QTreeWidgetItem(self.device_tree, ["车机设备", "", "", "", ""])
        car_machines = api_client.get_all_devices("车机")
        car_count = 0
        for device in car_machines:
            # 模糊搜索过滤（设备名、借用人、柜号）
            if keyword:
                # 处理设备名中的换行符和多余空格
                device_name_normalized = device.name.lower().replace('\n', ' ').replace('  ', ' ').strip()
                match = (keyword in device_name_normalized or
                        keyword in (device.borrower or "").lower() or
                        keyword in (device.cabinet_number or "").lower() or
                        keyword in (device.model or "").lower())
                if not match:
                    continue
            
            # 状态筛选
            if status_filter != "全部" and device.status.value != status_filter:
                continue
            
            # 借用人筛选
            if borrower_filter != "全部" and device.borrower != borrower_filter:
                continue
            
            # 柜号/保管人筛选
            if cabinet_filter != "全部" and device.cabinet_number != cabinet_filter:
                continue
            
            # 计算逾期天数
            overdue_days = self.get_overdue_days(device)
            
            # 过期筛选
            if overdue_filter == "已过期" and overdue_days <= 0:
                continue
            if overdue_filter == "未过期" and overdue_days > 0:
                continue
            
            car_count += 1
            
            overdue_text = f"{overdue_days}天" if overdue_days > 0 else ""
            
            item = QTreeWidgetItem(car_item, [
                device.name, 
                device.status.value,
                device.borrower if device.borrower else "-",
                device.cabinet_number if device.cabinet_number else "-",
                overdue_text
            ])
            item.setData(0, Qt.UserRole, device.id)
            # 设置状态颜色
            if device.status == DeviceStatus.BORROWED:
                item.setForeground(1, QBrush(QColor("#FF5722")))
            elif device.status == DeviceStatus.SHIPPED:
                item.setForeground(1, QBrush(QColor("#1890FF")))
            elif device.status == DeviceStatus.DAMAGED:
                item.setForeground(1, QBrush(QColor("#F5222D")))
            elif device.status == DeviceStatus.LOST:
                item.setForeground(1, QBrush(QColor("#722ED1")))
            elif device.status == DeviceStatus.SCRAPPED:
                item.setForeground(1, QBrush(QColor("#999999")))
            # 逾期天数标红
            if overdue_days > 0:
                item.setForeground(4, QBrush(QColor("#F5222D")))
        car_item.setExpanded(True)
        
        # 手机分类
        phone_item = QTreeWidgetItem(self.device_tree, ["手机设备", "", "", "", ""])
        phones = api_client.get_all_devices("手机")
        phone_count = 0
        for device in phones:
            # 模糊搜索过滤
            if keyword:
                # 处理设备名中的换行符和多余空格
                device_name_normalized = device.name.lower().replace('\n', ' ').replace('  ', ' ').strip()
                match = (keyword in device_name_normalized or
                        keyword in (device.borrower or "").lower() or
                        keyword in (device.cabinet_number or "").lower() or
                        keyword in (device.model or "").lower())
                if not match:
                    continue
            
            # 状态筛选
            if status_filter != "全部" and device.status.value != status_filter:
                continue
            
            # 借用人筛选
            if borrower_filter != "全部" and device.borrower != borrower_filter:
                continue
            
            # 柜号/保管人筛选
            if cabinet_filter != "全部" and device.cabinet_number != cabinet_filter:
                continue
            
            # 计算逾期天数
            overdue_days = self.get_overdue_days(device)
            
            # 过期筛选
            if overdue_filter == "已过期" and overdue_days <= 0:
                continue
            if overdue_filter == "未过期" and overdue_days > 0:
                continue
            
            phone_count += 1
            
            overdue_text = f"{overdue_days}天" if overdue_days > 0 else ""
            
            item = QTreeWidgetItem(phone_item, [
                device.name,
                device.status.value,
                device.borrower if device.borrower else "-",
                device.cabinet_number if device.cabinet_number else "-",
                overdue_text
            ])
            item.setData(0, Qt.UserRole, device.id)
            if device.status == DeviceStatus.BORROWED:
                item.setForeground(1, QBrush(QColor("#FF5722")))
            elif device.status == DeviceStatus.SHIPPED:
                item.setForeground(1, QBrush(QColor("#1890FF")))
            elif device.status == DeviceStatus.DAMAGED:
                item.setForeground(1, QBrush(QColor("#F5222D")))
            elif device.status == DeviceStatus.LOST:
                item.setForeground(1, QBrush(QColor("#722ED1")))
            elif device.status == DeviceStatus.SCRAPPED:
                item.setForeground(1, QBrush(QColor("#999999")))
            # 逾期天数标红
            if overdue_days > 0:
                item.setForeground(4, QBrush(QColor("#F5222D")))
        phone_item.setExpanded(True)
        
        # 更新状态栏
        filter_info = []
        if keyword:
            filter_info.append(f"搜索:'{keyword}'")
        if status_filter != "全部":
            filter_info.append(f"状态:{status_filter}")
        if borrower_filter != "全部":
            filter_info.append(f"借用人:{borrower_filter}")
        if cabinet_filter != "全部":
            filter_info.append(f"柜号:{cabinet_filter}")
        if overdue_filter != "全部":
            filter_info.append(f"过期:{overdue_filter}")
        
        if filter_info:
            self.statusbar.showMessage(
                f"当前管理员: {api_client.get_current_admin()} | "
                f"{' | '.join(filter_info)} | 车机: {car_count}台 | 手机: {phone_count}台"
            )
        else:
            self.statusbar.showMessage(
                f"当前管理员: {api_client.get_current_admin()} | "
                f"车机: {len(car_machines)}台 | 手机: {len(phones)}台"
            )
    
    def on_device_search(self):
        """设备搜索和筛选"""
        self.load_devices()
    
    def on_reset_filters(self):
        """重置所有筛选条件"""
        self.device_search_input.clear()
        self.status_filter.setCurrentIndex(0)
        self.borrower_filter.setCurrentIndex(0)
        self.cabinet_filter.setCurrentIndex(0)
        self.overdue_filter.setCurrentIndex(0)
        self.load_devices()
    
    def load_operation_logs(self):
        """加载操作日志"""
        logs = api_client.get_operation_logs(20)
        self.log_table.setRowCount(len(logs))
        
        for i, log in enumerate(logs):
            self.log_table.setItem(i, 0, QTableWidgetItem(log.operation_time.strftime("%Y-%m-%d %H:%M")))
            self.log_table.setItem(i, 1, QTableWidgetItem(log.operator))
            # 合并操作内容和设备信息
            content = f"{log.operation_content} - {log.device_info}"
            self.log_table.setItem(i, 2, QTableWidgetItem(content))
    
    def load_overdue_devices(self):
        """加载过期未还设备列表"""
        from datetime import datetime
        all_devices = api_client.get_all_devices()
        overdue_devices = []
        
        for device in all_devices:
            if device.status == DeviceStatus.BORROWED and device.expected_return_date:
                if datetime.now().date() > device.expected_return_date.date():
                    overdue_days = (datetime.now().date() - device.expected_return_date.date()).days
                    overdue_devices.append({
                        'device': device,
                        'overdue_days': overdue_days
                    })
        
        # 按超时天数排序
        overdue_devices.sort(key=lambda x: x['overdue_days'], reverse=True)
        
        self.overdue_table.setRowCount(len(overdue_devices))
        
        for i, item in enumerate(overdue_devices):
            device = item['device']
            self.overdue_table.setItem(i, 0, QTableWidgetItem(device.name))
            self.overdue_table.setItem(i, 1, QTableWidgetItem(device.borrower))
            self.overdue_table.setItem(i, 2, QTableWidgetItem(device.borrow_time.strftime("%Y-%m-%d") if device.borrow_time else "-"))
            self.overdue_table.setItem(i, 3, QTableWidgetItem(device.expected_return_date.strftime("%Y-%m-%d") if device.expected_return_date else "-"))
            
            overdue_item = QTableWidgetItem(f"{item['overdue_days']} 天")
            overdue_item.setForeground(QBrush(QColor("#F5222D")))
            self.overdue_table.setItem(i, 4, overdue_item)
        
        # 更新标签页标题显示数量
        if hasattr(self, 'bottom_left_tab'):
            if overdue_devices:
                self.bottom_left_tab.setTabText(1, f"过期未还 ({len(overdue_devices)})")
            else:
                self.bottom_left_tab.setTabText(1, "过期未还")
    
    def on_device_selected(self, current, previous):
        """设备选中事件"""
        if not current:
            return
        
        device_id = current.data(0, Qt.UserRole)
        if not device_id:
            return
        
        device = api_client.get_device_by_id(device_id)
        if not device:
            return
        
        self.current_device = device
        
        # 更新详情面板
        self.update_device_detail(device)
        
        # 加载设备借还记录
        self.load_device_records(device.name)
    
    def show_device_context_menu(self, position):
        """显示设备右键菜单"""
        item = self.device_tree.itemAt(position)
        if not item:
            return
        
        device_id = item.data(0, Qt.UserRole)
        if not device_id:
            return
        
        device = api_client.get_device_by_id(device_id)
        if not device:
            return
        
        menu = QMenu()
        
        edit_action = menu.addAction("编辑设备")
        
        # 为无柜号或流通设备添加设置柜号功能
        cabinet = device.cabinet_number or ""
        if not cabinet.strip() or cabinet.strip() == "流通":
            set_cabinet_action = menu.addAction("设置柜号")
        
        if device.status == DeviceStatus.IN_STOCK:
            borrow_action = menu.addAction("录入登记")
        elif device.status == DeviceStatus.BORROWED:
            transfer_action = menu.addAction("转借")
            return_action = menu.addAction("强制归还")
        
        # 状态设置子菜单（管理员专用）
        menu.addSeparator()
        status_menu = menu.addMenu("设置状态")
        status_instock = status_menu.addAction("在库")
        status_shipped = status_menu.addAction("已寄出")
        status_damaged = status_menu.addAction("已损坏")
        status_lost = status_menu.addAction("丢失")
        status_scrapped = status_menu.addAction("报废")
        
        menu.addSeparator()
        delete_action = menu.addAction("删除设备")
        
        action = menu.exec(self.device_tree.viewport().mapToGlobal(position))
        
        if action == edit_action:
            self.on_edit_device()
        elif 'set_cabinet_action' in locals() and action == set_cabinet_action:
            self.on_set_cabinet(device)
        elif device.status == DeviceStatus.IN_STOCK and action == borrow_action:
            self.on_force_borrow()
        elif device.status == DeviceStatus.BORROWED and 'transfer_action' in locals() and action == transfer_action:
            self.on_transfer()
        elif device.status == DeviceStatus.BORROWED and 'return_action' in locals() and action == return_action:
            self.on_force_return()
        elif action == status_instock:
            self.on_set_device_status(device, DeviceStatus.IN_STOCK)
        elif action == status_shipped:
            self.on_set_device_status(device, DeviceStatus.SHIPPED)
        elif action == status_damaged:
            self.on_set_device_status(device, DeviceStatus.DAMAGED)
        elif action == status_lost:
            self.on_set_device_status(device, DeviceStatus.LOST)
        elif action == status_scrapped:
            self.on_set_device_status(device, DeviceStatus.SCRAPPED)
        elif action == delete_action:
            self.on_delete_device()
    
    def on_add_device(self):
        """新增设备"""
        dialog = DeviceEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_devices()
            self.load_operation_logs()
    
    def on_edit_device(self):
        """编辑设备"""
        if not hasattr(self, 'current_device'):
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
        
        dialog = DeviceEditDialog(self.current_device, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_devices()
            self.load_operation_logs()
            self.load_overdue_devices()
    
    def on_set_cabinet(self, device):
        """为无柜号或流通设备设置柜号"""
        from PyQt5.QtWidgets import QInputDialog
        
        cabinet, ok = QInputDialog.getText(
            self, 
            "设置柜号", 
            f"为设备 [{device.name}] 设置柜号/保管人：\n\n（设置后将转为正常在库设备）",
            text=""
        )
        
        if ok and cabinet.strip():
            cabinet = cabinet.strip()
            
            # 检查柜号是否已存在
            existing = [d for d in api_client.get_all_devices() 
                       if d.cabinet_number == cabinet and d.id != device.id]
            if existing:
                reply = QMessageBox.question(
                    self, "柜号已存在",
                    f"柜号 [{cabinet}] 已被其他设备使用，是否继续？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # 设置柜号
            device.cabinet_number = cabinet
            
            # 如果原来是流通或无柜号，设置为在库状态
            if device.status not in [DeviceStatus.IN_STOCK, DeviceStatus.BORROWED]:
                device.status = DeviceStatus.IN_STOCK
                device.borrower = ""
                device.phone = ""
                device.borrow_time = None
                device.reason = ""
                device.entry_source = ""
                device.expected_return_date = None
            
            api_client.update_device(device)
            api_client.add_operation_log(f"设置柜号: {cabinet}", device.name)
            
            QMessageBox.information(self, "成功", f"设备 [{device.name}] 已设置柜号为 [{cabinet}]，转为正常在库设备")
            self.load_devices()
            self.load_operation_logs()
            self.load_overdue_devices()
        elif ok:
            QMessageBox.warning(self, "警告", "柜号不能为空")
    
    def on_delete_device(self):
        """删除设备"""
        if not hasattr(self, 'current_device'):
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除设备 {self.current_device.name} 吗？\n（删除后可在数据库中恢复）",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if api_client.delete_device(self.current_device.id):
                QMessageBox.information(self, "成功", "设备已删除")
                self.load_devices()
                self.load_operation_logs()
                self.load_overdue_devices()
            else:
                QMessageBox.warning(self, "失败", "删除设备失败")
    
    def on_set_device_status(self, device, status):
        """设置设备状态（管理员专用）"""
        status_name = status.value
        reply = QMessageBox.question(
            self, "确认设置",
            f"确定要将设备 {device.name} 的状态设置为【{status_name}】吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            device.status = status
            # 清空借用信息
            device.borrower = ''
            device.phone = ''
            device.borrow_time = None
            device.reason = ''
            device.entry_source = ''
            device.expected_return_date = None
            
            api_client.update_device(device)
            api_client.add_operation_log(f"设置状态为{status_name}", device.name)
            api_client._save_data()
            
            QMessageBox.information(self, "成功", f"设备状态已设置为【{status_name}】")
            self.load_devices()
            self.load_operation_logs()
            self.load_overdue_devices()
    
    def on_force_borrow(self):
        """录入登记（强制借出）"""
        if not hasattr(self, 'current_device'):
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
        
        dialog = ForceBorrowDialog(self.current_device, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_devices()
            self.load_operation_logs()
            self.load_overdue_devices()
    
    def on_force_return(self):
        """强制归还"""
        if not hasattr(self, 'current_device'):
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
        
        dialog = ForceReturnDialog(self.current_device, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_devices()
            self.load_operation_logs()
            self.load_overdue_devices()
    
    def on_transfer(self):
        """转借设备"""
        if not hasattr(self, 'current_device'):
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
        
        if self.current_device.status != DeviceStatus.BORROWED:
            QMessageBox.warning(self, "警告", "该设备未借出，无法转借")
            return
        
        dialog = TransferDialog(self.current_device, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_devices()
            self.load_operation_logs()
            self.load_overdue_devices()
            self.load_device_records(self.current_device.name)
    
    def on_query_records(self):
        """查询记录"""
        dialog = RecordQueryDialog(parent=self)
        dialog.exec()
    
    def on_user_management(self):
        """用户管理"""
        dialog = UserManagementDialog(parent=self)
        dialog.exec()
    
    def refresh_data(self):
        """刷新数据"""
        # 重新从Excel加载数据
        api_client._car_machines = ExcelDataStore.load_car_machines()
        api_client._phones = ExcelDataStore.load_phones()
        api_client._records = ExcelDataStore.load_records()
        api_client._remarks = ExcelDataStore.load_remarks()
        api_client._users = ExcelDataStore.load_users()
        api_client._operation_logs = ExcelDataStore.load_operation_logs()
        api_client._view_records = ExcelDataStore.load_view_records()
        
        self.update_filter_options()
        self.load_devices()
        self.load_operation_logs()
        self.load_overdue_devices()
        
        # 刷新当前选中设备的详情
        if hasattr(self, 'current_device'):
            # 重新获取设备最新数据
            device = api_client.get_device_by_id(self.current_device.id)
            if device:
                self.current_device = device
                self.update_device_detail(device)
                # 刷新设备记录
                self.load_device_records(device.name)
        
        self.statusbar.showMessage(f"当前管理员: {api_client.get_current_admin()} | 数据已从Excel刷新", 3000)
    
    def on_remind_borrower(self, device):
        """提醒借用人"""
        from datetime import datetime
        overdue_days = (datetime.now().date() - device.expected_return_date.date()).days
        
        QMessageBox.information(
            self, "提醒",
            f"设备：{device.name}\n"
            f"借用人：{device.borrower}\n"
            f"手机号：{device.phone or '未记录'}\n"
            f"已超时：{overdue_days} 天\n\n"
            f"建议通过电话或微信联系借用人尽快归还设备。"
        )
        
        # 添加操作日志
        api_client.add_operation_log(f"提醒归还(超时{overdue_days}天): {device.borrower}", device.name)
        api_client._save_data()
    
    def update_device_detail(self, device):
        """更新设备详情面板"""
        self.detail_name.setText(device.name)
        is_car = isinstance(device, CarMachine)
        self.detail_type.setText("车机" if is_car else "手机")
        self.detail_model.setText(device.model or "-")
        self.detail_cabinet.setText(device.cabinet_number if device.cabinet_number else "无柜号")
        # 根据设备类型更新标签：车机显示"柜号"，手机显示"保管人"
        self.cabinet_label.setText("柜号:" if is_car else "保管人:")
        self.detail_status.setText(device.status.value)
        self.detail_borrower.setText(device.borrower or "-")
        self.detail_phone.setText(device.phone or "-")
        self.detail_reason.setText(device.reason or "-")
        self.detail_entry.setText(device.entry_source or "-")
        self.detail_remark.setText(device.remark or "-")
        
        # 根据设备状态显示动态信息
        if device.status == DeviceStatus.BORROWED:
            self.detail_dynamic_label1.setText("借出时间:")
            self.detail_dynamic_value1.setText(device.borrow_time.strftime("%Y-%m-%d %H:%M") if device.borrow_time else "-")
            self.detail_dynamic_label2.setText("预计归还:")
            self.detail_dynamic_value2.setText(device.expected_return_date.strftime("%Y-%m-%d") if device.expected_return_date else "-")
        elif device.status == DeviceStatus.DAMAGED:
            self.detail_dynamic_label1.setText("损坏时间:")
            self.detail_dynamic_value1.setText(device.damage_time.strftime("%Y-%m-%d %H:%M") if device.damage_time else "-")
            self.detail_dynamic_label2.setText("损坏原因:")
            self.detail_dynamic_value2.setText(device.damage_reason or "-")
        elif device.status == DeviceStatus.LOST:
            self.detail_dynamic_label1.setText("丢失时间:")
            self.detail_dynamic_value1.setText(device.lost_time.strftime("%Y-%m-%d %H:%M") if device.lost_time else "-")
            self.detail_dynamic_label2.setText("")
            self.detail_dynamic_value2.setText("")
        elif device.status == DeviceStatus.SCRAPPED:
            self.detail_dynamic_label1.setText("报废时间:")
            self.detail_dynamic_value1.setText(device.damage_time.strftime("%Y-%m-%d %H:%M") if device.damage_time else "-")
            self.detail_dynamic_label2.setText("")
            self.detail_dynamic_value2.setText("")
        else:
            # 在库、已寄出等状态不显示动态信息
            self.detail_dynamic_label1.setText("")
            self.detail_dynamic_value1.setText("")
            self.detail_dynamic_label2.setText("")
            self.detail_dynamic_value2.setText("")
        
        # 根据状态设置按钮可用性
        is_borrowed = device.status == DeviceStatus.BORROWED
        is_in_stock = device.status == DeviceStatus.IN_STOCK
        
        # 编辑设备：始终可用
        self.edit_btn.setEnabled(True)
        self.edit_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; padding: 8px 16px; }
            QPushButton:disabled { background-color: #BDBDBD; color: #757575; }
        """)
        
        # 录入登记：仅在"在库"状态时可用
        self.borrow_btn.setEnabled(is_in_stock)
        self.borrow_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; }
            QPushButton:disabled { background-color: #BDBDBD; color: #757575; }
        """)
        
        # 转借：仅在"借出"状态时可用
        self.transfer_btn.setEnabled(is_borrowed)
        self.transfer_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; padding: 8px 16px; }
            QPushButton:disabled { background-color: #BDBDBD; color: #757575; }
        """)
        
        # 强制归还：仅在"借出"状态时可用
        self.return_btn.setEnabled(is_borrowed)
        self.return_btn.setStyleSheet("""
            QPushButton { background-color: #FF5722; color: white; padding: 8px 16px; }
            QPushButton:disabled { background-color: #BDBDBD; color: #757575; }
        """)
        
        # 删除设备：借出中的设备不能删除
        self.delete_btn.setEnabled(not is_borrowed)
        self.delete_btn.setStyleSheet("""
            QPushButton { background-color: #F44336; color: white; padding: 8px 16px; }
            QPushButton:disabled { background-color: #BDBDBD; color: #757575; }
        """)
    
    def load_device_records(self, device_name):
        """加载设备的借还记录"""
        device = api_client.get_device_by_name(device_name)
        
        # 加载借还记录（3列：时间、操作类型、借用人）
        records = api_client.get_records(device_name=device_name)
        self.device_record_table.setRowCount(len(records))
        
        for i, record in enumerate(records):
            self.device_record_table.setItem(i, 0, QTableWidgetItem(record.operation_time.strftime("%Y-%m-%d %H:%M")))
            self.device_record_table.setItem(i, 1, QTableWidgetItem(record.operation_type.value))
            self.device_record_table.setItem(i, 2, QTableWidgetItem(record.borrower))
        
        # 加载用户备注（3列：时间、创建人、内容）
        if device:
            remarks = api_client.get_remarks(device_id=device.id)
            self.device_remark_table.setRowCount(len(remarks))
            
            for i, remark in enumerate(remarks):
                self.device_remark_table.setItem(i, 0, QTableWidgetItem(remark.create_time.strftime("%Y-%m-%d %H:%M")))
                self.device_remark_table.setItem(i, 1, QTableWidgetItem(remark.creator))
                self.device_remark_table.setItem(i, 2, QTableWidgetItem(remark.content))
        else:
            self.device_remark_table.setRowCount(0)
        
        # 加载查看记录（3列：时间、查看人、设备）
        if device:
            view_records = api_client.get_view_records(device_id=device.id)
            self.device_view_table.setRowCount(len(view_records))
            
            for i, record in enumerate(view_records):
                self.device_view_table.setItem(i, 0, QTableWidgetItem(record.view_time.strftime("%Y-%m-%d %H:%M")))
                self.device_view_table.setItem(i, 1, QTableWidgetItem(record.viewer))
                self.device_view_table.setItem(i, 2, QTableWidgetItem(device_name))
        else:
            self.device_view_table.setRowCount(0)
    
    def start_auto_refresh(self):
        """启动自动刷新定时器（每30秒）"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.on_auto_refresh)
        self.refresh_timer.start(30000)  # 30秒
    
    def on_auto_refresh(self):
        """自动刷新回调"""
        # 重新从Excel加载操作日志和查看记录（可能由网页端更新）
        api_client._operation_logs = ExcelDataStore.load_operation_logs()
        api_client._view_records = ExcelDataStore.load_view_records()
        self.load_operation_logs()
        self.load_overdue_devices()
        # 如果有选中的设备，刷新查看记录
        if hasattr(self, 'current_device'):
            self.load_device_records(self.current_device.name)


class UserEditDialog(QDialog):
    """用户编辑对话框"""
    def __init__(self, user=None, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("编辑用户" if user else "新增用户")
        self.setFixedSize(400, 300)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        # 借用人名称
        self.borrower_name_input = QLineEdit()
        self.borrower_name_input.setPlaceholderText("请输入借用人名称（唯一）")
        if self.user:
            self.borrower_name_input.setText(self.user.borrower_name)
        form_layout.addRow("借用人名称*:", self.borrower_name_input)
        
        # 微信名
        self.wechat_name_input = QLineEdit()
        self.wechat_name_input.setPlaceholderText("请输入微信名")
        if self.user:
            self.wechat_name_input.setText(self.user.wechat_name)
        form_layout.addRow("微信名*:", self.wechat_name_input)
        
        # 手机号
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("请输入手机号")
        if self.user:
            self.phone_input.setText(self.user.phone)
        form_layout.addRow("手机号*:", self.phone_input)
        
        # 密码
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码（默认123456）")
        self.password_input.setEchoMode(QLineEdit.Password)
        if self.user:
            self.password_input.setText(self.user.password)
        else:
            self.password_input.setText("123456")
        form_layout.addRow("密码:", self.password_input)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px;")
        save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def on_save(self):
        borrower_name = self.borrower_name_input.text().strip()
        wechat_name = self.wechat_name_input.text().strip()
        phone = self.phone_input.text().strip()
        password = self.password_input.text().strip()
        
        if not borrower_name or not wechat_name or not phone:
            QMessageBox.warning(self, "警告", "借用人名称、微信名和手机号不能为空")
            return
        
        # 验证手机号格式
        if not phone.isdigit() or len(phone) != 11:
            QMessageBox.warning(self, "警告", "手机号格式不正确，请输入11位数字")
            return
        
        if self.user:
            # 编辑用户 - 检查借用人名称是否被其他用户使用
            if borrower_name != self.user.borrower_name:
                for u in api_client._users:
                    if u.borrower_name == borrower_name and u.id != self.user.id:
                        QMessageBox.warning(self, "警告", "该借用人名称已被使用，请更换")
                        return
            
            # 检查手机号是否被其他用户使用
            if phone != self.user.phone:
                for u in api_client._users:
                    if u.phone == phone and u.id != self.user.id:
                        QMessageBox.warning(self, "警告", "该手机号已被使用，请更换")
                        return
            
            # 更新用户信息
            self.user.borrower_name = borrower_name
            self.user.wechat_name = wechat_name
            self.user.phone = phone
            self.user.password = password if password else "123456"
            
            api_client.add_operation_log(f"编辑用户: {borrower_name}", wechat_name)
            api_client._save_data()
            QMessageBox.information(self, "成功", "用户信息已更新")
            self.accept()
        else:
            # 新增用户 - 检查借用人名称是否已存在
            for u in api_client._users:
                if u.borrower_name == borrower_name:
                    QMessageBox.warning(self, "警告", "该借用人名称已存在，请更换")
                    return
            
            # 检查手机号是否已存在
            for u in api_client._users:
                if u.phone == phone:
                    QMessageBox.warning(self, "警告", "该手机号已存在，请更换")
                    return
            
            # 创建新用户
            import uuid
            from datetime import datetime
            new_user = User(
                id=str(uuid.uuid4()),
                borrower_name=borrower_name,
                wechat_name=wechat_name,
                phone=phone,
                password=password if password else "123456",
                borrow_count=0,
                is_frozen=False,
                create_time=datetime.now()
            )
            
            api_client._users.append(new_user)
            api_client.add_operation_log(f"新增用户: {borrower_name}", wechat_name)
            api_client._save_data()
            QMessageBox.information(self, "成功", "用户已添加")
            self.accept()


class UserManagementDialog(QDialog):
    """人员管理对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户管理")
        self.resize(900, 600)
        self.setup_ui()
        self.load_users()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入借用人名称、微信名或手机号搜索...")
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # 用户表格
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(8)
        self.user_table.setHorizontalHeaderLabels(["借用人名称", "微信名", "手机号", "借用次数", "状态", "管理员", "注册时间", "密码"])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        self.user_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.user_table.setAlternatingRowColors(True)
        layout.addWidget(self.user_table)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.add_btn = QPushButton("+ 新增用户")
        self.add_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.add_btn.clicked.connect(self.on_add)
        btn_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.edit_btn.clicked.connect(self.on_edit)
        btn_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setStyleSheet("background-color: #F44336; color: white;")
        self.delete_btn.clicked.connect(self.on_delete)
        btn_layout.addWidget(self.delete_btn)
        
        btn_layout.addSpacing(20)
        
        self.freeze_btn = QPushButton("冻结账号")
        self.freeze_btn.setStyleSheet("background-color: #FF5722; color: white;")
        self.freeze_btn.clicked.connect(self.on_freeze)
        btn_layout.addWidget(self.freeze_btn)
        
        self.unfreeze_btn = QPushButton("解冻账号")
        self.unfreeze_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.unfreeze_btn.clicked.connect(self.on_unfreeze)
        btn_layout.addWidget(self.unfreeze_btn)
        
        btn_layout.addSpacing(20)
        
        self.set_admin_btn = QPushButton("设为管理员")
        self.set_admin_btn.setStyleSheet("background-color: #9C27B0; color: white;")
        self.set_admin_btn.clicked.connect(self.on_set_admin)
        btn_layout.addWidget(self.set_admin_btn)
        
        self.cancel_admin_btn = QPushButton("取消管理员")
        self.cancel_admin_btn.setStyleSheet("background-color: #607D8B; color: white;")
        self.cancel_admin_btn.clicked.connect(self.on_cancel_admin)
        btn_layout.addWidget(self.cancel_admin_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def load_users(self):
        """加载用户列表"""
        self.all_users = api_client.get_all_users()
        self.refresh_table(self.all_users)
    
    def refresh_table(self, users):
        """刷新表格显示"""
        self.user_table.setRowCount(len(users))
        
        for i, user in enumerate(users):
            self.user_table.setItem(i, 0, QTableWidgetItem(user.borrower_name))
            self.user_table.setItem(i, 1, QTableWidgetItem(user.wechat_name))
            self.user_table.setItem(i, 2, QTableWidgetItem(user.phone))
            self.user_table.setItem(i, 3, QTableWidgetItem(str(user.borrow_count)))
            
            status_item = QTableWidgetItem("已冻结" if user.is_frozen else "正常")
            if user.is_frozen:
                status_item.setForeground(QBrush(QColor("#FF5722")))
            self.user_table.setItem(i, 4, status_item)

            # 管理员标识
            admin_item = QTableWidgetItem("是" if user.is_admin else "否")
            if user.is_admin:
                admin_item.setForeground(QBrush(QColor("#9C27B0")))  # 紫色高亮
            self.user_table.setItem(i, 5, admin_item)

            self.user_table.setItem(i, 6, QTableWidgetItem(
                user.create_time.strftime("%Y-%m-%d") if user.create_time else ""
            ))

            # 显示密码（管理员可见）
            self.user_table.setItem(i, 7, QTableWidgetItem(user.password))
            
            # 保存用户ID到第一列
            self.user_table.item(i, 0).setData(Qt.UserRole, user.id)
    
    def on_search(self):
        """搜索用户"""
        keyword = self.search_input.text().strip().lower()
        if not keyword:
            self.refresh_table(self.all_users)
            return
        
        filtered = []
        for user in self.all_users:
            if (keyword in user.borrower_name.lower() or
                keyword in user.wechat_name.lower() or
                keyword in user.phone):
                filtered.append(user)
        
        self.refresh_table(filtered)
    
    def on_add(self):
        """新增用户"""
        dialog = UserEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_users()
    
    def on_edit(self):
        """编辑用户"""
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个用户")
            return
        
        user_id = self.user_table.item(row, 0).data(Qt.UserRole)
        user = None
        for u in api_client._users:
            if u.id == user_id:
                user = u
                break
        
        if not user:
            QMessageBox.warning(self, "错误", "用户不存在")
            return
        
        dialog = UserEditDialog(user, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.load_users()
    
    def on_delete(self):
        """删除用户"""
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个用户")
            return
        
        user_id = self.user_table.item(row, 0).data(Qt.UserRole)
        borrower_name = self.user_table.item(row, 0).text()
        wechat_name = self.user_table.item(row, 1).text()
        borrow_count = int(self.user_table.item(row, 3).text())
        
        # 检查用户是否有借用记录
        if borrow_count > 0:
            QMessageBox.warning(self, "警告", f"用户 {borrower_name} 有借用记录，不能删除")
            return
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除用户 {borrower_name}（{wechat_name}）吗？\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 从列表中删除用户
            for i, u in enumerate(api_client._users):
                if u.id == user_id:
                    del api_client._users[i]
                    break
            
            api_client.add_operation_log(f"删除用户: {borrower_name}", wechat_name)
            api_client._save_data()
            QMessageBox.information(self, "成功", "用户已删除")
            self.load_users()
    
    def on_freeze(self):
        """冻结用户"""
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个用户")
            return
        
        user_id = self.user_table.item(row, 0).data(Qt.UserRole)
        borrower_name = self.user_table.item(row, 0).text()
        
        reply = QMessageBox.question(self, "确认", f"确定要冻结用户 {borrower_name} 吗？")
        if reply == QMessageBox.Yes:
            if api_client.freeze_user(user_id):
                QMessageBox.information(self, "成功", "用户已冻结")
                self.load_users()
            else:
                QMessageBox.warning(self, "失败", "冻结用户失败")
    
    def on_unfreeze(self):
        """解冻用户"""
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个用户")
            return

        user_id = self.user_table.item(row, 0).data(Qt.UserRole)
        borrower_name = self.user_table.item(row, 0).text()

        reply = QMessageBox.question(self, "确认", f"确定要解冻用户 {borrower_name} 吗？")
        if reply == QMessageBox.Yes:
            if api_client.unfreeze_user(user_id):
                QMessageBox.information(self, "成功", "用户已解冻")
                self.load_users()
            else:
                QMessageBox.warning(self, "失败", "解冻用户失败")

    def on_set_admin(self):
        """设置用户为管理员"""
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个用户")
            return

        user_id = self.user_table.item(row, 0).data(Qt.UserRole)
        borrower_name = self.user_table.item(row, 0).text()

        reply = QMessageBox.question(self, "确认", f"确定要设置 {borrower_name} 为管理员吗？")
        if reply == QMessageBox.Yes:
            if api_client.set_user_admin(user_id):
                QMessageBox.information(self, "成功", "已设置为管理员")
                self.load_users()
            else:
                QMessageBox.warning(self, "失败", "设置管理员失败")

    def on_cancel_admin(self):
        """取消用户管理员权限"""
        row = self.user_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个用户")
            return

        user_id = self.user_table.item(row, 0).data(Qt.UserRole)
        borrower_name = self.user_table.item(row, 0).text()

        reply = QMessageBox.question(self, "确认", f"确定要取消 {borrower_name} 的管理员权限吗？")
        if reply == QMessageBox.Yes:
            if api_client.cancel_user_admin(user_id):
                QMessageBox.information(self, "成功", "已取消管理员权限")
                self.load_users()
            else:
                QMessageBox.warning(self, "失败", "取消管理员权限失败")


class RemarkManagementDialog(QDialog):
    """备注管理对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("备注管理")
        self.resize(900, 500)
        self.setup_ui()
        self.load_remarks()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 备注表格
        self.remark_table = QTableWidget()
        self.remark_table.setColumnCount(5)
        self.remark_table.setHorizontalHeaderLabels(["设备名", "备注内容", "创建人", "创建时间", "状态"])
        self.remark_table.horizontalHeader().setStretchLastSection(True)
        self.remark_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.remark_table.setAlternatingRowColors(True)
        layout.addWidget(self.remark_table)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.mark_btn = QPushButton("标记不当")
        self.mark_btn.setStyleSheet("background-color: #FF9800; color: white;")
        self.mark_btn.clicked.connect(self.on_mark)
        btn_layout.addWidget(self.mark_btn)
        
        self.delete_btn = QPushButton("删除备注")
        self.delete_btn.setStyleSheet("background-color: #F44336; color: white;")
        self.delete_btn.clicked.connect(self.on_delete)
        btn_layout.addWidget(self.delete_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def load_remarks(self):
        """加载备注列表"""
        remarks = api_client.get_remarks()
        self.remark_table.setRowCount(len(remarks))
        
        for i, remark in enumerate(remarks):
            device = api_client.get_device_by_id(remark.device_id)
            device_name = device.name if device else "未知设备"
            
            self.remark_table.setItem(i, 0, QTableWidgetItem(device_name))
            self.remark_table.setItem(i, 1, QTableWidgetItem(remark.content))
            self.remark_table.setItem(i, 2, QTableWidgetItem(remark.creator))
            self.remark_table.setItem(i, 3, QTableWidgetItem(
                remark.create_time.strftime("%Y-%m-%d %H:%M")
            ))
            
            status = "不当" if remark.is_inappropriate else "正常"
            status_item = QTableWidgetItem(status)
            if remark.is_inappropriate:
                status_item.setForeground(QBrush(QColor("#FF5722")))
            self.remark_table.setItem(i, 4, status_item)
            
            # 保存备注ID
            self.remark_table.item(i, 0).setData(Qt.UserRole, remark.id)
    
    def on_mark(self):
        """标记不当备注"""
        row = self.remark_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个备注")
            return
        
        remark_id = self.remark_table.item(row, 0).data(Qt.UserRole)
        
        if api_client.mark_inappropriate(remark_id):
            QMessageBox.information(self, "成功", "备注已标记为不当")
            self.load_remarks()
        else:
            QMessageBox.warning(self, "失败", "标记失败")
    
    def on_delete(self):
        """删除备注"""
        row = self.remark_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "警告", "请先选择一个备注")
            return
        
        remark_id = self.remark_table.item(row, 0).data(Qt.UserRole)
        
        reply = QMessageBox.question(self, "确认", "确定要删除该备注吗？")
        if reply == QMessageBox.Yes:
            if api_client.delete_remark(remark_id):
                QMessageBox.information(self, "成功", "备注已删除")
                self.load_remarks()
            else:
                QMessageBox.warning(self, "失败", "删除失败")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置应用样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            padding: 8px 16px;
            border-radius: 4px;
            border: none;
        }
        QTableWidget {
            border: 1px solid #dddddd;
            gridline-color: #eeeeee;
        }
        QHeaderView::section {
            background-color: #e3f2fd;
            padding: 5px;
            border: 1px solid #bbdefb;
            font-weight: bold;
        }
        QTreeWidget {
            border: 1px solid #dddddd;
        }
        QLabel {
            padding: 2px;
        }
    """)
    
    # 显示登录对话框
    login_dialog = LoginDialog()
    if login_dialog.exec() != QDialog.Accepted:
        return
    
    # 显示主窗口
    window = DeviceManager()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
