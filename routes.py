"""
API路由模块
实现RESTful风格的API路由组织
"""

from flask import Blueprint, request, jsonify
from functools import wraps
import logging
from datetime import datetime
import time

# 导入自定义模块
from .error_handlers import (
    error_handler, validate_json, success_response, 
    paginated_response, ValidationError, AuthenticationError, 
    AuthorizationError, NotFoundError
)
from .validation import DataValidator, SecurityChecker
from .user_preferences import UserPreferences
from .storage import FileStorage
from .resource_manager import CourseResourceManager
from .progress_tracker import ProgressTracker
from .audit_logger import audit_logger, AuditEventType
from .docs_and_tests import create_docs_and_tests_blueprint, register_existing_endpoints

# 设置日志
logger = logging.getLogger(__name__)

# 创建蓝图
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# 初始化组件
validator = DataValidator()
security_checker = SecurityChecker()
# 配置增强型存储系统
storage_config = {
    'local': {
        'base_path': 'uploads',
        'max_file_size': 16 * 1024 * 1024,  # 16MB
        'allowed_extensions': ['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'mp3', 'mp4', 'avi', 'mov']
    }
}

# 可以根据环境变量选择不同的存储类型
import os
storage_type = os.environ.get('STORAGE_TYPE', 'local')

file_storage = FileStorage(storage_type=storage_type, storage_config=storage_config.get(storage_type, {}))
user_preferences = UserPreferences()
resource_manager = CourseResourceManager(file_storage)
progress_tracker = ProgressTracker(db.session)

# 创建文档和测试蓝图
docs_and_tests_bp = create_docs_and_tests_blueprint()

# 注册现有端点到文档生成器
register_existing_endpoints()

# 认证装饰器
def authenticate(f):
    @wraps(f)
    @error_handler
    def decorated_function(*args, **kwargs):
        # 从请求头获取令牌
        token = request.headers.get('Authorization')
        if not token:
            raise AuthenticationError("Missing authorization header")
        
        # 验证令牌格式
        if not token.startswith('Bearer '):
            raise AuthenticationError("Invalid token format")
        
        token = token[7:]  # 移除 'Bearer ' 前缀
        
        # 验证令牌
        try:
            # 这里应该实现实际的令牌验证逻辑
            # 暂时使用模拟验证
            if not token or len(token) < 10:
                raise AuthenticationError("Invalid token")
            
            # 从令牌中提取用户信息
            # 实际应用中应该解析JWT令牌
            user_info = {
                'username': 'demo_user',  # 从令牌中解析
                'role': 'student',        # 从令牌中解析
                'user_id': 1              # 从令牌中解析
            }
            
            # 将用户信息添加到请求上下文
            request.current_user = user_info
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise AuthenticationError("Authentication failed")
    
    return decorated_function

# 角色检查装饰器
def require_role(required_role):
    def decorator(f):
        @wraps(f)
        @error_handler
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'current_user'):
                raise AuthenticationError("User not authenticated")
            
            if request.current_user.get('role') != required_role:
                raise AuthorizationError(f"Access denied. Required role: {required_role}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 用户偏好设置路由
@api_v1.route('/users/preferences', methods=['GET'])
@authenticate
def get_user_preferences():
    """获取用户偏好设置"""
    username = request.current_user.get('username')
    
    try:
        preferences = user_preferences.get_preferences(username)
        return success_response(data=preferences, message="Preferences retrieved successfully")
    except Exception as e:
        logger.error(f"Error getting user preferences for {username}: {str(e)}")
        raise ValidationError("Failed to get preferences")

@api_v1.route('/users/preferences', methods=['PUT'])
@authenticate
@validate_json(
    optional_fields={
        'theme': str,
        'language': str,
        'notifications': dict,
        'dashboard': dict,
        'privacy': dict,
        'accessibility': dict
    }
)
def update_user_preferences():
    """更新用户偏好设置"""
    username = request.current_user.get('username')
    data = request.get_json()
    
    try:
        # 验证输入数据
        if 'theme' in data and not validator.validate_theme(data['theme']):
            raise ValidationError("Invalid theme value", field='theme')
        if 'language' in data and not validator.validate_language(data['language']):
            raise ValidationError("Invalid language value", field='language')
        
        # 更新偏好设置
        updated = user_preferences.update_preferences(username, data)
        if updated:
            return success_response(message="Preferences updated successfully")
        else:
            raise ValidationError("Failed to update preferences")
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error updating user preferences for {username}: {str(e)}")
        raise ValidationError("Failed to update preferences")

@api_v1.route('/users/preferences/reset', methods=['POST'])
@authenticate
def reset_user_preferences():
    """重置用户偏好设置为默认值"""
    username = request.current_user.get('username')
    
    try:
        success = user_preferences.reset_preferences(username)
        if success:
            return success_response(message="Preferences reset successfully")
        else:
            raise ValidationError("Failed to reset preferences")
    except Exception as e:
        logger.error(f"Error resetting user preferences for {username}: {str(e)}")
        raise ValidationError("Failed to reset preferences")

# 课程公告路由
@api_v1.route('/courses/<course_code>/announcements', methods=['GET'])
@authenticate
def get_course_announcements(course_code):
    """获取课程公告列表"""
    username = request.current_user.get('username')
    user_role = request.current_user.get('role')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 检查用户权限（这里应该实现实际的权限检查）
        # 暂时跳过权限检查
        
        # 获取公告列表
        announcements = file_storage.read(f"course_announcements_{course_code}.json", [])
        
        # 分页参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        # 计算分页
        total = len(announcements)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_announcements = announcements[start:end]
        
        return paginated_response(
            items=paginated_announcements,
            page=page,
            per_page=per_page,
            total=total,
            message=f"Announcements for course {course_code}"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error getting announcements for course {course_code}: {str(e)}")
        raise ValidationError("Failed to get announcements")

@api_v1.route('/courses/<course_code>/announcements', methods=['POST'])
@authenticate
@require_role('teacher')
@validate_json(
    required_fields=['title', 'content'],
    optional_fields={'priority': str}
)
def create_course_announcement(course_code):
    """创建课程公告"""
    username = request.current_user.get('username')
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    priority = data.get('priority', 'normal')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 检查教师权限（这里应该实现实际的权限检查）
        # 暂时跳过权限检查
        
        # 创建新公告
        announcement = {
            "id": f"ann_{int(time.time())}",
            "title": security_checker.sanitize_input(title),
            "content": security_checker.sanitize_input(content),
            "author": username,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # 保存公告
        announcements = file_storage.read(f"course_announcements_{course_code}.json", [])
        announcements.insert(0, announcement)  # 最新公告在最前面
        file_storage.write(f"course_announcements_{course_code}.json", announcements)
        
        return success_response(
            data=announcement, 
            message="Announcement created successfully",
            status_code=201
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error creating announcement for course {course_code}: {str(e)}")
        raise ValidationError("Failed to create announcement")

@api_v1.route('/courses/<course_code>/announcements/<announcement_id>', methods=['PUT'])
@authenticate
@require_role('teacher')
@validate_json(
    optional_fields={'title': str, 'content': str, 'priority': str}
)
def update_course_announcement(course_code, announcement_id):
    """更新课程公告"""
    username = request.current_user.get('username')
    data = request.get_json()
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 检查教师权限（这里应该实现实际的权限检查）
        # 暂时跳过权限检查
        
        # 获取现有公告
        announcements = file_storage.read(f"course_announcements_{course_code}.json", [])
        found = False
        
        for i, ann in enumerate(announcements):
            if ann["id"] == announcement_id:
                found = True
                if 'title' in data:
                    announcements[i]["title"] = security_checker.sanitize_input(data['title'])
                if 'content' in data:
                    announcements[i]["content"] = security_checker.sanitize_input(data['content'])
                if 'priority' in data:
                    announcements[i]["priority"] = data['priority']
                announcements[i]["updated_at"] = datetime.now().isoformat()
                break
        
        if not found:
            raise NotFoundError("Announcement not found")
        
        # 保存更新后的公告
        file_storage.write(f"course_announcements_{course_code}.json", announcements)
        
        return success_response(message="Announcement updated successfully")
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error updating announcement {announcement_id} for course {course_code}: {str(e)}")
        raise ValidationError("Failed to update announcement")

@api_v1.route('/courses/<course_code>/announcements/<announcement_id>', methods=['DELETE'])
@authenticate
@require_role('teacher')
def delete_course_announcement(course_code, announcement_id):
    """删除课程公告"""
    username = request.current_user.get('username')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 检查教师权限（这里应该实现实际的权限检查）
        # 暂时跳过权限检查
        
        # 获取现有公告
        announcements = file_storage.read(f"course_announcements_{course_code}.json", [])
        found = False
        
        for i, ann in enumerate(announcements):
            if ann["id"] == announcement_id:
                found = True
                announcements.pop(i)
                break
        
        if not found:
            raise NotFoundError("Announcement not found")
        
        # 保存更新后的公告
        file_storage.write(f"course_announcements_{course_code}.json", announcements)
        
        return success_response(message="Announcement deleted successfully")
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error deleting announcement {announcement_id} for course {course_code}: {str(e)}")
        raise ValidationError("Failed to delete announcement")

# 作业管理路由
@api_v1.route('/courses/<course_code>/assignments', methods=['GET'])
@authenticate
def get_course_assignments(course_code):
    """获取课程作业列表"""
    username = request.current_user.get('username')
    user_role = request.current_user.get('role')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 检查用户权限（这里应该实现实际的权限检查）
        # 暂时跳过权限检查
        
        # 获取作业列表
        assignments = file_storage.read(f"course_assignments_{course_code}.json", [])
        
        # 如果是学生，添加提交状态信息
        if user_role == 'student':
            # 这里应该实现实际的提交状态检查
            # 暂时跳过
            pass
        
        # 分页参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        # 计算分页
        total = len(assignments)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_assignments = assignments[start:end]
        
        return paginated_response(
            items=paginated_assignments,
            page=page,
            per_page=per_page,
            total=total,
            message=f"Assignments for course {course_code}"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error getting assignments for course {course_code}: {str(e)}")
        raise ValidationError("Failed to get assignments")

@api_v1.route('/courses/<course_code>/assignments', methods=['POST'])
@authenticate
@require_role('teacher')
@validate_json(
    required_fields=['title', 'description', 'due_date'],
    optional_fields={'instructions': str, 'max_score': int}
)
def create_course_assignment(course_code):
    """创建课程作业"""
    username = request.current_user.get('username')
    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    due_date = data.get('due_date')
    instructions = data.get('instructions', '')
    max_score = data.get('max_score', 100)
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 检查教师权限（这里应该实现实际的权限检查）
        # 暂时跳过权限检查
        
        # 验证日期格式
        try:
            datetime.fromisoformat(due_date)
        except ValueError:
            raise ValidationError("Invalid due_date format, use ISO format (YYYY-MM-DDTHH:MM:SS)", field='due_date')
        
        # 创建新作业
        assignment = {
            "id": f"assign_{int(time.time())}",
            "title": security_checker.sanitize_input(title),
            "description": security_checker.sanitize_input(description),
            "instructions": security_checker.sanitize_input(instructions),
            "due_date": due_date,
            "max_score": max_score,
            "course_code": course_code,
            "created_by": username,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # 保存作业
        assignments = file_storage.read(f"course_assignments_{course_code}.json", [])
        assignments.insert(0, assignment)  # 最新作业在最前面
        file_storage.write(f"course_assignments_{course_code}.json", assignments)
        
        return success_response(
            data=assignment, 
            message="Assignment created successfully",
            status_code=201
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error creating assignment for course {course_code}: {str(e)}")
        raise ValidationError("Failed to create assignment")

# 学生选课和退课路由
@api_v1.route('/courses/enrollment', methods=['GET'])
@authenticate
@require_role('student')
def get_available_courses():
    """获取可选课程列表"""
    username = request.current_user.get('username')
    
    try:
        # 这里应该实现实际的课程查询逻辑
        # 暂时返回模拟数据
        available_courses = [
            {
                "code": "CS101",
                "title": "Introduction to Computer Science",
                "description": "Basic concepts of computer science",
                "credits": 3
            },
            {
                "code": "CS201",
                "title": "Data Structures",
                "description": "Introduction to data structures and algorithms",
                "credits": 4
            }
        ]
        
        # 分页参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        # 计算分页
        total = len(available_courses)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_courses = available_courses[start:end]
        
        return paginated_response(
            items=paginated_courses,
            page=page,
            per_page=per_page,
            total=total,
            message="Available courses"
        )
    except Exception as e:
        logger.error(f"Error getting available courses for {username}: {str(e)}")
        raise ValidationError("Failed to get available courses")

@api_v1.route('/courses/<course_code>/enrollment', methods=['POST'])
@authenticate
@require_role('student')
def enroll_in_course(course_code):
    """学生选课"""
    username = request.current_user.get('username')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 这里应该实现实际的选课逻辑
        # 暂时只返回成功响应
        
        return success_response(message="Successfully enrolled in course")
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error enrolling in course {course_code}: {str(e)}")
        raise ValidationError("Failed to enroll in course")

@api_v1.route('/courses/<course_code>/enrollment', methods=['DELETE'])
@authenticate
@require_role('student')
def drop_course(course_code):
    """学生退课"""
    username = request.current_user.get('username')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 这里应该实现实际的退课逻辑
        # 暂时只返回成功响应
        
        return success_response(message="Successfully dropped from course")
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error dropping course {course_code}: {str(e)}")
        raise ValidationError("Failed to drop from course")

# 健康检查端点
@api_v1.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return success_response(
        data={
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        },
        message="API is running"
    )

# 课程资源管理路由
@api_v1.route('/courses/<course_code>/resources', methods=['GET'])
@authenticate
def get_course_resources(course_code):
    """获取课程资源列表"""
    username = request.current_user.get('username')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 获取查询参数
        category = request.args.get('category')
        tags = request.args.getlist('tags')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # 获取资源列表
        result = resource_manager.get_course_resources(
            course_code=course_code,
            category=category,
            tags=tags,
            page=page,
            per_page=per_page
        )
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        return success_response(
            data={
                "resources": result["resources"],
                "pagination": result["pagination"]
            },
            message=f"Resources for course {course_code}"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error getting resources for course {course_code}: {str(e)}")
        raise ValidationError("Failed to get resources")

@api_v1.route('/courses/<course_code>/resources', methods=['POST'])
@authenticate
@require_role('teacher')
def upload_course_resource(course_code):
    """上传课程资源"""
    username = request.current_user.get('username')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 检查是否有文件上传
        if 'file' not in request.files:
            raise ValidationError("No file uploaded")
        
        file = request.files['file']
        if file.filename == '':
            raise ValidationError("No file selected")
        
        # 获取表单数据
        title = request.form.get('title')
        description = request.form.get('description', '')
        tags = request.form.getlist('tags')
        
        # 验证必填字段
        if not title:
            raise ValidationError("Title is required", field='title')
        
        # 读取文件数据
        file_data = file.read()
        file_name = file.filename
        
        # 上传资源
        result = resource_manager.upload_resource(
            course_code=course_code,
            title=title,
            description=description,
            file_data=file_data,
            file_name=file_name,
            uploader=username,
            tags=tags
        )
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        return success_response(
            data=result["resource"],
            message="Resource uploaded successfully",
            status_code=201
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error uploading resource for course {course_code}: {str(e)}")
        raise ValidationError("Failed to upload resource")

@api_v1.route('/resources/<resource_id>', methods=['GET'])
@authenticate
def get_resource(resource_id):
    """获取资源详情"""
    username = request.current_user.get('username')
    
    try:
        # 获取资源详情
        result = resource_manager.get_resource(resource_id)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        return success_response(
            data=result["resource"],
            message="Resource details retrieved successfully"
        )
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error getting resource {resource_id}: {str(e)}")
        raise ValidationError("Failed to get resource details")

@api_v1.route('/resources/<resource_id>/download', methods=['GET'])
@authenticate
def download_resource(resource_id):
    """下载资源"""
    username = request.current_user.get('username')
    
    try:
        # 下载资源
        result = resource_manager.download_resource(resource_id)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        # 返回文件数据
        from flask import Response
        return Response(
            result["file_data"],
            mimetype=result["file_type"],
            headers={
                "Content-Disposition": f"attachment; filename={result['file_name']}"
            }
        )
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error downloading resource {resource_id}: {str(e)}")
        raise ValidationError("Failed to download resource")

@api_v1.route('/resources/<resource_id>', methods=['PUT'])
@authenticate
@require_role('teacher')
@validate_json(
    optional_fields={'title': str, 'description': str, 'tags': list}
)
def update_resource(resource_id):
    """更新资源信息"""
    username = request.current_user.get('username')
    data = request.get_json()
    
    try:
        # 更新资源
        result = resource_manager.update_resource(
            resource_id=resource_id,
            title=data.get('title'),
            description=data.get('description'),
            tags=data.get('tags'),
            updater=username
        )
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        return success_response(message="Resource updated successfully")
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error updating resource {resource_id}: {str(e)}")
        raise ValidationError("Failed to update resource")

@api_v1.route('/resources/<resource_id>', methods=['DELETE'])
@authenticate
@require_role('teacher')
def delete_resource(resource_id):
    """删除资源"""
    username = request.current_user.get('username')
    
    try:
        # 删除资源
        result = resource_manager.delete_resource(resource_id)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        return success_response(message="Resource deleted successfully")
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error deleting resource {resource_id}: {str(e)}")
        raise ValidationError("Failed to delete resource")

@api_v1.route('/resources/categories', methods=['GET'])
@authenticate
def get_resource_categories():
    """获取资源类型列表"""
    try:
        # 获取资源类型
        result = resource_manager.get_resource_categories()
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        return success_response(
            data={"categories": result["categories"]},
            message="Resource categories retrieved successfully"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error("Error getting resource categories: {str(e)}")
        raise ValidationError("Failed to get resource categories")

@api_v1.route('/courses/<course_code>/resources/tags', methods=['GET'])
@authenticate
def get_course_resource_tags(course_code):
    """获取课程资源标签列表"""
    username = request.current_user.get('username')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 获取标签列表
        result = resource_manager.get_resource_tags(course_code)
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        return success_response(
            data={"tags": result["tags"]},
            message=f"Resource tags for course {course_code} retrieved successfully"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error getting resource tags for course {course_code}: {str(e)}")
        raise ValidationError("Failed to get resource tags")

@api_v1.route('/courses/<course_code>/resources/search', methods=['GET'])
@authenticate
def search_course_resources(course_code):
    """搜索课程资源"""
    username = request.current_user.get('username')
    
    try:
        # 验证课程代码
        if not validator.validate_course_code(course_code):
            raise ValidationError("Invalid course code", field='course_code')
        
        # 获取查询参数
        query = request.args.get('query')
        if not query:
            raise ValidationError("Query parameter is required", field='query')
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # 搜索资源
        result = resource_manager.search_resources(
            course_code=course_code,
            query=query,
            page=page,
            per_page=per_page
        )
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.RESOURCE_DOWNLOAD,
            user_id=username,
            details={
                "course_code": course_code,
                "query": query,
                "results_count": len(result.get("resources", []))
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data={
                "resources": result["resources"],
                "query": result["query"],
                "pagination": result["pagination"]
            },
            message=f"Search results for '{query}' in course {course_code}"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error searching resources for course {course_code}: {str(e)}")
        raise ValidationError("Failed to search resources")

# 学习进度跟踪和统计功能

@api_v1.route('/progress/student/course/<int:course_id>', methods=['GET'])
@authenticate
def get_student_course_progress(course_id):
    """获取学生在特定课程中的学习进度"""
    try:
        username = request.current_user.get('username')
        user_role = request.current_user.get('role')
        
        # 只有学生可以查看自己的进度，教师可以查看所有学生的进度
        if user_role == 'student':
            student_id = request.current_user.get('user_id')
        elif user_role == 'teacher':
            # 教师需要指定学生ID
            student_id = request.args.get('student_id', type=int)
            if not student_id:
                raise ValidationError("教师必须指定学生ID", field='student_id')
        else:
            raise AuthorizationError("权限不足")
        
        # 获取课程进度
        result = progress_tracker.get_student_course_progress(student_id, course_id)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_VIEW,
            user_id=username,
            details={
                "action": "view_course_progress",
                "student_id": student_id,
                "course_id": course_id
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result["data"],
            message=f"学生{student_id}在课程{course_id}中的进度获取成功"
        )
    except (ValidationError, AuthorizationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error getting student course progress: {str(e)}")
        raise ValidationError("获取课程进度失败")


@api_v1.route('/progress/student/overall', methods=['GET'])
@authenticate
def get_student_overall_progress():
    """获取学生整体学习进度"""
    try:
        username = request.current_user.get('username')
        user_role = request.current_user.get('role')
        
        # 只有学生可以查看自己的进度，教师可以查看所有学生的进度
        if user_role == 'student':
            student_id = request.current_user.get('user_id')
        elif user_role == 'teacher':
            # 教师需要指定学生ID
            student_id = request.args.get('student_id', type=int)
            if not student_id:
                raise ValidationError("教师必须指定学生ID", field='student_id')
        else:
            raise AuthorizationError("权限不足")
        
        # 获取整体进度
        result = progress_tracker.get_student_overall_progress(student_id)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_VIEW,
            user_id=username,
            details={
                "action": "view_overall_progress",
                "student_id": student_id
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result["data"],
            message=f"学生{student_id}的整体学习进度获取成功"
        )
    except (ValidationError, AuthorizationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error getting student overall progress: {str(e)}")
        raise ValidationError("获取整体进度失败")


@api_v1.route('/progress/course/<int:course_id>/statistics', methods=['GET'])
@authenticate
@require_role('teacher')
def get_course_statistics(course_id):
    """获取课程统计信息"""
    try:
        username = request.current_user.get('username')
        
        # 获取课程统计
        result = progress_tracker.get_course_statistics(course_id)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_VIEW,
            user_id=username,
            details={
                "action": "view_course_statistics",
                "course_id": course_id
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result["data"],
            message=f"课程{course_id}的统计信息获取成功"
        )
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error getting course statistics: {str(e)}")
        raise ValidationError("获取课程统计失败")


@api_v1.route('/progress/student/performance', methods=['GET'])
@authenticate
def get_student_performance_trends():
    """获取学生表现趋势"""
    try:
        username = request.current_user.get('username')
        user_role = request.current_user.get('role')
        
        # 获取查询参数
        days = request.args.get('days', 30, type=int)
        
        # 只有学生可以查看自己的趋势，教师可以查看所有学生的趋势
        if user_role == 'student':
            student_id = request.current_user.get('user_id')
        elif user_role == 'teacher':
            # 教师需要指定学生ID
            student_id = request.args.get('student_id', type=int)
            if not student_id:
                raise ValidationError("教师必须指定学生ID", field='student_id')
        else:
            raise AuthorizationError("权限不足")
        
        # 获取表现趋势
        result = progress_tracker.get_student_performance_trends(student_id, days)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_VIEW,
            user_id=username,
            details={
                "action": "view_performance_trends",
                "student_id": student_id,
                "days": days
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result["data"],
            message=f"学生{student_id}最近{days}天的表现趋势获取成功"
        )
    except (ValidationError, AuthorizationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error getting student performance trends: {str(e)}")
        raise ValidationError("获取表现趋势失败")


@api_v1.route('/progress/course/<int:course_id>/performance', methods=['GET'])
@authenticate
@require_role('teacher')
def get_course_performance_trends(course_id):
    """获取课程表现趋势"""
    try:
        username = request.current_user.get('username')
        
        # 获取查询参数
        days = request.args.get('days', 30, type=int)
        
        # 获取课程表现趋势
        result = progress_tracker.get_course_performance_trends(course_id, days)
        
        if not result["success"]:
            raise NotFoundError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_VIEW,
            user_id=username,
            details={
                "action": "view_course_performance_trends",
                "course_id": course_id,
                "days": days
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result["data"],
            message=f"课程{course_id}最近{days}天的表现趋势获取成功"
        )
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error getting course performance trends: {str(e)}")
        raise ValidationError("获取课程表现趋势失败")

# 审计日志管理路由
@api_v1.route('/audit/logs', methods=['GET'])
@authenticate
@require_role('teacher')  # 只有教师和管理员可以查看审计日志
def get_audit_logs():
    """获取审计日志"""
    username = request.current_user.get('username')
    
    try:
        # 获取查询参数
        event_type = request.args.get('event_type')
        user_id = request.args.get('user_id')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # 转换日期参数
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                raise ValidationError("Invalid start_date format", field='start_date')
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                raise ValidationError("Invalid end_date format", field='end_date')
        
        # 转换事件类型
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = AuditEventType(event_type)
            except ValueError:
                raise ValidationError("Invalid event_type", field='event_type')
        
        # 获取审计日志
        result = audit_logger.get_audit_logs(
            event_type=event_type_enum,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            per_page=per_page
        )
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_EXPORT,
            user_id=username,
            details={
                "export_type": "audit_logs",
                "filters": {
                    "event_type": event_type,
                    "user_id": user_id,
                    "start_date": start_date_str,
                    "end_date": end_date_str
                }
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result,
            message="Audit logs retrieved successfully"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error getting audit logs: {str(e)}")
        raise ValidationError("Failed to get audit logs")

@api_v1.route('/audit/user-activity/<user_id>', methods=['GET'])
@authenticate
@require_role('teacher')  # 只有教师和管理员可以查看用户活动
def get_user_activity(user_id):
    """获取用户活动统计"""
    username = request.current_user.get('username')
    
    try:
        # 获取查询参数
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # 转换日期参数
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                raise ValidationError("Invalid start_date format", field='start_date')
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                raise ValidationError("Invalid end_date format", field='end_date')
        
        # 获取用户活动统计
        result = audit_logger.get_user_activity(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_EXPORT,
            user_id=username,
            details={
                "export_type": "user_activity",
                "target_user": user_id,
                "period": {
                    "start_date": start_date_str,
                    "end_date": end_date_str
                }
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result,
            message=f"User activity for {user_id} retrieved successfully"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error getting user activity for {user_id}: {str(e)}")
        raise ValidationError("Failed to get user activity")

@api_v1.route('/audit/system-stats', methods=['GET'])
@authenticate
@require_role('teacher')  # 只有教师和管理员可以查看系统统计
def get_system_stats():
    """获取系统统计信息"""
    username = request.current_user.get('username')
    
    try:
        # 获取查询参数
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # 转换日期参数
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                raise ValidationError("Invalid start_date format", field='start_date')
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                raise ValidationError("Invalid end_date format", field='end_date')
        
        # 获取系统统计信息
        result = audit_logger.get_system_stats(
            start_date=start_date,
            end_date=end_date
        )
        
        if not result["success"]:
            raise ValidationError(result["message"])
        
        # 记录审计日志
        audit_logger.log_audit_event(
            event_type=AuditEventType.DATA_EXPORT,
            user_id=username,
            details={
                "export_type": "system_stats",
                "period": {
                    "start_date": start_date_str,
                    "end_date": end_date_str
                }
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return success_response(
            data=result,
            message="System statistics retrieved successfully"
        )
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise ValidationError("Failed to get system stats")