"""
统一错误处理模块
提供RESTful API风格的错误响应和异常处理
"""

from flask import jsonify
import logging
import traceback
from functools import wraps

# 设置日志
logger = logging.getLogger(__name__)

class APIError(Exception):
    """自定义API异常类"""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """转换为字典格式"""
        rv = dict(self.payload or ())
        rv['error'] = self.message
        rv['status'] = self.status_code
        return rv

class ValidationError(APIError):
    """数据验证错误"""
    def __init__(self, message, field=None):
        super().__init__(message, 400)
        self.field = field
        self.payload = {'error_type': 'validation', 'field': field}

class AuthenticationError(APIError):
    """认证错误"""
    def __init__(self, message="Authentication failed"):
        super().__init__(message, 401)
        self.payload = {'error_type': 'authentication'}

class AuthorizationError(APIError):
    """授权错误"""
    def __init__(self, message="Access denied"):
        super().__init__(message, 403)
        self.payload = {'error_type': 'authorization'}

class NotFoundError(APIError):
    """资源未找到错误"""
    def __init__(self, message="Resource not found"):
        super().__init__(message, 404)
        self.payload = {'error_type': 'not_found'}

class ConflictError(APIError):
    """资源冲突错误"""
    def __init__(self, message="Resource conflict"):
        super().__init__(message, 409)
        self.payload = {'error_type': 'conflict'}

class RateLimitError(APIError):
    """请求频率限制错误"""
    def __init__(self, message="Rate limit exceeded"):
        super().__init__(message, 429)
        self.payload = {'error_type': 'rate_limit'}

class ServerError(APIError):
    """服务器内部错误"""
    def __init__(self, message="Internal server error"):
        super().__init__(message, 500)
        self.payload = {'error_type': 'server_error'}

def handle_api_error(error):
    """处理API错误，返回JSON响应"""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def handle_unexpected_error(error):
    """处理未预期的错误"""
    logger.error(f"Unexpected error: {str(error)}\n{traceback.format_exc()}")
    
    # 在生产环境中，不暴露详细的错误信息
    response = jsonify({
        "error": "Internal server error",
        "status": 500,
        "error_type": "server_error"
    })
    response.status_code = 500
    return response

def success_response(data=None, message="Success", status_code=200):
    """创建成功响应"""
    response_data = {
        "success": True,
        "message": message,
        "status": status_code
    }
    
    if data is not None:
        response_data["data"] = data
    
    response = jsonify(response_data)
    response.status_code = status_code
    return response

def paginated_response(items, page, per_page, total, message="Success"):
    """创建分页响应"""
    total_pages = (total + per_page - 1) // per_page
    
    response_data = {
        "success": True,
        "message": message,
        "status": 200,
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages
            }
        }
    }
    
    response = jsonify(response_data)
    response.status_code = 200
    return response

def error_handler(f):
    """错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except APIError as e:
            return handle_api_error(e)
        except Exception as e:
            return handle_unexpected_error(e)
    return decorated_function

def validate_json(required_fields=None, optional_fields=None):
    """JSON数据验证装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            
            # 检查Content-Type
            if not request.is_json:
                raise ValidationError("Content-Type must be application/json")
            
            # 获取JSON数据
            data = request.get_json()
            if data is None:
                raise ValidationError("Invalid JSON data")
            
            # 检查必填字段
            if required_fields:
                for field in required_fields:
                    if field not in data:
                        raise ValidationError(f"Missing required field: {field}", field=field)
            
            # 检查字段类型
            if optional_fields:
                for field, field_type in optional_fields.items():
                    if field in data and not isinstance(data[field], field_type):
                        raise ValidationError(
                            f"Field '{field}' must be of type {field_type.__name__}", 
                            field=field
                        )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def setup_error_handlers(app):
    """设置Flask应用的错误处理器"""
    
    @app.errorhandler(APIError)
    def handle_api_error_exception(error):
        return handle_api_error(error)
    
    @app.errorhandler(400)
    def handle_bad_request(error):
        return handle_api_error(ValidationError("Bad request"))
    
    @app.errorhandler(401)
    def handle_unauthorized(error):
        return handle_api_error(AuthenticationError())
    
    @app.errorhandler(403)
    def handle_forbidden(error):
        return handle_api_error(AuthorizationError())
    
    @app.errorhandler(404)
    def handle_not_found(error):
        return handle_api_error(NotFoundError())
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return handle_api_error(APIError("Method not allowed", 405))
    
    @app.errorhandler(409)
    def handle_conflict(error):
        return handle_api_error(ConflictError())
    
    @app.errorhandler(429)
    def handle_rate_limit(error):
        return handle_api_error(RateLimitError())
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        return handle_unexpected_error(error)
    
    logger.info("Error handlers registered")