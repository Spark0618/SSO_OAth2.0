"""
日志配置模块
(修复版：适配 BaseApp 的参数调用)
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

class LoggerManager:
    """日志管理器"""
    
    _loggers: Dict[str, logging.Logger] = {}
    _configured = False
    
    @classmethod
    def setup_logging(cls, app_name: str, log_file: Optional[str] = None, level: str = "INFO"):
        """
        设置日志配置
        
        Args:
            app_name: 应用名称
            log_file: 日志文件路径
            level: 日志级别
        """
        # 即使配置过，如果有新的 app_name 进来，最好也重新配置一下或者是独立的
        # 这里为了简单，我们重新配置根 logger
        
        # 创建日志目录
        if log_file:
            log_path = Path(log_file)
            log_dir = log_path.parent
            log_dir.mkdir(parents=True, exist_ok=True)
        else:
            # 默认目录
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            log_file = str(log_dir / f"{app_name}.log")
        
        # 设置根日志级别
        root_logger = logging.getLogger()
        log_level_val = getattr(logging, level.upper(), logging.INFO)
        root_logger.setLevel(log_level_val)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 1. 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level_val)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 2. 创建文件处理器
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level_val)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Failed to setup file logging: {e}")

        cls._configured = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """获取日志记录器"""
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        return cls._loggers[name]
    
    @classmethod
    def log_request(cls, logger: logging.Logger, method: str, path: str, 
                    status_code: int, duration: float, user_id: Optional[str] = None):
        """记录API请求"""
        user_info = f" [User: {user_id}]" if user_id else ""
        
        msg = f"{method} {path} - {status_code} - {duration:.3f}s{user_info}"
        
        if status_code >= 500:
            logger.error(msg)
        elif status_code >= 400:
            logger.warning(msg)
        else:
            logger.info(msg)

# === 关键适配函数：必须保留这些参数签名 ===
def setup_logging(app_name: str, log_file: Optional[str] = None, level: str = "INFO"):
    """
    设置日志配置的便捷函数 (适配 BaseApp)
    """
    LoggerManager.setup_logging(app_name, log_file, level)

def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return LoggerManager.get_logger(name)