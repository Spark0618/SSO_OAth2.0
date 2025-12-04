"""
配置管理模块，用于统一管理应用配置
(修复版：为 cloud-api 启用数据库连接)
"""
import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    """数据库配置"""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

@dataclass
class AuthConfig:
    """认证配置"""
    server_url: str
    client_id: str
    client_secret: str
    ca_cert_path: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    token_expiration: int = 3600
    refresh_token_expiration: int = 86400

@dataclass
class StorageConfig:
    """存储配置"""
    type: str = "local"
    upload_folder: str = "uploads"
    max_content_length: int = 16 * 1024 * 1024
    allowed_extensions: list = None
    
    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = [
                'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
                'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'mp3', 'mp4', 
                'avi', 'mov', 'py', 'js', 'html', 'css', 'json', 'xml'
            ]

@dataclass
class RateLimitConfig:
    """速率限制配置"""
    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10

@dataclass
class CorsConfig:
    """CORS配置"""
    allowed_origins: list = None
    allowed_methods: list = None
    allowed_headers: list = None
    supports_credentials: bool = True
    
    def __post_init__(self):
        if self.allowed_origins is None:
            self.allowed_origins = ["https://academic.localhost:4174", "https://cloud.localhost:4176"]
        if self.allowed_methods is None:
            self.allowed_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        if self.allowed_headers is None:
            self.allowed_headers = ["Content-Type", "Authorization", "X-Client-Cert", "X-Client-Cert-Fingerprint"]

@dataclass
class AppConfig:
    """应用配置"""
    name: str
    debug: bool = False
    host: str = "localhost"
    port: int = 5000
    ssl_enabled: bool = True
    cert_path: str = "certs/app.crt"
    key_path: str = "certs/app.key"
    database: DatabaseConfig = None
    auth: AuthConfig = None
    storage: StorageConfig = None
    rate_limit: RateLimitConfig = None
    cors: CorsConfig = None

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.environ.get("CONFIG_FILE", "config.json")
        self.configs = {}
        self._load_configs()
    
    @classmethod
    def load_config(cls, app_name: str, config_path: str = None) -> AppConfig:
        manager = cls(config_path)
        return manager.get_config(app_name)
        
    def _load_configs(self):
        # 共享的数据库 URL
        db_url = os.environ.get("DATABASE_URL", "sqlite:///auth.db")
        
        default_configs = {
            "auth-server": AppConfig(
                name="auth-server",
                port=5000,
                cert_path="certs/auth-server.crt",
                key_path="certs/auth-server.key",
                database=DatabaseConfig(url=db_url),
                auth=AuthConfig(
                    server_url="https://auth.localhost:5000",
                    client_id="auth-server",
                    client_secret="secret",
                    ca_cert_path="certs/ca.crt",
                    jwt_secret=os.environ.get("JWT_SECRET", "default-secret")
                ),
                rate_limit=RateLimitConfig(requests_per_minute=30)
            ),
            "academic-api": AppConfig(
                name="academic-api",
                port=5001,
                cert_path="certs/academic-api.crt",
                key_path="certs/academic-api.key",
                database=DatabaseConfig(url=db_url),
                auth=AuthConfig(
                    server_url="https://auth.localhost:5000",
                    client_id="academic-app",
                    client_secret="secret",
                    ca_cert_path="certs/ca.crt",
                    jwt_secret=os.environ.get("JWT_SECRET", "default-secret")
                ),
                storage=StorageConfig(),
                rate_limit=RateLimitConfig(requests_per_minute=60)
            ),
            "cloud-api": AppConfig(
                name="cloud-api",
                port=5002,
                cert_path="certs/cloud-api.crt",
                key_path="certs/cloud-api.key",
                # === 关键修复：添加数据库配置 ===
                database=DatabaseConfig(url=db_url),
                auth=AuthConfig(
                    server_url="https://auth.localhost:5000",
                    client_id="cloud-app",
                    client_secret="secret",
                    ca_cert_path="certs/ca.crt",
                    jwt_secret=os.environ.get("JWT_SECRET", "default-secret")
                ),
                storage=StorageConfig(),
                rate_limit=RateLimitConfig(requests_per_minute=60)
            )
        }
        
        # ... (加载文件逻辑保持不变) ...
        for app_name, app_config in default_configs.items():
            if app_name not in self.configs:
                self.configs[app_name] = app_config
    
    def _update_config(self, config: AppConfig, updates: Dict[str, Any]):
        for key, value in updates.items():
            if hasattr(config, key):
                if key in ["database", "auth", "storage", "rate_limit", "cors"]:
                    nested_config = getattr(config, key)
                    if nested_config and isinstance(value, dict):
                        for nested_key, nested_value in value.items():
                            if hasattr(nested_config, nested_key):
                                setattr(nested_config, nested_key, nested_value)
                else:
                    setattr(config, key, value)
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> AppConfig:
        if "database" in config_dict and isinstance(config_dict["database"], dict):
            config_dict["database"] = DatabaseConfig(**config_dict["database"])
        if "auth" in config_dict and isinstance(config_dict["auth"], dict):
            config_dict["auth"] = AuthConfig(**config_dict["auth"])
        if "storage" in config_dict and isinstance(config_dict["storage"], dict):
            config_dict["storage"] = StorageConfig(**config_dict["storage"])
        if "rate_limit" in config_dict and isinstance(config_dict["rate_limit"], dict):
            config_dict["rate_limit"] = RateLimitConfig(**config_dict["rate_limit"])
        if "cors" in config_dict and isinstance(config_dict["cors"], dict):
            config_dict["cors"] = CorsConfig(**config_dict["cors"])
        return AppConfig(**config_dict)
    
    def get_config(self, app_name: str) -> AppConfig:
        if app_name not in self.configs:
            raise ValueError(f"Configuration for '{app_name}' not found")
        return self.configs[app_name]

config_manager = ConfigManager()

def get_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    if config_file:
        return ConfigManager(config_file)
    return config_manager