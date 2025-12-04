"""
通用模块包初始化文件
"""

from .config import ConfigManager, AppConfig, DatabaseConfig, AuthConfig, StorageConfig, RateLimitConfig, CorsConfig, get_config_manager
from .security import SecurityUtils, RateLimiter, require_csrf_token, rate_limit, validate_input
from .database import DatabaseManager, get_db_manager, get_db_manager as get_database_manager, close_db_manager, cache_result, transactional
from .file_handler import FileProcessor, FileMetadata
from .api_utils import APIResponse, APIError, APIException, APIValidator, APIHandler, api_handler, \
    api_endpoint, paginate, cache_response, require_auth, require_roles, log_requests
from .logging_config import LoggerManager, get_logger, setup_logging
from .monitoring import MetricsCollector, SystemMonitor, get_metrics_collector, get_system_monitor, \
    init_monitoring, record_request, record_database_query, record_file_operation, get_metrics_summary
from .base_app import BaseApp

# === 修复 1：添加别名，兼容 require_role (单数) ===
require_role = require_roles

__all__ = [
    # Config
    'ConfigManager', 'AppConfig', 'DatabaseConfig', 'AuthConfig', 'StorageConfig', 
    'RateLimitConfig', 'CorsConfig', 'get_config_manager',
    
    # Security
    'SecurityUtils', 'RateLimiter', 'require_csrf_token', 'rate_limit', 'validate_input',
    
    # Database
    'DatabaseManager', 'get_db_manager', 'get_database_manager', 'close_db_manager', 'cache_result', 'transactional',
    
    # File Handler
    'FileProcessor', 'FileMetadata',
    
    # API Utils
    # === 修复 1：在导出列表中添加 require_role ===
    'APIResponse', 'APIError', 'APIException', 'APIValidator', 'APIHandler', 'api_handler',
    'api_endpoint', 'paginate', 'cache_response', 'require_auth', 'require_roles', 'require_role', 'log_requests',
    
    # Logging
    'LoggerManager', 'get_logger', 'setup_logging',
    
    # Monitoring
    'MetricsCollector', 'SystemMonitor', 'get_metrics_collector', 'get_system_monitor',
    'init_monitoring', 'record_request', 'record_database_query', 'record_file_operation', 
    'get_metrics_summary',
    
    # Base App
    'BaseApp'
]