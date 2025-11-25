# 教务数据库初始化

本方案使用 SQLite 作为轻量级演示存储，后续可平滑迁移到 MySQL/PostgreSQL。

## 表设计
- `users`：账号/密码哈希/角色（student|teacher）。
- `students`、`teachers`：学生/教师档案，与 `users` 一对一。
- `courses`：课程，关联授课教师。
- `enrollments`：选课关系，含课程成绩；用于教师在课程管理页增删学生和改分。

## 创建数据库
1. 安装 sqlite3（示例：`sudo apt-get install sqlite3`）。
2. 在项目根目录执行：  
   ```bash
   sqlite3 db/academic.db < db/schema.sql
   ```
3. 生成的数据库文件位于 `db/academic.db`。

## 迁移到其他数据库的提示
- 将 `schema.sql` 中的自增类型/时间默认值适配目标数据库（如改为 SERIAL/TIMESTAMP）。
- 创建用户/库并导入结构：`psql -f schema.sql` 或 `mysql < schema.sql` 等（注意语法差异）。
