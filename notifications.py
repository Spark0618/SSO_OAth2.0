"""
实时通知和消息推送系统
支持多种通知渠道和消息类型
"""

import json
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import threading
import queue
import os

from cache import get_default_cache_manager


class NotificationType(Enum):
    """通知类型枚举"""
    SYSTEM = "system"           # 系统通知
    COURSE = "course"           # 课程通知
    ASSIGNMENT = "assignment"   # 作业通知
    ANNOUNCEMENT = "announcement" # 公告通知
    GRADE = "grade"             # 成绩通知
    MESSAGE = "message"         # 私信通知
    REMINDER = "reminder"       # 提醒通知


class NotificationPriority(Enum):
    """通知优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(Enum):
    """通知渠道枚举"""
    IN_APP = "in_app"           # 应用内通知
    EMAIL = "email"             # 邮件通知
    SMS = "sms"                 # 短信通知
    WEBSOCKET = "websocket"     # WebSocket实时推送
    PUSH = "push"               # 推送通知


class NotificationStatus(Enum):
    """通知状态枚举"""
    PENDING = "pending"         # 待发送
    SENT = "sent"               # 已发送
    DELIVERED = "delivered"     # 已送达
    READ = "read"               # 已读
    FAILED = "failed"           # 发送失败


class Notification:
    """通知对象"""
    def __init__(
        self,
        id: str = None,
        recipient_id: str = None,
        title: str = None,
        content: str = None,
        notification_type: NotificationType = NotificationType.SYSTEM,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: List[NotificationChannel] = None,
        data: Dict[str, Any] = None,
        expires_at: datetime = None,
        created_at: datetime = None
    ):
        self.id = id or str(uuid.uuid4())
        self.recipient_id = recipient_id
        self.title = title
        self.content = content
        self.notification_type = notification_type
        self.priority = priority
        self.channels = channels or [NotificationChannel.IN_APP]
        self.data = data or {}
        self.expires_at = expires_at or (datetime.now() + timedelta(days=30))
        self.created_at = created_at or datetime.now()
        self.status = NotificationStatus.PENDING
        self.sent_at = None
        self.read_at = None
        self.delivery_attempts = 0
        self.error_message = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "recipient_id": self.recipient_id,
            "title": self.title,
            "content": self.content,
            "type": self.notification_type.value,
            "priority": self.priority.value,
            "channels": [c.value for c in self.channels],
            "data": self.data,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status.value,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "delivery_attempts": self.delivery_attempts,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """从字典创建通知对象"""
        notification = cls(
            id=data.get("id"),
            recipient_id=data.get("recipient_id"),
            title=data.get("title"),
            content=data.get("content"),
            notification_type=NotificationType(data.get("type", "system")),
            priority=NotificationPriority(data.get("priority", "normal")),
            channels=[NotificationChannel(c) for c in data.get("channels", ["in_app"])],
            data=data.get("data", {}),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
        
        status = data.get("status")
        if status:
            notification.status = NotificationStatus(status)
        
        sent_at = data.get("sent_at")
        if sent_at:
            notification.sent_at = datetime.fromisoformat(sent_at)
        
        read_at = data.get("read_at")
        if read_at:
            notification.read_at = datetime.fromisoformat(read_at)
        
        notification.delivery_attempts = data.get("delivery_attempts", 0)
        notification.error_message = data.get("error_message")
        
        return notification


class NotificationProvider(ABC):
    """通知提供者抽象基类"""
    
    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """发送通知"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查提供者是否可用"""
        pass


