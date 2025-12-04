import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

# 日志级别枚举
class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

# 审计事件类型枚举
class AuditEventType(Enum):
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_REGISTER = "USER_REGISTER"
    USER_UPDATE = "USER_UPDATE"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    
    COURSE_CREATE = "COURSE_CREATE"
    COURSE_UPDATE = "COURSE_UPDATE"
    COURSE_DELETE = "COURSE_DELETE"
    COURSE_ENROLL = "COURSE_ENROLL"
    COURSE_DROP = "COURSE_DROP"
    
    RESOURCE_UPLOAD = "RESOURCE_UPLOAD"
    RESOURCE_DOWNLOAD = "RESOURCE_DOWNLOAD"
    RESOURCE_UPDATE = "RESOURCE_UPDATE"
    RESOURCE_DELETE = "RESOURCE_DELETE"
    
    ASSIGNMENT_CREATE = "ASSIGNMENT_CREATE"
    ASSIGNMENT_UPDATE = "ASSIGNMENT_UPDATE"
    ASSIGNMENT_DELETE = "ASSIGNMENT_DELETE"
    ASSIGNMENT_SUBMIT = "ASSIGNMENT_SUBMIT"
    ASSIGNMENT_GRADE = "ASSIGNMENT_GRADE"
    
    ANNOUNCEMENT_CREATE = "ANNOUNCEMENT_CREATE"
    ANNOUNCEMENT_UPDATE = "ANNOUNCEMENT_UPDATE"
    ANNOUNCEMENT_DELETE = "ANNOUNCEMENT_DELETE"
    
    GRADE_UPDATE = "GRADE_UPDATE"
    GRADE_VIEW = "GRADE_VIEW"
    
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SECURITY_ALERT = "SECURITY_ALERT"
    DATA_EXPORT = "DATA_EXPORT"
    DATA_IMPORT = "DATA_IMPORT"

