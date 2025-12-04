"""
性能监控模块
提供API性能监控、数据库性能监控和缓存命中率监控功能
"""

import os
import time
import psutil
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from functools import wraps
from flask import request, g

from cache import get_default_cache_manager
from connection_pool import get_pool_manager

# 设置日志
logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_records: int = 1000):
        """
        初始化性能监控器
        
        Args:
            max_records: 最大记录数
        """
        self.max_records = max_records
        
        # API性能记录
        self.api_records = deque(maxlen=max_records)
        
        # 数据库性能记录
        self.db_records = deque(maxlen=max_records)
        
        # 缓存统计
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }
        
        # 系统资源使用记录
        self.system_records = deque(maxlen=max_records)
        
        # 统计信息锁
        self._stats_lock = threading.Lock()
        
        # 启动系统资源监控线程
        self._monitor_thread = threading.Thread(target=self._monitor_system_resources, daemon=True)
        self._monitor_thread.start()
    
    def record_api_call(self, endpoint: str, method: str, status_code: int, 
                       response_time: float, user_id: Optional[int] = None):
        """
        记录API调用
        
        Args:
            endpoint: API端点
            method: HTTP方法
            status_code: 状态码
            response_time: 响应时间(秒)
            user_id: 用户ID
        """
        record = {
            "timestamp": datetime.now(),
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "response_time": response_time,
            "user_id": user_id,
            "ip_address": getattr(request, 'remote_addr', None) if request else None
        }
        
        with self._stats_lock:
            self.api_records.append(record)
    
    def record_db_query(self, query: str, execution_time: float, 
                       success: bool = True, error: Optional[str] = None):
        """
        记录数据库查询
        
        Args:
            query: 查询语句
            execution_time: 执行时间(秒)
            success: 是否成功
            error: 错误信息
        """
        record = {
            "timestamp": datetime.now(),
            "query": query[:200],  # 限制查询长度
            "execution_time": execution_time,
            "success": success,
            "error": error
        }
        
        with self._stats_lock:
            self.db_records.append(record)
    
    def record_cache_hit(self):
        """记录缓存命中"""
        with self._stats_lock:
            self.cache_stats["hits"] += 1
    
    def record_cache_miss(self):
        """记录缓存未命中"""
        with self._stats_lock:
            self.cache_stats["misses"] += 1
    
    def record_cache_set(self):
        """记录缓存设置"""
        with self._stats_lock:
            self.cache_stats["sets"] += 1
    
    def record_cache_delete(self):
        """记录缓存删除"""
        with self._stats_lock:
            self.cache_stats["deletes"] += 1
    
    def record_cache_eviction(self):
        """记录缓存驱逐"""
        with self._stats_lock:
            self.cache_stats["evictions"] += 1
    
    def _monitor_system_resources(self):
        """监控系统资源使用情况"""
        while True:
            try:
                # 获取CPU使用率
                cpu_percent = psutil.cpu_percent(interval=1)
                
                # 获取内存使用情况
                memory = psutil.virtual_memory()
                
                # 获取磁盘使用情况
                disk = psutil.disk_usage('/')
                
                # 获取网络IO
                network = psutil.net_io_counters()
                
                # 获取进程信息
                process = psutil.Process(os.getpid())
                process_memory = process.memory_info()
                
                record = {
                    "timestamp": datetime.now(),
                    "cpu_percent": cpu_percent,
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent,
                        "used": memory.used,
                        "free": memory.free
                    },
                    "disk": {
                        "total": disk.total,
                        "used": disk.used,
                        "free": disk.free,
                        "percent": (disk.used / disk.total) * 100
                    },
                    "network": {
                        "bytes_sent": network.bytes_sent,
                        "bytes_recv": network.bytes_recv,
                        "packets_sent": network.packets_sent,
                        "packets_recv": network.packets_recv
                    },
                    "process": {
                        "pid": process.pid,
                        "memory_rss": process_memory.rss,
                        "memory_vms": process_memory.vms,
                        "cpu_percent": process.cpu_percent(),
                        "num_threads": process.num_threads(),
                        "create_time": process.create_time()
                    }
                }
                
                with self._stats_lock:
                    self.system_records.append(record)
                
                # 每5分钟记录一次
                time.sleep(300)
                
            except Exception as e:
                logger.error(f"监控系统资源时出错: {str(e)}")
                time.sleep(60)  # 出错时等待1分钟再试
    
    def get_api_stats(self, minutes: int = 60) -> Dict:
        """
        获取API统计信息
        
        Args:
            minutes: 统计时间范围(分钟)
            
        Returns:
            API统计信息
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self._stats_lock:
            recent_records = [r for r in self.api_records if r["timestamp"] > cutoff_time]
        
        if not recent_records:
            return {
                "total_requests": 0,
                "avg_response_time": 0,
                "max_response_time": 0,
                "min_response_time": 0,
                "status_codes": {},
                "endpoints": {},
                "methods": {},
                "error_rate": 0
            }
        
        # 计算响应时间统计
        response_times = [r["response_time"] for r in recent_records]
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        # 统计状态码
        status_codes = defaultdict(int)
        for record in recent_records:
            status_codes[record["status_code"]] += 1
        
        # 统计端点
        endpoints = defaultdict(list)
        for record in recent_records:
            endpoints[record["endpoint"]].append(record["response_time"])
        
        endpoint_stats = {}
        for endpoint, times in endpoints.items():
            endpoint_stats[endpoint] = {
                "count": len(times),
                "avg_time": sum(times) / len(times),
                "max_time": max(times),
                "min_time": min(times)
            }
        
        # 统计方法
        methods = defaultdict(int)
        for record in recent_records:
            methods[record["method"]] += 1
        
        # 计算错误率
        error_count = sum(1 for r in recent_records if r["status_code"] >= 400)
        error_rate = error_count / len(recent_records)
        
        return {
            "total_requests": len(recent_records),
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "min_response_time": min_response_time,
            "status_codes": dict(status_codes),
            "endpoints": endpoint_stats,
            "methods": dict(methods),
            "error_rate": error_rate
        }
    
    def get_db_stats(self, minutes: int = 60) -> Dict:
        """
        获取数据库统计信息
        
        Args:
            minutes: 统计时间范围(分钟)
            
        Returns:
            数据库统计信息
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self._stats_lock:
            recent_records = [r for r in self.db_records if r["timestamp"] > cutoff_time]
        
        if not recent_records:
            return {
                "total_queries": 0,
                "avg_execution_time": 0,
                "max_execution_time": 0,
                "min_execution_time": 0,
                "success_rate": 0,
                "error_count": 0,
                "errors": {}
            }
        
        # 计算执行时间统计
        execution_times = [r["execution_time"] for r in recent_records]
        avg_execution_time = sum(execution_times) / len(execution_times)
        max_execution_time = max(execution_times)
        min_execution_time = min(execution_times)
        
        # 统计成功率
        success_count = sum(1 for r in recent_records if r["success"])
        success_rate = success_count / len(recent_records)
        
        # 统计错误
        error_records = [r for r in recent_records if not r["success"]]
        errors = defaultdict(int)
        for record in error_records:
            # 提取错误类型
            error_type = record["error"].split(":")[0] if record["error"] else "Unknown"
            errors[error_type] += 1
        
        return {
            "total_queries": len(recent_records),
            "avg_execution_time": avg_execution_time,
            "max_execution_time": max_execution_time,
            "min_execution_time": min_execution_time,
            "success_rate": success_rate,
            "error_count": len(error_records),
            "errors": dict(errors)
        }
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        with self._stats_lock:
            total_operations = (
                self.cache_stats["hits"] + 
                self.cache_stats["misses"] + 
                self.cache_stats["sets"] + 
                self.cache_stats["deletes"]
            )
            
            hit_rate = (
                self.cache_stats["hits"] / 
                max(self.cache_stats["hits"] + self.cache_stats["misses"], 1)
            )
            
            return {
                "hits": self.cache_stats["hits"],
                "misses": self.cache_stats["misses"],
                "sets": self.cache_stats["sets"],
                "deletes": self.cache_stats["deletes"],
                "evictions": self.cache_stats["evictions"],
                "total_operations": total_operations,
                "hit_rate": hit_rate
            }
    
    def get_system_stats(self) -> Dict:
        """获取系统统计信息"""
        with self._stats_lock:
            if not self.system_records:
                return {}
            
            latest_record = self.system_records[-1]
            
            # 计算最近一小时的系统资源平均值
            cutoff_time = datetime.now() - timedelta(hours=1)
            recent_records = [r for r in self.system_records if r["timestamp"] > cutoff_time]
            
            if recent_records:
                avg_cpu = sum(r["cpu_percent"] for r in recent_records) / len(recent_records)
                avg_memory = sum(r["memory"]["percent"] for r in recent_records) / len(recent_records)
            else:
                avg_cpu = latest_record["cpu_percent"]
                avg_memory = latest_record["memory"]["percent"]
            
            return {
                "current": latest_record,
                "hourly_avg": {
                    "cpu_percent": avg_cpu,
                    "memory_percent": avg_memory
                }
            }
    
    def get_connection_pool_stats(self) -> Dict:
        """获取连接池统计信息"""
        try:
            pool_manager = get_pool_manager()
            return pool_manager.get_pool_status()
        except Exception as e:
            logger.error(f"获取连接池统计信息失败: {str(e)}")
            return {"error": str(e)}
    
    def get_comprehensive_stats(self) -> Dict:
        """获取综合性能统计信息"""
        return {
            "api": self.get_api_stats(),
            "database": self.get_db_stats(),
            "cache": self.get_cache_stats(),
            "system": self.get_system_stats(),
            "connection_pool": self.get_connection_pool_stats()
        }


