# 系统安装与测试指南

本指南将帮助您完成系统的安装、配置和测试，即使您是编程新手也能轻松跟随。

## 目录

1. [Python库安装](#python库安装)
2. [额外软件和工具安装](#额外软件和工具安装)
3. [详细测试流程](#详细测试流程)

## Python库安装

### 1. 打开命令提示符或PowerShell

- 在Windows中，按`Win + R`键，输入`cmd`或`powershell`，然后按回车
- 或者右键点击"开始"按钮，选择"命令提示符"或"Windows PowerShell"

### 2. 导航到项目目录

```bash
cd e:\数认实验\SSO_OAth2.0-academic1.0\SSO_OAth2.0-academic1.0
```

### 3. 激活虚拟环境（如果已创建）

```bash
venv\Scripts\activate
```

如果看到命令提示符前面出现`(venv)`，表示虚拟环境已激活。

### 4. 安装所有必需的Python库

执行以下命令安装所有必需的库：

```bash
pip install -r requirements.txt
```

如果您想了解具体安装了哪些库，以下是主要库的单独安装命令：

```bash
# Web框架
pip install Flask==2.3.3
pip install Flask-SocketIO==5.3.6
pip install Flask-JWT-Extended==4.5.2
pip install Flask-Limiter==3.5.0
pip install Flask-CORS==4.0.0
pip install Flask-Session==0.5.0
pip install Werkzeug==2.3.7

# Socket.IO
pip install python-socketio==5.9.0
pip install eventlet==0.33.3

# 数据库
pip install SQLAlchemy==2.0.30
pip install Flask-SQLAlchemy==3.0.5
pip install alembic==1.12.0
pip install psycopg2-binary==2.9.7
pip install PyMySQL==1.1.0

# 缓存和会话
pip install redis==5.0.0

# 认证和安全
pip install PyJWT==2.8.0
pip install cryptography==41.0.4
pip install passlib==1.7.4
pip install bcrypt==4.0.1

# 文件处理
pip install Pillow==10.0.1
pip install python-magic==0.4.27
pip install boto3==1.28.57
pip install azure-storage-blob==12.19.0
pip install google-cloud-storage==2.10.0

# 数据验证和序列化
pip install marshmallow==3.20.1
pip install jsonschema==4.19.0
pip install email-validator==2.0.0

# 日志和监控
pip install structlog==23.1.0
pip install prometheus-client==0.17.1

# 测试
pip install pytest==7.4.2
pip install pytest-flask==1.2.0
pip install pytest-cov==4.1.0
pip install factory-boy==3.3.0
pip install faker==19.6.2

# 开发工具
pip install black==23.9.1
pip install flake8==6.1.0
pip install isort==5.12.0
pip install mypy==1.5.1

# 其他工具
pip install python-dotenv==1.0.0
pip install click==8.1.7
pip install requests==2.31.0
pip install urllib3==2.0.5
pip install certifi==2023.7.22
pip install idna==3.4
pip install chardet==5.2.0
```

### 5. 验证安装

执行以下命令验证主要库是否安装成功：

```bash
python -c "import flask, sqlalchemy, requests, pytest; print('所有主要库安装成功')"
```

如果看到"所有主要库安装成功"的消息，表示安装正常。

## 额外软件和工具安装

除了Python环境和MySQL数据库外，您还需要安装以下软件：

### 1. Git（版本控制工具）

虽然不是必需的，但建议安装Git用于版本控制：

- 下载地址：https://git-scm.com/download/win
- 下载后运行安装程序，使用默认设置即可

### 2. Redis（缓存服务器）

Redis用于缓存和会话存储：

- 下载地址：https://github.com/microsoftarchive/redis/releases
- 下载`.msi`文件（如`Redis-x64-3.0.504.msi`）
- 运行安装程序，使用默认设置
- 安装后，Redis服务会自动启动

### 3. MySQL数据库

如果您尚未安装MySQL：

- 下载地址：https://dev.mysql.com/downloads/mysql/
- 选择"MySQL Community Server"
- 下载适合您系统的安装程序
- 运行安装程序，设置root密码（请记住此密码）

### 4. 代码编辑器（可选）

推荐安装Visual Studio Code：

- 下载地址：https://code.visualstudio.com/
- 安装后，可以安装Python扩展以获得更好的开发体验

### 5. 浏览器

确保您安装了现代浏览器（Chrome、Firefox或Edge）用于前端测试。

## 详细测试流程

### 准备工作

#### 1. 创建数据库

打开MySQL命令行客户端（或使用MySQL Workbench）：

```sql
CREATE DATABASE academic_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### 2. 配置数据库连接

在项目根目录创建`.env`文件（如果不存在），添加以下内容：

```
DATABASE_URL=mysql+pymysql://root:你的密码@localhost/academic_system
```

将"你的密码"替换为您设置的MySQL root密码。

#### 3. 初始化数据库

在命令提示符中执行：

```bash
python init_db.py
```

预期结果：
```
Default users created successfully
数据库初始化完成
```

### 测试步骤

#### 步骤1：启动服务

##### 方法A：使用脚本启动所有服务

```bash
python start_services.py
```

预期结果：
```
============================================================
 启动所有服务
============================================================
启动 认证服务器 (auth-server)...
✓ 认证服务器 已启动 (PID: 12345)
启动 学术API服务 (academic-api)...
✓ 学术API服务 已启动 (PID: 12346)
启动 云盘API服务 (cloud-api)...
✓ 云盘API服务 已启动 (PID: 12347)

检查服务状态...
✓ 认证服务器 正在运行 (PID: 12345)
✓ 学术API服务 正在运行 (PID: 12346)
✓ 云盘API服务 正在运行 (PID: 12347)
```

##### 方法B：手动启动每个服务（用于调试）

打开三个命令提示符窗口，分别执行：

窗口1：
```bash
python auth-server/app_refactored.py
```

窗口2：
```bash
python academic-api/app_refactored.py
```

窗口3：
```bash
python cloud-api/app_refactored.py
```

每个窗口应显示类似以下内容：
```
* Running on http://localhost:5000
```

#### 步骤2：运行单元测试

```bash
python -m pytest tests/ -v
```

预期结果：
```
============================= test session starts =============================
collected 6 items

tests/test_common.py::TestConfigManager::test_load_config PASSED
tests/test_common.py::TestSecurityUtils::test_hash_password PASSED
tests/test_common.py::TestSecurityUtils::test_verify_password PASSED
tests/test_common.py::TestRateLimiter::test_is_allowed PASSED
tests/test_common.py::TestDatabaseManager::test_get_connection PASSED
tests/test_common.py::TestFileProcessor::test_validate_file_type PASSED

============================== 6 passed in ...s ==============================
```

可能遇到的问题及解决方法：

1. **问题**：`ModuleNotFoundError: No module named 'pytest'`
   - **解决**：执行`pip install pytest`

2. **问题**：`ImportError: cannot import name 'SecurityUtils'`
   - **解决**：确保您在项目根目录执行命令，并且common目录存在

#### 步骤3：运行系统测试

```bash
python test_system.py
```

预期结果：
```
开始系统测试...
请确保所有服务已启动:
- auth-server (端口 5000)
- academic-api (端口 5001)
- cloud-api (端口 5002)

按Enter键开始测试...

=== 测试健康检查端点 ===
✓ auth 健康检查
✓ academic 健康检查
✓ cloud 健康检查

=== 测试认证服务 ===
✓ 用户注册
✓ 用户登录
✓ 令牌验证
✓ 获取用户信息

=== 测试学术服务 ===
✓ 获取论文列表（未认证）
✓ 获取论文列表（已认证）
✓ 获取论文分类
✓ 创建论文

=== 测试云存储服务 ===
✓ 获取文件列表
✓ 获取文件类型

=== 测试结果摘要 ===
总测试数: 12
通过: 12
失败: 0
成功率: 100.0%
```

可能遇到的问题及解决方法：

1. **问题**：`Connection refused`
   - **解决**：确保所有服务已正确启动，检查端口是否被占用

2. **问题**：测试失败，显示401未授权
   - **解决**：这是正常的，某些测试预期会返回401

#### 步骤4：运行性能测试

```bash
python test_performance.py
```

预期结果：
```
开始性能测试...
请确保所有服务已启动:
- auth-server (端口 5000)
- academic-api (端口 5001)
- cloud-api (端口 5002)

按Enter键开始测试...

=== 认证服务性能测试 ===
测试端点: 健康检查
  成功率: 100.00%
  平均响应时间: 12.34ms
  95%响应时间: 20.56ms
  每秒请求数: 81.02

测试端点: 令牌验证
  成功率: 100.00%
  平均响应时间: 25.67ms
  95%响应时间: 45.89ms
  每秒请求数: 38.95

...

=== 性能测试摘要 ===
...
```

可能遇到的问题及解决方法：

1. **问题**：测试超时
   - **解决**：系统负载可能过高，可以稍后重试

#### 步骤5：运行数据库分析

```bash
python analyze_database.py
```

预期结果：
```
开始数据库分析...

=== 数据库分析摘要 ===
表数量: 6
总行数: 15
总索引数: 12
优化建议数: 3

数据库分析报告已保存到 database_analysis.md
```

可能遇到的问题及解决方法：

1. **问题**：`sqlite3.OperationalError: no such table`
   - **解决**：确保已执行`python init_db.py`初始化数据库

#### 步骤6：运行安全分析

```bash
python analyze_security.py
```

预期结果：
```
开始安全与性能分析...
找到 15 个文件进行分析
分析完成，发现 2 个安全问题，3 个性能问题
分析报告已保存到 security_analysis.md

=== 分析摘要 ===
安全问题: 2 个
  - 高严重程度: 0 个
  - 中严重程度: 2 个
  - 低严重程度: 0 个
性能问题: 3 个
```

#### 步骤7：运行综合测试（一键执行所有测试）

```bash
python run_comprehensive_tests.py
```

预期结果：
```
开始综合测试...
检查先决条件...
Python版本: Python 3.9.7

运行单元测试...
...

运行系统测试...
...

运行性能测试...
...

运行数据库分析...
...

运行安全分析...
...

生成综合报告...
综合报告已保存到 comprehensive_test_report.md
测试结果已保存到 test_results.json

============================================================
测试完成!
============================================================
总测试数: 5
通过: 5
失败: 0
成功率: 100.0%
总测试时间: 125.34 秒
```

### 测试报告解读

测试完成后，您可以在项目根目录找到以下报告文件：

1. **comprehensive_test_report.md** - 综合测试报告
2. **database_analysis.md** - 数据库分析报告
3. **security_analysis.md** - 安全分析报告
4. **test_results.json** - 测试结果JSON数据

### 常见问题与解决方法

#### 1. 端口冲突

**问题**：`Address already in use`

**解决**：
- 查找占用端口的进程：`netstat -ano | findstr :5000`
- 终止进程：`taskkill /PID 进程ID /F`
- 或者修改服务端口（在app_refactored.py中）

#### 2. 数据库连接失败

**问题**：`Can't connect to MySQL server`

**解决**：
- 确保MySQL服务已启动
- 检查.env文件中的数据库连接字符串
- 确认数据库用户名和密码正确

#### 3. Redis连接失败

**问题**：`Redis connection failed`

**解决**：
- 确保Redis服务已启动
- 检查Redis配置（默认端口6379）
- 如果不使用Redis，可以修改配置禁用缓存

#### 4. 模块导入错误

**问题**：`ModuleNotFoundError: No module named 'xxx'`

**解决**：
- 确保虚拟环境已激活
- 执行`pip install xxx`安装缺失的模块
- 检查requirements.txt是否包含所有依赖

#### 5. 测试失败

**问题**：测试用例失败

**解决**：
- 查看详细错误信息
- 检查服务是否正常启动
- 确认数据库是否正确初始化
- 查看测试报告了解具体失败原因

### 高级测试选项

#### 1. 生成测试覆盖率报告

```bash
python -m pytest tests/ --cov=common --cov-report=html
```

报告将生成在`htmlcov`目录中，打开`index.html`查看详细覆盖率。

#### 2. 运行特定测试

```bash
# 运行特定测试文件
python -m pytest tests/test_common.py

# 运行特定测试类
python -m pytest tests/test_common.py::TestSecurityUtils

# 运行特定测试方法
python -m pytest tests/test_common.py::TestSecurityUtils::test_hash_password
```

#### 3. 性能测试自定义参数

编辑`test_performance.py`文件，修改以下参数：

```python
# 修改请求数量
num_requests = 100  # 默认50

# 修改并发级别
concurrency_levels = [5, 10, 20, 50]  # 默认值
```

### 总结

按照本指南，您应该能够：

1. 成功安装所有必需的Python库和额外软件
2. 正确初始化和配置系统
3. 运行各种测试验证系统功能
4. 解读测试报告并解决常见问题

如果您在测试过程中遇到其他问题，请参考各测试脚本中的详细错误信息，或者查看生成的测试报告获取更多帮助。
  "refresh_token": "refresh-token",
  "expires_in": 300,
  "username": "student01"
}
```

### 3. 学术API测试

#### 3.1 获取会话状态
```bash
curl.exe -k -X GET https://academic.localhost:5001/api/v1/session/status -b cookies.txt
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "logged_in": true,
    "username": "student01",
    "role": "student"
  }
}
```

#### 3.2 获取课程列表
```bash
curl.exe -k -X GET https://academic.localhost:5001/api/v1/courses -b cookies.txt
```

**预期响应**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "code": "CS101",
      "title": "程序设计基础",
      "description": "C语言与程序设计入门",
      "teacher": "王老师",
      "credits": 3,
      "day": 1,
      "slot": 1,
      "location": "一教101"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 1
  }
}
```

