"""
数据库连接池管理模块
提供连接池配置、监控和管理功能
"""

import os
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

# 设置日志
logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """数据库连接池管理器"""
    
    def __init__(self, database_url: str, pool_config: Optional[Dict] = None):
        """
        初始化连接池管理器
        
        Args:
            database_url: 数据库连接URL
            pool_config: 连接池配置
        """
        self.database_url = database_url
        self.pool_config = pool_config or self._get_default_pool_config()
        self.engine = None
        self.session_factory = None
        self._setup_engine()
        self._setup_session_factory()
        self._setup_pool_listeners()
        
        # 连接池统计信息
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "overflow_connections": 0,
            "checkout_count": 0,
            "checkin_count": 0,
            "invalid_count": 0,
            "failures": 0,
            "last_reset": time.time()
        }
        
        # 统计信息锁
        self._stats_lock = threading.Lock()
    
    def _get_default_pool_config(self) -> Dict:
        """获取默认连接池配置"""
        return {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
            "pool_pre_ping": os.getenv("DB_POOL_PRE_PING", "true").lower() == "true",
            "echo": os.getenv("DB_ECHO", "false").lower() == "true"
        }
    
    def _setup_engine(self):
        """设置数据库引擎"""
        try:
            # 根据数据库类型设置不同的连接池
            if self.database_url.startswith("sqlite"):
                # SQLite使用StaticPool
                self.engine = create_engine(
                    self.database_url,
                    poolclass=StaticPool,
                    connect_args={
                        "check_same_thread": False,
                        "timeout": self.pool_config.get("pool_timeout", 30)
                    },
                    echo=self.pool_config.get("echo", False)
                )
            else:
                # 其他数据库使用QueuePool
                self.engine = create_engine(
                    self.database_url,
                    poolclass=QueuePool,
                    pool_size=self.pool_config.get("pool_size", 10),
                    max_overflow=self.pool_config.get("max_overflow", 20),
                    pool_timeout=self.pool_config.get("pool_timeout", 30),
                    pool_recycle=self.pool_config.get("pool_recycle", 3600),
                    pool_pre_ping=self.pool_config.get("pool_pre_ping", True),
                    echo=self.pool_config.get("echo", False)
                )
            
            logger.info("数据库引擎初始化成功")
            
        except Exception as e:
            logger.error(f"数据库引擎初始化失败: {str(e)}")
            raise
    
    def _setup_session_factory(self):
        """设置会话工厂"""
        try:
            self.session_factory = sessionmaker(bind=self.engine)
            logger.info("会话工厂初始化成功")
            
        except Exception as e:
            logger.error(f"会话工厂初始化失败: {str(e)}")
            raise
    
    def _setup_pool_listeners(self):
        """设置连接池监听器"""
        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """连接建立时触发"""
            with self._stats_lock:
                self.stats["total_connections"] += 1
                self.stats["checkout_count"] += 1
            
            logger.debug("数据库连接已建立")
        
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """从连接池检出连接时触发"""
            with self._stats_lock:
                self.stats["active_connections"] += 1
                if self.stats["active_connections"] > self.pool_config.get("pool_size", 10):
                    self.stats["overflow_connections"] += 1
            
            logger.debug("从连接池检出连接")
        
        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """连接归还连接池时触发"""
            with self._stats_lock:
                self.stats["active_connections"] -= 1
                self.stats["idle_connections"] += 1
                self.stats["checkin_count"] += 1
            
            logger.debug("连接归还连接池")
        
        @event.listens_for(self.engine, "invalidate")
        def receive_invalidate(dbapi_connection, connection_record, exception):
            """连接失效时触发"""
            with self._stats_lock:
                self.stats["invalid_count"] += 1
                if self.stats["active_connections"] > 0:
                    self.stats["active_connections"] -= 1
            
            logger.warning(f"数据库连接失效: {str(exception)}")
        
        @event.listens_for(self.engine, "engine_connect")
        def receive_engine_connect(branch, connection):
            """引擎连接时触发"""
            if branch:
                # 分支连接
                logger.debug("创建分支连接")
            else:
                # 主连接
                logger.debug("创建主连接")
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        try:
            return self.session_factory()
        except Exception as e:
            with self._stats_lock:
                self.stats["failures"] += 1
            logger.error(f"获取数据库会话失败: {str(e)}")
            raise
    
    @contextmanager
    def session_scope(self):
        """会话作用域上下文管理器"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_pool_status(self) -> Dict:
        """获取连接池状态"""
        pool = self.engine.pool
        
        with self._stats_lock:
            status = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
                "total_connections": self.stats["total_connections"],
                "active_connections": self.stats["active_connections"],
                "idle_connections": self.stats["idle_connections"],
                "overflow_connections": self.stats["overflow_connections"],
                "checkout_count": self.stats["checkout_count"],
                "checkin_count": self.stats["checkin_count"],
                "invalid_count": self.stats["invalid_count"],
                "failures": self.stats["failures"],
                "last_reset": self.stats["last_reset"]
            }
        
        return status
    
    def reset_stats(self):
        """重置统计信息"""
        with self._stats_lock:
            self.stats = {
                "total_connections": 0,
                "active_connections": 0,
                "idle_connections": 0,
                "overflow_connections": 0,
                "checkout_count": 0,
                "checkin_count": 0,
                "invalid_count": 0,
                "failures": 0,
                "last_reset": time.time()
            }
        
        logger.info("连接池统计信息已重置")
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            return False
    
    def close_all_connections(self):
        """关闭所有连接"""
        try:
            self.engine.dispose()
            logger.info("所有数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {str(e)}")
            raise
    
    def health_check(self) -> Dict:
        """连接池健康检查"""
        is_healthy = self.test_connection()
        pool_status = self.get_pool_status()
        
        # 计算健康指标
        pool_size = self.pool_config.get("pool_size", 10)
        max_overflow = self.pool_config.get("max_overflow", 20)
        
        # 连接使用率
        connection_usage = pool_status["checked_out"] / (pool_size + max_overflow)
        
        # 失败率
        total_operations = pool_status["checkout_count"] + pool_status["checkin_count"]
        failure_rate = pool_status["failures"] / max(total_operations, 1)
        
        # 健康状态
        health_status = "healthy"
        if not is_healthy:
            health_status = "unhealthy"
        elif connection_usage > 0.9:
            health_status = "warning"
        elif failure_rate > 0.05:
            health_status = "warning"
        
        return {
            "status": health_status,
            "is_healthy": is_healthy,
            "connection_usage": connection_usage,
            "failure_rate": failure_rate,
            "pool_status": pool_status,
            "config": self.pool_config
        }


# 全局连接池管理器实例
_pool_manager: Optional[ConnectionPoolManager] = None


def get_pool_manager() -> ConnectionPoolManager:
    """获取全局连接池管理器实例"""
    global _pool_manager
    if _pool_manager is None:
        from app import DATABASE_URL
        _pool_manager = ConnectionPoolManager(DATABASE_URL)
    return _pool_manager


def init_pool_manager(database_url: str, pool_config: Optional[Dict] = None) -> ConnectionPoolManager:
    """初始化全局连接池管理器"""
    global _pool_manager
    _pool_manager = ConnectionPoolManager(database_url, pool_config)
    return _pool_manager


@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器"""
    pool_manager = get_pool_manager()
    with pool_manager.session_scope() as session:
        yield session


def get_pool_status() -> Dict:
    """获取连接池状态"""
    pool_manager = get_pool_manager()
    return pool_manager.get_pool_status()


def test_db_connection() -> bool:
    """测试数据库连接"""
    pool_manager = get_pool_manager()
    return pool_manager.test_connection()


def pool_health_check() -> Dict:
    """连接池健康检查"""
    pool_manager = get_pool_manager()
    return pool_manager.health_check()


def reset_pool_stats():
    """重置连接池统计信息"""
    pool_manager = get_pool_manager()
    pool_manager.reset_stats()


def close_all_connections():
    """关闭所有数据库连接"""
    pool_manager = get_pool_manager()
    pool_manager.close_all_connections()