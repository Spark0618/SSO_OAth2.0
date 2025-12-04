"""
系统监控模块
"""

import time
import threading
import psutil
import os
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import json

from .logging_config import get_logger


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class PerformanceMetrics:
    """性能指标"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_connections: int
    request_count: int
    error_count: int
    avg_response_time: float
    timestamp: datetime


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
        self.logger = get_logger(__name__)
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """
        增加计数器
        
        Args:
            name: 指标名称
            value: 增加的值
            tags: 标签
        """
        with self.lock:
            key = self._make_key(name, tags)
            self.counters[key] += value
            
            metric = MetricValue(
                name=name,
                value=self.counters[key],
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[key].append(metric)
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """
        设置仪表盘值
        
        Args:
            name: 指标名称
            value: 值
            tags: 标签
        """
        with self.lock:
            key = self._make_key(name, tags)
            self.gauges[key] = value
            
            metric = MetricValue(
                name=name,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[key].append(metric)
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """
        记录直方图值
        
        Args:
            name: 指标名称
            value: 值
            tags: 标签
        """
        with self.lock:
            key = self._make_key(name, tags)
            self.histograms[key].append(value)
            
            # 限制直方图大小
            if len(self.histograms[key]) > self.max_history:
                self.histograms[key] = self.histograms[key][-self.max_history:]
            
            metric = MetricValue(
                name=name,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[key].append(metric)
    
    def get_metric(self, name: str, tags: Dict[str, str] = None) -> Optional[MetricValue]:
        """
        获取最新的指标值
        
        Args:
            name: 指标名称
            tags: 标签
            
        Returns:
            最新的指标值
        """
        with self.lock:
            key = self._make_key(name, tags)
            if key in self.metrics and self.metrics[key]:
                return self.metrics[key][-1]
            return None
    
    def get_metrics_history(self, name: str, tags: Dict[str, str] = None, 
                           since: Optional[datetime] = None) -> List[MetricValue]:
        """
        获取指标历史
        
        Args:
            name: 指标名称
            tags: 标签
            since: 起始时间
            
        Returns:
            指标历史列表
        """
        with self.lock:
            key = self._make_key(name, tags)
            if key not in self.metrics:
                return []
            
            if since is None:
                return list(self.metrics[key])
            
            return [m for m in self.metrics[key] if m.timestamp >= since]
    
    def get_counter_value(self, name: str, tags: Dict[str, str] = None) -> float:
        """
        获取计数器值
        
        Args:
            name: 指标名称
            tags: 标签
            
        Returns:
            计数器值
        """
        with self.lock:
            key = self._make_key(name, tags)
            return self.counters.get(key, 0.0)
    
    def get_gauge_value(self, name: str, tags: Dict[str, str] = None) -> float:
        """
        获取仪表盘值
        
        Args:
            name: 指标名称
            tags: 标签
            
        Returns:
            仪表盘值
        """
        with self.lock:
            key = self._make_key(name, tags)
            return self.gauges.get(key, 0.0)
    
    def get_histogram_stats(self, name: str, tags: Dict[str, str] = None) -> Dict[str, float]:
        """
        获取直方图统计
        
        Args:
            name: 指标名称
            tags: 标签
            
        Returns:
            统计信息
        """
        with self.lock:
            key = self._make_key(name, tags)
            values = self.histograms.get(key, [])
            
            if not values:
                return {}
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return {
                "count": count,
                "sum": sum(sorted_values),
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "mean": sum(sorted_values) / count,
                "p50": sorted_values[int(count * 0.5)],
                "p95": sorted_values[int(count * 0.95)],
                "p99": sorted_values[int(count * 0.99)]
            }
    
    def reset_metrics(self):
        """重置所有指标"""
        with self.lock:
            self.metrics.clear()
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()
    
    def _make_key(self, name: str, tags: Dict[str, str] = None) -> str:
        """
        创建指标键
        
        Args:
            name: 指标名称
            tags: 标签
            
        Returns:
            指标键
        """
        if not tags:
            return name
        
        tag_str = ",".join([f"{k}={v}" for k, v in sorted(tags.items())])
        return f"{name}{{{tag_str}}}"


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, collector: MetricsCollector, interval: int = 30):
        self.collector = collector
        self.interval = interval
        self.running = False
        self.thread = None
        self.logger = get_logger(__name__)
        self.process = psutil.Process(os.getpid())
    
    def start(self):
        """启动监控"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"System monitor started with interval {self.interval}s")
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        self.logger.info("System monitor stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                self._collect_system_metrics()
                time.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"Error in system monitor: {e}", exc_info=True)
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        self.collector.set_gauge("system.cpu.percent", cpu_percent)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        self.collector.set_gauge("system.memory.percent", memory.percent)
        self.collector.set_gauge("system.memory.used_mb", memory.used / (1024 * 1024))
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        self.collector.set_gauge("system.disk.percent", disk.percent)
        
        # 进程特定指标
        process_memory = self.process.memory_info()
        self.collector.set_gauge("process.memory.rss_mb", process_memory.rss / (1024 * 1024))
        self.collector.set_gauge("process.cpu.percent", self.process.cpu_percent())
        self.collector.set_gauge("process.threads", self.process.num_threads())
        
        # 网络连接数
        try:
            connections = len(self.process.connections())
            self.collector.set_gauge("process.connections", connections)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """
        获取性能指标
        
        Returns:
            性能指标对象
        """
        return PerformanceMetrics(
            cpu_percent=self.collector.get_gauge_value("system.cpu.percent"),
            memory_percent=self.collector.get_gauge_value("system.memory.percent"),
            memory_used_mb=self.collector.get_gauge_value("system.memory.used_mb"),
            disk_usage_percent=self.collector.get_gauge_value("system.disk.percent"),
            active_connections=int(self.collector.get_gauge_value("process.connections")),
            request_count=int(self.collector.get_counter_value("http.requests.total")),
            error_count=int(self.collector.get_counter_value("http.errors.total")),
            avg_response_time=self.collector.get_histogram_stats("http.request.duration").get("mean", 0),
            timestamp=datetime.now()
        )


