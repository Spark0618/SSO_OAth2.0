"""
API测试用例生成模块
用于自动生成API测试用例
"""

import json
import os
import unittest
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from flask import Flask
from unittest.mock import MagicMock, patch
import requests
from requests.auth import HTTPBasicAuth


class APITestCaseGenerator:
    """API测试用例生成器"""
    
    def __init__(self, app: Optional[Flask] = None, base_url: str = "http://localhost:5001"):
        """
        初始化API测试用例生成器
        
        Args:
            app: Flask应用实例
            base_url: API基础URL
        """
        self.app = app
        self.base_url = base_url
        self.test_cases = []
        self.auth_token = None
        self.auth_headers = {}
    
    def set_auth_token(self, token: str):
        """
        设置认证令牌
        
        Args:
            token: 认证令牌
        """
        self.auth_token = token
        self.auth_headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def add_test_case(self, name: str, method: str, path: str, 
                     data: Dict = None, params: Dict = None, 
                     headers: Dict = None, expected_status: int = 200,
                     expected_response: Dict = None, description: str = ""):
        """
        添加测试用例
        
        Args:
            name: 测试用例名称
            method: HTTP方法
            path: API路径
            data: 请求数据
            params: 查询参数
            headers: 请求头
            expected_status: 期望的HTTP状态码
            expected_response: 期望的响应内容
            description: 测试用例描述
        """
        if headers is None:
            headers = {}
        
        # 合并认证头
        test_headers = {**self.auth_headers, **headers}
        
        test_case = {
            'name': name,
            'method': method,
            'path': path,
            'data': data or {},
            'params': params or {},
            'headers': test_headers,
            'expected_status': expected_status,
            'expected_response': expected_response or {},
            'description': description
        }
        
        self.test_cases.append(test_case)
    
    def generate_unittest_file(self, output_path: str = 'test_api.py') -> str:
        """
        生成unittest测试文件
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            生成的文件路径
        """
        # 生成测试类
        test_class = f'''"""
API测试用例
自动生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

import unittest
import json
import requests
from requests.auth import HTTPBasicAuth


class APITestCase(unittest.TestCase):
    """API测试用例类"""
    
    def setUp(self):
        """测试前准备"""
        self.base_url = "{self.base_url}"
        self.auth_token = "{self.auth_token or ''}"
        self.auth_headers = {{}}
        
        if self.auth_token:
            self.auth_headers['Authorization'] = f'Bearer {{self.auth_token}}'
            self.auth_headers['Content-Type'] = 'application/json'
    
    def _make_request(self, method: str, path: str, data: dict = None, 
                     params: dict = None, headers: dict = None):
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法
            path: API路径
            data: 请求数据
            params: 查询参数
            headers: 请求头
            
        Returns:
            响应对象
        """
        url = f"{{self.base_url}}{{path}}"
        req_headers = {{**self.auth_headers, **(headers or {{}})}}
        
        if method.upper() == 'GET':
            return requests.get(url, params=params, headers=req_headers, verify=False)
        elif method.upper() == 'POST':
            return requests.post(url, json=data, params=params, headers=req_headers, verify=False)
        elif method.upper() == 'PUT':
            return requests.put(url, json=data, params=params, headers=req_headers, verify=False)
        elif method.upper() == 'DELETE':
            return requests.delete(url, params=params, headers=req_headers, verify=False)
        else:
            raise ValueError(f"Unsupported HTTP method: {{method}}")
    
'''

        # 为每个测试用例生成测试方法
        for i, test_case in enumerate(self.test_cases):
            method_name = f"test_{i+1:02d}_{test_case['name'].replace(' ', '_').replace('-', '_')}"
            
            # 生成测试方法
            test_method = f'''
    def {method_name}(self):
        """{test_case['description']}"""
        
        # 发送请求
        response = self._make_request(
            method="{test_case['method']}",
            path="{test_case['path']}",
            data={json.dumps(test_case['data'], indent=12)},
            params={json.dumps(test_case['params'], indent=12)},
            headers={json.dumps(test_case['headers'], indent=12)}
        )
        
        # 验证状态码
        self.assertEqual(response.status_code, {test_case['expected_status']}, 
                        f"Expected status code {test_case['expected_status']}, got {{response.status_code}}")
        
        # 验证响应内容
        if response.status_code == 200:
            response_data = response.json()
            expected_data = {json.dumps(test_case['expected_response'], indent=12)}
            
            # 这里可以根据需要添加更详细的响应验证
            self.assertIsInstance(response_data, dict, "Response should be a JSON object")
'''
            
            test_class += test_method
        
        # 添加主函数
        test_class += '''
if __name__ == '__main__':
    unittest.main()
'''
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(test_class)
        
        return output_path
    
    def generate_postman_tests(self, output_path: str = 'postman_tests.json') -> str:
        """
        生成Postman测试集合
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            生成的文件路径
        """
        collection = {
            'info': {
                'name': 'Academic API Tests',
                'description': 'API测试集合',
                'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'
            },
            'item': []
        }
        
        # 按标签分组测试用例
        tags = {}
        for test_case in self.test_cases:
            # 从路径中提取标签
            path_parts = test_case['path'].strip('/').split('/')
            tag = path_parts[0] if path_parts else 'General'
            
            if tag not in tags:
                tags[tag] = []
            
            tags[tag].append(test_case)
        
        # 创建文件夹和测试
        for tag, items in tags.items():
            folder = {
                'name': tag,
                'item': []
            }
            
            for test_case in items:
                request = {
                    'name': test_case['name'],
                    'event': [
                        {
                            'listen': 'test',
                            'script': {
                                'exec': [
                                    f"pm.test(\"Status code is {test_case['expected_status']}\", function () {{",
                                    f"    pm.response.to.have.status({test_case['expected_status']});",
                                    "});"
                                ],
                                'type': 'text/javascript'
                            }
                        }
                    ],
                    'request': {
                        'method': test_case['method'],
                        'header': [],
                        'url': {
                            'raw': f"{{{{base_url}}}}{test_case['path']}",
                            'host': ['{{base_url}}'],
                            'path': test_case['path'].strip('/').split('/')
                        }
                    }
                }
                
                # 添加请求头
                for key, value in test_case['headers'].items():
                    request['request']['header'].append({
                        'key': key,
                        'value': value
                    })
                
                # 添加参数或请求体
                if test_case['method'].upper() == 'GET' and test_case['params']:
                    request['request']['url']['query'] = []
                    for key, value in test_case['params'].items():
                        request['request']['url']['query'].append({
                            'key': key,
                            'value': str(value)
                        })
                elif test_case['method'].upper() in ['POST', 'PUT'] and test_case['data']:
                    request['request']['body'] = {
                        'mode': 'raw',
                        'raw': json.dumps(test_case['data'], indent=2),
                        'options': {
                            'raw': {
                                'language': 'json'
                            }
                        }
                    }
                
                folder['item'].append(request)
            
            collection['item'].append(folder)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def generate_pytest_file(self, output_path: str = 'test_api_pytest.py') -> str:
        """
        生成pytest测试文件
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            生成的文件路径
        """
        # 生成测试文件
        test_file = f'''"""
API测试用例 (pytest)
自动生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

import pytest
import json
import requests
from requests.auth import HTTPBasicAuth


# 配置
BASE_URL = "{self.base_url}"
AUTH_TOKEN = "{self.auth_token or ''}"

# 认证头
AUTH_HEADERS = {{}}
if AUTH_TOKEN:
    AUTH_HEADERS['Authorization'] = f'Bearer {{AUTH_TOKEN}}'
    AUTH_HEADERS['Content-Type'] = 'application/json'


@pytest.fixture
def api_client():
    """API客户端fixture"""
    class APIClient:
        def __init__(self, base_url, auth_headers):
            self.base_url = base_url
            self.auth_headers = auth_headers
        
        def request(self, method, path, data=None, params=None, headers=None):
            url = f"{{self.base_url}}{{path}}"
            req_headers = {{**self.auth_headers, **(headers or {{}})}}
            
            if method.upper() == 'GET':
                return requests.get(url, params=params, headers=req_headers, verify=False)
            elif method.upper() == 'POST':
                return requests.post(url, json=data, params=params, headers=req_headers, verify=False)
            elif method.upper() == 'PUT':
                return requests.put(url, json=data, params=params, headers=req_headers, verify=False)
            elif method.upper() == 'DELETE':
                return requests.delete(url, params=params, headers=req_headers, verify=False)
            else:
                raise ValueError(f"Unsupported HTTP method: {{method}}")
    
    return APIClient(BASE_URL, AUTH_HEADERS)


'''

        # 为每个测试用例生成测试函数
        for i, test_case in enumerate(self.test_cases):
            function_name = f"test_{i+1:02d}_{test_case['name'].replace(' ', '_').replace('-', '_')}"
            
            # 生成测试函数
            test_function = f'''
def {function_name}(api_client):
    """{test_case['description']}"""
    
    # 发送请求
    response = api_client.request(
        method="{test_case['method']}",
        path="{test_case['path']}",
        data={json.dumps(test_case['data'], indent=8)},
        params={json.dumps(test_case['params'], indent=8)},
        headers={json.dumps(test_case['headers'], indent=8)}
    )
    
    # 验证状态码
    assert response.status_code == {test_case['expected_status']}, \\
        f"Expected status code {test_case['expected_status']}, got {{response.status_code}}"
    
    # 验证响应内容
    if response.status_code == 200:
        response_data = response.json()
        assert isinstance(response_data, dict), "Response should be a JSON object"
        
        # 这里可以根据需要添加更详细的响应验证
        # expected_data = {json.dumps(test_case['expected_response'], indent=8)}
        # assert response_data == expected_data, "Response data does not match expected data"
'''
            
            test_file += test_function
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(test_file)
        
        return output_path
    
    def save_all_tests(self, output_dir: str = 'tests'):
        """
        保存所有测试文件
        
        Args:
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成unittest测试文件
        unittest_path = os.path.join(output_dir, 'test_api_unittest.py')
        self.generate_unittest_file(unittest_path)
        
        # 生成pytest测试文件
        pytest_path = os.path.join(output_dir, 'test_api_pytest.py')
        self.generate_pytest_file(pytest_path)
        
        # 生成Postman测试集合
        postman_path = os.path.join(output_dir, 'postman_tests.json')
        self.generate_postman_tests(postman_path)
        
        # 生成测试配置文件
        config = {
            'base_url': self.base_url,
            'auth_token': self.auth_token,
            'test_cases_count': len(self.test_cases),
            'generated_at': datetime.now().isoformat()
        }
        
        config_path = os.path.join(output_dir, 'test_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {
            'unittest': unittest_path,
            'pytest': pytest_path,
            'postman': postman_path,
            'config': config_path
        }


# 创建全局测试用例生成器实例
api_test_generator = APITestCaseGenerator()