"""
WebSocket支持模块
用于实时消息推送和双向通信
"""

import json
import time
import uuid
import threading
from typing import Dict, List, Set, Any, Callable, Optional
from datetime import datetime
import logging

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from notifications import get_notification_service, NotificationChannel

logger = logging.getLogger(__name__)

# WebSocket事件类型
class SocketEvent:
    """WebSocket事件类型"""
    CONNECT = 'connect'
    DISCONNECT = 'disconnect'
    JOIN_ROOM = 'join_room'
    LEAVE_ROOM = 'leave_room'
    MESSAGE = 'message'
    NOTIFICATION = 'notification'
    TYPING = 'typing'
    ONLINE_STATUS = 'online_status'
    ERROR = 'error'


class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.active_connections: Dict[str, Dict[str, Any]] = {}  # session_id -> connection_info
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self.rooms: Dict[str, Set[str]] = {}  # room_id -> set of session_ids
        self.message_handlers: Dict[str, Callable] = {}  # event_name -> handler
        self.notification_service = get_notification_service()
        
        # 注册WebSocket提供者
        ws_provider = WebSocketNotificationProvider(self)
        self.notification_service.register_provider(NotificationChannel.WEBSOCKET, ws_provider)
        
        # 注册默认事件处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认事件处理器"""
        self.register_handler(SocketEvent.CONNECT, self._handle_connect)
        self.register_handler(SocketEvent.DISCONNECT, self._handle_disconnect)
        self.register_handler(SocketEvent.JOIN_ROOM, self._handle_join_room)
        self.register_handler(SocketEvent.LEAVE_ROOM, self._handle_leave_room)
        self.register_handler(SocketEvent.MESSAGE, self._handle_message)
        self.register_handler(SocketEvent.TYPING, self._handle_typing)
    
    def register_handler(self, event: str, handler: Callable):
        """注册事件处理器"""
        self.message_handlers[event] = handler
        self.socketio.on(event, handler)
    
    def _handle_connect(self):
        """处理连接事件"""
        session_id = request.sid
        user_id = getattr(request, 'user_id', None)
        
        # 记录连接信息
        self.active_connections[session_id] = {
            'user_id': user_id,
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
            'rooms': set()
        }
        
        # 如果有用户ID，添加到用户连接集合
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(session_id)
            
            # 加入用户专属房间
            join_room(f"user_{user_id}")
            self.active_connections[session_id]['rooms'].add(f"user_{user_id}")
            
            # 更新在线状态
            self._broadcast_online_status(user_id, True)
            
            # 发送未读通知
            self._send_pending_notifications(user_id)
        
        logger.info(f"WebSocket连接建立: {session_id}, 用户: {user_id}")
        
        # 发送连接确认
        emit(SocketEvent.CONNECT, {
            'status': 'connected',
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        })
    
    def _handle_disconnect(self):
        """处理断开连接事件"""
        session_id = request.sid
        connection_info = self.active_connections.get(session_id)
        
        if connection_info:
            user_id = connection_info.get('user_id')
            
            # 离开所有房间
            for room_id in connection_info.get('rooms', set()):
                leave_room(room_id)
                if room_id in self.rooms:
                    self.rooms[room_id].discard(session_id)
                    if not self.rooms[room_id]:
                        del self.rooms[room_id]
            
            # 从用户连接集合中移除
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(session_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
                    # 更新离线状态
                    self._broadcast_online_status(user_id, False)
            
            # 移除连接记录
            del self.active_connections[session_id]
        
        logger.info(f"WebSocket连接断开: {session_id}, 用户: {user_id}")
    
    def _handle_join_room(self, data):
        """处理加入房间事件"""
        session_id = request.sid
        room_id = data.get('room_id')
        
        if not room_id:
            emit(SocketEvent.ERROR, {'message': '房间ID不能为空'})
            return
        
        # 加入房间
        join_room(room_id)
        
        # 更新连接信息
        if session_id in self.active_connections:
            self.active_connections[session_id]['rooms'].add(room_id)
        
        # 记录房间成员
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(session_id)
        
        # 通知房间其他成员
        emit(SocketEvent.MESSAGE, {
            'type': 'user_joined',
            'user_id': self.active_connections[session_id].get('user_id'),
            'timestamp': datetime.now().isoformat()
        }, room=room_id, include_self=False)
        
        # 发送确认
        emit(SocketEvent.JOIN_ROOM, {
            'status': 'success',
            'room_id': room_id,
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"用户 {self.active_connections[session_id].get('user_id')} 加入房间: {room_id}")
    
    def _handle_leave_room(self, data):
        """处理离开房间事件"""
        session_id = request.sid
        room_id = data.get('room_id')
        
        if not room_id:
            emit(SocketEvent.ERROR, {'message': '房间ID不能为空'})
            return
        
        # 离开房间
        leave_room(room_id)
        
        # 更新连接信息
        if session_id in self.active_connections:
            self.active_connections[session_id]['rooms'].discard(room_id)
        
        # 从房间成员中移除
        if room_id in self.rooms:
            self.rooms[room_id].discard(session_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        
        # 通知房间其他成员
        emit(SocketEvent.MESSAGE, {
            'type': 'user_left',
            'user_id': self.active_connections[session_id].get('user_id'),
            'timestamp': datetime.now().isoformat()
        }, room=room_id, include_self=False)
        
        # 发送确认
        emit(SocketEvent.LEAVE_ROOM, {
            'status': 'success',
            'room_id': room_id,
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"用户 {self.active_connections[session_id].get('user_id')} 离开房间: {room_id}")
    
    def _handle_message(self, data):
        """处理消息事件"""
        session_id = request.sid
        connection_info = self.active_connections.get(session_id)
        
        if not connection_info:
            emit(SocketEvent.ERROR, {'message': '未找到连接信息'})
            return
        
        user_id = connection_info.get('user_id')
        room_id = data.get('room_id')
        message = data.get('message')
        
        if not message:
            emit(SocketEvent.ERROR, {'message': '消息内容不能为空'})
            return
        
        # 更新最后活动时间
        connection_info['last_activity'] = datetime.now()
        
        # 创建消息对象
        message_data = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'room_id': room_id,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        # 发送消息
        if room_id:
            # 发送到指定房间
            emit(SocketEvent.MESSAGE, message_data, room=room_id)
        else:
            # 广播到所有连接
            emit(SocketEvent.MESSAGE, message_data, broadcast=True)
        
        logger.info(f"用户 {user_id} 发送消息: {message}")
    
    def _handle_typing(self, data):
        """处理正在输入事件"""
        session_id = request.sid
        connection_info = self.active_connections.get(session_id)
        
        if not connection_info:
            return
        
        user_id = connection_info.get('user_id')
        room_id = data.get('room_id')
        is_typing = data.get('is_typing', False)
        
        # 更新最后活动时间
        connection_info['last_activity'] = datetime.now()
        
        # 发送正在输入状态
        typing_data = {
            'user_id': user_id,
            'is_typing': is_typing,
            'timestamp': datetime.now().isoformat()
        }
        
        if room_id:
            # 发送到指定房间
            emit(SocketEvent.TYPING, typing_data, room=room_id, include_self=False)
        else:
            # 广播到所有连接
            emit(SocketEvent.TYPING, typing_data, broadcast=True)
    
    def _broadcast_online_status(self, user_id: str, is_online: bool):
        """广播用户在线状态"""
        status_data = {
            'user_id': user_id,
            'is_online': is_online,
            'timestamp': datetime.now().isoformat()
        }
        
        # 发送到用户专属房间的好友或相关用户
        # 这里简化处理，实际应该根据好友关系或课程关系发送
        self.socketio.emit(SocketEvent.ONLINE_STATUS, status_data, room=f"user_{user_id}")
    
    def _send_pending_notifications(self, user_id: str):
        """发送待处理的通知"""
        try:
            notifications = self.notification_service.get_user_notifications(
                user_id=user_id,
                limit=10,
                unread_only=True
            )
            
            if notifications.get('notifications'):
                emit(SocketEvent.NOTIFICATION, {
                    'type': 'pending_notifications',
                    'data': notifications['notifications']
                })
        except Exception as e:
            logger.error(f"发送待处理通知失败: {str(e)}")
    
    def send_to_user(self, user_id: str, event: str, data: Any):
        """向特定用户发送消息"""
        self.socketio.emit(event, data, room=f"user_{user_id}")
    
    def send_to_room(self, room_id: str, event: str, data: Any):
        """向特定房间发送消息"""
        self.socketio.emit(event, data, room=room_id)
    
    def broadcast(self, event: str, data: Any):
        """广播消息到所有连接"""
        self.socketio.emit(event, data, broadcast=True)
    
    def get_online_users(self) -> List[str]:
        """获取在线用户列表"""
        return list(self.user_connections.keys())
    
    def is_user_online(self, user_id: str) -> bool:
        """检查用户是否在线"""
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0
    
    def get_user_connections(self, user_id: str) -> List[str]:
        """获取用户的连接ID列表"""
        return list(self.user_connections.get(user_id, set()))
    
    def get_room_members(self, room_id: str) -> List[str]:
        """获取房间成员列表"""
        if room_id not in self.rooms:
            return []
        
        members = []
        for session_id in self.rooms[room_id]:
            if session_id in self.active_connections:
                user_id = self.active_connections[session_id].get('user_id')
                if user_id:
                    members.append(user_id)
        
        return members
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return {
            'total_connections': len(self.active_connections),
            'unique_users': len(self.user_connections),
            'total_rooms': len(self.rooms),
            'online_users': self.get_online_users()
        }


class WebSocketNotificationProvider:
    """WebSocket通知提供者"""
    
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
    
    def send(self, notification) -> bool:
        """发送WebSocket通知"""
        try:
            self.ws_manager.send_to_user(
                user_id=notification.recipient_id,
                event=SocketEvent.NOTIFICATION,
                data={
                    'type': 'notification',
                    'data': notification.to_dict()
                }
            )
            return True
        except Exception as e:
            logger.error(f"WebSocket通知发送失败: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """检查提供者是否可用"""
        return True


# 全局WebSocket管理器实例
_ws_manager = None


def init_websocket(socketio: SocketIO) -> WebSocketManager:
    """初始化WebSocket管理器"""
    global _ws_manager
    _ws_manager = WebSocketManager(socketio)
    return _ws_manager


def get_websocket_manager() -> Optional[WebSocketManager]:
    """获取全局WebSocket管理器实例"""
    return _ws_manager


def send_notification_to_user(user_id: str, notification):
    """向用户发送通知的便捷函数"""
    ws_manager = get_websocket_manager()
    if ws_manager:
        ws_manager.send_to_user(
            user_id=user_id,
            event=SocketEvent.NOTIFICATION,
            data={
                'type': 'notification',
                'data': notification.to_dict()
            }
        )