"""
缓存模块
提供多种缓存实现，包括内存缓存、Redis缓存等
"""

import json
import time
import hashlib
import pickle
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps
from abc import ABC, abstractmethod
import threading
import os
from datetime import datetime, timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Redis not available, using in-memory cache only")


class CacheBackend(ABC):
    """缓存后端抽象基类"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """清空缓存"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass
    
    @abstractmethod
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的键列表"""
        pass


class MemoryCache(CacheBackend):
    """内存缓存实现"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        初始化内存缓存
        
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认TTL（秒）
        """
        self._cache = {}
        self._expiry_times = {}
        self._access_times = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
    
    def _is_expired(self, key: str) -> bool:
        """检查键是否过期"""
        if key not in self._expiry_times:
            return False
        
        return time.time() > self._expiry_times[key]
    
    def _evict_if_needed(self):
        """如果需要，驱逐最旧的条目"""
        if len(self._cache) <= self._max_size:
            return
        
        # 按访问时间排序，删除最旧的条目
        sorted_keys = sorted(
            self._access_times.items(),
            key=lambda item: item[1]
        )
        
        # 删除最旧的10%条目
        num_to_evict = max(1, int(self._max_size * 0.1))
        for key, _ in sorted_keys[:num_to_evict]:
            if key in self._cache:
                del self._cache[key]
                del self._expiry_times[key]
                del self._access_times[key]
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                return None
            
            if self._is_expired(key):
                self.delete(key)
                return None
            
            # 更新访问时间
            self._access_times[key] = time.time()
            return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        with self._lock:
            self._evict_if_needed()
            
            self._cache[key] = value
            self._access_times[key] = time.time()
            
            if ttl is None:
                ttl = self._default_ttl
            
            if ttl > 0:
                self._expiry_times[key] = time.time() + ttl
            
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._expiry_times:
                    del self._expiry_times[key]
                if key in self._access_times:
                    del self._access_times[key]
                return True
            return False
    
    def clear(self) -> bool:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._expiry_times.clear()
            self._access_times.clear()
            return True
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        with self._lock:
            if key not in self._cache:
                return False
            
            if self._is_expired(key):
                self.delete(key)
                return False
            
            return True
    
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的键列表"""
        import fnmatch
        with self._lock:
            # 过滤掉过期的键
            for key in list(self._cache.keys()):
                if self._is_expired(key):
                    self.delete(key)
            
            return [key for key in self._cache.keys() if fnmatch.fnmatch(key, pattern)]


class RedisCache(CacheBackend):
    """Redis缓存实现"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 db: int = 0, password: Optional[str] = None,
                 default_ttl: int = 3600, key_prefix: str = 'academic_cache:'):
        """
        初始化Redis缓存
        
        Args:
            host: Redis主机
            port: Redis端口
            db: Redis数据库
            password: Redis密码
            default_ttl: 默认TTL（秒）
            key_prefix: 键前缀
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not available. Install with: pip install redis")
        
        self._default_ttl = default_ttl
        self._key_prefix = key_prefix
        self._redis = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password,
            decode_responses=False  # 使用二进制模式，支持pickle
        )
        
        # 测试连接
        try:
            self._redis.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis: {str(e)}")
    
    def _make_key(self, key: str) -> str:
        """添加键前缀"""
        return f"{self._key_prefix}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """序列化值"""
        return pickle.dumps(value)
    
    def _deserialize(self, value: bytes) -> Any:
        """反序列化值"""
        return pickle.loads(value)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            value = self._redis.get(self._make_key(key))
            if value is None:
                return None
            return self._deserialize(value)
        except Exception:
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            serialized = self._serialize(value)
            if ttl is None:
                ttl = self._default_ttl
            
            if ttl > 0:
                return self._redis.setex(self._make_key(key), ttl, serialized)
            else:
                return self._redis.set(self._make_key(key), serialized)
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            return bool(self._redis.delete(self._make_key(key)))
        except Exception:
            return False
    
    def clear(self) -> bool:
        """清空缓存"""
        try:
            keys = self._redis.keys(f"{self._key_prefix}*")
            if keys:
                return bool(self._redis.delete(*keys))
            return True
        except Exception:
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            return bool(self._redis.exists(self._make_key(key)))
        except Exception:
            return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的键列表"""
        try:
            keys = self._redis.keys(f"{self._key_prefix}{pattern}")
            # 移除前缀
            return [key.decode('utf-8').replace(self._key_prefix, '', 1) 
                   for key in keys if isinstance(key, bytes)]
        except Exception:
            return []


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, backend: Optional[CacheBackend] = None):
        """
        初始化缓存管理器
        
        Args:
            backend: 缓存后端，如果为None则使用内存缓存
        """
        if backend is None:
            backend = MemoryCache()
        
        self._backend = backend
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        return self._backend.get(key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        return self._backend.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        return self._backend.delete(key)
    
    def clear(self) -> bool:
        """清空缓存"""
        return self._backend.clear()
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self._backend.exists(key)
    
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的键列表"""
        return self._backend.keys(pattern)
    
    def get_or_set(self, key: str, factory: Callable[[], Any], 
                  ttl: Optional[int] = None) -> Any:
        """
        获取缓存值，如果不存在则通过工厂函数创建
        
        Args:
            key: 缓存键
            factory: 值工厂函数
            ttl: TTL（秒）
            
        Returns:
            缓存值
        """
        value = self.get(key)
        if value is not None:
            return value
        
        value = factory()
        self.set(key, value, ttl)
        return value
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存值"""
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, mapping: Dict[str, Any], 
                ttl: Optional[int] = None) -> bool:
        """批量设置缓存值"""
        success = True
        for key, value in mapping.items():
            if not self.set(key, value, ttl):
                success = False
        return success
    
    def delete_many(self, keys: List[str]) -> bool:
        """批量删除缓存"""
        success = True
        for key in keys:
            if not self.delete(key):
                success = False
        return success


