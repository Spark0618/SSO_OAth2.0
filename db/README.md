# 教务数据库初始化（MySQL 版）

目前推荐使用 MySQL，已提供兼容脚本 `db/schema.mysql.sql`。

## 表设计
- `users`：账号/密码哈希/角色（student|teacher）。
- `students`、`teachers`：学生/教师档案，与 `users` 一对一。
- `courses`：课程，关联授课教师。
- `enrollments`：选课关系，含课程成绩；用于教师在课程管理页增删学生和改分。

## 在 MySQL 创建数据库
1. 安装 MySQL 服务（示例）：`sudo apt-get install -y mysql-server`
2. 创建库与账号（进入 `sudo mysql`）：  
   ```sql
   CREATE DATABASE academic CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'academic_user'@'localhost' IDENTIFIED BY '强密码';
   GRANT ALL PRIVILEGES ON academic.* TO 'academic_user'@'localhost';
   FLUSH PRIVILEGES;
   ```
3. 导入结构与示例数据（在仓库根目录执行）：  
   ```bash
   mysql -u academic_user -p academic < db/schema.mysql.sql
   ```
   请先将脚本中的 `REPLACE_ME_HASH` 替换为真实的密码哈希（如 bcrypt）。

## 其他数据库/SQLite
- 若继续用 SQLite，可使用 `db/schema.sql`，命令：`sqlite3 db/academic.db < db/schema.sql`。
- 迁移到 PostgreSQL 时，将自增/时间字段语法调整为 SERIAL/TIMESTAMP 等后再导入。
