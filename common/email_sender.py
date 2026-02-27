# -*- coding: utf-8 -*-
"""
邮件发送模块
用于发送系统通知邮件
"""
import smtplib
import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List, Optional


def encode_rfc2047(text: str) -> str:
    """
    使用RFC2047标准编码非ASCII文本（如中文）
    格式: "=?charset?encoding?encoded-text?="
    注意：根据QQ邮箱要求，编码后的文本需要用双引号包裹
    """
    if not text:
        return text
    # 检查是否包含非ASCII字符
    try:
        text.encode('ascii')
        return text  # 纯ASCII，无需编码
    except UnicodeEncodeError:
        # 需要base64编码，并用双引号包裹
        encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
        return f"\"=?UTF-8?B?{encoded}?=\""

# 邮件配置
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.company.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', '设备管理系统')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'noreply@company.com')

# 系统URL
USER_DOMAIN = os.getenv('USER_DOMAIN', 'device.carbit.com.cn')
ADMIN_DOMAIN = os.getenv('ADMIN_DOMAIN', 'admin.device.carbit.com.cn')


class EmailSender:
    """邮件发送器"""
    
    def __init__(self):
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_name = SMTP_FROM_NAME
        self.from_email = SMTP_FROM_EMAIL
        
    def _create_smtp_connection(self):
        """创建SMTP连接"""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            return server
        except Exception as e:
            print(f"SMTP连接失败: {e}")
            return None
    
    def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML格式的邮件内容
            
        Returns:
            发送成功返回True，否则返回False
        """
        if not self.username or not self.password:
            print("邮件配置不完整，跳过发送")
            return False
            
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            # 主题使用Header编码
            msg['Subject'] = Header(subject, 'utf-8').encode()
            # From使用RFC2047编码（中文昵称需要base64编码）
            encoded_name = encode_rfc2047(self.from_name)
            msg['From'] = f"{encoded_name} <{self.from_email}>"
            # To直接使用邮箱地址
            msg['To'] = to_email
            
            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送邮件
            server = self._create_smtp_connection()
            if not server:
                return False
                
            server.sendmail(self.from_email, [to_email], msg.as_string())
            server.quit()
            
            print(f"邮件发送成功: {to_email}")
            return True
            
        except Exception as e:
            print(f"邮件发送失败: {e}")
            return False
    
    def send_overdue_reminder(self, to_email: str, borrower_name: str, 
                              devices: List[dict]) -> bool:
        """
        发送逾期提醒邮件
        
        Args:
            to_email: 收件人邮箱
            borrower_name: 借用人姓名
            devices: 逾期设备列表，每个设备包含name, overdue_days, device_type
        """
        subject = f"【设备管理系统】您有{len(devices)}个设备已逾期3天以上，请尽快归还"
        
        # 构建设备列表HTML
        devices_html = ""
        for device in devices:
            overdue_days = device.get('overdue_days', 0)
            device_name = device.get('name', '')
            device_type = device.get('device_type', '')
            devices_html += f"""
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd;">{device_name}</td>
                <td style="padding: 10px; border: 1px solid #ddd;">{device_type}</td>
                <td style="padding: 10px; border: 1px solid #ddd; color: #ff4d4f; font-weight: bold;">逾期{overdue_days}天</td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #ff4d4f; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f5f5f5; padding: 20px; margin: 20px 0; }}
                .device-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .device-table th {{ background: #1890ff; color: white; padding: 10px; text-align: left; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #1890ff; color: white; 
                          text-decoration: none; border-radius: 4px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>⚠️ 设备逾期提醒</h2>
                </div>
                
                <div class="content">
                    <p>尊敬的 {borrower_name}，</p>
                    <p>您借用的以下设备已<strong style="color: #ff4d4f;">逾期3天以上</strong>，请尽快归还：</p>
                    
                    <table class="device-table">
                        <thead>
                            <tr>
                                <th>设备名称</th>
                                <th>设备类型</th>
                                <th>逾期时间</th>
                            </tr>
                        </thead>
                        <tbody>
                            {devices_html}
                        </tbody>
                    </table>
                    
                    <p style="color: #ff4d4f; font-weight: bold;">
                        请尽快登录系统归还设备，以免影响您的借用权限。
                    </p>
                    
                    <div style="text-align: center;">
                        <a href="http://{USER_DOMAIN}" class="button">立即登录系统</a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>此邮件由设备管理系统自动发送，请勿回复</p>
                    <p>发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def send_reservation_pending_reminder(self, to_email: str, recipient_name: str,
                                          device_name: str, device_type: str,
                                          start_time: datetime, end_time: datetime,
                                          reserver_name: str, role: str) -> bool:
        """
        发送预约待确认提醒邮件
        
        Args:
            to_email: 收件人邮箱
            recipient_name: 收件人姓名
            device_name: 设备名称
            device_type: 设备类型
            start_time: 预约开始时间
            end_time: 预约结束时间
            reserver_name: 预约人姓名
            role: 角色（'borrower'借用人 或 'custodian'保管人）
        """
        role_text = "借用" if role == 'borrower' else "保管"
        subject = f"【设备管理系统】您{role_text}的设备有人预约借用，请尽快确认"
        
        time_range = f"{start_time.strftime('%Y年%m月%d日 %H:%M')} 至 {end_time.strftime('%Y年%m月%d日 %H:%M')}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1890ff; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f5f5f5; padding: 20px; margin: 20px 0; }}
                .info-box {{ background: white; padding: 15px; margin: 15px 0; border-left: 4px solid #1890ff; }}
                .highlight {{ color: #1890ff; font-weight: bold; }}
                .warning {{ color: #ff4d4f; font-weight: bold; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #52c41a; color: white; 
                          text-decoration: none; border-radius: 4px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>📅 设备预约确认提醒</h2>
                </div>
                
                <div class="content">
                    <p>尊敬的 {recipient_name}，</p>
                    
                    <p>您<span class="highlight">{role_text}</span>的以下设备有人预约借用，请尽快登录系统确认：</p>
                    
                    <div class="info-box">
                        <p><strong>设备名称：</strong>{device_name}</p>
                        <p><strong>设备类型：</strong>{device_type}</p>
                        <p><strong>预约人：</strong>{reserver_name}</p>
                        <p><strong>预约时间：</strong><span class="warning">{time_range}</span></p>
                    </div>
                    
                    <p style="color: #666;">
                        请在预约开始时间前登录系统确认是否同意该预约，逾期未确认将自动过期。
                    </p>
                    
                    <div style="text-align: center;">
                        <a href="http://{USER_DOMAIN}" class="button">立即登录确认</a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>此邮件由设备管理系统自动发送，请勿回复</p>
                    <p>发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)


# 全局邮件发送器实例
email_sender = EmailSender()
