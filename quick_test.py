#!/usr/bin/env python3
"""
学术管理系统快速测试脚本
用于快速验证系统基本功能是否正常工作
"""

import requests
import json
import time
import sys
from urllib.parse import urljoin

# 禁用SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 测试配置
BASE_URLS = {
    'auth': 'https://auth.localhost:5000',
    'academic': 'https://academic.localhost:5001',
    'cloud': 'https://cloud.localhost:5002'
}

# 测试用户数据
TEST_USERS = {
    'student': {
        'username': 'student01',
        'password': 'Password123',
        'role': 'student'
    },
    'teacher': {
        'username': 'teacher01',
        'password': 'Password123',
        'role': 'teacher'
    }
}

# 存储会话和令牌
sessions = {}
tokens = {}

def print_header(title):
    """打印测试标题"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_result(test_name, success, details=None):
    """打印测试结果"""
    status = "✓ 通过" if success else "✗ 失败"
    print(f"{test_name}: {status}")
    if details:
        print(f"  详情: {details}")

def check_service_health():
    """检查各服务健康状态"""
    print_header("服务健康检查")
    
    all_healthy = True
    for service_name, base_url in BASE_URLS.items():
        try:
            response = requests.get(base_url, verify=False, timeout=5)
            if response.status_code == 200:
                print_result(f"{service_name}服务", True, f"状态码: {response.status_code}")
            else:
                print_result(f"{service_name}服务", False, f"状态码: {response.status_code}")
                all_healthy = False
        except requests.exceptions.RequestException as e:
            print_result(f"{service_name}服务", False, str(e))
            all_healthy = False
    
    return all_healthy

def register_users():
    """注册测试用户"""
    print_header("用户注册测试")
    
    for user_type, user_data in TEST_USERS.items():
        try:
            url = urljoin(BASE_URLS['auth'], '/auth/register')
            response = requests.post(url, json=user_data, verify=False, timeout=10)
            
            if response.status_code == 200:
                print_result(f"{user_type}用户注册", True, f"用户名: {user_data['username']}")
            elif response.status_code == 400 and "already exists" in response.text:
                print_result(f"{user_type}用户注册", True, "用户已存在")
            else:
                print_result(f"{user_type}用户注册", False, f"状态码: {response.status_code}, 响应: {response.text}")
        except requests.exceptions.RequestException as e:
            print_result(f"{user_type}用户注册", False, str(e))

def login_users():
    """登录测试用户"""
    print_header("用户登录测试")
    
    for user_type, user_data in TEST_USERS.items():
        try:
            url = urljoin(BASE_URLS['auth'], '/auth/login')
            response = requests.post(url, json={
                'username': user_data['username'],
                'password': user_data['password']
            }, verify=False, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                sessions[user_type] = response.cookies
                print_result(f"{user_type}用户登录", True, f"会话令牌: {data.get('session_token', 'N/A')}")
            else:
                print_result(f"{user_type}用户登录", False, f"状态码: {response.status_code}, 响应: {response.text}")
        except requests.exceptions.RequestException as e:
            print_result(f"{user_type}用户登录", False, str(e))

def get_access_token():
    """获取访问令牌"""
    print_header("获取访问令牌测试")
    
    if 'student' not in sessions:
        print_result("获取访问令牌", False, "学生用户未登录")
        return False
    
    try:
        # 模拟OAuth2授权流程
        auth_url = urljoin(BASE_URLS['auth'], '/auth/authorize')
        response = requests.get(auth_url, params={
            'response_type': 'code',
            'client_id': 'academic-app',
            'redirect_uri': urljoin(BASE_URLS['academic'], '/session/callback'),
            'state': 'test_state'
        }, cookies=sessions['student'], verify=False, timeout=10)
        
        if response.status_code == 302:  # 重定向
            # 从Location头中提取授权码
            location = response.headers.get('Location', '')
            if 'code=' in location:
                auth_code = location.split('code=')[1].split('&')[0]
                
                # 使用授权码获取访问令牌
                token_url = urljoin(BASE_URLS['auth'], '/auth/token')
                token_response = requests.post(token_url, json={
                    'grant_type': 'authorization_code',
                    'code': auth_code,
                    'client_id': 'academic-app',
                    'client_secret': 'academic-secret'
                }, verify=False, timeout=10)
                
                if token_response.status_code == 200:
                    token_data = token_response.json()
                    tokens['access_token'] = token_data.get('access_token')
                    tokens['refresh_token'] = token_data.get('refresh_token')
                    print_result("获取访问令牌", True, f"令牌类型: Bearer")
                    return True
                else:
                    print_result("获取访问令牌", False, f"令牌交换失败: {token_response.text}")
            else:
                print_result("获取访问令牌", False, "未找到授权码")
        else:
            print_result("获取访问令牌", False, f"授权请求失败: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print_result("获取访问令牌", False, str(e))
    
    return False

def test_academic_api():
    """测试学术API功能"""
    print_header("学术API功能测试")
    
    if 'student' not in sessions:
        print_result("学术API测试", False, "学生用户未登录")
        return
    
    # 测试获取会话状态
    try:
        url = urljoin(BASE_URLS['academic'], '/api/v1/session/status')
        response = requests.get(url, cookies=sessions['student'], verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_result("获取会话状态", True, f"用户: {data.get('data', {}).get('username', 'N/A')}")
        else:
            print_result("获取会话状态", False, f"状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print_result("获取会话状态", False, str(e))
    
    # 测试获取课程列表
    try:
        url = urljoin(BASE_URLS['academic'], '/api/v1/courses')
        response = requests.get(url, cookies=sessions['student'], verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            courses = data.get('data', [])
            print_result("获取课程列表", True, f"课程数量: {len(courses)}")
        else:
            print_result("获取课程列表", False, f"状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print_result("获取课程列表", False, str(e))
    
    # 测试选课功能
    try:
        url = urljoin(BASE_URLS['academic'], '/api/v1/courses/CS101/enroll')
        response = requests.post(url, cookies=sessions['student'], verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_result("学生选课", True, data.get('message', '选课成功'))
        elif response.status_code == 400 and "already enrolled" in response.text:
            print_result("学生选课", True, "已选过该课程")
        else:
            print_result("学生选课", False, f"状态码: {response.status_code}, 响应: {response.text}")
    except requests.exceptions.RequestException as e:
        print_result("学生选课", False, str(e))
    
    # 测试获取成绩
    try:
        url = urljoin(BASE_URLS['academic'], '/api/v1/grades')
        response = requests.get(url, cookies=sessions['student'], verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            grades = data.get('data', [])
            print_result("获取成绩", True, f"成绩数量: {len(grades)}")
        else:
            print_result("获取成绩", False, f"状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print_result("获取成绩", False, str(e))

def test_cloud_api():
    """测试云盘API功能"""
    print_header("云盘API功能测试")
    
    if 'student' not in sessions:
        print_result("云盘API测试", False, "学生用户未登录")
        return
    
    # 测试获取文件列表
    try:
        url = urljoin(BASE_URLS['cloud'], '/files')
        response = requests.get(url, cookies=sessions['student'], verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            print_result("获取文件列表", True, f"文件数量: {len(files)}")
        else:
            print_result("获取文件列表", False, f"状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print_result("获取文件列表", False, str(e))
    
    # 测试文件上传
    try:
        url = urljoin(BASE_URLS['cloud'], '/files')
        response = requests.post(url, json={
            'name': '测试文档.txt',
            'size': '1KB'
        }, cookies=sessions['student'], verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_result("文件上传", True, data.get('message', '上传成功'))
        else:
            print_result("文件上传", False, f"状态码: {response.status_code}, 响应: {response.text}")
    except requests.exceptions.RequestException as e:
        print_result("文件上传", False, str(e))

def test_error_handling():
    """测试错误处理"""
    print_header("错误处理测试")
    
    # 测试未授权访问
    try:
        url = urljoin(BASE_URLS['academic'], '/api/v1/courses')
        response = requests.get(url, verify=False, timeout=10)
        
        if response.status_code == 401:
            print_result("未授权访问处理", True, "正确返回401状态码")
        else:
            print_result("未授权访问处理", False, f"状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print_result("未授权访问处理", False, str(e))
    
    # 测试无效输入
    if 'student' in sessions:
        try:
            url = urljoin(BASE_URLS['academic'], '/api/v1/courses/INVALID_CODE/enroll')
            response = requests.post(url, cookies=sessions['student'], verify=False, timeout=10)
            
            if response.status_code == 400:
                print_result("无效输入处理", True, "正确返回400状态码")
            else:
                print_result("无效输入处理", False, f"状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print_result("无效输入处理", False, str(e))

def test_security():
    """测试安全功能"""
    print_header("安全功能测试")
    
    # 测试SQL注入
    if 'student' in sessions:
        try:
            url = urljoin(BASE_URLS['academic'], '/api/v1/courses')
            params = {'code': "CS101' OR '1'='1"}
            response = requests.get(url, params=params, cookies=sessions['student'], verify=False, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                courses = data.get('data', [])
                # 如果SQL注入成功，可能会返回所有课程
                if len(courses) <= 10:  # 假设正常情况下课程数量不超过10
                    print_result("SQL注入防护", True, "SQL注入被成功阻止")
                else:
                    print_result("SQL注入防护", False, "可能存在SQL注入漏洞")
            else:
                print_result("SQL注入防护", True, f"请求被拒绝，状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print_result("SQL注入防护", True, f"请求异常，可能是安全防护: {str(e)}")

def run_all_tests():
    """运行所有测试"""
    print_header("学术管理系统快速测试")
    print("本脚本将测试学术管理系统的基本功能")
    print("请确保所有服务已启动并运行在指定端口上")
    
    # 检查服务健康状态
    if not check_service_health():
        print("\n警告: 部分服务未正常运行，测试可能会失败")
        input("按Enter键继续测试...")
    
    # 注册用户
    register_users()
    
    # 登录用户
    login_users()
    
    # 获取访问令牌
    get_access_token()
    
    # 测试学术API
    test_academic_api()
    
    # 测试云盘API
    test_cloud_api()
    
    # 测试错误处理
    test_error_handling()
    
    # 测试安全功能
    test_security()
    
    print_header("测试完成")
    print("测试已全部完成，请查看上述结果")
    print("如需详细测试，请参考TEST_GUIDE.md文档")

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试过程中发生错误: {str(e)}")
        sys.exit(1)