"""
数据库查询优化模块
提供查询优化、批量操作、连接池管理等功能
"""

import time
import logging
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from functools import wraps
from contextlib import contextmanager
from sqlalchemy import text, func, and_, or_, not_, desc, asc
from sqlalchemy.orm import sessionmaker, joinedload, selectinload, subqueryload
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.exc import SQLAlchemyError

from cache import get_default_cache_manager, cached, CACHE_KEYS, CACHE_TTL

# 设置日志
logger = logging.getLogger(__name__)


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self, session: Session, cache_manager=None):
        """
        初始化查询优化器
        
        Args:
            session: 数据库会话
            cache_manager: 缓存管理器
        """
        self.session = session
        self.cache_manager = cache_manager or get_default_cache_manager()
    
    def get_user_profile(self, user_id: int, use_cache: bool = True) -> Optional[Dict]:
        """
        获取用户档案（优化版本）
        
        Args:
            user_id: 用户ID
            use_cache: 是否使用缓存
            
        Returns:
            用户档案字典
        """
        cache_key = f"{CACHE_KEYS['user_profile']}{user_id}"
        
        if use_cache:
            cached_profile = self.cache_manager.get(cache_key)
            if cached_profile is not None:
                return cached_profile
        
        try:
            # 使用单个查询获取用户基本信息和角色信息
            user_query = text("""
                SELECT u.id, u.username, u.email, u.role, u.created_at, u.updated_at,
                       s.name as student_name, s.student_no, s.gender, s.hometown, 
                       s.grade, s.college, s.major,
                       t.name as teacher_name, t.employee_no, t.title, t.department
                FROM users u
                LEFT JOIN students s ON u.id = s.user_id
                LEFT JOIN teachers t ON u.id = t.user_id
                WHERE u.id = :user_id
            """)
            
            result = self.session.execute(user_query, {"user_id": user_id}).fetchone()
            
            if not result:
                return None
            
            profile = {
                "id": result.id,
                "username": result.username,
                "email": result.email,
                "role": result.role,
                "created_at": result.created_at.isoformat() if result.created_at else None,
                "updated_at": result.updated_at.isoformat() if result.updated_at else None
            }
            
            # 添加角色特定信息
            if result.role == "student" and result.student_name:
                profile["student_info"] = {
                    "name": result.student_name,
                    "student_no": result.student_no,
                    "gender": result.gender,
                    "hometown": result.hometown,
                    "grade": result.grade,
                    "college": result.college,
                    "major": result.major
                }
            elif result.role == "teacher" and result.teacher_name:
                profile["teacher_info"] = {
                    "name": result.teacher_name,
                    "employee_no": result.employee_no,
                    "title": result.title,
                    "department": result.department
                }
            
            if use_cache:
                self.cache_manager.set(cache_key, profile, CACHE_TTL['medium'])
            
            return profile
            
        except SQLAlchemyError as e:
            logger.error(f"获取用户档案失败: {str(e)}")
            return None
    
    def get_user_courses(self, user_id: int, role: str, use_cache: bool = True) -> List[Dict]:
        """
        获取用户课程列表（优化版本）
        
        Args:
            user_id: 用户ID
            role: 用户角色 (student/teacher)
            use_cache: 是否使用缓存
            
        Returns:
            课程列表
        """
        cache_key = f"{CACHE_KEYS['user_courses']}{user_id}:{role}"
        
        if use_cache:
            cached_courses = self.cache_manager.get(cache_key)
            if cached_courses is not None:
                return cached_courses
        
        try:
            if role == "student":
                query = text("""
                    SELECT c.id, c.code, c.title, c.description, c.day, c.slot, c.location,
                           c.teacher_id, t.name as teacher_name, e.grade, e.enrolled_at
                    FROM courses c
                    JOIN enrollments e ON c.id = e.course_id
                    JOIN students s ON e.student_id = s.id
                    LEFT JOIN teachers t ON c.teacher_id = t.id
                    WHERE s.user_id = :user_id
                    ORDER BY c.code
                """)
            else:  # teacher
                query = text("""
                    SELECT c.id, c.code, c.title, c.description, c.day, c.slot, c.location,
                           c.teacher_id, t.name as teacher_name, NULL as grade, NULL as enrolled_at
                    FROM courses c
                    JOIN teachers t ON c.teacher_id = t.id
                    WHERE t.user_id = :user_id
                    ORDER BY c.code
                """)
            
            results = self.session.execute(query, {"user_id": user_id}).fetchall()
            
            courses = []
            for result in results:
                course = {
                    "id": result.id,
                    "code": result.code,
                    "title": result.title,
                    "description": result.description,
                    "day": result.day,
                    "slot": result.slot,
                    "location": result.location,
                    "teacher_id": result.teacher_id,
                    "teacher_name": result.teacher_name
                }
                
                if role == "student":
                    course["grade"] = result.grade
                    course["enrolled_at"] = result.enrolled_at.isoformat() if result.enrolled_at else None
                
                courses.append(course)
            
            if use_cache:
                self.cache_manager.set(cache_key, courses, CACHE_TTL['medium'])
            
            return courses
            
        except SQLAlchemyError as e:
            logger.error(f"获取用户课程列表失败: {str(e)}")
            return []
    
    def get_course_students(self, course_id: int, use_cache: bool = True) -> List[Dict]:
        """
        获取课程学生列表（优化版本）
        
        Args:
            course_id: 课程ID
            use_cache: 是否使用缓存
            
        Returns:
            学生列表
        """
        cache_key = f"{CACHE_KEYS['course_students']}{course_id}"
        
        if use_cache:
            cached_students = self.cache_manager.get(cache_key)
            if cached_students is not None:
                return cached_students
        
        try:
            query = text("""
                SELECT s.id, s.name, s.student_no, s.gender, s.hometown, 
                       s.grade, s.college, s.major, e.grade as course_grade, e.enrolled_at
                FROM students s
                JOIN enrollments e ON s.id = e.student_id
                WHERE e.course_id = :course_id
                ORDER BY s.student_no
            """)
            
            results = self.session.execute(query, {"course_id": course_id}).fetchall()
            
            students = []
            for result in results:
                student = {
                    "id": result.id,
                    "name": result.name,
                    "student_no": result.student_no,
                    "gender": result.gender,
                    "hometown": result.hometown,
                    "grade": result.grade,
                    "college": result.college,
                    "major": result.major,
                    "course_grade": result.course_grade,
                    "enrolled_at": result.enrolled_at.isoformat() if result.enrolled_at else None
                }
                students.append(student)
            
            if use_cache:
                self.cache_manager.set(cache_key, students, CACHE_TTL['medium'])
            
            return students
            
        except SQLAlchemyError as e:
            logger.error(f"获取课程学生列表失败: {str(e)}")
            return []
    
    def get_course_announcements(self, course_id: int, use_cache: bool = True) -> List[Dict]:
        """
        获取课程公告列表（优化版本）
        
        Args:
            course_id: 课程ID
            use_cache: 是否使用缓存
            
        Returns:
            公告列表
        """
        cache_key = f"{CACHE_KEYS['course_announcements']}{course_id}"
        
        if use_cache:
            cached_announcements = self.cache_manager.get(cache_key)
            if cached_announcements is not None:
                return cached_announcements
        
        try:
            query = text("""
                SELECT a.id, a.title, a.content, a.created_at, a.updated_at, u.username
                FROM course_announcements a
                JOIN users u ON a.teacher_id = u.id
                WHERE a.course_id = :course_id
                ORDER BY a.created_at DESC
            """)
            
            results = self.session.execute(query, {"course_id": course_id}).fetchall()
            
            announcements = []
            for result in results:
                announcement = {
                    "id": result.id,
                    "title": result.title,
                    "content": result.content,
                    "created_at": result.created_at.isoformat() if result.created_at else None,
                    "updated_at": result.updated_at.isoformat() if result.updated_at else None,
                    "teacher_username": result.username
                }
                announcements.append(announcement)
            
            if use_cache:
                self.cache_manager.set(cache_key, announcements, CACHE_TTL['short'])
            
            return announcements
            
        except SQLAlchemyError as e:
            logger.error(f"获取课程公告列表失败: {str(e)}")
            return []
    
    def get_course_assignments(self, course_id: int, use_cache: bool = True) -> List[Dict]:
        """
        获取课程作业列表（优化版本）
        
        Args:
            course_id: 课程ID
            use_cache: 是否使用缓存
            
        Returns:
            作业列表
        """
        cache_key = f"{CACHE_KEYS['course_assignments']}{course_id}"
        
        if use_cache:
            cached_assignments = self.cache_manager.get(cache_key)
            if cached_assignments is not None:
                return cached_assignments
        
        try:
            query = text("""
                SELECT a.id, a.title, a.description, a.due_date, a.created_at, a.updated_at, 
                       a.max_score, u.username
                FROM assignments a
                JOIN users u ON a.teacher_id = u.id
                WHERE a.course_id = :course_id
                ORDER BY a.due_date ASC
            """)
            
            results = self.session.execute(query, {"course_id": course_id}).fetchall()
            
            assignments = []
            for result in results:
                assignment = {
                    "id": result.id,
                    "title": result.title,
                    "description": result.description,
                    "due_date": result.due_date.isoformat() if result.due_date else None,
                    "created_at": result.created_at.isoformat() if result.created_at else None,
                    "updated_at": result.updated_at.isoformat() if result.updated_at else None,
                    "max_score": result.max_score,
                    "teacher_username": result.username
                }
                assignments.append(assignment)
            
            if use_cache:
                self.cache_manager.set(cache_key, assignments, CACHE_TTL['short'])
            
            return assignments
            
        except SQLAlchemyError as e:
            logger.error(f"获取课程作业列表失败: {str(e)}")
            return []
    
    def get_assignment_submissions(self, assignment_id: int, use_cache: bool = True) -> List[Dict]:
        """
        获取作业提交列表（优化版本）
        
        Args:
            assignment_id: 作业ID
            use_cache: 是否使用缓存
            
        Returns:
            提交列表
        """
        cache_key = f"{CACHE_KEYS['assignment_submissions']}{assignment_id}"
        
        if use_cache:
            cached_submissions = self.cache_manager.get(cache_key)
            if cached_submissions is not None:
                return cached_submissions
        
        try:
            query = text("""
                SELECT s.id, s.student_id, s.submitted_at, s.score, s.feedback, s.file_path,
                       st.name as student_name, st.student_no
                FROM assignment_submissions s
                JOIN students st ON s.student_id = st.id
                WHERE s.assignment_id = :assignment_id
                ORDER BY s.submitted_at DESC
            """)
            
            results = self.session.execute(query, {"assignment_id": assignment_id}).fetchall()
            
            submissions = []
            for result in results:
                submission = {
                    "id": result.id,
                    "student_id": result.student_id,
                    "student_name": result.student_name,
                    "student_no": result.student_no,
                    "submitted_at": result.submitted_at.isoformat() if result.submitted_at else None,
                    "score": result.score,
                    "feedback": result.feedback,
                    "file_path": result.file_path
                }
                submissions.append(submission)
            
            if use_cache:
                self.cache_manager.set(cache_key, submissions, CACHE_TTL['short'])
            
            return submissions
            
        except SQLAlchemyError as e:
            logger.error(f"获取作业提交列表失败: {str(e)}")
            return []
    
    def get_student_progress(self, student_id: int, use_cache: bool = True) -> Dict:
        """
        获取学生学习进度（优化版本）
        
        Args:
            student_id: 学生ID
            use_cache: 是否使用缓存
            
        Returns:
            学习进度字典
        """
        cache_key = f"{CACHE_KEYS['student_progress']}{student_id}"
        
        if use_cache:
            cached_progress = self.cache_manager.get(cache_key)
            if cached_progress is not None:
                return cached_progress
        
        try:
            # 获取学生基本信息
            student_query = text("""
                SELECT s.name, s.student_no, s.grade, s.college, s.major
                FROM students s
                WHERE s.id = :student_id
            """)
            
            student_result = self.session.execute(student_query, {"student_id": student_id}).fetchone()
            
            if not student_result:
                return {}
            
            # 获取课程数量和成绩统计
            stats_query = text("""
                SELECT 
                    COUNT(*) as total_courses,
                    AVG(e.grade) as avg_grade,
                    MIN(e.grade) as min_grade,
                    MAX(e.grade) as max_grade,
                    COUNT(CASE WHEN e.grade >= 90 THEN 1 END) as excellent_count,
                    COUNT(CASE WHEN e.grade >= 80 AND e.grade < 90 THEN 1 END) as good_count,
                    COUNT(CASE WHEN e.grade >= 70 AND e.grade < 80 THEN 1 END) as average_count,
                    COUNT(CASE WHEN e.grade >= 60 AND e.grade < 70 THEN 1 END) as pass_count,
                    COUNT(CASE WHEN e.grade < 60 THEN 1 END) as fail_count
                FROM enrollments e
                WHERE e.student_id = :student_id AND e.grade IS NOT NULL
            """)
            
            stats_result = self.session.execute(stats_query, {"student_id": student_id}).fetchone()
            
            progress = {
                "student_info": {
                    "name": student_result.name,
                    "student_no": student_result.student_no,
                    "grade": student_result.grade,
                    "college": student_result.college,
                    "major": student_result.major
                },
                "course_stats": {
                    "total_courses": stats_result.total_courses or 0,
                    "avg_grade": float(stats_result.avg_grade) if stats_result.avg_grade else 0,
                    "min_grade": stats_result.min_grade,
                    "max_grade": stats_result.max_grade,
                    "grade_distribution": {
                        "excellent": stats_result.excellent_count or 0,
                        "good": stats_result.good_count or 0,
                        "average": stats_result.average_count or 0,
                        "pass": stats_result.pass_count or 0,
                        "fail": stats_result.fail_count or 0
                    }
                }
            }
            
            if use_cache:
                self.cache_manager.set(cache_key, progress, CACHE_TTL['long'])
            
            return progress
            
        except SQLAlchemyError as e:
            logger.error(f"获取学生学习进度失败: {str(e)}")
            return {}
    
    def get_course_stats(self, course_id: int, use_cache: bool = True) -> Dict:
        """
        获取课程统计信息（优化版本）
        
        Args:
            course_id: 课程ID
            use_cache: 是否使用缓存
            
        Returns:
            课程统计信息
        """
        cache_key = f"{CACHE_KEYS['course_stats']}{course_id}"
        
        if use_cache:
            cached_stats = self.cache_manager.get(cache_key)
            if cached_stats is not None:
                return cached_stats
        
        try:
            # 获取课程基本信息
            course_query = text("""
                SELECT c.code, c.title, c.description, t.name as teacher_name
                FROM courses c
                LEFT JOIN teachers t ON c.teacher_id = t.id
                WHERE c.id = :course_id
            """)
            
            course_result = self.session.execute(course_query, {"course_id": course_id}).fetchone()
            
            if not course_result:
                return {}
            
            # 获取学生统计
            stats_query = text("""
                SELECT 
                    COUNT(*) as total_students,
                    COUNT(CASE WHEN e.grade IS NOT NULL THEN 1 END) as graded_students,
                    AVG(e.grade) as avg_grade,
                    MIN(e.grade) as min_grade,
                    MAX(e.grade) as max_grade,
                    COUNT(CASE WHEN e.grade >= 90 THEN 1 END) as excellent_count,
                    COUNT(CASE WHEN e.grade >= 80 AND e.grade < 90 THEN 1 END) as good_count,
                    COUNT(CASE WHEN e.grade >= 70 AND e.grade < 80 THEN 1 END) as average_count,
                    COUNT(CASE WHEN e.grade >= 60 AND e.grade < 70 THEN 1 END) as pass_count,
                    COUNT(CASE WHEN e.grade < 60 THEN 1 END) as fail_count
                FROM enrollments e
                WHERE e.course_id = :course_id
            """)
            
            stats_result = self.session.execute(stats_query, {"course_id": course_id}).fetchone()
            
            # 获取作业统计
            assignment_query = text("""
                SELECT 
                    COUNT(*) as total_assignments,
                    COUNT(CASE WHEN a.due_date > NOW() THEN 1 END) as upcoming_assignments,
                    COUNT(CASE WHEN a.due_date <= NOW() THEN 1 END) as past_assignments
                FROM assignments a
                WHERE a.course_id = :course_id
            """)
            
            assignment_result = self.session.execute(assignment_query, {"course_id": course_id}).fetchone()
            
            stats = {
                "course_info": {
                    "code": course_result.code,
                    "title": course_result.title,
                    "description": course_result.description,
                    "teacher_name": course_result.teacher_name
                },
                "student_stats": {
                    "total_students": stats_result.total_students or 0,
                    "graded_students": stats_result.graded_students or 0,
                    "avg_grade": float(stats_result.avg_grade) if stats_result.avg_grade else 0,
                    "min_grade": stats_result.min_grade,
                    "max_grade": stats_result.max_grade,
                    "grade_distribution": {
                        "excellent": stats_result.excellent_count or 0,
                        "good": stats_result.good_count or 0,
                        "average": stats_result.average_count or 0,
                        "pass": stats_result.pass_count or 0,
                        "fail": stats_result.fail_count or 0
                    }
                },
                "assignment_stats": {
                    "total_assignments": assignment_result.total_assignments or 0,
                    "upcoming_assignments": assignment_result.upcoming_assignments or 0,
                    "past_assignments": assignment_result.past_assignments or 0
                }
            }
            
            if use_cache:
                self.cache_manager.set(cache_key, stats, CACHE_TTL['medium'])
            
            return stats
            
        except SQLAlchemyError as e:
            logger.error(f"获取课程统计信息失败: {str(e)}")
            return {}
    
    def invalidate_user_cache(self, user_id: int):
        """使用户相关缓存失效"""
        patterns = [
            f"{CACHE_KEYS['user_profile']}{user_id}",
            f"{CACHE_KEYS['user_courses']}{user_id}:*",
            f"{CACHE_KEYS['student_progress']}{user_id}"
        ]
        
        for pattern in patterns:
            keys = self.cache_manager.keys(pattern)
            if keys:
                self.cache_manager.delete_many(keys)
    
    def invalidate_course_cache(self, course_id: int):
        """使课程相关缓存失效"""
        patterns = [
            f"{CACHE_KEYS['course_students']}{course_id}",
            f"{CACHE_KEYS['course_announcements']}{course_id}",
            f"{CACHE_KEYS['course_assignments']}{course_id}",
            f"{CACHE_KEYS['course_stats']}{course_id}"
        ]
        
        for pattern in patterns:
            keys = self.cache_manager.keys(pattern)
            if keys:
                self.cache_manager.delete_many(keys)
    
    def invalidate_assignment_cache(self, assignment_id: int):
        """使作业相关缓存失效"""
        pattern = f"{CACHE_KEYS['assignment_submissions']}{assignment_id}"
        keys = self.cache_manager.keys(pattern)
        if keys:
            self.cache_manager.delete_many(keys)


