"""
数据库工具模块，提供优化的数据库操作
(修复版：适配 SQLAlchemy 2.0，修复 execute_query 字典转换错误)
"""
import os
import time
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import contextmanager
from functools import wraps
from sqlalchemy import create_engine, text, event, pool
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
import redis
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QueryStats:
    """查询统计信息"""
    query: str
    execution_time: float
    rows_affected: int
    timestamp: float

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url: str, pool_size: int = 10, 
                 max_overflow: int = 20, pool_timeout: int = 30, 
                 pool_recycle: int = 3600, echo: bool = False,
                 redis_url: Optional[str] = None):
        """
        初始化数据库管理器
        """
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.echo = echo
        self.redis_url = redis_url
        
        # 初始化数据库引擎
        self.engine = self._create_engine()
        
        # 初始化会话工厂
        self.Session = scoped_session(
            sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        )
        
        # 初始化Redis连接（如果提供）
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()  # 测试连接
                logger.info("Connected to Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                self.redis_client = None
        
        # 查询统计
        self.query_stats = []
        self.slow_query_threshold = 1.0  # 慢查询阈值（秒）
    
    def _create_engine(self):
        """创建数据库引擎"""
        # 创建连接池
        engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,  # 连接前检查连接是否有效
            echo=self.echo
        )
        
        # 添加事件监听器
        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - context._query_start_time
            
            # 记录查询统计
            stats = QueryStats(
                query=statement,
                execution_time=total,
                rows_affected=cursor.rowcount,
                timestamp=time.time()
            )
            
            self.query_stats.append(stats)
            
            # 记录慢查询
            if total > self.slow_query_threshold:
                logger.warning(f"Slow query detected: {total:.3f}s - {statement[:100]}...")
            
            # 限制查询统计数量
            if len(self.query_stats) > 1000:
                self.query_stats = self.query_stats[-500:]
        
        return engine
    
    @contextmanager
    def get_session(self):
        """获取数据库会话的上下文管理器"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            self.Session.remove()
    
    # === 关键修复：使用 mappings() 处理结果集 ===
    def execute_query(self, query: str, params: Dict[str, Any] = None, 
                      fetch_one: bool = False, fetch_all: bool = True) -> Union[Dict, List[Dict], None]:
        """
        执行查询
        """
        with self.get_session() as session:
            try:
                # 注意这里的 .mappings()，这是 SQLAlchemy 2.0 获取字典的关键
                result = session.execute(text(query), params or {}).mappings()
                
                if fetch_one:
                    row = result.fetchone()
                    return dict(row) if row else None
                elif fetch_all:
                    rows = result.fetchall()
                    return [dict(row) for row in rows]
                else:
                    return None
            except SQLAlchemyError as e:
                logger.error(f"Query execution error: {e}")
                raise
    
    def execute_update(self, query: str, params: Dict[str, Any] = None) -> int:
        """
        执行更新操作
        """
        with self.get_session() as session:
            try:
                result = session.execute(text(query), params or {})
                return result.rowcount
            except SQLAlchemyError as e:
                logger.error(f"Update execution error: {e}")
                raise
    
    def execute_batch(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """
        批量执行操作
        """
        with self.get_session() as session:
            try:
                result = session.execute(text(query), params_list)
                return result.rowcount
            except SQLAlchemyError as e:
                logger.error(f"Batch execution error: {e}")
                raise
    
    # ... (后续缓存方法保持不变，为了完整性我这里全部列出) ...
    def get_cache(self, key: str, default: Any = None) -> Any:
        if not self.redis_client:
            return default
        try:
            data = self.redis_client.get(key)
            if data is not None:
                return data.decode('utf-8')
            return default
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return default
    
    def set_cache(self, key: str, value: Any, expire: int = 3600) -> bool:
        if not self.redis_client:
            return False
        try:
            return self.redis_client.setex(key, expire, value)
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete_cache(self, key: str) -> bool:
        if not self.redis_client:
            return False
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear_cache(self, pattern: str = "*") -> int:
        if not self.redis_client:
            return 0
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
            
    def get_query_stats(self, limit: int = 100) -> List[Dict[str, Any]]:
        stats = self.query_stats[-limit:] if self.query_stats else []
        return [
            {
                'query': stat.query,
                'execution_time': stat.execution_time,
                'rows_affected': stat.rows_affected,
                'timestamp': stat.timestamp
            }
            for stat in stats
        ]
        
    def get_slow_queries(self, limit: int = 50) -> List[Dict[str, Any]]:
        slow_queries = [
            stat for stat in self.query_stats 
            if stat.execution_time > self.slow_query_threshold
        ]
        slow_queries.sort(key=lambda x: x.execution_time, reverse=True)
        return [
            {
                'query': stat.query,
                'execution_time': stat.execution_time,
                'rows_affected': stat.rows_affected,
                'timestamp': stat.timestamp
            }
            for stat in slow_queries[:limit]
        ]

    def get_connection_pool_status(self) -> Dict[str, Any]:
        pool = self.engine.pool
        return {
            'pool_size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': pool.invalid()
        }

    def close(self):
        self.engine.dispose()
        if self.redis_client:
            self.redis_client.close()

def cache_result(expire: int = 3600, key_prefix: str = "", key_func: Optional[callable] = None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 简化版实现，防止循环引用
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def transactional(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        db_manager = getattr(f, '__self__', None)
        if not db_manager or not hasattr(db_manager, 'get_session'):
            return f(*args, **kwargs)
        with db_manager.get_session() as session:
            try:
                return f(session, *args, **kwargs)
            except Exception as e:
                logger.error(f"Transaction error: {e}")
                raise
    return decorated_function

# 全局数据库管理器实例
_db_manager = None

def get_db_manager(database_url: str, **kwargs) -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(database_url, **kwargs)
    return _db_manager

def close_db_manager():
    global _db_manager
    if _db_manager is not None:
        _db_manager.close()
        _db_manager = None