# 全局性能监控器实例
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def init_performance_monitor(max_records: int = 1000) -> PerformanceMonitor:
    """初始化全局性能监控器"""
    global _performance_monitor
    _performance_monitor = PerformanceMonitor(max_records)
    return _performance_monitor


def monitor_performance(func):
    """
    性能监控装饰器
    
    Args:
        func: 被装饰的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        endpoint = request.endpoint if request else func.__name__
        method = request.method if request else "UNKNOWN"
        user_id = getattr(g, 'user_id', None)
        
        try:
            result = func(*args, **kwargs)
            status_code = getattr(result, 'status_code', 200)
            
            # 记录API调用
            execution_time = time.time() - start_time
            monitor = get_performance_monitor()
            monitor.record_api_call(endpoint, method, status_code, execution_time, user_id)
            
            return result
            
        except Exception as e:
            # 记录错误
            execution_time = time.time() - start_time
            monitor = get_performance_monitor()
            monitor.record_api_call(endpoint, method, 500, execution_time, user_id)
            
            raise
    
    return wrapper


def monitor_db_query(func):
    """
    数据库查询监控装饰器
    
    Args:
        func: 被装饰的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            
            # 记录成功查询
            execution_time = time.time() - start_time
            monitor = get_performance_monitor()
            monitor.record_db_query(str(func.__name__), execution_time, True)
            
            return result
            
        except Exception as e:
            # 记录失败查询
            execution_time = time.time() - start_time
            monitor = get_performance_monitor()
            monitor.record_db_query(str(func.__name__), execution_time, False, str(e))
            
            raise
    
    return wrapper


def record_cache_hit():
    """记录缓存命中"""
    monitor = get_performance_monitor()
    monitor.record_cache_hit()


def record_cache_miss():
    """记录缓存未命中"""
    monitor = get_performance_monitor()
    monitor.record_cache_miss()


def record_cache_set():
    """记录缓存设置"""
    monitor = get_performance_monitor()
    monitor.record_cache_set()


def record_cache_delete():
    """记录缓存删除"""
    monitor = get_performance_monitor()
    monitor.record_cache_delete()


def record_cache_eviction():
    """记录缓存驱逐"""
    monitor = get_performance_monitor()
    monitor.record_cache_eviction()