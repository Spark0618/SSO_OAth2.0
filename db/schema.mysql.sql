-- 教务系统示例数据库（MySQL 兼容版）
-- 角色：学生、教师；支持课程管理与成绩修改

SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- 用户表：登录账户 + 角色
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('student','teacher', 'admin') NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 学生档案
CREATE TABLE students (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  student_no VARCHAR(50) NOT NULL UNIQUE,
  gender VARCHAR(20),
  hometown VARCHAR(100),
  grade VARCHAR(50),
  college VARCHAR(100),
  major VARCHAR(100),
  CONSTRAINT fk_student_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 教师档案
CREATE TABLE teachers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  employee_no VARCHAR(50) NOT NULL UNIQUE,
  title VARCHAR(50),
  department VARCHAR(100),
  CONSTRAINT fk_teacher_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 课程表（教师任课）
CREATE TABLE courses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE,
  title VARCHAR(200) NOT NULL,
  teacher_id INT NOT NULL,
  description TEXT,
  day TINYINT,
  slot TINYINT,
  location VARCHAR(100),
  CONSTRAINT fk_course_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 选课/任课关联，含成绩
CREATE TABLE enrollments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  course_id INT NOT NULL,
  student_id INT NOT NULL,
  grade VARCHAR(20),
  UNIQUE KEY uniq_enrollment (course_id, student_id),
  CONSTRAINT fk_enroll_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
  CONSTRAINT fk_enroll_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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
