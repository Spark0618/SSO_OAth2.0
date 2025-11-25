-- 教务系统示例数据库（SQLite）
-- 角色：学生、教师；支持课程管理与成绩修改

PRAGMA foreign_keys = ON;

-- 用户表：登录账户 + 角色
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('student', 'teacher')),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 学生档案
CREATE TABLE students (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  student_no TEXT NOT NULL UNIQUE,
  gender TEXT,
  hometown TEXT,
  grade TEXT,
  college TEXT,
  major TEXT
);

-- 教师档案
CREATE TABLE teachers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  employee_no TEXT NOT NULL UNIQUE,
  title TEXT,
  department TEXT
);

-- 课程表（教师任课）
CREATE TABLE courses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  description TEXT
);

-- 选课/任课关联，含成绩
CREATE TABLE enrollments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  grade TEXT, -- 课程得分，可由教师修改
  UNIQUE(course_id, student_id)
);

-- 便于查询教师的任课列表
CREATE INDEX idx_courses_teacher ON courses(teacher_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
CREATE INDEX idx_enrollments_student ON enrollments(student_id);

-- 示例数据（密码需替换为真实哈希；此处仅为占位）
INSERT INTO users (username, password_hash, role) VALUES
  ('student01', 'REPLACE_ME_HASH', 'student'),
  ('student02', 'REPLACE_ME_HASH', 'student'),
  ('teacher01', 'REPLACE_ME_HASH', 'teacher');

INSERT INTO students (user_id, name, student_no, gender, hometown, grade, college, major) VALUES
  (1, '张三', '2021123456', '男', '北京', '2021级', '计算机与通信工程学院', '计算机科学与技术'),
  (2, '李四', '2021123457', '女', '上海', '2021级', '计算机与通信工程学院', '软件工程');

INSERT INTO teachers (user_id, name, employee_no, title, department) VALUES
  (3, '王老师', 'T2021001', '副教授', '计算机与通信工程学院');

INSERT INTO courses (code, title, teacher_id, description) VALUES
  ('CS101', '程序设计基础', 1, 'C 语言与程序设计入门'),
  ('DS150', '数据结构', 1, '线性表、树、图及算法分析');

INSERT INTO enrollments (course_id, student_id, grade) VALUES
  (1, 1, 'A-'),
  (1, 2, 'B+'),
  (2, 1, 'A');

-- 使用说明：
-- 1) 安装 sqlite3：sudo apt-get install sqlite3（或等效方式）
-- 2) 在项目根目录执行：sqlite3 db/academic.db < db/schema.sql
-- 3) 启动后端时，将数据库文件路径配置到应用（后续代码适配时使用）
