"""
扩展的数据库模型，添加更多业务实体和关系
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

# 多对多关系表
# 学生和课程的多对多关系（已存在于enrollments表中，这里为了完整性保留）
# enrollment_association = Table(
#     'enrollments', Base.metadata,
#     Column('id', Integer, primary_key=True),
#     Column('student_id', Integer, ForeignKey('students.id')),
#     Column('course_id', Integer, ForeignKey('courses.id')),
#     Column('grade', String(10)),
#     Column('enrolled_at', DateTime, default=datetime.utcnow)
# )

# 课程公告的多对多关系（公告可以关联多个课程）
announcement_course_association = Table(
    'announcement_courses', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('announcement_id', Integer, ForeignKey('course_announcements.id')),
    Column('course_id', Integer, ForeignKey('courses.id'))
)

# 课程资源的标签多对多关系
resource_tag_association = Table(
    'resource_tags', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('resource_id', Integer, ForeignKey('course_resources.id')),
    Column('tag_id', Integer, ForeignKey('resource_tags.id'))
)

# 用户模型（扩展）
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # student, teacher, admin
    email = Column(String(100))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # 关系
    student_profile = relationship("Student", back_populates="user", uselist=False)
    teacher_profile = relationship("Teacher", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")
    login_logs = relationship("LoginLog", back_populates="user")

# 学生模型（扩展）
class Student(Base):
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    student_no = Column(String(20), unique=True, nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    gender = Column(String(10))
    birth_date = Column(DateTime)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    major = Column(String(100))
    department = Column(String(100))
    grade = Column(String(20))  # 年级
    class_name = Column(String(50))  # 班级
    advisor_id = Column(Integer, ForeignKey('teachers.id'))
    status = Column(String(20), default='active')  # active, suspended, graduated
    
    # 关系
    user = relationship("User", back_populates="student_profile")
    enrollments = relationship("Enrollment", back_populates="student")
    advisor = relationship("Teacher", back_populates="advisees")
    assignment_submissions = relationship("AssignmentSubmission", back_populates="student")
    study_logs = relationship("StudyLog", back_populates="student")

# 教师模型（扩展）
class Teacher(Base):
    __tablename__ = 'teachers'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    teacher_no = Column(String(20), unique=True, nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    gender = Column(String(10))
    birth_date = Column(DateTime)
    hire_date = Column(DateTime, default=datetime.utcnow)
    department = Column(String(100))
    title = Column(String(50))  # 职称
    office = Column(String(100))
    research_interests = Column(Text)
    status = Column(String(20), default='active')  # active, suspended, resigned
    
    # 关系
    user = relationship("User", back_populates="teacher_profile")
    courses = relationship("Course", back_populates="teacher")
    advisees = relationship("Student", back_populates="advisor")
    announcements = relationship("CourseAnnouncement", back_populates="teacher")
    assignments = relationship("Assignment", back_populates="teacher")
    resources = relationship("CourseResource", back_populates="teacher")

# 课程模型（扩展）
class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    credits = Column(Integer, default=3)
    hours = Column(Integer, default=48)  # 总课时
    semester = Column(String(20))  # 学期，如2023-2024-1
    year = Column(Integer)  # 学年
    day = Column(Integer)  # 上课星期几，1-7
    slot = Column(Integer)  # 上课节次，1-12
    location = Column(String(100))
    max_students = Column(Integer, default=50)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    teacher = relationship("Teacher", back_populates="courses")
    enrollments = relationship("Enrollment", back_populates="course")
    announcements = relationship("CourseAnnouncement", secondary=announcement_course_association, back_populates="courses")
    assignments = relationship("Assignment", back_populates="course")
    resources = relationship("CourseResource", back_populates="course")
    schedules = relationship("CourseSchedule", back_populates="course")

# 选课记录模型（扩展）
class Enrollment(Base):
    __tablename__ = 'enrollments'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    course_id = Column(Integer, ForeignKey('courses.id'))
    grade = Column(String(10))
    status = Column(String(20), default='active')  # active, dropped, completed
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    dropped_at = Column(DateTime)
    
    # 关系
    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")

# 课程公告模型
class CourseAnnouncement(Base):
    __tablename__ = 'course_announcements'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    is_pinned = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)  # 是否公开，非公开只有选课学生可见
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    teacher = relationship("Teacher", back_populates="announcements")
    courses = relationship("Course", secondary=announcement_course_association, back_populates="announcements")

# 课程作业模型
class Assignment(Base):
    __tablename__ = 'assignments'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    course_id = Column(Integer, ForeignKey('courses.id'))
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    max_score = Column(Float, default=100.0)
    due_date = Column(DateTime)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    course = relationship("Course", back_populates="assignments")
    teacher = relationship("Teacher", back_populates="assignments")
    submissions = relationship("AssignmentSubmission", back_populates="assignment")
    resources = relationship("AssignmentResource", back_populates="assignment")

# 作业提交模型
class AssignmentSubmission(Base):
    __tablename__ = 'assignment_submissions'
    
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey('assignments.id'))
    student_id = Column(Integer, ForeignKey('students.id'))
    content = Column(Text)
    score = Column(Float)
    feedback = Column(Text)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    graded_at = Column(DateTime)
    is_late = Column(Boolean, default=False)
    
    # 关系
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("Student", back_populates="assignment_submissions")
    files = relationship("SubmissionFile", back_populates="submission")

# 提交文件模型
class SubmissionFile(Base):
    __tablename__ = 'submission_files'
    
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('assignment_submissions.id'))
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    submission = relationship("AssignmentSubmission", back_populates="files")

# 课程资源模型
class CourseResource(Base):
    __tablename__ = 'course_resources'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    course_id = Column(Integer, ForeignKey('courses.id'))
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    file_path = Column(String(500))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    is_public = Column(Boolean, default=True)
    download_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    course = relationship("Course", back_populates="resources")
    teacher = relationship("Teacher", back_populates="resources")
    tags = relationship("ResourceTag", secondary=resource_tag_association, back_populates="resources")

# 资源标签模型
class ResourceTag(Base):
    __tablename__ = 'resource_tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(7), default="#007bff")  # 十六进制颜色代码
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    resources = relationship("CourseResource", secondary=resource_tag_association, back_populates="tags")

# 作业资源模型
class AssignmentResource(Base):
    __tablename__ = 'assignment_resources'
    
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey('assignments.id'))
    title = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    assignment = relationship("Assignment", back_populates="resources")

# 课程时间表模型
class CourseSchedule(Base):
    __tablename__ = 'course_schedules'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    day = Column(Integer, nullable=False)  # 1-7，星期一到星期日
    slot = Column(Integer, nullable=False)  # 1-12，节次
    location = Column(String(100))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_recurring = Column(Boolean, default=True)  # 是否重复
    
    # 关系
    course = relationship("Course", back_populates="schedules")

# 通知模型
class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    title = Column(String(200), nullable=False)
    content = Column(Text)
    type = Column(String(50), nullable=False)  # system, course, assignment, announcement
    related_id = Column(Integer)  # 相关实体ID，如课程ID、作业ID等
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="notifications")

# 登录日志模型
class LoginLog(Base):
    __tablename__ = 'login_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    ip_address = Column(String(45))  # 支持IPv6
    user_agent = Column(Text)
    login_time = Column(DateTime, default=datetime.utcnow)
    is_successful = Column(Boolean, default=True)
    
    # 关系
    user = relationship("User", back_populates="login_logs")

# 学习日志模型
class StudyLog(Base):
    __tablename__ = 'study_logs'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    course_id = Column(Integer, ForeignKey('courses.id'))
    activity_type = Column(String(50), nullable=False)  # view, download, submit, etc.
    details = Column(Text)  # 活动详情，JSON格式
    duration = Column(Integer)  # 活动持续时间，秒
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    student = relationship("Student", back_populates="study_logs")
    course = relationship("Course")

# 选课申请模型
class EnrollmentRequest(Base):
    __tablename__ = 'enrollment_requests'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    course_id = Column(Integer, ForeignKey('courses.id'))
    reason = Column(Text)
    status = Column(String(20), default='pending')  # pending, approved, rejected
    processed_by = Column(Integer, ForeignKey('teachers.id'))
    processed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    student = relationship("Student")
    course = relationship("Course")
    processor = relationship("Teacher")

# 系统配置模型
class SystemConfig(Base):
    __tablename__ = 'system_configs'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(Text)
    is_public = Column(Boolean, default=False)  # 是否对前端公开
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 创建所有表
def create_tables(engine):
    """创建所有表"""
    Base.metadata.create_all(engine)