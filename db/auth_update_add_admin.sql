-- 运行命令
-- mysql -u academic_user -p academic < db/auth_update_add_admin.sql 
-- 更新数据库结构
ALTER TABLE users MODIFY COLUMN role ENUM('student', 'teacher', 'admin') NOT NULL;