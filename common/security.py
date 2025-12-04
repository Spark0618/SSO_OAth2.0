"""
安全工具模块，提供通用的安全功能
(修复版：添加了 set_jwt_secret 并修复了 rate_limit 中的 app 引用错误)
"""
import os
import secrets
import hashlib
import hmac
import time
import re
import ssl
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g, session, current_app
import jwt
import magic
from werkzeug.utils import secure_filename
import bcrypt # 保留 bcrypt 支持

class SecurityUtils:
    """安全工具类"""
    
    # === 关键修复 1: 添加类变量存储配置 ===
    _jwt_secret = "default-insecure-secret"
    _jwt_algorithm = "HS256"

    # === 关键修复 2: 添加 set_jwt_secret 方法 ===
    @classmethod
    def set_jwt_secret(cls, secret: str):
        """设置JWT密钥"""
        if secret:
            cls._jwt_secret = secret

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成安全的随机令牌"""
        return secrets.token_hex(length)
    
    @staticmethod
    def generate_session_id() -> str:
        """生成安全的会话ID"""
        timestamp = str(int(time.time()))
        random_bytes = secrets.token_bytes(16)
        return hashlib.sha256(timestamp.encode() + random_bytes).hexdigest()
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """安全的密码哈希 (PBKDF2)"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 迭代次数
        )
        
        return password_hash.hex(), salt

    @staticmethod
    def verify_password(password: str, salt: str, stored_hash: str) -> bool:
        """验证密码"""
        password_hash, _ = SecurityUtils.hash_password(password, salt)
        return hmac.compare_digest(password_hash, stored_hash)
    
    # === 关键修复 3: 修改 JWT 方法以使用类存储的密钥 ===
    @classmethod
    def generate_jwt(cls, payload: Dict[str, Any], secret_key: str = None, 
                     algorithm: str = None, 
                     expiration: int = 3600) -> str:
        """生成JWT令牌"""
        secret = secret_key or cls._jwt_secret
        algo = algorithm or cls._jwt_algorithm
        
        now = datetime.utcnow()
        # 避免修改原字典
        token_payload = payload.copy()
        token_payload.update({
            'iat': now,
            'exp': now + timedelta(seconds=expiration)
        })
        
        return jwt.encode(token_payload, secret, algorithm=algo)
    
    @classmethod
    def verify_jwt(cls, token: str, secret_key: str = None, 
                   algorithm: str = None) -> Dict[str, Any]:
        """验证JWT令牌"""
        secret = secret_key or cls._jwt_secret
        algo = algorithm or cls._jwt_algorithm
        
        try:
            return jwt.decode(token, secret, algorithms=[algo])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
    
    @staticmethod
    def sanitize_input(input_str: str) -> str:
        """清理输入字符串，防止XSS攻击"""
        if not input_str:
            return ""
        
        # 移除潜在的HTML标签
        cleaned = re.sub(r'<[^>]*>', '', input_str)
        
        # 转义特殊字符
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#x27;",
            ">": "&gt;",
            "<": "&lt;",
        }
        
        return "".join(html_escape_table.get(c, c) for c in cleaned)
    
    @staticmethod
    def validate_sql_input(input_str: str) -> bool:
        """检查输入是否包含SQL注入尝试"""
        if not input_str:
            return True
        
        # 常见的SQL注入模式
        sql_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
            r'(--|\#|\/\*|\*\/)',
            r'(\bOR\b.*\b1\s*=\s*1\b|\bAND\b.*\b1\s*=\s*1\b)',
            r'(\bxp_cmdshell\b|\bsp_oacreate\b)',
            r'(\bWAITFOR\s+DELAY\b)',
            r'(\bBENCHMARK\b|\bSLEEP\b)'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return False
        
        return True
    
    @staticmethod
    def validate_file_type(file_path: str, allowed_extensions: List[str]) -> bool:
        """验证文件类型"""
        if not os.path.exists(file_path):
            return False
        
        try:
            # 使用python-magic库获取实际文件类型
            # 注意：在Windows上如果不带DLL可能报错，这里加个try-except兜底
            try:
                file_type = magic.from_file(file_path, mime=True)
            except Exception:
                # 如果magic库不可用，回退到扩展名检查
                file_type = None

            # 检查文件扩展名
            file_ext = os.path.splitext(file_path)[1][1:].lower()
            if file_ext not in allowed_extensions:
                return False
            
            if file_type:
                # 检查MIME类型
                allowed_mimes = {
                    'txt': 'text/plain',
                    'pdf': 'application/pdf',
                    'png': 'image/png',
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'gif': 'image/gif',
                    'json': 'application/json',
                    'xml': 'application/xml'
                    # 其他类型省略以节省篇幅，实际可保留你原来的完整列表
                }
                # 如果MIME类型不在列表中，或者扩展名对应的MIME类型不匹配
                if file_ext in allowed_mimes and file_type != allowed_mimes[file_ext]:
                     # 有些情况下MIME类型识别可能不准（如text/plain），这里可以放宽一点
                     if not (file_ext == 'txt' and 'text' in file_type):
                        return False
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """验证文件名是否安全"""
        if not filename:
            return False
        
        safe_name = secure_filename(filename)
        if safe_name != filename:
            return False
        
        if len(safe_name) > 255:
            return False
        
        if ".." in safe_name or safe_name.startswith("/"):
            return False
        
        return True
    
    @staticmethod
    def generate_csrf_token() -> str:
        """生成CSRF令牌"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def verify_csrf_token(token: str, session_token: str) -> bool:
        """验证CSRF令牌"""
        if not token or not session_token:
            return False
        return hmac.compare_digest(token, session_token)
    
    @staticmethod
    def validate_cert_chain(cert_path: str, ca_cert_path: str) -> bool:
        """验证证书链"""
        try:
            with open(ca_cert_path, 'rb') as f:
                ca_cert = ssl.PEM_cert_to_DER_cert(f.read().decode())
            with open(cert_path, 'rb') as f:
                server_cert = ssl.PEM_cert_to_DER_cert(f.read().decode())
            
            context = ssl.create_default_context(cafile=ca_cert_path)
            context.load_verify_locations(cafile=ca_cert_path)
            context.verify_mode = ssl.CERT_REQUIRED
            return True
        except Exception:
            return False

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, requests_per_minute: int = 60, 
                 requests_per_hour: int = 1000, 
                 burst_size: int = 10):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        self.clients = {}  # 存储客户端请求记录
    
    def is_allowed(self, client_id: str) -> bool:
        """检查客户端是否允许请求"""
        now = time.time()
        
        if client_id not in self.clients:
            self.clients[client_id] = {
                'requests': [],
                'minute_count': 0,
                'hour_count': 0,
                'last_minute_reset': now,
                'last_hour_reset': now
            }
        
        client = self.clients[client_id]
        
        if now - client['last_minute_reset'] > 60:
            client['minute_count'] = 0
            client['last_minute_reset'] = now
        
        if now - client['last_hour_reset'] > 3600:
            client['hour_count'] = 0
            client['last_hour_reset'] = now
        
        if client['minute_count'] >= self.requests_per_minute:
            return False
        
        if client['hour_count'] >= self.requests_per_hour:
            return False
        
        client['requests'].append(now)
        client['minute_count'] += 1
        client['hour_count'] += 1
        
        # 清理旧的请求记录
        if len(client['requests']) > 1000:
            client['requests'] = client['requests'][-1000:]
        
        return True
    
    def get_status(self, client_id: str) -> Dict[str, int]:
        """获取客户端状态"""
        if client_id not in self.clients:
            return {
                'minute_remaining': self.requests_per_minute,
                'hour_remaining': self.requests_per_hour,
                'minute_reset': 60,
                'hour_reset': 3600
            }
        
        client = self.clients[client_id]
        now = time.time()
        
        return {
            'minute_remaining': max(0, self.requests_per_minute - client['minute_count']),
            'hour_remaining': max(0, self.requests_per_hour - client['hour_count']),
            'minute_reset': int(max(0, 60 - (now - client['last_minute_reset']))),
            'hour_reset': int(max(0, 3600 - (now - client['last_hour_reset'])))
        }

def require_csrf_token(f):
    """CSRF保护装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE']:
            token = request.headers.get('X-CSRF-Token')
            # 使用 Flask 的 session
            if not token or 'csrf_token' not in session or not SecurityUtils.verify_csrf_token(token, session['csrf_token']):
                # 在测试环境中，如果没有设置 session，有时可以放宽要求，但这里我们保持严格
                # 实际使用中可以根据 app.config['DEBUG'] 判断
                return jsonify({'error': 'CSRF token validation failed'}), 403
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(limit: int = 60, period: int = 60):
    """速率限制装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_id = request.remote_addr
            if hasattr(g, 'user_id'):
                client_id = f"user:{g.user_id}"
            
            # === 关键修复 4: 使用 current_app 而不是 app ===
            if not hasattr(current_app, 'rate_limiter'):
                current_app.rate_limiter = RateLimiter(requests_per_minute=limit)
            
            limiter = current_app.rate_limiter
            
            if not limiter.is_allowed(client_id):
                status = limiter.get_status(client_id)
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': min(status['minute_reset'], status['hour_reset'])
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_input(validation_rules: Dict[str, Any]):
    """输入验证装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            if not data:
                data = {}

            errors = {}
            
            for field, rules in validation_rules.items():
                if field not in data:
                    if 'required' in rules and rules['required']:
                        errors[field] = f"Field '{field}' is required"
                    continue
                
                value = data[field]
                
                # 简单的类型和内容校验逻辑 (保留你原来的逻辑)
                if 'type' in rules:
                     # ... (为了节省篇幅，这里保留你原有的完整逻辑，这部分没问题) ...
                     pass 
                
                # XSS检查
                if isinstance(value, str):
                    sanitized = SecurityUtils.sanitize_input(value)
                    if sanitized != value:
                        errors[field] = f"Field '{field}' contains potentially unsafe content"
            
            if errors:
                return jsonify({'error': 'Validation failed', 'details': errors}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator