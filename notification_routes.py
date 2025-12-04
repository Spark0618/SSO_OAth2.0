"""
通知API路由
提供通知的发送、查询和管理功能
"""

from flask import Blueprint, request, jsonify
from functools import wraps
from typing import Dict, Any, List

from notifications import (
    get_notification_service, 
    Notification, 
    NotificationType, 
    NotificationPriority, 
    NotificationChannel,
    send_notification
)
from websocket_support import get_websocket_manager
from validation import require_role
from audit_logger import audit_logger, AuditEventType

# 创建通知蓝图
notification_bp = Blueprint('notifications', __name__, url_prefix='/api/v1/notifications')


def require_auth(f):
    """要求认证的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 这里应该从请求中获取用户认证信息
        # 简化实现，实际应该从认证信息中获取
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({"error": "需要认证"}), 401
        return f(*args, **kwargs)
    return decorated_function


@notification_bp.route('/', methods=['GET'])
@require_auth
def get_notifications():
    """获取用户通知列表"""
    try:
        user_id = getattr(request, 'user_id')
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        unread_only = request.args.get('unread_only', False, type=bool)
        
        # 获取通知服务
        service = get_notification_service()
        
        # 获取通知列表
        result = service.get_user_notifications(
            user_id=user_id,
            limit=limit,
            offset=offset,
            unread_only=unread_only
        )
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=user_id,
            resource="通知列表",
            details=f"获取通知列表，偏移量: {offset}, 限制: {limit}, 仅未读: {unread_only}"
        )
        
        return jsonify({
            "success": True,
            "data": result
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="通知列表",
            details=f"获取通知列表失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/<notification_id>', methods=['GET'])
@require_auth
def get_notification(notification_id):
    """获取特定通知详情"""
    try:
        user_id = getattr(request, 'user_id')
        
        # 获取通知服务
        service = get_notification_service()
        
        # 获取用户所有通知
        notifications = service.get_user_notifications(
            user_id=user_id,
            limit=1000  # 获取足够多的通知
        ).get('notifications', [])
        
        # 查找指定ID的通知
        notification = None
        for n in notifications:
            if n.get('id') == notification_id:
                notification = n
                break
        
        if not notification:
            return jsonify({
                "success": False,
                "error": "通知不存在"
            }), 404
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=user_id,
            resource="通知详情",
            details=f"查看通知详情: {notification_id}"
        )
        
        return jsonify({
            "success": True,
            "data": notification
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="通知详情",
            details=f"获取通知详情失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/<notification_id>/read', methods=['POST'])
@require_auth
def mark_notification_read(notification_id):
    """标记通知为已读"""
    try:
        user_id = getattr(request, 'user_id')
        
        # 获取通知服务
        service = get_notification_service()
        
        # 标记为已读
        success = service.mark_as_read(user_id, notification_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": "通知不存在或已读"
            }), 404
        
        # 记录操作日志
        audit_logger.log_event(
            AuditEventType.UPDATE,
            user_id=user_id,
            resource="通知状态",
            details=f"标记通知为已读: {notification_id}"
        )
        
        return jsonify({
            "success": True,
            "message": "通知已标记为已读"
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="通知状态",
            details=f"标记通知已读失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/read-all', methods=['POST'])
@require_auth
def mark_all_notifications_read():
    """标记所有通知为已读"""
    try:
        user_id = getattr(request, 'user_id')
        
        # 获取通知服务
        service = get_notification_service()
        
        # 标记所有通知为已读
        count = service.mark_all_as_read(user_id)
        
        # 记录操作日志
        audit_logger.log_event(
            AuditEventType.UPDATE,
            user_id=user_id,
            resource="通知状态",
            details=f"标记所有通知为已读，共 {count} 条"
        )
        
        return jsonify({
            "success": True,
            "message": f"已标记 {count} 条通知为已读"
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="通知状态",
            details=f"标记所有通知已读失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/<notification_id>', methods=['DELETE'])
@require_auth
def delete_notification(notification_id):
    """删除通知"""
    try:
        user_id = getattr(request, 'user_id')
        
        # 获取通知服务
        service = get_notification_service()
        
        # 删除通知
        success = service.delete_notification(user_id, notification_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": "通知不存在"
            }), 404
        
        # 记录操作日志
        audit_logger.log_event(
            AuditEventType.DELETE,
            user_id=user_id,
            resource="通知",
            details=f"删除通知: {notification_id}"
        )
        
        return jsonify({
            "success": True,
            "message": "通知已删除"
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="通知",
            details=f"删除通知失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/unread-count', methods=['GET'])
@require_auth
def get_unread_count():
    """获取未读通知数量"""
    try:
        user_id = getattr(request, 'user_id')
        
        # 获取通知服务
        service = get_notification_service()
        
        # 获取未读数量
        count = service.get_unread_count(user_id)
        
        return jsonify({
            "success": True,
            "data": {
                "unread_count": count
            }
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="未读通知数量",
            details=f"获取未读通知数量失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/send', methods=['POST'])
@require_auth
def send_custom_notification():
    """发送自定义通知"""
    try:
        user_id = getattr(request, 'user_id')
        data = request.get_json()
        
        # 验证请求数据
        if not data:
            return jsonify({
                "success": False,
                "error": "请求数据不能为空"
            }), 400
        
        recipient_id = data.get('recipient_id')
        title = data.get('title')
        content = data.get('content')
        
        if not recipient_id or not title or not content:
            return jsonify({
                "success": False,
                "error": "收件人、标题和内容不能为空"
            }), 400
        
        # 解析通知类型
        notification_type_str = data.get('type', 'system')
        try:
            notification_type = NotificationType(notification_type_str)
        except ValueError:
            notification_type = NotificationType.SYSTEM
        
        # 解析优先级
        priority_str = data.get('priority', 'normal')
        try:
            priority = NotificationPriority(priority_str)
        except ValueError:
            priority = NotificationPriority.NORMAL
        
        # 解析渠道
        channels_str = data.get('channels', ['in_app'])
        channels = []
        for channel_str in channels_str:
            try:
                channels.append(NotificationChannel(channel_str))
            except ValueError:
                if channel_str == 'in_app':
                    channels.append(NotificationChannel.IN_APP)
        
        # 获取额外数据
        extra_data = data.get('data', {})
        
        # 发送通知
        notification_id = send_notification(
            recipient_id=recipient_id,
            title=title,
            content=content,
            notification_type=notification_type,
            priority=priority,
            channels=channels,
            data=extra_data
        )
        
        # 记录操作日志
        audit_logger.log_event(
            AuditEventType.CREATE,
            user_id=user_id,
            resource="通知",
            details=f"发送通知给 {recipient_id}: {title}"
        )
        
        return jsonify({
            "success": True,
            "data": {
                "notification_id": notification_id
            }
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="通知",
            details=f"发送通知失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/broadcast', methods=['POST'])
@require_role('admin')
def broadcast_notification():
    """广播通知给所有用户"""
    try:
        user_id = getattr(request, 'user_id')
        data = request.get_json()
        
        # 验证请求数据
        if not data:
            return jsonify({
                "success": False,
                "error": "请求数据不能为空"
            }), 400
        
        title = data.get('title')
        content = data.get('content')
        
        if not title or not content:
            return jsonify({
                "success": False,
                "error": "标题和内容不能为空"
            }), 400
        
        # 解析通知类型
        notification_type_str = data.get('type', 'system')
        try:
            notification_type = NotificationType(notification_type_str)
        except ValueError:
            notification_type = NotificationType.SYSTEM
        
        # 解析优先级
        priority_str = data.get('priority', 'normal')
        try:
            priority = NotificationPriority(priority_str)
        except ValueError:
            priority = NotificationPriority.NORMAL
        
        # 解析渠道
        channels_str = data.get('channels', ['in_app'])
        channels = []
        for channel_str in channels_str:
            try:
                channels.append(NotificationChannel(channel_str))
            except ValueError:
                if channel_str == 'in_app':
                    channels.append(NotificationChannel.IN_APP)
        
        # 获取额外数据
        extra_data = data.get('data', {})
        
        # 这里简化处理，实际应该从数据库获取所有用户ID
        # 为了演示，我们只发送给当前用户
        notification_id = send_notification(
            recipient_id=user_id,
            title=f"[广播] {title}",
            content=content,
            notification_type=notification_type,
            priority=priority,
            channels=channels,
            data=extra_data
        )
        
        # 记录操作日志
        audit_logger.log_event(
            AuditEventType.CREATE,
            user_id=user_id,
            resource="广播通知",
            details=f"发送广播通知: {title}"
        )
        
        return jsonify({
            "success": True,
            "data": {
                "notification_id": notification_id
            }
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="广播通知",
            details=f"发送广播通知失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/types', methods=['GET'])
def get_notification_types():
    """获取通知类型列表"""
    try:
        types = [t.value for t in NotificationType]
        priorities = [p.value for p in NotificationPriority]
        channels = [c.value for c in NotificationChannel]
        
        return jsonify({
            "success": True,
            "data": {
                "types": types,
                "priorities": priorities,
                "channels": channels
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@notification_bp.route('/websocket/status', methods=['GET'])
@require_auth
def get_websocket_status():
    """获取WebSocket连接状态"""
    try:
        user_id = getattr(request, 'user_id')
        
        # 获取WebSocket管理器
        ws_manager = get_websocket_manager()
        if not ws_manager:
            return jsonify({
                "success": False,
                "error": "WebSocket服务未初始化"
            }), 500
        
        # 检查用户是否在线
        is_online = ws_manager.is_user_online(user_id)
        connections = ws_manager.get_user_connections(user_id)
        
        return jsonify({
            "success": True,
            "data": {
                "is_online": is_online,
                "connection_count": len(connections),
                "connections": connections
            }
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id'),
            resource="WebSocket状态",
            details=f"获取WebSocket状态失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def create_notification_blueprint():
    """创建通知蓝图"""
    return notification_bp