#### 3.3 学生选课
```bash
curl.exe -k -X POST https://academic.localhost:5001/api/v1/courses/CS101/enroll -b cookies.txt
```

**预期响应**:
```json
{
  "success": true,
  "message": "Successfully enrolled in course CS101"
}
```

#### 3.4 获取学生成绩
```bash
curl.exe -k -X GET https://academic.localhost:5001/api/v1/grades -b cookies.txt
```

**预期响应**:
```json
{
  "success": true,
  "data": [
    {
      "course_code": "CS101",
      "course_title": "程序设计基础",
      "grade": "A-",
      "credits": 3,
      "semester": "2023-2024-1"
    }
  ]
}
```

#### 3.5 获取课程公告
```bash
curl.exe -k -X GET https://academic.localhost:5001/api/v1/courses/CS101/announcements -b cookies.txt
```

**预期响应**:
```json
{
  "success": true,
  "data": [
    {
      "id": "ann_1234567890",
      "title": "期中考试通知",
      "content": "期中考试将于下周三举行...",
      "author": "王老师",
      "priority": "high",
      "created_at": "2023-10-15T10:00:00",
      "updated_at": "2023-10-15T10:00:00"
    }
  ]
}
```

#### 3.6 创建课程公告（教师权限）
```bash
curl.exe --% -k -X POST https://academic.localhost:5001/api/v1/courses/CS101/announcements -b cookies.txt -H "Content-Type: application/json" -d "{\"title\": \"期中考试通知\", \"content\": \"期中考试将于下周三举行\", \"priority\": \"high\"}"
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "id": "ann_1234567890",
    "title": "期中考试通知",
    "content": "期中考试将于下周三举行，请同学们做好准备。",
    "author": "teacher01",
    "priority": "high",
    "created_at": "2023-10-15T10:00:00",
    "updated_at": "2023-10-15T10:00:00"
  }
}
```

