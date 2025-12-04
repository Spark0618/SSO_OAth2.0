"""
API文档和测试集成模块
用于自动生成API文档和测试用例，并提供相关API端点
"""

import os
import json
import tempfile
import shutil
from typing import Dict, List, Any, Optional
from flask import Blueprint, jsonify, request, send_file, current_app
from datetime import datetime

from api_documentation import api_doc_generator, document_endpoint
from api_test_generator import api_test_generator


def create_docs_and_tests_blueprint():
    """创建文档和测试蓝图"""
    blueprint = Blueprint('docs_and_tests', __name__, url_prefix='/api/v1/docs')
    
    @blueprint.route('/generate', methods=['POST'])
    @document_endpoint(
        path='/api/v1/docs/generate',
        method='POST',
        description='生成API文档和测试用例',
        tags=['文档和测试']
    )
    def generate_docs_and_tests():
        """生成API文档和测试用例"""
        try:
            # 获取请求参数
            data = request.get_json() or {}
            output_dir = data.get('output_dir', 'docs_and_tests')
            base_url = data.get('base_url', 'http://localhost:5001')
            auth_token = data.get('auth_token', '')
            
            # 设置认证令牌
            if auth_token:
                api_test_generator.set_auth_token(auth_token)
            
            # 生成API文档
            docs_dir = os.path.join(output_dir, 'docs')
            api_doc_generator.save_documentation(docs_dir)
            
            # 生成测试用例
            tests_dir = os.path.join(output_dir, 'tests')
            test_files = api_test_generator.save_all_tests(tests_dir)
            
            # 创建索引文件
            index_file = os.path.join(output_dir, 'index.html')
            create_index_file(index_file, docs_dir, tests_dir, test_files)
            
            return jsonify({
                'success': True,
                'message': 'API文档和测试用例生成成功',
                'output_dir': output_dir,
                'docs_dir': docs_dir,
                'tests_dir': tests_dir,
                'test_files': test_files,
                'index_file': index_file
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'生成API文档和测试用例失败: {str(e)}'
            }), 500
    
    @blueprint.route('/download/<file_type>', methods=['GET'])
    @document_endpoint(
        path='/api/v1/docs/download/<file_type>',
        method='GET',
        description='下载API文档或测试文件',
        tags=['文档和测试']
    )
    def download_file(file_type):
        """下载API文档或测试文件"""
        try:
            # 支持的文件类型
            supported_types = {
                'openapi': 'docs/openapi.json',
                'postman': 'docs/postman_collection.json',
                'markdown': 'docs/api_documentation.md',
                'unittest': 'tests/test_api_unittest.py',
                'pytest': 'tests/test_api_pytest.py',
                'postman_tests': 'tests/postman_tests.json'
            }
            
            if file_type not in supported_types:
                return jsonify({
                    'success': False,
                    'message': f'不支持的文件类型: {file_type}'
                }), 400
            
            file_path = supported_types[file_type]
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                # 如果文件不存在，先生成
                api_doc_generator.save_documentation('docs')
                api_test_generator.save_all_tests('tests')
            
            # 返回文件
            return send_file(file_path, as_attachment=True)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'下载文件失败: {str(e)}'
            }), 500
    
    @blueprint.route('/register-endpoint', methods=['POST'])
    @document_endpoint(
        path='/api/v1/docs/register-endpoint',
        method='POST',
        description='注册API端点信息',
        tags=['文档和测试']
    )
    def register_endpoint():
        """注册API端点信息"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({
                    'success': False,
                    'message': '请求数据不能为空'
                }), 400
            
            # 验证必需字段
            required_fields = ['path', 'method', 'description']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'message': f'缺少必需字段: {field}'
                    }), 400
            
            # 注册端点
            api_doc_generator.register_endpoint(
                path=data['path'],
                method=data['method'],
                handler=None,  # 这里可以传入处理函数
                description=data['description'],
                parameters=data.get('parameters', []),
                responses=data.get('responses', {'200': {'description': 'Success'}}),
                tags=data.get('tags', [])
            )
            
            # 添加测试用例
            api_test_generator.add_test_case(
                name=data['description'],
                method=data['method'],
                path=data['path'],
                data=data.get('example_request', {}),
                params=data.get('example_params', {}),
                expected_status=data.get('expected_status', 200),
                expected_response=data.get('example_response', {}),
                description=data['description']
            )
            
            return jsonify({
                'success': True,
                'message': 'API端点注册成功'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'注册API端点失败: {str(e)}'
            }), 500
    
    @blueprint.route('/register-schema', methods=['POST'])
    @document_endpoint(
        path='/api/v1/docs/register-schema',
        method='POST',
        description='注册数据模型定义',
        tags=['文档和测试']
    )
    def register_schema():
        """注册数据模型定义"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({
                    'success': False,
                    'message': '请求数据不能为空'
                }), 400
            
            # 验证必需字段
            required_fields = ['name', 'schema']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'message': f'缺少必需字段: {field}'
                    }), 400
            
            # 注册模型
            api_doc_generator.register_schema(data['name'], data['schema'])
            
            return jsonify({
                'success': True,
                'message': '数据模型注册成功'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'注册数据模型失败: {str(e)}'
            }), 500
    
    @blueprint.route('/openapi', methods=['GET'])
    @document_endpoint(
        path='/api/v1/docs/openapi',
        method='GET',
        description='获取OpenAPI规范文档',
        tags=['文档和测试']
    )
    def get_openapi_spec():
        """获取OpenAPI规范文档"""
        try:
            spec = api_doc_generator.generate_openapi_spec()
            return jsonify(spec)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取OpenAPI规范文档失败: {str(e)}'
            }), 500
    
    @blueprint.route('/postman', methods=['GET'])
    @document_endpoint(
        path='/api/v1/docs/postman',
        method='GET',
        description='获取Postman集合',
        tags=['文档和测试']
    )
    def get_postman_collection():
        """获取Postman集合"""
        try:
            collection = api_doc_generator.generate_postman_collection()
            return jsonify(collection)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取Postman集合失败: {str(e)}'
            }), 500
    
    @blueprint.route('/markdown', methods=['GET'])
    @document_endpoint(
        path='/api/v1/docs/markdown',
        method='GET',
        description='获取Markdown格式文档',
        tags=['文档和测试']
    )
    def get_markdown_doc():
        """获取Markdown格式文档"""
        try:
            doc = api_doc_generator.generate_markdown_documentation()
            return doc, 200, {'Content-Type': 'text/markdown'}
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取Markdown文档失败: {str(e)}'
            }), 500
    
    @blueprint.route('/test-cases', methods=['GET'])
    @document_endpoint(
        path='/api/v1/docs/test-cases',
        method='GET',
        description='获取测试用例列表',
        tags=['文档和测试']
    )
    def get_test_cases():
        """获取测试用例列表"""
        try:
            test_cases = []
            
            for test_case in api_test_generator.test_cases:
                test_cases.append({
                    'name': test_case['name'],
                    'method': test_case['method'],
                    'path': test_case['path'],
                    'description': test_case['description'],
                    'expected_status': test_case['expected_status']
                })
            
            return jsonify({
                'success': True,
                'test_cases': test_cases,
                'total': len(test_cases)
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取测试用例列表失败: {str(e)}'
            }), 500
    
    return blueprint


