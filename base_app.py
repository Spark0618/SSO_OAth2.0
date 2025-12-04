"""
应用基础类
(修复版：解决了 create_tables 报错和 NoneType 配置报错)
"""

import os
import time
import atexit
from typing import Optional, Dict, Any, Callable
from functools import wraps
from flask import Flask, request, g, jsonify, current_app
from flask_cors import CORS

# 引入 RateLimiter 类以便正确实现全局限流
from . import ConfigManager, SecurityUtils, DatabaseManager, FileProcessor, \
    LoggerManager, get_logger, setup_logging, init_monitoring, record_request, \
    get_metrics_collector, get_system_monitor, APIResponse, APIError, \
    RateLimiter, close_db_manager

class BaseApp:
    """应用基础类"""
    
    def __init__(self, app_name: str, config_path: Optional[str] = None):
        """
        初始化应用
        """
        self.app_name = app_name
        self.config = None
        self.db_manager = None
        self.file_processor = None
        self.logger = None
        self.app = None
        self.config_path = config_path or "config.json"
        
        # 初始化应用流程
        self._init_config()
        self._init_app()
        self._init_logging()
        self._init_security()
        self._init_database()
        self._init_file_processor()
        self._init_monitoring()
        self._init_cors()
        self._init_error_handlers()
        self._init_request_handlers()

        # 注册退出清理
        atexit.register(self.shutdown)
    
    def _init_config(self):
        """初始化配置"""
        # 使用 ConfigManager.load_config (我们刚刚修复的方法)
        self.config = ConfigManager.load_config(self.app_name, self.config_path)
    
    def _init_app(self):
        """初始化Flask应用"""
        self.app = Flask(self.app_name)
        
        # 确保 auth 配置存在
        jwt_secret = "default-secret"
        if self.config.auth and self.config.auth.jwt_secret:
            jwt_secret = self.config.auth.jwt_secret

        self.app.config.update({
            'SECRET_KEY': jwt_secret,
            'DEBUG': self.config.debug,
            'JSON_SORT_KEYS': False
        })
    
    def _init_logging(self):
        """初始化日志"""
        log_level = "DEBUG" if self.config.debug else "INFO"
        
        # 确保日志目录存在
        if not os.path.exists("logs"):
            os.makedirs("logs")

        setup_logging(
            app_name=self.app_name, 
            log_file=f"logs/{self.app_name}.log",
            level=log_level
        )
        self.logger = get_logger(self.app_name)
        self.logger.info(f"Application {self.app_name} initialized")
    
    def _init_security(self):
        """初始化安全配置"""
        if self.config.auth and self.config.auth.jwt_secret:
            # 调用我们刚刚在 SecurityUtils 中添加的方法
            SecurityUtils.set_jwt_secret(self.config.auth.jwt_secret)
            self.logger.info("Security configuration initialized")
    
    def _init_database(self):
        """初始化数据库 (关键修复)"""
        # 1. 检查配置是否存在 (Cloud API 可能没有数据库配置)
        if not self.config.database or not self.config.database.url:
            self.logger.info("No database configuration found. Skipping database initialization.")
            return

        try:
            # 2. 初始化管理器 (不调用 create_tables)
            self.db_manager = DatabaseManager(
                self.config.database.url,
                pool_size=self.config.database.pool_size,
                max_overflow=self.config.database.max_overflow,
                pool_timeout=self.config.database.pool_timeout,
                pool_recycle=self.config.database.pool_recycle
            )
            self.logger.info(f"Database initialized for {self.app_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            # 视情况决定是否抛出异常，这里抛出以便发现错误
            raise e
    
    def _init_file_processor(self):
        """初始化文件处理器"""
        if hasattr(self.config, 'storage') and self.config.storage:
            self.file_processor = FileProcessor(
                storage_type=self.config.storage.type,
                upload_folder=self.config.storage.upload_folder,
                max_content_length=self.config.storage.max_content_length,
                allowed_extensions=self.config.storage.allowed_extensions
            )
            self.logger.info("File processor initialized")
    
    def _init_monitoring(self):
        """初始化监控"""
        init_monitoring(interval=30)
        self.logger.info("Monitoring initialized")
    
    def _init_cors(self):
        """初始化CORS"""
        if hasattr(self.config, 'cors') and self.config.cors:
            CORS(self.app, 
                 origins=self.config.cors.allowed_origins,
                 methods=self.config.cors.allowed_methods,
                 allow_headers=self.config.cors.allowed_headers,
                 supports_credentials=self.config.cors.supports_credentials)
            self.logger.info("CORS initialized")
    
    def _init_error_handlers(self):
        """初始化错误处理器"""
        @self.app.errorhandler(400)
        def bad_request(error):
            return jsonify(APIResponse.error("Bad request", 400)), 400
        
        @self.app.errorhandler(401)
        def unauthorized(error):
            return jsonify(APIResponse.error("Unauthorized", 401)), 401
        
        @self.app.errorhandler(403)
        def forbidden(error):
            return jsonify(APIResponse.error("Forbidden", 403)), 403
        
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify(APIResponse.error("Not found", 404)), 404
        
        @self.app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify(APIResponse.error("Method not allowed", 405)), 405
        
        @self.app.errorhandler(500)
        def internal_error(error):
            self.logger.error(f"Internal server error: {error}", exc_info=True)
            return jsonify(APIResponse.error("Internal server error", 500)), 500
        
        self.logger.info("Error handlers initialized")
    
    def _init_request_handlers(self):
        """初始化请求处理器"""
        @self.app.before_request
        def before_request():
            g.start_time = time.time()
            # 简单的请求ID生成
            g.request_id = str(time.time())
        
        @self.app.after_request
        def after_request(response):
            if hasattr(g, 'start_time'):
                duration = time.time() - g.start_time
                
                # 记录请求指标
                record_request(
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    duration=duration
                )
                
                # 记录日志
                if self.logger:
                    self.logger.info(
                        f"{request.method} {request.path} {response.status_code} {duration:.4f}s"
                    )
            
            return response
        
        self.logger.info("Request handlers initialized")
    
    def add_route(self, rule: str, endpoint: Optional[str] = None, 
                  view_func: Callable = None, **options):
        """添加路由"""
        self.app.add_url_rule(rule, endpoint, view_func, **options)
    
    def register_blueprint(self, blueprint, **options):
        """注册蓝图"""
        self.app.register_blueprint(blueprint, **options)
    
    def run(self, host: Optional[str] = None, port: Optional[int] = None, 
            debug: Optional[bool] = None, ssl_context: Optional[tuple] = None):
        """运行应用"""
        host = host or self.config.host
        port = port or self.config.port
        debug = debug if debug is not None else self.config.debug
        
        # SSL 配置处理
        if ssl_context is None and hasattr(self.config, 'ssl_enabled') and self.config.ssl_enabled:
            cert_path = getattr(self.config, 'cert_path', None)
            key_path = getattr(self.config, 'key_path', None)
            
            if cert_path and key_path and os.path.exists(cert_path) and os.path.exists(key_path):
                ssl_context = (cert_path, key_path)
                self.logger.info(f"Running with SSL: {cert_path}, {key_path}")
        
        self.logger.info(f"Starting {self.app_name} on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)
    
    def get_app(self) -> Flask:
        return self.app
    
    def get_config(self):
        return self.config
    
    def get_db_manager(self) -> DatabaseManager:
        return self.db_manager
    
    def add_health_check(self, path: str = "/health"):
        """添加健康检查"""
        @self.app.route(path)
        def health_check():
            system_monitor = get_system_monitor()
            metrics = system_monitor.get_performance_metrics()
            
            db_status = "healthy"
            if self.db_manager:
                try:
                    self.db_manager.execute_query("SELECT 1", fetch_all=False)
                except Exception:
                    db_status = "unhealthy"
            
            return jsonify({
                "status": "healthy" if db_status == "healthy" else "unhealthy",
                "timestamp": time.time(),
                "services": {"database": db_status},
                "metrics": {
                    "cpu": metrics.cpu_percent,
                    "memory": metrics.memory_percent
                }
            })
    
    def add_metrics_endpoint(self, path: str = "/metrics"):
        """添加指标端点"""
        @self.app.route(path)
        def metrics():
            from .monitoring import get_metrics_summary
            return jsonify(get_metrics_summary())

    def add_rate_limiting(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        """添加全局速率限制 (修复版)"""
        # 创建一个全局限流器实例绑定到 app 上
        self.app.rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour
        )

        @self.app.before_request
        def check_rate_limit():
            # 获取客户端IP
            client_ip = request.remote_addr or 'unknown'
            
            # 使用绑定的限流器实例
            if not current_app.rate_limiter.is_allowed(client_ip):
                return jsonify(APIResponse.error("Rate limit exceeded", 429)), 429
        
        self.logger.info(f"Rate limiting added: {requests_per_minute}/min")
    
    def shutdown(self):
        """关闭应用"""
        if self.logger:
            self.logger.info(f"Shutting down {self.app_name}")
        
        if self.db_manager:
            close_db_manager()
        
        system_monitor = get_system_monitor()
        if system_monitor:
            system_monitor.stop()