#### 3.7 更新课程公告（教师权限）
```bash
curl.exe --% -k -X PUT https://academic.localhost:5001/api/v1/courses/CS101/announcements/ann_1234567890 -b cookies.txt -H "Content-Type: application/json" -d "{\"title\": \"期中考试通知（更新）\", \"content\": \"内容...\", \"priority\": \"high\"}"
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "id": "ann_1234567890",
    "title": "期中考试通知（更新）",
    "content": "期中考试将于下周三下午2点举行，请同学们做好准备。",
    "author": "teacher01",
    "priority": "high",
    "created_at": "2023-10-15T10:00:00",
    "updated_at": "2023-10-16T09:00:00"
  }
}
```

#### 3.8 删除课程公告（教师权限）
```bash
curl.exe -k -X DELETE https://academic.localhost:5001/api/v1/courses/CS101/announcements/ann_1234567890 -b cookies.txt
```

**预期响应**:
```json
{
  "success": true,
  "message": "Announcement deleted successfully"
}
```

#### 3.9 获取课程作业
```bash
curl.exe -k -X GET https://academic.localhost:5001/api/v1/courses/CS101/assignments \
  -b cookies.txt
```

**预期响应**:
```json
{
  "success": true,
  "data": [
    {
      "id": "assign_1234567890",
      "title": "第一次作业",
      "description": "完成教材第1-3章的习题...",
      "due_date": "2023-10-20T23:59:59",
      "max_score": 100,
      "is_published": true
    }
  ]
}
```

