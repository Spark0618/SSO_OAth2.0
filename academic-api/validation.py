"""
数据验证和安全检查模块
"""
import re
import hashlib
import hmac
from functools import wraps
from typing import Dict, List, Optional, Any, Callable, Tuple
from flask import request, jsonify, g

class ValidationError(Exception):
    """验证错误异常"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)

class SecurityError(Exception):
    """安全错误异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class DataValidator:
    """数据验证器"""
    
    @staticmethod
    def validate_username(username: str) -> str:
        """验证用户名"""
        if not username:
            raise ValidationError("用户名不能为空", "username")
        
        if len(username) < 3 or len(username) > 20:
            raise ValidationError("用户名长度必须在3-20个字符之间", "username")
        
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError("用户名只能包含字母、数字和下划线", "username")
        
        return username
    
    @staticmethod
    def validate_password(password: str) -> str:
        """验证密码"""
        if not password:
            raise ValidationError("密码不能为空", "password")
        
        if len(password) < 6:
            raise ValidationError("密码长度不能少于6个字符", "password")
        
        # 检查密码强度
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        if not (has_upper and has_lower and has_digit):
            raise ValidationError("密码必须包含大写字母、小写字母和数字", "password")
        
        return password
    
    @staticmethod
    def validate_email(email: str) -> str:
        """验证邮箱"""
        if not email:
            return email  # 邮箱可以为空
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("邮箱格式不正确", "email")
        
        return email
    
    @staticmethod
    def validate_student_no(student_no: str) -> str:
        """验证学号"""
        if not student_no:
            raise ValidationError("学号不能为空", "student_no")
        
        # 假设学号是8-12位数字
        if not re.match(r'^\d{8,12}$', student_no):
            raise ValidationError("学号必须是8-12位数字", "student_no")
        
        return student_no
    
    @staticmethod
    def validate_course_code(course_code: str) -> str:
        """验证课程代码"""
        if not course_code:
            raise ValidationError("课程代码不能为空", "course_code")
        
        if len(course_code) < 3 or len(course_code) > 10:
            raise ValidationError("课程代码长度必须在3-10个字符之间", "course_code")
        
        if not re.match(r'^[a-zA-Z0-9]+$', course_code):
            raise ValidationError("课程代码只能包含字母和数字", "course_code")
        
        return course_code
    
    @staticmethod
    def validate_grade(grade: str) -> str:
        """验证成绩"""
        if not grade:
            return grade  # 成绩可以为空
        
        # 允许数字等级（90, 85.5等）或字母等级（A, B+, C-等）
        if re.match(r'^\d+(\.\d+)?$', grade):
            num_grade = float(grade)
            if not (0 <= num_grade <= 100):
                raise ValidationError("数字成绩必须在0-100之间", "grade")
        elif not re.match(r'^[A-F][+-]?$', grade):
            raise ValidationError("成绩格式不正确，应为数字(0-100)或字母等级(A-F)", "grade")
        
        return grade
    
    @staticmethod
    def validate_day_slot(day: Any, slot: Any) -> Tuple[int, int]:
        """验证上课时间"""
        try:
            day = int(day)
            slot = int(slot)
        except (ValueError, TypeError):
            raise ValidationError("上课时间必须是数字")
        
        if not (1 <= day <= 7):
            raise ValidationError("星期必须在1-7之间")
        
        if not (1 <= slot <= 12):
            raise ValidationError("节次必须在1-12之间")
        
        return day, slot
    
    @staticmethod
    def validate_text_field(value: str, field_name: str, min_length: int = 1, max_length: int = 255) -> str:
        """验证文本字段"""
        if value is None:
            value = ""
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name}长度不能少于{min_length}个字符", field_name)
        
        if len(value) > max_length:
            raise ValidationError(f"{field_name}长度不能超过{max_length}个字符", field_name)
        
        return value
    
    @staticmethod
    def validate_json_payload(required_fields: List[str], optional_fields: List[str] = None) -> Dict:
        """验证JSON请求负载"""
        if not request.is_json:
            raise ValidationError("请求必须是JSON格式")
        
        data = request.get_json()
        if not data:
            raise ValidationError("请求体不能为空")
        
        # 检查必需字段
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"缺少必需字段: {field}", field)
        
        # 检查额外字段
        allowed_fields = set(required_fields + (optional_fields or []))
        extra_fields = set(data.keys()) - allowed_fields
        if extra_fields:
            raise ValidationError(f"包含不允许的字段: {', '.join(extra_fields)}")
        
        return data

class SecurityChecker:
    """安全检查器"""
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """清理输入文本，防止XSS攻击"""
        if not text:
            return text
        
        # 移除潜在的HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除潜在的JavaScript代码
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        
        return text
    
    @staticmethod
    def check_sql_injection(text: str) -> str:
        """检查SQL注入"""
        if not text:
            return text
        
        # 常见SQL注入模式
        patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
            r'(--|#|/\*|\*/)',
            r'(\bOR\b.*=.*\bOR\b)',
            r'(\bAND\b.*=.*\bAND\b)',
            r'(\'\s*OR\s*\')',
            r'(1\s*=\s*1)',
            r'(1\s*=\s*1\s*--)',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                raise SecurityError("输入包含潜在的SQL注入攻击")
        
        return text
    
    @staticmethod
    def generate_csrf_token() -> str:
        """生成CSRF令牌"""
        import secrets
        return secrets.token_hex(16)
    
    @staticmethod
    def verify_csrf_token(token: str, expected_token: str) -> bool:
        """验证CSRF令牌"""
        return hmac.compare_digest(token, expected_token)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希"""
        import bcrypt
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """验证密码"""
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def validate_json_payload(required_fields: List[str], optional_fields: List[str] = None):
    """验证JSON请求负载的装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = DataValidator.validate_json_payload(required_fields, optional_fields)
                g.validated_data = data
                return f(*args, **kwargs)
            except ValidationError as e:
                return jsonify({"error": e.message, "field": e.field}), 400
            except Exception as e:
                return jsonify({"error": f"验证失败: {str(e)}"}), 500
        return decorated_function
    return decorator

def validate_user_role(allowed_roles: List[str]):
    """验证用户角色的装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 这里假设已经通过_token验证并设置了g.user
            if not hasattr(g, 'user') or not g.user:
                return jsonify({"error": "未认证"}), 401
            
            user_role = g.user.get('role')
            if user_role not in allowed_roles:
                return jsonify({"error": "权限不足"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_inputs(*field_names):
    """清理输入字段的装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.is_json:
                data = request.get_json() or {}
                for field in field_names:
                    if field in data:
                        data[field] = SecurityChecker.sanitize_input(data[field])
                        data[field] = SecurityChecker.check_sql_injection(data[field])
                request._cached_json = (data, False)
            else:
                # 处理表单数据
                for field in field_names:
                    if field in request.form:
                        request.form[field] = SecurityChecker.sanitize_input(request.form[field])
                        request.form[field] = SecurityChecker.check_sql_injection(request.form[field])
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_security_event(event_type: str, details: Dict = None):
    """记录安全事件"""
    from .storage import storage
    from datetime import datetime
    
    event = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "ip_address": request.remote_addr,
        "user_agent": request.headers.get('User-Agent'),
        "details": details or {}
    }
    
    # 如果有用户信息，添加到事件中
    if hasattr(g, 'user') and g.user:
        event["user"] = g.user.get("username")
    
    storage.append_to_list("system_logs", "security_events", event)