class InAppNotificationProvider(NotificationProvider):
    """应用内通知提供者"""
    
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
    
    def send(self, notification: Notification) -> bool:
        """发送应用内通知"""
        try:
            # 获取用户的通知列表
            key = f"notifications:{notification.recipient_id}"
            notifications = self.cache_manager.get(key) or []
            
            # 添加新通知
            notifications.append(notification.to_dict())
            
            # 限制通知数量，保留最新的100条
            if len(notifications) > 100:
                notifications = notifications[-100:]
            
            # 更新缓存
            self.cache_manager.set(key, notifications, expire=86400)  # 24小时过期
            
            # 更新未读计数
            unread_key = f"notifications:unread:{notification.recipient_id}"
            unread_count = self.cache_manager.get(unread_key) or 0
            self.cache_manager.set(unread_key, unread_count + 1, expire=86400)
            
            return True
        except Exception as e:
            print(f"应用内通知发送失败: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """检查提供者是否可用"""
        return self.cache_manager is not None


class WebSocketNotificationProvider(NotificationProvider):
    """WebSocket通知提供者"""
    
    def __init__(self):
        self.active_connections = {}  # user_id -> list of connections
    
    def add_connection(self, user_id: str, connection):
        """添加WebSocket连接"""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(connection)
    
    def remove_connection(self, user_id: str, connection):
        """移除WebSocket连接"""
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(connection)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            except ValueError:
                pass
    
    def send(self, notification: Notification) -> bool:
        """发送WebSocket通知"""
        try:
            if notification.recipient_id not in self.active_connections:
                return False
            
            message = {
                "type": "notification",
                "data": notification.to_dict()
            }
            
            message_str = json.dumps(message)
            sent = False
            
            for connection in self.active_connections[notification.recipient_id]:
                try:
                    connection.send(message_str)
                    sent = True
                except Exception as e:
                    print(f"WebSocket发送失败: {str(e)}")
                    # 移除无效连接
                    self.remove_connection(notification.recipient_id, connection)
            
            return sent
        except Exception as e:
            print(f"WebSocket通知发送失败: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """检查提供者是否可用"""
        return True  # WebSocket提供者总是可用的


class EmailNotificationProvider(NotificationProvider):
    """邮件通知提供者"""
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.example.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@example.com")
    
    def send(self, notification: Notification) -> bool:
        """发送邮件通知"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = notification.data.get('email', '')
            msg['Subject'] = notification.title
            
            # 添加邮件正文
            body = MIMEText(notification.content, 'html')
            msg.attach(body)
            
            # 连接SMTP服务器并发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"邮件通知发送失败: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """检查提供者是否可用"""
        return all([
            self.smtp_server,
            self.smtp_port,
            self.smtp_username,
            self.smtp_password,
            self.from_email
        ])


class NotificationService:
    """通知服务"""
    
    def __init__(self, cache_manager=None):
        self.cache_manager = cache_manager or get_default_cache_manager()
        self.providers = {
            NotificationChannel.IN_APP: InAppNotificationProvider(self.cache_manager),
            NotificationChannel.WEBSOCKET: WebSocketNotificationProvider(),
            NotificationChannel.EMAIL: EmailNotificationProvider()
        }
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
    
    def register_provider(self, channel: NotificationChannel, provider: NotificationProvider):
        """注册通知提供者"""
        self.providers[channel] = provider
    
    def send_notification(self, notification: Notification) -> str:
        """发送通知"""
        # 添加到队列
        self.queue.put(notification)
        return notification.id
    
    def send_immediate(self, notification: Notification) -> bool:
        """立即发送通知"""
        success = False
        for channel in notification.channels:
            if channel in self.providers and self.providers[channel].is_available():
                if self.providers[channel].send(notification):
                    success = True
        
        if success:
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now()
        else:
            notification.status = NotificationStatus.FAILED
            notification.error_message = "所有渠道发送失败"
            notification.delivery_attempts += 1
        
        return success
    
    def get_user_notifications(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """获取用户通知列表"""
        key = f"notifications:{user_id}"
        notifications = self.cache_manager.get(key) or []
        
        # 过滤未读通知
        if unread_only:
            notifications = [n for n in notifications if n.get("read_at") is None]
        
        # 排序（最新的在前）
        notifications.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # 分页
        total = len(notifications)
        notifications = notifications[offset:offset+limit]
        
        return {
            "notifications": notifications,
            "total": total,
            "unread_count": self.get_unread_count(user_id)
        }
    
    def mark_as_read(self, user_id: str, notification_id: str) -> bool:
        """标记通知为已读"""
        try:
            key = f"notifications:{user_id}"
            notifications = self.cache_manager.get(key) or []
            
            updated = False
            for notification in notifications:
                if notification.get("id") == notification_id and notification.get("read_at") is None:
                    notification["read_at"] = datetime.now().isoformat()
                    notification["status"] = NotificationStatus.READ.value
                    updated = True
                    break
            
            if updated:
                self.cache_manager.set(key, notifications, expire=86400)
                
                # 更新未读计数
                unread_key = f"notifications:unread:{user_id}"
                unread_count = self.cache_manager.get(unread_key) or 0
                if unread_count > 0:
                    self.cache_manager.set(unread_key, unread_count - 1, expire=86400)
                
                return True
            
            return False
        except Exception as e:
            print(f"标记通知已读失败: {str(e)}")
            return False
    
    def mark_all_as_read(self, user_id: str) -> int:
        """标记所有通知为已读"""
        try:
            key = f"notifications:{user_id}"
            notifications = self.cache_manager.get(key) or []
            
            count = 0
            for notification in notifications:
                if notification.get("read_at") is None:
                    notification["read_at"] = datetime.now().isoformat()
                    notification["status"] = NotificationStatus.READ.value
                    count += 1
            
            if count > 0:
                self.cache_manager.set(key, notifications, expire=86400)
                # 重置未读计数
                unread_key = f"notifications:unread:{user_id}"
                self.cache_manager.set(unread_key, 0, expire=86400)
            
            return count
        except Exception as e:
            print(f"标记所有通知已读失败: {str(e)}")
            return 0
    
    def get_unread_count(self, user_id: str) -> int:
        """获取未读通知数量"""
        unread_key = f"notifications:unread:{user_id}"
        return self.cache_manager.get(unread_key) or 0
    
    def delete_notification(self, user_id: str, notification_id: str) -> bool:
        """删除通知"""
        try:
            key = f"notifications:{user_id}"
            notifications = self.cache_manager.get(key) or []
            
            original_length = len(notifications)
            notifications = [n for n in notifications if n.get("id") != notification_id]
            
            if len(notifications) < original_length:
                self.cache_manager.set(key, notifications, expire=86400)
                
                # 如果删除的是未读通知，更新未读计数
                deleted_notification = next((n for n in notifications if n.get("id") == notification_id), None)
                if deleted_notification and deleted_notification.get("read_at") is None:
                    unread_key = f"notifications:unread:{user_id}"
                    unread_count = self.cache_manager.get(unread_key) or 0
                    if unread_count > 0:
                        self.cache_manager.set(unread_key, unread_count - 1, expire=86400)
                
                return True
            
            return False
        except Exception as e:
            print(f"删除通知失败: {str(e)}")
            return False
    
    def _process_queue(self):
        """处理通知队列"""
        while True:
            try:
                # 从队列获取通知
                notification = self.queue.get(timeout=1)
                
                # 发送通知
                self.send_immediate(notification)
                
                # 标记任务完成
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理通知队列失败: {str(e)}")


# 全局通知服务实例
_notification_service = None


def get_notification_service() -> NotificationService:
    """获取全局通知服务实例"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def create_notification(
    recipient_id: str,
    title: str,
    content: str,
    notification_type: NotificationType = NotificationType.SYSTEM,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    channels: List[NotificationChannel] = None,
    data: Dict[str, Any] = None
) -> Notification:
    """创建通知对象"""
    return Notification(
        recipient_id=recipient_id,
        title=title,
        content=content,
        notification_type=notification_type,
        priority=priority,
        channels=channels or [NotificationChannel.IN_APP],
        data=data or {}
    )


def send_notification(
    recipient_id: str,
    title: str,
    content: str,
    notification_type: NotificationType = NotificationType.SYSTEM,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    channels: List[NotificationChannel] = None,
    data: Dict[str, Any] = None
) -> str:
    """发送通知的便捷函数"""
    notification = create_notification(
        recipient_id=recipient_id,
        title=title,
        content=content,
        notification_type=notification_type,
        priority=priority,
        channels=channels,
        data=data
    )
    
    service = get_notification_service()
    return service.send_notification(notification)