### 4. 云盘API测试

#### 4.1 获取文件列表
```bash
curl -k -X GET https://cloud.localhost:5002/files \
  -b cookies.txt
```

**预期响应**:
```json
{
  "user": "student01",
  "files": [
    {
      "name": "通告.txt",
      "size": "2KB",
      "uploaded_at": "2024-06-01"
    }
  ]
}
```

#### 4.2 上传文件
```bash
curl -k -X POST https://cloud.localhost:5002/files \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "name": "新文档.txt",
    "size": "5KB"
  }'
```

**预期响应**:
```json
{
  "message": "uploaded",
  "files": [
    {
      "name": "通告.txt",
      "size": "2KB",
      "uploaded_at": "2024-06-01"
    },
    {
      "name": "新文档.txt",
      "size": "5KB",
      "uploaded_at": "2024-06-15"
    }
  ],
  "user": "student01"
}
```

### 5. 错误处理测试

#### 5.1 认证错误测试
```bash
# 错误的用户名或密码
curl -k -X POST https://auth.localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "wronguser",
    "password": "wrongpass"
  }'
```

**预期响应**:
```json
{
  "error": "invalid credentials"
}
```

#### 5.2 授权错误测试
```bash
# 未登录访问受保护资源
curl -k -X GET https://academic.localhost:5001/api/v1/courses
```

