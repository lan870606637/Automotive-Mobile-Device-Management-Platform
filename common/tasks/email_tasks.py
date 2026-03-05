# -*- coding: utf-8 -*-
"""
邮件发送异步任务
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_async(self, to_email: str, subject: str, content: str, content_type: str = 'html'):
    """
    异步发送邮件
    :param to_email: 收件人邮箱
    :param subject: 邮件主题
    :param content: 邮件内容
    :param content_type: 内容类型
    """
    try:
        from common.email_sender import email_sender

        result = email_sender.send_email(
            to_email=to_email,
            subject=subject,
            content=content,
            content_type=content_type
        )

        if result:
            print(f"✓ 邮件发送成功: {to_email}")
            return {'success': True, 'message': '邮件发送成功'}
        else:
            print(f"✗ 邮件发送失败: {to_email}")
            # 重试
            raise self.retry(exc=Exception("邮件发送失败"))

    except MaxRetriesExceededError:
        print(f"✗ 邮件发送重试次数超限: {to_email}")
        return {'success': False, 'message': '邮件发送重试次数超限'}
    except Exception as e:
        print(f"✗ 邮件发送异常: {to_email}, 错误: {e}")
        # 重试
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_overdue_reminder_async(self, user_id: str, user_email: str, device_name: str, days_overdue: int):
    """
    异步发送逾期提醒邮件
    :param user_id: 用户ID
    :param user_email: 用户邮箱
    :param device_name: 设备名称
    :param days_overdue: 逾期天数
    """
    try:
        from common.email_sender import email_sender

        subject = f"【设备管理系统】设备逾期归还提醒 - {device_name}"
        content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #e74c3c;">设备逾期归还提醒</h2>
                <p>尊敬的用户：</p>
                <p>您借用的设备 <strong>{device_name}</strong> 已逾期 <strong>{days_overdue}</strong> 天未归还。</p>
                <p>请尽快归还设备，以免影响您的信用记录。</p>
                <p style="margin-top: 30px; color: #666; font-size: 12px;">
                    此邮件由系统自动发送，请勿回复。
                </p>
            </div>
        </body>
        </html>
        """

        result = email_sender.send_email(
            to_email=user_email,
            subject=subject,
            content=content,
            content_type='html'
        )

        if result:
            # 记录邮件发送日志
            from common.db_store import DatabaseStore
            db = DatabaseStore()
            db.save_email_log(
                user_id=user_id,
                user_email=user_email,
                email_type='overdue_reminder',
                related_id=device_name,
                related_type='device',
                status='sent'
            )
            print(f"✓ 逾期提醒邮件发送成功: {user_email}")
            return {'success': True, 'message': '逾期提醒邮件发送成功'}
        else:
            raise self.retry(exc=Exception("邮件发送失败"))

    except MaxRetriesExceededError:
        # 记录失败日志
        from common.db_store import DatabaseStore
        db = DatabaseStore()
        db.save_email_log(
            user_id=user_id,
            user_email=user_email,
            email_type='overdue_reminder',
            related_id=device_name,
            related_type='device',
            status='failed'
        )
        print(f"✗ 逾期提醒邮件发送重试次数超限: {user_email}")
        return {'success': False, 'message': '邮件发送重试次数超限'}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_reservation_notification_async(self, user_id: str, user_email: str, notification_type: str, **kwargs):
    """
    异步发送预约通知邮件
    :param user_id: 用户ID
    :param user_email: 用户邮箱
    :param notification_type: 通知类型 (approved/rejected/cancelled/reminder)
    :param kwargs: 其他参数
    """
    try:
        from common.email_sender import email_sender

        if notification_type == 'approved':
            subject = f"【设备管理系统】预约申请已通过 - {kwargs.get('device_name', '')}"
            content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #27ae60;">预约申请已通过</h2>
                    <p>尊敬的用户：</p>
                    <p>您的设备预约申请已通过审核。</p>
                    <p><strong>设备名称：</strong>{kwargs.get('device_name', '')}</p>
                    <p><strong>预约时间：</strong>{kwargs.get('start_time', '')} 至 {kwargs.get('end_time', '')}</p>
                    <p>请在预约时间开始时领取设备。</p>
                </div>
            </body>
            </html>
            """
        elif notification_type == 'rejected':
            subject = f"【设备管理系统】预约申请被拒绝 - {kwargs.get('device_name', '')}"
            content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #e74c3c;">预约申请被拒绝</h2>
                    <p>尊敬的用户：</p>
                    <p>很抱歉，您的设备预约申请未通过审核。</p>
                    <p><strong>设备名称：</strong>{kwargs.get('device_name', '')}</p>
                    <p><strong>拒绝原因：</strong>{kwargs.get('reason', '无')}</p>
                </div>
            </body>
            </html>
            """
        else:
            return {'success': False, 'message': '未知的通知类型'}

        result = email_sender.send_email(
            to_email=user_email,
            subject=subject,
            content=content,
            content_type='html'
        )

        if result:
            print(f"✓ 预约通知邮件发送成功: {user_email}")
            return {'success': True, 'message': '预约通知邮件发送成功'}
        else:
            raise self.retry(exc=Exception("邮件发送失败"))

    except Exception as e:
        raise self.retry(exc=e)
