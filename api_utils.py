"""
API工具模块，提供API设计和处理的通用功能
(修复版：补全 require_auth 中的 Token 解析逻辑)
"""
import json
import time
import traceback
from typing import Dict, List, Optional, Any, Callable, Union
from functools import wraps
from flask import request, jsonify, g, current_app
from dataclasses import dataclass, asdict
from .security import SecurityUtils

@dataclass
class APIResponse:
    """API响应格式"""
    success: bool = False
    message: str = "Success"
    data: Optional[Any] = None
    error_code: Optional[str] = None
    timestamp: Optional[float] = None
    request_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict:
        return asdict(APIResponse(success=True, message=message, data=data))

    @staticmethod
    def error(message: str, code: int = 400, details: Any = None) -> Dict:
        return asdict(APIResponse(
            success=False, 
            message=message, 
            error_code=str(code), 
            data=details
        ))

@dataclass
class APIError:
    """API错误信息"""
    code: str = "UNKNOWN_ERROR"
    message: str = "Unknown Error"
    status_code: int = 400
    details: Optional[Dict[str, Any]] = None

class APIException(Exception):
    def __init__(self, error: APIError):
        self.error = error
        super().__init__(error.message)

class APIValidator:
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == "":
                missing_fields.append(field)
        return missing_fields
    
    @staticmethod
    def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type]) -> List[str]:
        type_errors = []
        for field, expected_type in field_types.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    try:
                        if expected_type == int: int(data[field])
                        elif expected_type == float: float(data[field])
                        elif expected_type == str: str(data[field])
                        elif expected_type == bool: bool(data[field])
                        else: type_errors.append(field)
                    except:
                        type_errors.append(field)
        return type_errors

class APIHandler:
    def __init__(self):
        self.error_handlers = {}
        self.request_hooks = {'before': [], 'after': [], 'error': []}
    
    def handle_request(self, func: Callable) -> Callable:
        @wraps(func)
        def decorated_function(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if isinstance(result, APIResponse):
                    response = result
                else:
                    response = APIResponse(success=True, message="Success", data=result)
                return jsonify(asdict(response))
            except APIException as e:
                return jsonify(asdict(APIResponse(
                    success=False, 
                    message=e.error.message, 
                    error_code=e.error.code,
                    data=e.error.details
                ))), e.error.status_code
            except Exception as e:
                if current_app:
                    current_app.logger.error(f"Error: {e}", exc_info=True)
                return jsonify(APIResponse.error("Internal Server Error", 500)), 500
        return decorated_function

api_handler = APIHandler()

# === 关键修复：require_auth 必须解析 Token 并设置 g.user_id ===

def _authenticate_request():
    """内部认证逻辑"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise APIException(APIError("Authentication required", "UNAUTHORIZED", 401))
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise APIException(APIError("Invalid authorization header format", "INVALID_HEADER", 401))
        
    token = parts[1]
    try:
        # 验证 Token
        payload = SecurityUtils.verify_jwt(token)
        # 将用户信息注入全局变量 g
        g.user_id = payload.get("user_id")
        g.username = payload.get("username")
        g.user_role = payload.get("role")
        return True
    except Exception as e:
        raise APIException(APIError(str(e), "INVALID_TOKEN", 401))

def require_auth(arg=None):
    """
    认证装饰器 (兼容 @require_auth 和 @require_auth(func))
    """
    # 1. 作为普通装饰器使用 @require_auth
    if callable(arg):
        f = arg
        @wraps(f)
        def decorated_function(*args, **kwargs):
            _authenticate_request() # 执行认证
            return f(*args, **kwargs)
        return decorated_function
    
    # 2. 作为工厂使用 @require_auth(auth_func=...)
    auth_func = arg
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if auth_func:
                if not auth_func(request):
                    return jsonify(APIResponse.error("Authentication failed", 401)), 401
            else:
                _authenticate_request()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_requests(arg=None):
    log_level = "INFO"
    if callable(arg):
        f = arg
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if hasattr(current_app, 'logger'):
                current_app.logger.info(f"Request: {request.method} {request.path}")
            return f(*args, **kwargs)
        return decorated_function
    
    if isinstance(arg, str):
        log_level = arg

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if hasattr(current_app, 'logger'):
                log_func = getattr(current_app.logger, log_level.lower(), current_app.logger.info)
                log_func(f"Request: {request.method} {request.path}")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def api_endpoint(*args, **kwargs):
    def decorator(f):
        return api_handler.handle_request(f)
    return decorator

def require_roles(roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated
    return decorator

def paginate(*args, **kwargs):
    def decorator(f):
        @wraps(f)
        def decorated(*a, **k):
            return f(*a, **k)
        return decorated
    return decorator

def cache_response(*args, **kwargs):
    def decorator(f):
        @wraps(f)
        def decorated(*a, **k):
            return f(*a, **k)
        return decorated
    return decorator