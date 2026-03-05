# -*- coding: utf-8 -*-
"""
系统维护异步任务
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from celery import shared_task
from datetime import datetime, timedelta


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cleanup_old_records_async(self, days: int = 90):
    """
    异步清理旧记录
    :param days: 保留天数，默认90天
    """
    try:
        from common.db_store import DatabaseStore

        db = DatabaseStore()
        cutoff_date = datetime.now() - timedelta(days=days)

        print(f"开始清理 {days} 天前的记录...")

        # 清理操作日志
        deleted_logs = db.clear_admin_operation_logs(days=days)
        print(f"✓ 清理后台操作日志: {deleted_logs} 条")

        # 清理查看记录
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM view_records WHERE view_time < %s",
                (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
            )
            deleted_views = cursor.rowcount
            conn.commit()
            print(f"✓ 清理查看记录: {deleted_views} 条")

        # 清理邮件日志
            cursor.execute(
                "DELETE FROM email_logs WHERE sent_at < %s",
                (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),)
            )
            deleted_emails = cursor.rowcount
            conn.commit()
            print(f"✓ 清理邮件日志: {deleted_emails} 条")

        total_deleted = deleted_logs + deleted_views + deleted_emails
        print(f"✓ 清理完成，共清理 {total_deleted} 条记录")

        return {
            'success': True,
            'message': '清理完成',
            'deleted_logs': deleted_logs,
            'deleted_views': deleted_views,
            'deleted_emails': deleted_emails,
            'total_deleted': total_deleted
        }

    except Exception as e:
        print(f"✗ 清理记录时发生错误: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_expired_reservations_async(self):
    """
    异步处理过期预约
    将过期预约标记为已过期
    """
    try:
        from common.db_store import DatabaseStore
        from common.models import ReservationStatus

        db = DatabaseStore()

        print("开始处理过期预约...")

        # 获取已过期的待确认预约
        expired_reservations = db.get_expired_pending_reservations()

        processed_count = 0
        for reservation in expired_reservations:
            try:
                # 更新状态为已过期
                reservation.status = ReservationStatus.EXPIRED.value
                db.save_reservation(reservation)
                processed_count += 1
                print(f"✓ 预约 {reservation.id} 已标记为过期")
            except Exception as e:
                print(f"✗ 处理预约 {reservation.id} 时出错: {e}")

        print(f"✓ 过期预约处理完成，共处理 {processed_count} 条")

        return {
            'success': True,
            'message': '过期预约处理完成',
            'processed_count': processed_count
        }

    except Exception as e:
        print(f"✗ 处理过期预约时发生错误: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def convert_due_reservations_async(self):
    """
    异步转换到期预约为借用
    已到开始时间的已同意预约自动转为借用状态
    """
    try:
        from common.db_store import DatabaseStore
        from common.api_client import api_client

        db = DatabaseStore()

        print("开始转换到期预约...")

        # 获取需要转换的预约
        pending_reservations = db.get_pending_reservations_to_convert()

        converted_count = 0
        for reservation in pending_reservations:
            try:
                # 转换预约为借用
                result = api_client.convert_reservation_to_borrow(reservation.id)
                if result.get('success'):
                    converted_count += 1
                    print(f"✓ 预约 {reservation.id} 已转换为借用")
                else:
                    print(f"✗ 预约 {reservation.id} 转换失败: {result.get('message')}")
            except Exception as e:
                print(f"✗ 转换预约 {reservation.id} 时出错: {e}")

        print(f"✓ 到期预约转换完成，共转换 {converted_count} 条")

        return {
            'success': True,
            'message': '到期预约转换完成',
            'converted_count': converted_count
        }

    except Exception as e:
        print(f"✗ 转换到期预约时发生错误: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cancel_expired_bounties_async(self):
    """
    异步取消过期悬赏
    """
    try:
        from common.db_store import DatabaseStore

        db = DatabaseStore()

        print("开始取消过期悬赏...")

        # 获取并取消过期悬赏
        cancelled_bounties = db.auto_cancel_expired_bounties()

        print(f"✓ 过期悬赏取消完成，共取消 {len(cancelled_bounties)} 条")

        return {
            'success': True,
            'message': '过期悬赏取消完成',
            'cancelled_count': len(cancelled_bounties)
        }

    except Exception as e:
        print(f"✗ 取消过期悬赏时发生错误: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_overdue_reminders_async(self):
    """
    异步发送逾期提醒
    """
    try:
        from common.db_store import DatabaseStore
        from common.tasks.email_tasks import send_overdue_reminder_async

        db = DatabaseStore()

        print("开始发送逾期提醒...")

        # 获取逾期设备
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.id, d.name, d.borrower_id, d.expected_return_date, u.email
                FROM devices d
                JOIN users u ON d.borrower_id = u.id
                WHERE d.status = 'BORROWED'
                AND d.is_deleted = 0
                AND d.expected_return_date IS NOT NULL
                AND d.expected_return_date < DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            overdue_devices = cursor.fetchall()

        sent_count = 0
        for device in overdue_devices:
            try:
                # 计算逾期天数
                expected_date = device['expected_return_date']
                if isinstance(expected_date, str):
                    expected_date = datetime.strptime(expected_date, '%Y-%m-%d %H:%M:%S')

                days_overdue = (datetime.now() - expected_date).days
                if days_overdue < 1:
                    days_overdue = 1

                # 发送异步邮件
                send_overdue_reminder_async.delay(
                    user_id=device['borrower_id'],
                    user_email=device['email'],
                    device_name=device['name'],
                    days_overdue=days_overdue
                )
                sent_count += 1

            except Exception as e:
                print(f"✗ 发送设备 {device['id']} 的逾期提醒时出错: {e}")

        print(f"✓ 逾期提醒发送完成，共发送 {sent_count} 条")

        return {
            'success': True,
            'message': '逾期提醒发送完成',
            'sent_count': sent_count
        }

    except Exception as e:
        print(f"✗ 发送逾期提醒时发生错误: {e}")
        raise self.retry(exc=e)