class AuditLogger:
    """系统审计日志记录器"""
    
    def __init__(self, log_dir: str = "logs"):
        """
        初始化审计日志记录器
        
        Args:
            log_dir: 日志文件存储目录
        """
        self.log_dir = log_dir
        self._ensure_log_directory()
        self._setup_loggers()
    
    def _ensure_log_directory(self):
        """确保日志目录存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def _setup_loggers(self):
        """设置日志记录器"""
        # 应用日志记录器
        self.app_logger = logging.getLogger('academic_api')
        self.app_logger.setLevel(logging.INFO)
        
        # 审计日志记录器
        self.audit_logger = logging.getLogger('academic_api.audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # 错误日志记录器
        self.error_logger = logging.getLogger('academic_api.error')
        self.error_logger.setLevel(logging.ERROR)
        
        # 安全日志记录器
        self.security_logger = logging.getLogger('academic_api.security')
        self.security_logger.setLevel(logging.WARNING)
        
        # 避免重复添加处理器
        if not self.app_logger.handlers:
            # 应用日志处理器
            app_handler = logging.FileHandler(os.path.join(self.log_dir, 'app.log'))
            app_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.app_logger.addHandler(app_handler)
            
            # 审计日志处理器
            audit_handler = logging.FileHandler(os.path.join(self.log_dir, 'audit.log'))
            audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            self.audit_logger.addHandler(audit_handler)
            
            # 错误日志处理器
            error_handler = logging.FileHandler(os.path.join(self.log_dir, 'error.log'))
            error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.error_logger.addHandler(error_handler)
            
            # 安全日志处理器
            security_handler = logging.FileHandler(os.path.join(self.log_dir, 'security.log'))
            security_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            self.security_logger.addHandler(security_handler)
    
    def log_audit_event(self, event_type: AuditEventType, user_id: str, 
                       details: Dict[str, Any] = None, ip_address: str = None, 
                       user_agent: str = None, success: bool = True):
        """
        记录审计事件
        
        Args:
            event_type: 事件类型
            user_id: 用户ID
            details: 事件详情
            ip_address: IP地址
            user_agent: 用户代理
            success: 操作是否成功
        """
        audit_data = {
            "event_type": event_type.value,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "details": details or {}
        }
        
        # 记录到审计日志
        self.audit_logger.info(json.dumps(audit_data))
        
        # 如果是安全相关事件，同时记录到安全日志
        if event_type in [AuditEventType.SECURITY_ALERT, AuditEventType.USER_LOGIN, 
                         AuditEventType.PASSWORD_CHANGE]:
            self.security_logger.warning(json.dumps(audit_data))
    
    def log_error(self, message: str, error: Exception = None, user_id: str = None, 
                  context: Dict[str, Any] = None):
        """
        记录错误日志
        
        Args:
            message: 错误消息
            error: 异常对象
            user_id: 用户ID
            context: 上下文信息
        """
        error_data = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "context": context or {}
        }
        
        if error:
            error_data["error_type"] = type(error).__name__
            error_data["error_message"] = str(error)
        
        # 记录到错误日志
        self.error_logger.error(json.dumps(error_data))
        
        # 记录审计事件
        self.log_audit_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            user_id=user_id or "system",
            details=error_data
        )
    
    def log_security_event(self, message: str, user_id: str = None, 
                          ip_address: str = None, context: Dict[str, Any] = None):
        """
        记录安全事件
        
        Args:
            message: 安全事件消息
            user_id: 用户ID
            ip_address: IP地址
            context: 上下文信息
        """
        security_data = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "ip_address": ip_address,
            "context": context or {}
        }
        
        # 记录到安全日志
        self.security_logger.warning(json.dumps(security_data))
        
        # 记录审计事件
        self.log_audit_event(
            event_type=AuditEventType.SECURITY_ALERT,
            user_id=user_id or "unknown",
            details=security_data,
            ip_address=ip_address
        )
    
    def get_audit_logs(self, event_type: AuditEventType = None, user_id: str = None,
                      start_date: datetime = None, end_date: datetime = None,
                      page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """
        获取审计日志
        
        Args:
            event_type: 事件类型
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            page: 页码
            per_page: 每页记录数
            
        Returns:
            包含日志列表和分页信息的字典
        """
        try:
            # 读取审计日志文件
            audit_log_path = os.path.join(self.log_dir, 'audit.log')
            if not os.path.exists(audit_log_path):
                return {"success": False, "message": "Audit log file not found"}
            
            # 读取并解析日志
            logs = []
            with open(audit_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        # 分离时间戳和JSON数据
                        parts = line.strip().split(' - ', 1)
                        if len(parts) < 2:
                            continue
                        
                        timestamp_str = parts[0]
                        json_data = parts[1]
                        
                        # 解析JSON
                        log_entry = json.loads(json_data)
                        log_entry['log_timestamp'] = timestamp_str
                        
                        # 应用过滤器
                        if event_type and log_entry.get('event_type') != event_type.value:
                            continue
                        
                        if user_id and log_entry.get('user_id') != user_id:
                            continue
                        
                        if start_date:
                            entry_date = datetime.fromisoformat(log_entry.get('timestamp', ''))
                            if entry_date < start_date:
                                continue
                        
                        if end_date:
                            entry_date = datetime.fromisoformat(log_entry.get('timestamp', ''))
                            if entry_date > end_date:
                                continue
                        
                        logs.append(log_entry)
                    except (json.JSONDecodeError, ValueError):
                        continue
            
            # 按时间戳倒序排序
            logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # 分页
            total = len(logs)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_logs = logs[start_idx:end_idx]
            
            # 计算分页信息
            total_pages = (total + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages
            
            return {
                "success": True,
                "logs": paginated_logs,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                    "has_prev": has_prev,
                    "has_next": has_next
                }
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_user_activity(self, user_id: str, start_date: datetime = None,
                         end_date: datetime = None) -> Dict[str, Any]:
        """
        获取用户活动统计
        
        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            包含用户活动统计的字典
        """
        try:
            # 获取用户审计日志
            result = self.get_audit_logs(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                per_page=1000  # 获取更多记录用于统计
            )
            
            if not result["success"]:
                return result
            
            logs = result["logs"]
            
            # 统计事件类型
            event_counts = {}
            for log in logs:
                event_type = log.get('event_type', 'UNKNOWN')
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            # 统计成功/失败次数
            success_count = sum(1 for log in logs if log.get('success', False))
            failure_count = len(logs) - success_count
            
            # 获取最后活动时间
            last_activity = None
            if logs:
                last_activity = logs[0].get('timestamp')
            
            return {
                "success": True,
                "user_id": user_id,
                "total_activities": len(logs),
                "success_count": success_count,
                "failure_count": failure_count,
                "event_counts": event_counts,
                "last_activity": last_activity,
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_system_stats(self, start_date: datetime = None,
                        end_date: datetime = None) -> Dict[str, Any]:
        """
        获取系统统计信息
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            包含系统统计信息的字典
        """
        try:
            # 获取所有审计日志
            result = self.get_audit_logs(
                start_date=start_date,
                end_date=end_date,
                per_page=10000  # 获取更多记录用于统计
            )
            
            if not result["success"]:
                return result
            
            logs = result["logs"]
            
            # 统计事件类型
            event_counts = {}
            for log in logs:
                event_type = log.get('event_type', 'UNKNOWN')
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            # 统计活跃用户
            active_users = set()
            for log in logs:
                user_id = log.get('user_id')
                if user_id:
                    active_users.add(user_id)
            
            # 统计安全事件
            security_events = [log for log in logs if log.get('event_type') == AuditEventType.SECURITY_ALERT.value]
            
            # 统计错误事件
            error_events = [log for log in logs if log.get('event_type') == AuditEventType.SYSTEM_ERROR.value]
            
            return {
                "success": True,
                "total_events": len(logs),
                "active_users": len(active_users),
                "event_counts": event_counts,
                "security_events": len(security_events),
                "error_events": len(error_events),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

# 全局审计日志记录器实例
audit_logger = AuditLogger()