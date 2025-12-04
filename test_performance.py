"""
性能测试脚本
用于评估系统性能表现 (修复版：适配 HTTPS)
"""

import time
import requests
import statistics
import threading
import concurrent.futures
from typing import List, Dict, Any, Tuple
import sys
import urllib3

# 禁用不安全请求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class PerformanceTester:
    """性能测试器"""
    
    def __init__(self):
        # === 关键修复：使用 HTTPS ===
        self.base_urls = {
            "auth": "https://localhost:5000",
            "academic": "https://localhost:5001",
            "cloud": "https://localhost:5002"
        }
        self.test_token = None
        self.results = {}
    
    def get_auth_token(self) -> bool:
        """获取认证令牌"""
        try:
            # 1. 先尝试注册一个性能测试专用的 admin 用户
            # 使用时间戳避免重复
            ts = int(time.time())
            admin_user = {
                "username": f"perf_admin_{ts}",
                "email": f"perf_{ts}@example.com",
                "password": "admin123",
                "role": "admin"
            }
            
            # 注册
            reg_url = f"{self.base_urls['auth']}/auth/register"
            # verify=False 忽略证书错误
            requests.post(reg_url, json=admin_user, timeout=5, verify=False)
            
            # 2. 登录
            login_url = f"{self.base_urls['auth']}/auth/login"
            login_data = {
                "username": admin_user["username"],
                "password": admin_user["password"]
            }
            
            response = requests.post(login_url, json=login_data, timeout=5, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                # 适配不同的返回结构
                if "data" in result and "access_token" in result["data"]:
                    self.test_token = result["data"]["access_token"]
                    return True
                if "access_token" in result:
                    self.test_token = result["access_token"]
                    return True
            
            print(f"登录失败: {response.text}")
            return False
        except Exception as e:
            print(f"获取认证令牌失败: {str(e)}")
            return False
    
    def measure_response_time(self, url: str, method: str = "GET", 
                            data: Dict = None, headers: Dict = None) -> Tuple[float, int]:
        """测量单个请求的响应时间"""
        start_time = time.time()
        
        try:
            # === 关键修复：verify=False ===
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10, verify=False)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=10, verify=False)
            else:
                return -1, 0
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # 转换为毫秒
            return response_time, response.status_code
        except Exception as e:
            # print(f"请求异常: {e}") # 调试时可取消注释
            return -1, 0
    
    def run_single_endpoint_test(self, endpoint_name: str, url: str, 
                               method: str = "GET", data: Dict = None, 
                               headers: Dict = None, num_requests: int = 50) -> Dict[str, Any]:
        """对单个端点进行性能测试"""
        print(f"测试端点: {endpoint_name}")
        
        response_times = []
        success_count = 0
        
        for i in range(num_requests):
            response_time, status_code = self.measure_response_time(
                url, method, data, headers
            )
            
            if response_time > 0:
                response_times.append(response_time)
                # 200, 201, 404 等都算服务器响应成功（只要没崩）
                if status_code < 500:
                    success_count += 1
        
        if not response_times:
            return {
                "endpoint": endpoint_name,
                "success_rate": 0,
                "avg_response_time": 0,
                "min_response_time": 0,
                "max_response_time": 0,
                "median_response_time": 0,
                "p95_response_time": 0,
                "p99_response_time": 0,
                "requests_per_second": 0
            }
        
        # 计算统计数据
        avg_time = statistics.mean(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        median_time = statistics.median(response_times)
        
        # 计算百分位数
        sorted_times = sorted(response_times)
        p95_index = int(0.95 * len(sorted_times))
        p99_index = int(0.99 * len(sorted_times))
        p95_time = sorted_times[p95_index] if p95_index < len(sorted_times) else max_time
        p99_time = sorted_times[p99_index] if p99_index < len(sorted_times) else max_time
        
        # 计算每秒请求数
        total_time = sum(response_times) / 1000  # 转换为秒
        rps = num_requests / total_time if total_time > 0 else 0
        
        result = {
            "endpoint": endpoint_name,
            "success_rate": success_count / num_requests * 100,
            "avg_response_time": avg_time,
            "min_response_time": min_time,
            "max_response_time": max_time,
            "median_response_time": median_time,
            "p95_response_time": p95_time,
            "p99_response_time": p99_time,
            "requests_per_second": rps
        }
        
        print(f"  成功率: {result['success_rate']:.2f}%")
        print(f"  平均响应时间: {avg_time:.2f}ms")
        print(f"  95%响应时间: {p95_time:.2f}ms")
        print(f"  每秒请求数: {rps:.2f}")
        
        return result
    
    def test_auth_endpoints(self):
        """测试认证服务端点性能"""
        print("\n=== 认证服务性能测试 ===")
        
        results = {}
        
        # 测试健康检查
        url = f"{self.base_urls['auth']}/health"
        results["health"] = self.run_single_endpoint_test(
            "健康检查", url, "GET", None, None, 20
        )
        
        # 测试令牌验证
        if self.test_token:
            url = f"{self.base_urls['auth']}/auth/validate"
            data = {"token": self.test_token}
            results["validate"] = self.run_single_endpoint_test(
                "令牌验证", url, "POST", data, None, 20
            )
        
        # 测试获取用户信息
        if self.test_token:
            url = f"{self.base_urls['auth']}/auth/user"
            headers = {"Authorization": f"Bearer {self.test_token}"}
            results["user_info"] = self.run_single_endpoint_test(
                "获取用户信息", url, "GET", None, headers, 20
            )
        
        self.results["auth"] = results
    
    def test_academic_endpoints(self):
        """测试学术服务端点性能"""
        print("\n=== 学术服务性能测试 ===")
        
        results = {}
        
        if not self.test_token:
            print("缺少认证令牌，跳过学术服务性能测试")
            return
        
        headers = {"Authorization": f"Bearer {self.test_token}"}
        
        # 测试获取论文列表
        url = f"{self.base_urls['academic']}/api/papers"
        results["papers_list"] = self.run_single_endpoint_test(
            "获取论文列表", url, "GET", None, headers, 20
        )
        
        self.results["academic"] = results
    
    def test_cloud_endpoints(self):
        """测试云存储服务端点性能"""
        print("\n=== 云存储服务性能测试 ===")
        
        results = {}
        
        if not self.test_token:
            print("缺少认证令牌，跳过云存储服务性能测试")
            return
        
        headers = {"Authorization": f"Bearer {self.test_token}"}
        
        # 测试获取文件列表
        url = f"{self.base_urls['cloud']}/api/files"
        results["files_list"] = self.run_single_endpoint_test(
            "获取文件列表", url, "GET", None, headers, 20
        )
        
        self.results["cloud"] = results
    
    def test_concurrent_requests(self):
        """测试并发请求性能"""
        print("\n=== 并发请求性能测试 ===")
        
        # 使用健康检查接口测试并发，避免给数据库太大压力
        test_url = f"{self.base_urls['auth']}/health"
        
        concurrency_levels = [5, 10, 20]
        
        for concurrency in concurrency_levels:
            print(f"\n测试并发级别: {concurrency}")
            
            response_times = []
            success_count = 0
            
            def make_request():
                nonlocal success_count
                response_time, status_code = self.measure_response_time(
                    test_url, "GET", None, None
                )
                if response_time > 0:
                    response_times.append(response_time)
                    if status_code < 500:
                        success_count += 1
            
            # 使用线程池模拟并发请求
            start_time = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                # 每个并发级别发送 5 倍于并发数的请求
                futures = [executor.submit(make_request) for _ in range(concurrency * 5)]
                concurrent.futures.wait(futures)
            end_time = time.time()
            
            total_time = end_time - start_time
            total_requests = len(response_times)
            
            if response_times:
                avg_time = statistics.mean(response_times)
                p95_time = sorted(response_times)[int(0.95 * len(response_times))]
                rps = total_requests / total_time if total_time > 0 else 0
                
                print(f"  成功率: {success_count/len(futures)*100:.2f}%")
                print(f"  平均响应时间: {avg_time:.2f}ms")
                print(f"  95%响应时间: {p95_time:.2f}ms")
                print(f"  每秒请求数: {rps:.2f}")
    
    def print_performance_summary(self):
        """打印性能测试摘要"""
        print("\n=== 性能测试摘要 ===")
        
        for service_name, service_results in self.results.items():
            print(f"\n{service_name.upper()} 服务:")
            
            for endpoint_name, result in service_results.items():
                print(f"  {endpoint_name}:")
                print(f"    成功率: {result['success_rate']:.2f}%")
                print(f"    平均响应: {result['avg_response_time']:.2f}ms")
                print(f"    QPS: {result['requests_per_second']:.2f}")
    
    def run_all_tests(self):
        """运行所有性能测试"""
        print("开始性能测试 (HTTPS)...")
        print("请确保所有服务已启动")
        print()
        
        # 等待用户确认
        # input("按Enter键开始测试...")
        
        # 获取认证令牌
        print("正在获取测试令牌...")
        if not self.get_auth_token():
            print("无法获取认证令牌，某些测试将被跳过")
        
        # 运行测试
        self.test_auth_endpoints()
        self.test_academic_endpoints()
        self.test_cloud_endpoints()
        self.test_concurrent_requests()
        
        # 打印测试结果摘要
        self.print_performance_summary()

def main():
    """主函数"""
    tester = PerformanceTester()
    tester.run_all_tests()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行时发生错误: {str(e)}")
        sys.exit(1)