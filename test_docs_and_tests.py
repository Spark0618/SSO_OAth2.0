#!/usr/bin/env python3
"""
API文档和测试功能验证脚本
用于测试API文档生成和测试用例生成功能
"""

import os
import sys
import json
import requests
import time
from datetime import datetime

# 添加项目路径到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置
API_BASE_URL = "http://localhost:5001"
DOCS_API_URL = f"{API_BASE_URL}/api/v1/docs"
AUTH_API_URL = f"{API_BASE_URL}/api/v1/auth"

# 测试用户凭据
TEST_USERNAME = "test_user"
TEST_PASSWORD = "test_password"


def test_health_check():
    """测试API健康检查"""
    print("测试API健康检查...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ API健康检查通过")
            return True
        else:
            print(f"✗ API健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ API健康检查异常: {str(e)}")
        return False


def get_auth_token():
    """获取认证令牌"""
    print("获取认证令牌...")
    try:
        # 尝试登录获取令牌
        login_data = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(f"{AUTH_API_URL}/login", json=login_data, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("token"):
                print("✓ 认证令牌获取成功")
                return data.get("token")
            else:
                print("✗ 认证响应格式不正确")
                return None
        else:
            print(f"✗ 登录请求失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ 获取认证令牌异常: {str(e)}")
        return None


def test_generate_docs_and_tests(auth_token=None):
    """测试生成文档和测试用例"""
    print("测试生成文档和测试用例...")
    
    try:
        # 准备请求数据
        request_data = {
            "output_dir": "generated_docs",
            "base_url": API_BASE_URL,
            "auth_token": auth_token or ""
        }
        
        # 发送请求
        response = requests.post(f"{DOCS_API_URL}/generate", json=request_data, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✓ 文档和测试用例生成成功")
                print(f"  输出目录: {data.get('output_dir')}")
                print(f"  文档目录: {data.get('docs_dir')}")
                print(f"  测试目录: {data.get('tests_dir')}")
                return True
            else:
                print(f"✗ 生成失败: {data.get('message')}")
                return False
        else:
            print(f"✗ 生成请求失败: {response.status_code}")
            try:
                error_data = response.json()
                print(f"  错误信息: {error_data.get('message')}")
            except:
                print(f"  响应内容: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 生成文档和测试用例异常: {str(e)}")
        return False


def test_download_file(file_type, auth_token=None):
    """测试下载文件"""
    print(f"测试下载{file_type}文件...")
    
    try:
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        response = requests.get(f"{DOCS_API_URL}/download/{file_type}", headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"✓ {file_type}文件下载成功")
            return True
        else:
            print(f"✗ {file_type}文件下载失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 下载{file_type}文件异常: {str(e)}")
        return False


def test_register_endpoint():
    """测试注册API端点"""
    print("测试注册API端点...")
    
    try:
        # 准备端点数据
        endpoint_data = {
            "path": "/api/v1/test/endpoint",
            "method": "GET",
            "description": "测试端点",
            "parameters": [
                {
                    "name": "param1",
                    "in": "query",
                    "required": True,
                    "type": "string",
                    "description": "测试参数"
                }
            ],
            "responses": {
                "200": {
                    "description": "成功响应",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "message": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            },
            "tags": ["测试"]
        }
        
        response = requests.post(f"{DOCS_API_URL}/register-endpoint", json=endpoint_data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✓ API端点注册成功")
                return True
            else:
                print(f"✗ 端点注册失败: {data.get('message')}")
                return False
        else:
            print(f"✗ 端点注册请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 注册API端点异常: {str(e)}")
        return False


def test_register_schema():
    """测试注册数据模型"""
    print("测试注册数据模型...")
    
    try:
        # 准备模型数据
        schema_data = {
            "name": "TestModel",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "ID"},
                    "name": {"type": "string", "description": "名称"},
                    "created_at": {"type": "string", "format": "date-time", "description": "创建时间"}
                },
                "required": ["id", "name"]
            }
        }
        
        response = requests.post(f"{DOCS_API_URL}/register-schema", json=schema_data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✓ 数据模型注册成功")
                return True
            else:
                print(f"✗ 模型注册失败: {data.get('message')}")
                return False
        else:
            print(f"✗ 模型注册请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 注册数据模型异常: {str(e)}")
        return False


def test_get_openapi_spec():
    """测试获取OpenAPI规范"""
    print("测试获取OpenAPI规范...")
    
    try:
        response = requests.get(f"{DOCS_API_URL}/openapi", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("openapi") and data.get("info"):
                print("✓ OpenAPI规范获取成功")
                print(f"  API标题: {data.get('info', {}).get('title')}")
                print(f"  API版本: {data.get('info', {}).get('version')}")
                return True
            else:
                print("✗ OpenAPI规范格式不正确")
                return False
        else:
            print(f"✗ 获取OpenAPI规范失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取OpenAPI规范异常: {str(e)}")
        return False


def test_get_postman_collection():
    """测试获取Postman集合"""
    print("测试获取Postman集合...")
    
    try:
        response = requests.get(f"{DOCS_API_URL}/postman", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("info") and data.get("item"):
                print("✓ Postman集合获取成功")
                print(f"  集合名称: {data.get('info', {}).get('name')}")
                print(f"  端点数量: {len(data.get('item', []))}")
                return True
            else:
                print("✗ Postman集合格式不正确")
                return False
        else:
            print(f"✗ 获取Postman集合失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取Postman集合异常: {str(e)}")
        return False


def test_get_test_cases():
    """测试获取测试用例列表"""
    print("测试获取测试用例列表...")
    
    try:
        response = requests.get(f"{DOCS_API_URL}/test-cases", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✓ 测试用例列表获取成功")
                print(f"  测试用例数量: {data.get('total', 0)}")
                return True
            else:
                print(f"✗ 获取测试用例列表失败: {data.get('message')}")
                return False
        else:
            print(f"✗ 获取测试用例列表请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取测试用例列表异常: {str(e)}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("API文档和测试功能验证脚本")
    print("=" * 50)
    
    # 记录开始时间
    start_time = time.time()
    
    # 测试结果统计
    test_results = {
        "total": 0,
        "passed": 0,
        "failed": 0
    }
    
    # 执行测试
    tests = [
        ("API健康检查", test_health_check),
        ("获取认证令牌", lambda: get_auth_token() is not None),
        ("生成文档和测试用例", lambda: test_generate_docs_and_tests(get_auth_token())),
        ("下载OpenAPI规范", lambda: test_download_file("openapi", get_auth_token())),
        ("下载Postman集合", lambda: test_download_file("postman", get_auth_token())),
        ("下载Markdown文档", lambda: test_download_file("markdown", get_auth_token())),
        ("下载Unittest测试", lambda: test_download_file("unittest", get_auth_token())),
        ("下载Pytest测试", lambda: test_download_file("pytest", get_auth_token())),
        ("注册API端点", test_register_endpoint),
        ("注册数据模型", test_register_schema),
        ("获取OpenAPI规范", test_get_openapi_spec),
        ("获取Postman集合", test_get_postman_collection),
        ("获取测试用例列表", test_get_test_cases)
    ]
    
    for test_name, test_func in tests:
        test_results["total"] += 1
        print(f"\n[{test_results['total']}] {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            if result:
                test_results["passed"] += 1
            else:
                test_results["failed"] += 1
        except Exception as e:
            print(f"✗ 测试异常: {str(e)}")
            test_results["failed"] += 1
    
    # 输出测试结果
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"总测试数: {test_results['total']}")
    print(f"通过: {test_results['passed']}")
    print(f"失败: {test_results['failed']}")
    print(f"通过率: {test_results['passed']/test_results['total']*100:.1f}%")
    
    # 计算耗时
    elapsed_time = time.time() - start_time
    print(f"耗时: {elapsed_time:.2f}秒")
    
    # 返回退出码
    return 0 if test_results["failed"] == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)