def create_index_file(index_path: str, docs_dir: str, tests_dir: str, test_files: Dict[str, str]):
    """创建索引HTML文件"""
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API文档和测试</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .container {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .card {{
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
            flex: 1;
            min-width: 300px;
        }}
        .file-list {{
            list-style-type: none;
            padding: 0;
        }}
        .file-list li {{
            padding: 10px;
            border-bottom: 1px solid #eee;
        }}
        .file-list li:last-child {{
            border-bottom: none;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>API文档和测试</h1>
    <p class="timestamp">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="container">
        <div class="card">
            <h2>API文档</h2>
            <ul class="file-list">
                <li><a href="{docs_dir}/openapi.json" target="_blank">OpenAPI 规范</a></li>
                <li><a href="{docs_dir}/postman_collection.json" target="_blank">Postman 集合</a></li>
                <li><a href="{docs_dir}/api_documentation.md" target="_blank">Markdown 文档</a></li>
            </ul>
        </div>
        
        <div class="card">
            <h2>测试用例</h2>
            <ul class="file-list">
                <li><a href="{test_files['unittest']}" target="_blank">Unittest 测试</a></li>
                <li><a href="{test_files['pytest']}" target="_blank">Pytest 测试</a></li>
                <li><a href="{test_files['postman']}" target="_blank">Postman 测试集合</a></li>
                <li><a href="{test_files['config']}" target="_blank">测试配置</a></li>
            </ul>
        </div>
    </div>
    
    <div class="card">
        <h2>使用说明</h2>
        <h3>API文档</h3>
        <ul>
            <li><strong>OpenAPI 规范</strong>: 可以导入到 Swagger UI、Postman 等工具中查看</li>
            <li><strong>Postman 集合</strong>: 可以直接导入到 Postman 中进行 API 测试</li>
            <li><strong>Markdown 文档</strong>: 可以在 GitHub 或其他支持 Markdown 的平台查看</li>
        </ul>
        
        <h3>测试用例</h3>
        <ul>
            <li><strong>Unittest 测试</strong>: 使用 Python 标准库 unittest 框架的测试用例</li>
            <li><strong>Pytest 测试</strong>: 使用 pytest 框架的测试用例，更简洁灵活</li>
            <li><strong>Postman 测试集合</strong>: 可以在 Postman 中运行的测试集合</li>
        </ul>
    </div>
</body>
</html>"""
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def register_existing_endpoints():
    """注册现有端点到文档生成器"""
    # 这里可以添加现有端点的注册逻辑
    # 例如遍历所有蓝图和路由，自动注册到文档生成器
    
    # 示例：注册一些核心端点
    endpoints = [
        {
            'path': '/api/v1/health',
            'method': 'GET',
            'description': '健康检查',
            'tags': ['系统'],
            'responses': {
                '200': {
                    'description': '系统正常',
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'status': {'type': 'string'},
                                    'message': {'type': 'string'}
                                }
                            }
                        }
                    }
                }
            }
        },
        {
            'path': '/api/v1/auth/login',
            'method': 'POST',
            'description': '用户登录',
            'tags': ['认证'],
            'parameters': [
                {
                    'name': 'username',
                    'in': 'json',
                    'required': True,
                    'type': 'string',
                    'description': '用户名'
                },
                {
                    'name': 'password',
                    'in': 'json',
                    'required': True,
                    'type': 'string',
                    'description': '密码'
                }
            ],
            'responses': {
                '200': {
                    'description': '登录成功',
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'success': {'type': 'boolean'},
                                    'token': {'type': 'string'},
                                    'user': {'type': 'object'}
                                }
                            }
                        }
                    }
                }
            }
        }
    ]
    
    for endpoint in endpoints:
        api_doc_generator.register_endpoint(**endpoint)
        
        # 添加测试用例
        api_test_generator.add_test_case(
            name=endpoint['description'],
            method=endpoint['method'],
            path=endpoint['path'],
            data=endpoint.get('example_request', {}),
            params=endpoint.get('example_params', {}),
            expected_status=endpoint.get('expected_status', 200),
            expected_response=endpoint.get('example_response', {}),
            description=endpoint['description']
        )