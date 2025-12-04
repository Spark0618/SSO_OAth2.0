"""
性能监控API端点
提供性能统计和监控数据的访问接口
"""

from flask import Blueprint, jsonify, request
from functools import wraps

from performance_monitor import get_performance_monitor
from validation import require_role
from audit_logger import audit_logger, AuditEventType

# 创建性能监控蓝图
performance_bp = Blueprint('performance', __name__, url_prefix='/api/v1/performance')


def require_admin_role(f):
    """要求管理员角色的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 这里应该从请求中获取用户角色信息
        # 简化实现，实际应该从认证信息中获取
        user_role = getattr(request, 'user_role', None)
        if user_role != 'admin':
            return jsonify({"error": "需要管理员权限"}), 403
        return f(*args, **kwargs)
    return decorated_function


@performance_bp.route('/stats', methods=['GET'])
@require_admin_role
def get_performance_stats():
    """获取综合性能统计信息"""
    try:
        monitor = get_performance_monitor()
        stats = monitor.get_comprehensive_stats()
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=getattr(request, 'user_id', None),
            resource="性能统计信息",
            details="访问综合性能统计信息"
        )
        
        return jsonify({
            "success": True,
            "data": stats
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id', None),
            resource="性能统计信息",
            details=f"获取性能统计信息失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@performance_bp.route('/api', methods=['GET'])
@require_admin_role
def get_api_stats():
    """获取API性能统计信息"""
    try:
        minutes = request.args.get('minutes', 60, type=int)
        monitor = get_performance_monitor()
        stats = monitor.get_api_stats(minutes)
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=getattr(request, 'user_id', None),
            resource="API性能统计",
            details=f"获取最近{minutes}分钟的API性能统计"
        )
        
        return jsonify({
            "success": True,
            "data": stats,
            "minutes": minutes
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id', None),
            resource="API性能统计",
            details=f"获取API性能统计失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@performance_bp.route('/database', methods=['GET'])
@require_admin_role
def get_database_stats():
    """获取数据库性能统计信息"""
    try:
        minutes = request.args.get('minutes', 60, type=int)
        monitor = get_performance_monitor()
        stats = monitor.get_db_stats(minutes)
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=getattr(request, 'user_id', None),
            resource="数据库性能统计",
            details=f"获取最近{minutes}分钟的数据库性能统计"
        )
        
        return jsonify({
            "success": True,
            "data": stats,
            "minutes": minutes
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id', None),
            resource="数据库性能统计",
            details=f"获取数据库性能统计失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@performance_bp.route('/cache', methods=['GET'])
@require_admin_role
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        monitor = get_performance_monitor()
        stats = monitor.get_cache_stats()
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=getattr(request, 'user_id', None),
            resource="缓存统计",
            details="获取缓存统计信息"
        )
        
        return jsonify({
            "success": True,
            "data": stats
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id', None),
            resource="缓存统计",
            details=f"获取缓存统计失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@performance_bp.route('/system', methods=['GET'])
@require_admin_role
def get_system_stats():
    """获取系统资源统计信息"""
    try:
        monitor = get_performance_monitor()
        stats = monitor.get_system_stats()
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=getattr(request, 'user_id', None),
            resource="系统资源统计",
            details="获取系统资源统计信息"
        )
        
        return jsonify({
            "success": True,
            "data": stats
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id', None),
            resource="系统资源统计",
            details=f"获取系统资源统计失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@performance_bp.route('/connection-pool', methods=['GET'])
@require_admin_role
def get_connection_pool_stats():
    """获取连接池统计信息"""
    try:
        monitor = get_performance_monitor()
        stats = monitor.get_connection_pool_stats()
        
        # 记录访问日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=getattr(request, 'user_id', None),
            resource="连接池统计",
            details="获取连接池统计信息"
        )
        
        return jsonify({
            "success": True,
            "data": stats
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id', None),
            resource="连接池统计",
            details=f"获取连接池统计失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@performance_bp.route('/health', methods=['GET'])
def get_health_status():
    """获取系统健康状态"""
    try:
        monitor = get_performance_monitor()
        
        # 获取各项统计信息
        api_stats = monitor.get_api_stats(5)  # 最近5分钟
        db_stats = monitor.get_db_stats(5)     # 最近5分钟
        cache_stats = monitor.get_cache_stats()
        system_stats = monitor.get_system_stats()
        pool_stats = monitor.get_connection_pool_stats()
        
        # 计算健康状态
        health_status = "healthy"
        issues = []
        
        # 检查API错误率
        if api_stats.get("error_rate", 0) > 0.1:  # 错误率超过10%
            health_status = "warning"
            issues.append(f"API错误率过高: {api_stats['error_rate']:.2%}")
        
        # 检查数据库成功率
        if db_stats.get("success_rate", 1) < 0.95:  # 成功率低于95%
            health_status = "warning"
            issues.append(f"数据库成功率过低: {db_stats['success_rate']:.2%}")
        
        # 检查缓存命中率
        if cache_stats.get("hit_rate", 0) < 0.5:  # 命中率低于50%
            health_status = "warning"
            issues.append(f"缓存命中率过低: {cache_stats['hit_rate']:.2%}")
        
        # 检查系统资源
        if system_stats.get("current", {}).get("memory", {}).get("percent", 0) > 90:  # 内存使用率超过90%
            health_status = "critical"
            issues.append(f"内存使用率过高: {system_stats['current']['memory']['percent']:.2%}")
        
        # 检查连接池状态
        if isinstance(pool_stats, dict) and "status" in pool_stats:
            if pool_stats["status"] == "unhealthy":
                health_status = "critical"
                issues.append("数据库连接池状态不健康")
            elif pool_stats["status"] == "warning" and health_status == "healthy":
                health_status = "warning"
                issues.append("数据库连接池状态警告")
        
        # 记录健康检查日志
        audit_logger.log_event(
            AuditEventType.ACCESS,
            user_id=getattr(request, 'user_id', None),
            resource="系统健康状态",
            details=f"系统健康状态: {health_status}"
        )
        
        return jsonify({
            "success": True,
            "status": health_status,
            "issues": issues,
            "timestamp": monitor.system_records[-1]["timestamp"].isoformat() if monitor.system_records else None
        })
    except Exception as e:
        audit_logger.log_event(
            AuditEventType.ERROR,
            user_id=getattr(request, 'user_id', None),
            resource="系统健康状态",
            details=f"获取系统健康状态失败: {str(e)}"
        )
        return jsonify({
            "success": False,
            "status": "unknown",
            "error": str(e)
        }), 500


def create_performance_blueprint():
    """创建性能监控蓝图"""
    return performance_bp