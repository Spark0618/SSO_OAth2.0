# 代码安全与性能分析报告

## 安全问题

### 1. Hardcoded Credentials (High)
- **文件**: `academic-api\api_test_generator.py` (行 113)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `token = "{self.auth_token or '`
- **建议**: 使用环境变量存储敏感信息

### 2. Hardcoded Credentials (High)
- **文件**: `academic-api\api_test_generator.py` (行 321)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `TOKEN = "{self.auth_token or '`
- **建议**: 使用环境变量存储敏感信息

### 3. Hardcoded Credentials (High)
- **文件**: `academic-api\app.py` (行 37)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `SECRET = "academic-secret"`
- **建议**: 使用环境变量存储敏感信息

### 4. Hardcoded Credentials (High)
- **文件**: `academic-api\test_docs_and_tests.py` (行 24)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `PASSWORD = "test_password"`
- **建议**: 使用环境变量存储敏感信息

### 5. Hardcoded Credentials (High)
- **文件**: `auth-server\app.py` (行 15)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `PASSWORD = "academic_user@USTB2025"`
- **建议**: 使用环境变量存储敏感信息

### 6. Hardcoded Credentials (High)
- **文件**: `auth-server\app.py` (行 28)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `SECRET = "dev-secret-signing-key"`
- **建议**: 使用环境变量存储敏感信息

### 7. Hardcoded Credentials (High)
- **文件**: `cloud-api\app.py` (行 10)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `SECRET = "cloud-secret"`
- **建议**: 使用环境变量存储敏感信息

### 8. Hardcoded Credentials (High)
- **文件**: `common\base_app.py` (行 60)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret = "default-secret"`
- **建议**: 使用环境变量存储敏感信息

### 9. Hardcoded Credentials (High)
- **文件**: `common\config.py` (行 114)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret="secret"`
- **建议**: 使用环境变量存储敏感信息

### 10. Hardcoded Credentials (High)
- **文件**: `common\config.py` (行 129)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret="secret"`
- **建议**: 使用环境变量存储敏感信息

### 11. Hardcoded Credentials (High)
- **文件**: `common\config.py` (行 146)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret="secret"`
- **建议**: 使用环境变量存储敏感信息

### 12. Hardcoded Credentials (High)
- **文件**: `common\security.py` (行 25)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret = "default-insecure-secret"`
- **建议**: 使用环境变量存储敏感信息

### 13. Hardcoded Credentials (High)
- **文件**: `common\common\base_app.py` (行 60)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret = "default-secret"`
- **建议**: 使用环境变量存储敏感信息

### 14. Hardcoded Credentials (High)
- **文件**: `common\common\config.py` (行 114)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret="secret"`
- **建议**: 使用环境变量存储敏感信息

### 15. Hardcoded Credentials (High)
- **文件**: `common\common\config.py` (行 129)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret="secret"`
- **建议**: 使用环境变量存储敏感信息

### 16. Hardcoded Credentials (High)
- **文件**: `common\common\config.py` (行 146)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret="secret"`
- **建议**: 使用环境变量存储敏感信息

### 17. Hardcoded Credentials (High)
- **文件**: `common\common\security.py` (行 25)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `secret = "default-insecure-secret"`
- **建议**: 使用环境变量存储敏感信息

### 18. Hardcoded Credentials (High)
- **文件**: `frontends\auth\auth.html` (行 71)
- **描述**: 发现潜在的硬编码凭据
- **代码**: `password: "password123"`
- **建议**: 使用环境变量存储敏感信息

## 性能问题

✅ 未发现明显的性能问题。
