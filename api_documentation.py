"""
API文档生成模块
用于自动生成API文档和测试用例
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from flask import Blueprint, Flask, current_app
from inspect import signature, Parameter
from functools import wraps


class APIDocumentationGenerator:
    """API文档生成器"""
    
    def __init__(self, app: Optional[Flask] = None):
        """
        初始化API文档生成器
        
        Args:
            app: Flask应用实例
        """
        self.app = app
        self.endpoints = {}
        self.schemas = {}
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """初始化Flask应用"""
        self.app = app
        
        # 注册文档生成钩子
        app.before_request(self._record_request)
        app.after_request(self._record_response)
    
    def _record_request(self):
        """记录请求信息"""
        # 在实际应用中，这里可以记录请求信息用于文档生成
        pass
    
    def _record_response(self, response):
        """记录响应信息"""
        # 在实际应用中，这里可以记录响应信息用于文档生成
        return response
    
    def register_endpoint(self, path: str, method: str, handler: Any, 
                         description: str = "", parameters: List[Dict] = None,
                         responses: Dict = None, tags: List[str] = None):
        """
        注册API端点信息
        
        Args:
            path: API路径
            method: HTTP方法
            handler: 处理函数
            description: 端点描述
            parameters: 参数列表
            responses: 响应定义
            tags: 标签列表
        """
        if path not in self.endpoints:
            self.endpoints[path] = {}
        
        if parameters is None:
            parameters = []
        
        if responses is None:
            responses = {'200': {'description': 'Success'}}
        
        if tags is None:
            tags = []
        
        # 从处理函数中提取参数信息
        sig = signature(handler)
        func_params = []
        
        for name, param in sig.parameters.items():
            if name in ['self', 'args', 'kwargs']:
                continue
                
            param_info = {
                'name': name,
                'in': 'query' if method == 'GET' else 'json',
                'required': param.default == Parameter.empty,
                'type': 'string',
                'description': f"Parameter {name}"
            }
            
            if param.default != Parameter.empty:
                param_info['default'] = param.default
            
            func_params.append(param_info)
        
        # 合并手动提供的参数和从函数提取的参数
        all_params = parameters + func_params
        
        self.endpoints[path][method.lower()] = {
            'handler': handler.__name__,
            'description': description,
            'parameters': all_params,
            'responses': responses,
            'tags': tags
        }
    
    def register_schema(self, name: str, schema: Dict):
        """
        注册数据模型定义
        
        Args:
            name: 模型名称
            schema: 模型定义
        """
        self.schemas[name] = schema
    
    def generate_openapi_spec(self, info: Dict = None) -> Dict:
        """
        生成OpenAPI规范文档
        
        Args:
            info: API基本信息
            
        Returns:
            OpenAPI规范字典
        """
        if info is None:
            info = {
                'title': 'Academic API',
                'version': '1.0.0',
                'description': 'Academic Management System API'
            }
        
        spec = {
            'openapi': '3.0.0',
            'info': info,
            'paths': {},
            'components': {
                'schemas': self.schemas
            }
        }
        
        # 转换端点信息为OpenAPI格式
        for path, methods in self.endpoints.items():
            spec['paths'][path] = {}
            
            for method, endpoint_info in methods.items():
                operation = {
                    'summary': endpoint_info['description'],
                    'description': endpoint_info['description'],
                    'tags': endpoint_info['tags'],
                    'responses': endpoint_info['responses']
                }
                
                if endpoint_info['parameters']:
                    operation['parameters'] = endpoint_info['parameters']
                
                spec['paths'][path][method] = operation
        
        return spec
    
    def generate_postman_collection(self, info: Dict = None) -> Dict:
        """
        生成Postman集合
        
        Args:
            info: 集合基本信息
            
        Returns:
            Postman集合字典
        """
        if info is None:
            info = {
                'name': 'Academic API',
                'description': 'Academic Management System API Collection'
            }
        
        collection = {
            'info': {
                'name': info['name'],
                'description': info.get('description', ''),
                'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'
            },
            'item': []
        }
        
        # 按标签分组
        tags = {}
        for path, methods in self.endpoints.items():
            for method, endpoint_info in methods.items():
                for tag in endpoint_info['tags']:
                    if tag not in tags:
                        tags[tag] = []
                    
                    tags[tag].append({
                        'path': path,
                        'method': method.upper(),
                        'description': endpoint_info['description'],
                        'parameters': endpoint_info['parameters']
                    })
        
        # 创建文件夹和请求
        for tag, items in tags.items():
            folder = {
                'name': tag,
                'item': []
            }
            
            for item in items:
                request = {
                    'name': f"{item['method']} {item['path']}",
                    'request': {
                        'method': item['method'],
                        'header': [],
                        'url': {
                            'raw': "{{base_url}}" + item['path'],
                            'host': ['{{base_url}}'],
                            'path': item['path'].strip('/').split('/')
                        }
                    }
                }
                
                # 添加参数
                if item['parameters']:
                    if item['method'] == 'GET':
                        request['request']['url']['query'] = []
                        for param in item['parameters']:
                            query_param = {
                                'key': param['name'],
                                'value': param.get('default', ''),
                                'description': param.get('description', '')
                            }
                            if not param.get('required', False):
                                query_param['disabled'] = True
                            request['request']['url']['query'].append(query_param)
                    else:
                        # 对于POST/PUT等请求，添加示例body
                        body = {}
                        for param in item['parameters']:
                            if param.get('required', False):
                                body[param['name']] = param.get('default', '')
                        
                        if body:
                            request['request']['body'] = {
                                'mode': 'raw',
                                'raw': json.dumps(body, indent=2),
                                'options': {
                                    'raw': {
                                        'language': 'json'
                                    }
                                }
                            }
                
                folder['item'].append(request)
            
            collection['item'].append(folder)
        
        return collection
    
    def save_documentation(self, output_dir: str = 'docs'):
        """
        保存API文档到文件
        
        Args:
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成OpenAPI规范
        openapi_spec = self.generate_openapi_spec()
        with open(os.path.join(output_dir, 'openapi.json'), 'w', encoding='utf-8') as f:
            json.dump(openapi_spec, f, ensure_ascii=False, indent=2)
        
        # 生成Postman集合
        postman_collection = self.generate_postman_collection()
        with open(os.path.join(output_dir, 'postman_collection.json'), 'w', encoding='utf-8') as f:
            json.dump(postman_collection, f, ensure_ascii=False, indent=2)
        
        # 生成Markdown文档
        markdown_doc = self.generate_markdown_documentation()
        with open(os.path.join(output_dir, 'api_documentation.md'), 'w', encoding='utf-8') as f:
            f.write(markdown_doc)
    
    def generate_markdown_documentation(self) -> str:
        """
        生成Markdown格式的API文档
        
        Returns:
            Markdown文档字符串
        """
        doc = "# Academic API Documentation\n\n"
        doc += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # 按标签分组
        tags = {}
        for path, methods in self.endpoints.items():
            for method, endpoint_info in methods.items():
                for tag in endpoint_info['tags']:
                    if tag not in tags:
                        tags[tag] = []
                    
                    tags[tag].append({
                        'path': path,
                        'method': method.upper(),
                        'description': endpoint_info['description'],
                        'parameters': endpoint_info['parameters'],
                        'responses': endpoint_info['responses']
                    })
        
        # 生成文档
        for tag, items in tags.items():
            doc += f"## {tag}\n\n"
            
            for item in items:
                doc += f"### {item['method']} {item['path']}\n\n"
                doc += f"{item['description']}\n\n"
                
                if item['parameters']:
                    doc += "#### Parameters\n\n"
                    doc += "| Name | In | Type | Required | Description |\n"
                    doc += "|------|----|----|----------|-------------|\n"
                    
                    for param in item['parameters']:
                        required = "Yes" if param.get('required', False) else "No"
                        doc += f"| {param['name']} | {param.get('in', 'query')} | {param.get('type', 'string')} | {required} | {param.get('description', '')} |\n"
                    
                    doc += "\n"
                
                if item['responses']:
                    doc += "#### Responses\n\n"
                    for status, response in item['responses'].items():
                        doc += f"- **{status}**: {response.get('description', '')}\n"
                    doc += "\n"
                
                doc += "---\n\n"
        
        return doc


def document_endpoint(path: str, method: str, description: str = "", 
                     parameters: List[Dict] = None, responses: Dict = None, 
                     tags: List[str] = None):
    """
    装饰器，用于记录API端点信息
    
    Args:
        path: API路径
        method: HTTP方法
        description: 端点描述
        parameters: 参数列表
        responses: 响应定义
        tags: 标签列表
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # 标记函数，以便后续处理
        wrapper._api_doc = {
            'path': path,
            'method': method,
            'description': description,
            'parameters': parameters or [],
            'responses': responses or {'200': {'description': 'Success'}},
            'tags': tags or []
        }
        
        return wrapper
    
    return decorator


# 创建全局文档生成器实例
api_doc_generator = APIDocumentationGenerator()