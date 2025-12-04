"""
系统测试脚本
用于验证重构后的系统功能 (修复版：Windows 兼容性优化)
"""

import requests
import time
import sys
import urllib3
from typing import Dict, Any, Optional

# 禁用不安全请求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SystemTester:
    """系统测试器"""
    
    def __init__(self):
        self.base_urls = {
            "auth": "https://localhost:5000",
            "academic": "https://localhost:5001",
            "cloud": "https://localhost:5002"
        }
        self.tokens = {}
        self.user_data = {}
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        # === 修复：使用 ASCII 字符代替 Unicode 图标，防止 Windows 管道崩溃 ===
        status = "[PASS]" if success else "[FAIL]"
        self.test_results.append({
            "name": test_name,
            "success": success,
            "message": message
        })
        # 强制刷新缓冲区，确保实时输出
        print(f"{status} {test_name}", flush=True)
        if message:
            print(f"  {message}", flush=True)
    
    def check_service_health(self, service_name: str) -> bool:
        """检查服务健康状态"""
        try:
            url = f"{self.base_urls[service_name]}/health"
            response = requests.get(url, timeout=5, verify=False)
            return response.status_code == 200
        except Exception as e:
            return False
    
    def test_health_checks(self):
        """测试健康检查端点"""
        print("\n=== 测试健康检查端点 ===")
        
        for service_name in self.base_urls:
            is_healthy = self.check_service_health(service_name)
            self.log_test(
                f"{service_name} 健康检查",
                is_healthy,
                f"URL: {self.base_urls[service_name]}/health"
            )
    
    def register_user(self, username: str, email: str, password: str, role: str) -> Optional[Dict[str, Any]]:
        """注册用户"""
        try:
            url = f"{self.base_urls['auth']}/auth/register"
            data = {
                "username": username,
                "email": email,
                "password": password,
                "role": role
            }
            response = requests.post(url, json=data, timeout=5, verify=False)
            
            if response.status_code in [200, 201]:
                return response.json()
            elif "already exists" in response.text:
                return {"success": True, "message": "User already exists"}
            else:
                return None
        except Exception as e:
            return None
    
    def login_user(self, username: str, password: str) -> Optional[str]:
        """用户登录"""
        try:
            url = f"{self.base_urls['auth']}/auth/login"
            data = {
                "username": username,
                "password": password
            }
            response = requests.post(url, json=data, timeout=5, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("data"):
                    return result["data"].get("access_token")
            return None
        except Exception as e:
            return None
    
    def test_auth_service(self):
        """测试认证服务"""
        print("\n=== 测试认证服务 ===")
        
        ts = int(time.time())
        test_user = {
            "username": f"testuser_{ts}",
            "email": f"test_{ts}@example.com",
            "password": "testpass123",
            "role": "student"
        }
        
        register_result = self.register_user(**test_user)
        self.log_test(
            "用户注册",
            register_result is not None,
            "成功创建测试用户" if register_result else "注册失败"
        )
        
        if register_result:
            self.user_data["student"] = test_user
            token = self.login_user(test_user["username"], test_user["password"])
            self.log_test(
                "用户登录",
                token is not None,
                "成功获取访问令牌" if token else "登录失败"
            )
            
            if token:
                self.tokens["student"] = token
                try:
                    headers = {"Authorization": f"Bearer {token}"}
                    url = f"{self.base_urls['auth']}/auth/user"
                    response = requests.get(url, headers=headers, timeout=5, verify=False)
                    is_success = response.status_code == 200
                    self.log_test(
                        "获取用户信息",
                        is_success,
                        "成功获取用户信息" if is_success else f"失败: {response.status_code}"
                    )
                except Exception as e:
                    self.log_test("获取用户信息", False, f"异常: {e}")

    def test_academic_service(self):
        """测试学术服务"""
        print("\n=== 测试学术服务 ===")
        
        token = self.tokens.get("student")
        if not token:
            self.log_test("学术服务测试", False, "缺少认证令牌，跳过")
            return

        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            endpoints = ["/api/papers", "/api/v1/papers", "/api/courses"]
            success = False
            for ep in endpoints:
                url = f"{self.base_urls['academic']}{ep}"
                response = requests.get(url, headers=headers, timeout=5, verify=False)
                if response.status_code == 200:
                    success = True
                    break
            
            self.log_test(
                "获取资源列表",
                success,
                "成功获取列表" if success else "所有尝试的端点均未返回200"
            )
        except Exception as e:
            self.log_test("获取资源列表", False, f"异常: {e}")

    def test_cloud_service(self):
        """测试云存储服务"""
        print("\n=== 测试云存储服务 ===")
        
        token = self.tokens.get("student")
        if not token:
            self.log_test("云存储服务测试", False, "缺少认证令牌，跳过")
            return

        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            url = f"{self.base_urls['cloud']}/api/files"
            response = requests.get(url, headers=headers, timeout=5, verify=False)
            success = response.status_code in [200, 404]
            self.log_test(
                "获取文件列表",
                success,
                f"响应状态码: {response.status_code}"
            )
        except Exception as e:
            self.log_test("获取文件列表", False, f"异常: {e}")

    def run_all_tests(self):
        """运行所有测试"""
        print("开始系统测试 (HTTPS)...")
        print("请确保所有服务已启动")
        print()
        
        self.test_health_checks()
        self.test_auth_service()
        self.test_academic_service()
        self.test_cloud_service()
        
        return self.print_test_summary()
    
    def print_test_summary(self):
        """打印测试结果摘要"""
        print("\n=== 测试结果摘要 ===")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        if total_tests > 0:
            print(f"总测试数: {total_tests}")
            print(f"通过: {passed_tests}")
            print(f"失败: {failed_tests}")
            print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        else:
            print("未运行任何测试")
        
        if failed_tests > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"- {result['name']}: {result['message']}")
            return False # 有失败
        return True # 全部通过

def main():
    tester = SystemTester()
    success = tester.run_all_tests()
    # === 关键修复：根据测试结果返回退出码 ===
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行时发生错误: {str(e)}")
        sys.exit(1)