# 全局指标收集器
_metrics_collector = MetricsCollector()
_system_monitor = SystemMonitor(_metrics_collector)


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    return _metrics_collector


def get_system_monitor() -> SystemMonitor:
    """获取全局系统监控器"""
    return _system_monitor


def init_monitoring(interval: int = 30):
    """
    初始化监控系统
    
    Args:
        interval: 监控间隔(秒)
    """
    global _system_monitor
    _system_monitor = SystemMonitor(_metrics_collector, interval)
    _system_monitor.start()


def record_request(method: str, path: str, status_code: int, duration: float):
    """
    记录HTTP请求指标
    
    Args:
        method: HTTP方法
        path: 请求路径
        status_code: 响应状态码
        duration: 请求处理时间(秒)
    """
    tags = {
        "method": method,
        "path": path,
        "status": str(status_code)
    }
    
    _metrics_collector.increment_counter("http.requests.total", tags=tags)
    _metrics_collector.record_histogram("http.request.duration", duration, tags=tags)
    
    if status_code >= 400:
        _metrics_collector.increment_counter("http.errors.total", tags=tags)


def record_database_query(query: str, duration: float, error: bool = False):
    """
    记录数据库查询指标
    
    Args:
        query: 查询类型
        duration: 查询时间(秒)
        error: 是否出错
    """
    tags = {
        "query": query,
        "error": str(error)
    }
    
    _metrics_collector.increment_counter("db.queries.total", tags=tags)
    _metrics_collector.record_histogram("db.query.duration", duration, tags=tags)
    
    if error:
        _metrics_collector.increment_counter("db.errors.total", tags=tags)


def record_file_operation(operation: str, file_type: str, size: float, duration: float):
    """
    记录文件操作指标
    
    Args:
        operation: 操作类型
        file_type: 文件类型
        size: 文件大小(字节)
        duration: 操作时间(秒)
    """
    tags = {
        "operation": operation,
        "type": file_type
    }
    
    _metrics_collector.increment_counter("file.operations.total", tags=tags)
    _metrics_collector.record_histogram("file.operation.duration", duration, tags=tags)
    _metrics_collector.record_histogram("file.operation.size", size, tags=tags)


def get_metrics_summary() -> Dict[str, Any]:
    """
    获取指标摘要
    
    Returns:
        指标摘要
    """
    performance = _system_monitor.get_performance_metrics()
    
    return {
        "performance": asdict(performance),
        "http_requests": {
            "total": _metrics_collector.get_counter_value("http.requests.total"),
            "errors": _metrics_collector.get_counter_value("http.errors.total"),
            "avg_response_time": _metrics_collector.get_histogram_stats("http.request.duration").get("mean", 0)
        },
        "database": {
            "queries": _metrics_collector.get_counter_value("db.queries.total"),
            "errors": _metrics_collector.get_counter_value("db.errors.total"),
            "avg_query_time": _metrics_collector.get_histogram_stats("db.query.duration").get("mean", 0)
        },
        "files": {
            "operations": _metrics_collector.get_counter_value("file.operations.total"),
            "avg_operation_time": _metrics_collector.get_histogram_stats("file.operation.duration").get("mean", 0),
            "avg_file_size": _metrics_collector.get_histogram_stats("file.operation.size").get("mean", 0)
        }
    }