**预期响应**:
```json
{
  "error": "unauthorized"
}
```

#### 5.3 权限错误测试
```bash
# 学生尝试创建课程公告
curl -k -X POST https://academic.localhost:5001/api/v1/courses/CS101/announcements \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "title": "测试公告",
    "content": "这是一条测试公告"
  }'
```

**预期响应**:
```json
{
  "error": "insufficient permissions"
}
```

#### 5.4 输入验证错误测试
```bash
# 无效的课程代码
curl -k -X POST https://academic.localhost:5001/api/v1/courses/INVALID_CODE/enroll \
  -b cookies.txt
```

**预期响应**:
```json
{
  "error": "Invalid course code",
  "field": "course_code"
}
```

### 6. 安全测试

#### 6.1 SQL注入测试
```bash
# 尝试SQL注入
curl -k -X GET "https://academic.localhost:5001/api/v1/courses?code=CS101' OR '1'='1" \
  -b cookies.txt
```

**预期响应**: 应该返回错误或空结果，而不是所有课程

#### 6.2 XSS测试
```bash
# 尝试XSS攻击
curl -k -X POST https://academic.localhost:5001/api/v1/courses/CS101/announcements \
  -b cookies_teacher.txt \
  -H "Content-Type: application/json" \
  -d '{
    "title": "<script>alert(\"XSS\")</script>",
    "content": "测试内容"
  }'
```

**预期响应**: 应该清理或拒绝包含脚本的输入

### 7. 性能测试

#### 7.1 并发测试
```bash
# 使用Apache Bench进行并发测试
ab -n 100 -c 10 -k https://academic.localhost:5001/api/v1/courses
```

#### 7.2 响应时间测试
```bash
# 创建curl格式文件
echo "     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n" > curl-format.txt

# 使用curl测量响应时间
curl -k -w "@curl-format.txt" -o /dev/null -s https://academic.localhost:5001/api/v1/courses
```

## 测试结果验证

### 1. 功能验证
- [ ] 用户注册功能正常
- [ ] 用户登录功能正常
- [ ] OAuth2.0认证流程正常
- [ ] 课程列表获取正常
- [ ] 学生选课功能正常
- [ ] 成绩查询功能正常
- [ ] 课程公告功能正常
- [ ] 文件上传下载功能正常

