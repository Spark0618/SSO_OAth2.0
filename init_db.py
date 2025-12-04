"""
数据库初始化脚本
创建必要的表结构 (MySQL 适配版)
"""

import os
import sys
from dotenv import load_dotenv

# 1. 强制指定 .env 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')
load_dotenv(env_path)

# 2. 检查环境变量
print("-" * 50)
print(f"正在加载 .env 文件: {env_path}")
db_url_from_env = os.getenv("DATABASE_URL")

if db_url_from_env:
    print(f"成功读取环境变量 DATABASE_URL: {db_url_from_env[:25]}...") 
else:
    print("ERROR: 未能读取到 DATABASE_URL！")
print("-" * 50)

from common import get_config_manager, get_database_manager, SecurityUtils

def create_tables(db_manager):
    """创建数据库表"""
    
    # 所有的 SQL 语句 (已修改为 MySQL 语法: AUTO_INCREMENT)
    queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('student', 'teacher', 'admin')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS papers (
            id INT PRIMARY KEY AUTO_INCREMENT,
            title VARCHAR(255) NOT NULL,
            abstract TEXT,
            author VARCHAR(100) NOT NULL,
            category VARCHAR(50),
            year INT,
            published_date DATE,
            view_count INT DEFAULT 0,
            created_by INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INT PRIMARY KEY AUTO_INCREMENT,
            paper_id INT NOT NULL,
            user_id INT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS files (
            id INT PRIMARY KEY AUTO_INCREMENT,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            file_size INT NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            description TEXT,
            tags VARCHAR(255),
            is_public BOOLEAN DEFAULT FALSE,
            access_count INT DEFAULT 0,
            download_count INT DEFAULT 0,
            uploaded_by INT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS file_permissions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            file_id INT NOT NULL,
            user_id INT NOT NULL,
            permission VARCHAR(20) NOT NULL CHECK (permission IN ('read', 'write', 'admin')),
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            granted_by INT,
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (granted_by) REFERENCES users(id),
            UNIQUE(file_id, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id VARCHAR(255) PRIMARY KEY,
            user_id INT NOT NULL,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        # 索引 (保持不变)
        "CREATE INDEX idx_users_username ON users(username)",
        "CREATE INDEX idx_users_email ON users(email)",
        "CREATE INDEX idx_papers_created_by ON papers(created_by)",
        "CREATE INDEX idx_papers_category ON papers(category)",
        "CREATE INDEX idx_comments_paper_id ON comments(paper_id)",
        "CREATE INDEX idx_comments_user_id ON comments(user_id)",
        "CREATE INDEX idx_files_uploaded_by ON files(uploaded_by)",
        "CREATE INDEX idx_files_file_type ON files(file_type)",
        "CREATE INDEX idx_file_permissions_file_id ON file_permissions(file_id)",
        "CREATE INDEX idx_file_permissions_user_id ON file_permissions(user_id)",
        "CREATE INDEX idx_sessions_user_id ON sessions(user_id)",
        "CREATE INDEX idx_sessions_expires_at ON sessions(expires_at)"
    ]

    for q in queries:
        try:
            # MySQL 创建索引时，如果索引已存在会报错，所以这里加个简单的异常处理或者忽略
            # 为了简单起见，我们假设是全新初始化。如果报错 "Duplicate key/index" 是正常的。
            db_manager.execute_query(q, fetch_all=False)
        except Exception as e:
            if "Duplicate key name" in str(e) or "Already exists" in str(e):
                pass # 索引已存在，忽略
            else:
                raise e

def get_hash_string(pwd_data):
    """处理密码哈希"""
    if isinstance(pwd_data, tuple):
        return pwd_data[0]
    return pwd_data

def create_default_data(db_manager):
    """创建默认数据"""
    
    # 1. 管理员
    raw_admin = SecurityUtils.hash_password("admin123")
    admin_password_hash = get_hash_string(raw_admin)
    
    try:
        db_manager.execute_query("""
            INSERT INTO users (id, username, email, password_hash, role)
            VALUES (1, 'admin', 'admin@example.com', :pwd, 'admin')
        """, {'pwd': admin_password_hash}, fetch_all=False)
        
        # 2. 教师
        raw_teacher = SecurityUtils.hash_password("teacher123")
        teacher_password_hash = get_hash_string(raw_teacher)
        
        db_manager.execute_query("""
            INSERT INTO users (id, username, email, password_hash, role)
            VALUES (2, 'teacher', 'teacher@example.com', :pwd, 'teacher')
        """, {'pwd': teacher_password_hash}, fetch_all=False)
        
        # 3. 学生
        raw_student = SecurityUtils.hash_password("student123")
        student_password_hash = get_hash_string(raw_student)
        
        db_manager.execute_query("""
            INSERT INTO users (id, username, email, password_hash, role)
            VALUES (3, 'student', 'student@example.com', :pwd, 'student')
        """, {'pwd': student_password_hash}, fetch_all=False)
        
        print("Default users created successfully")
    except Exception as e:
        if "Duplicate entry" in str(e) or "1062" in str(e):
            print("Users already exist, skipping.")
        else:
            print(f"Error creating default users: {e}")
            raise e

def main():
    """主函数"""
    target_db_url = os.getenv("DATABASE_URL")
    
    if not target_db_url:
        print("CRITICAL ERROR: 环境变量 DATABASE_URL 为空！")
        sys.exit(1)
        
    print(f"Connecting to database (FORCE ENV): {target_db_url}")
    
    db_manager = get_database_manager(target_db_url)
    
    try:
        print("Creating database tables...")
        create_tables(db_manager)
        print("Database tables created successfully")
        
        print("Creating default data...")
        create_default_data(db_manager)
        
        print("\nSUCCESS: Database initialization completed successfully on MySQL!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()