def query_performance_logger(func):
    """
    查询性能日志装饰器
    
    Args:
        func: 被装饰的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        logger.info(f"查询 {func.__name__} 执行时间: {execution_time:.4f}秒")
        
        # 如果执行时间过长，记录警告
        if execution_time > 1.0:
            logger.warning(f"查询 {func.__name__} 执行时间过长: {execution_time:.4f}秒")
        
        return result
    
    return wrapper


@contextmanager
def db_session(session_factory):
    """
    数据库会话上下文管理器
    
    Args:
        session_factory: 会话工厂
        
    Yields:
        数据库会话
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库操作失败: {str(e)}")
        raise
    finally:
        session.close()


def batch_insert(session: Session, model_class, data_list: List[Dict], 
                batch_size: int = 1000) -> int:
    """
    批量插入数据
    
    Args:
        session: 数据库会话
        model_class: 模型类
        data_list: 数据列表
        batch_size: 批次大小
        
    Returns:
        插入的记录数
    """
    total_inserted = 0
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i + batch_size]
        session.bulk_insert_mappings(model_class, batch)
        total_inserted += len(batch)
    
    return total_inserted


def batch_update(session: Session, model_class, data_list: List[Dict], 
                batch_size: int = 1000) -> int:
    """
    批量更新数据
    
    Args:
        session: 数据库会话
        model_class: 模型类
        data_list: 数据列表
        batch_size: 批次大小
        
    Returns:
        更新的记录数
    """
    total_updated = 0
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i + batch_size]
        session.bulk_update_mappings(model_class, batch)
        total_updated += len(batch)
    
    return total_updated