def cache_key(*args, **kwargs) -> str:
    """
    生成缓存键
    
    Args:
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        缓存键字符串
    """
    # 创建一个包含所有参数的字典
    key_dict = {
        'args': args,
        'kwargs': sorted(kwargs.items())  # 排序确保一致性
    }
    
    # 序列化并计算哈希
    serialized = json.dumps(key_dict, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()


def cached(ttl: int = 3600, key_prefix: str = "", 
          key_generator: Optional[Callable] = None,
          cache_manager: Optional[CacheManager] = None):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存TTL（秒）
        key_prefix: 键前缀
        key_generator: 自定义键生成函数
        cache_manager: 缓存管理器
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 使用提供的缓存管理器或默认的
            cm = cache_manager or get_default_cache_manager()
            
            # 生成缓存键
            if key_generator:
                cache_key_value = key_generator(*args, **kwargs)
            else:
                cache_key_value = f"{key_prefix}{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # 尝试从缓存获取
            cached_result = cm.get(cache_key_value)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cm.set(cache_key_value, result, ttl)
            return result
        
        return wrapper
    return decorator


# 全局默认缓存管理器
_default_cache_manager: Optional[CacheManager] = None


def get_default_cache_manager() -> CacheManager:
    """获取默认缓存管理器"""
    global _default_cache_manager
    if _default_cache_manager is None:
        # 尝试使用Redis缓存，如果不可用则使用内存缓存
        try:
            redis_host = os.environ.get('REDIS_HOST', 'localhost')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))
            redis_db = int(os.environ.get('REDIS_DB', 0))
            redis_password = os.environ.get('REDIS_PASSWORD')
            
            backend = RedisCache(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                default_ttl=3600
            )
            _default_cache_manager = CacheManager(backend)
        except (ImportError, ConnectionError):
            _default_cache_manager = CacheManager(MemoryCache())
    
    return _default_cache_manager


def set_default_cache_manager(cache_manager: CacheManager):
    """设置默认缓存管理器"""
    global _default_cache_manager
    _default_cache_manager = cache_manager


# 预定义的缓存键前缀
CACHE_KEYS = {
    'user_profile': 'user_profile:',
    'user_courses': 'user_courses:',
    'course_students': 'course_students:',
    'course_announcements': 'course_announcements:',
    'course_assignments': 'course_assignments:',
    'assignment_submissions': 'assignment_submissions:',
    'student_progress': 'student_progress:',
    'course_stats': 'course_stats:',
    'system_stats': 'system_stats:'
}


# 缓存TTL常量（秒）
CACHE_TTL = {
    'short': 300,      # 5分钟
    'medium': 1800,    # 30分钟
    'long': 3600,      # 1小时
    'very_long': 86400  # 24小时
}