### 2. 错误处理验证
- [ ] 认证错误处理正确
- [ ] 授权错误处理正确
- [ ] 权限错误处理正确
- [ ] 输入验证错误处理正确

### 3. 安全验证
- [ ] SQL注入防护有效
- [ ] XSS防护有效
- [ ] CSRF防护有效

### 4. 性能验证
- [ ] 并发请求处理正常
- [ ] 响应时间在可接受范围内
- [ ] 系统资源使用合理

## 故障排除

### 1. 常见问题

#### 1.1 证书错误
**问题**: 访问HTTPS服务时出现证书错误
**解决方案**:
```bash
cd certs
./generate_certs.sh
```

#### 1.2 数据库连接失败
**问题**: 应用无法连接到数据库
**解决方案**:
1. 检查MySQL服务是否运行
```bash
# Windows
net start mysql

# Linux
sudo systemctl status mysql
```

2. 检查数据库配置
```bash
# 检查数据库是否存在
mysql -u root -p -e "SHOW DATABASES;"

# 检查用户是否有权限
mysql -u root -p -e "SELECT User, Host FROM mysql.user;"
```

#### 1.3 端口冲突
**问题**: 应用启动失败，提示端口已被占用
**解决方案**:
1. 查找占用端口的进程
```bash
# Windows
netstat -ano | findstr :5000

# Linux
sudo lsof -i :5000
```

2. 终止占用端口的进程
```bash
# Windows
taskkill /PID <PID> /F

# Linux
sudo kill -9 <PID>
```

#### 1.4 依赖缺失
**问题**: 导入模块失败
**解决方案**:
```bash
pip install -r requirements.txt
```

### 2. 调试技巧

#### 2.1 启用详细日志
修改应用配置，将日志级别设置为DEBUG
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### 2.2 使用调试模式运行应用
```bash
# 认证服务器
cd auth-server
python app.py --debug

# 学术API服务器
cd academic-api
python app.py --debug

# 云API服务器
cd cloud-api
python app.py --debug
```

#### 2.3 检查网络连接和防火墙设置
```bash
# 测试端口连通性
telnet localhost 5000
telnet localhost 5001
telnet localhost 5002
```

#### 2.4 验证环境变量配置
```bash
# Windows
echo %DB_HOST%
echo %DB_USER%

# Linux
echo $DB_HOST
echo $DB_USER
```

### 3. 性能优化

#### 3.1 数据库优化
1. 添加适当的索引
2. 优化查询语句
3. 使用连接池
4. 启用查询缓存

#### 3.2 应用优化
1. 使用缓存减少数据库访问
2. 压缩响应数据
3. 使用CDN加速静态资源
4. 启用Gzip压缩

#### 3.3 系统优化
1. 调整系统参数
2. 优化网络配置
3. 增加内存和CPU资源
4. 使用负载均衡

## 自动化测试

### 1. 单元测试
```bash
# 运行单元测试
python -m pytest tests/unit/
```

### 2. 集成测试
```bash
# 运行集成测试
python -m pytest tests/integration/
```

### 3. API测试
```bash
# 使用Postman集合进行API测试
# 导入tests/postman_collection.json到Postman
```

### 4. 端到端测试
```bash
# 运行端到端测试
python -m pytest tests/e2e/
```

## 监控与日志

### 1. 查看应用日志
```bash
# 查看认证服务器日志
tail -f logs/auth-server.log

# 查看学术API服务器日志
tail -f logs/academic-api.log

# 查看云API服务器日志
tail -f logs/cloud-api.log
```

### 2. 查看数据库日志
```bash
# 查看MySQL错误日志
tail -f /var/log/mysql/error.log

# 查看MySQL慢查询日志
tail -f /var/log/mysql/mysql-slow.log
```

### 3. 查看性能监控
```bash
# 访问性能监控端点
curl -k -X GET https://academic.localhost:5001/api/v1/performance/stats \
  -b cookies.txt
```

---

本测试指南提供了学术管理系统的完整测试流程和故障排除方法，帮助测试人员全面验证系统功能、性能和安全性。