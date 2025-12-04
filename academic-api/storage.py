"""
文件存储模块，用于替换内存存储，实现数据持久化
"""
import os
import json
import pickle
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, BinaryIO
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from enhanced_storage import EnhancedFileStorage

class FileStorage:
    """文件存储管理器，基于增强型存储系统"""
    
    def __init__(self, storage_type: str = 'local', storage_config: Optional[Dict] = None):
        """
        初始化文件存储管理器
        
        Args:
            storage_type: 存储类型 ('local', 's3', 'azure', 'gcp')
            storage_config: 存储配置参数
        """
        self.enhanced_storage = EnhancedFileStorage(storage_type, storage_config)
        
        # 元数据存储（在实际应用中，这部分应该存储在数据库中）
        self.metadata_file = 'file_metadata.json'
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """加载文件元数据"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_metadata(self):
        """保存文件元数据"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def save_file(self, file: FileStorage, folder: Optional[str] = None, 
                  custom_filename: Optional[str] = None, 
                  metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        保存文件并记录元数据
        
        Args:
            file: 文件对象
            folder: 文件夹路径
            custom_filename: 自定义文件名
            metadata: 额外的元数据
            
        Returns:
            包含文件信息的字典
        """
        # 保存文件
        result = self.enhanced_storage.save_file(file, folder, custom_filename)
        
        if not result.get('success'):
            return result
        
        # 添加额外的元数据
        file_id = result['file_id']
        file_metadata = {
            'file_id': file_id,
            'filename': result['filename'],
            'original_filename': result['original_filename'],
            'file_path': result['relative_path'],
            'file_size': result['file_size'],
            'file_hash': result['file_hash'],
            'content_type': result['content_type'],
            'storage_type': result['storage_type'],
            'upload_date': result['upload_date'],
            'tags': metadata.get('tags', []) if metadata else [],
            'description': metadata.get('description', '') if metadata else '',
            'uploaded_by': metadata.get('uploaded_by', '') if metadata else '',
            'course_id': metadata.get('course_id', '') if metadata else '',
            'is_public': metadata.get('is_public', False) if metadata else False,
            'download_count': 0,
            'last_accessed': None
        }
        
        # 保存元数据
        self.metadata[file_id] = file_metadata
        self._save_metadata()
        
        return {
            'success': True,
            'file_id': file_id,
            'file_metadata': file_metadata
        }
    
    def get_file(self, file_id: str) -> Optional[BinaryIO]:
        """
        通过文件ID获取文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件对象或None
        """
        file_metadata = self.metadata.get(file_id)
        if not file_metadata:
            return None
        
        # 更新访问计数和最后访问时间
        file_metadata['download_count'] += 1
        file_metadata['last_accessed'] = datetime.now().isoformat()
        self._save_metadata()
        
        return self.enhanced_storage.get_file(file_metadata['file_path'])
    
    def delete_file(self, file_id: str) -> bool:
        """
        通过文件ID删除文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            是否删除成功
        """
        file_metadata = self.metadata.get(file_id)
        if not file_metadata:
            return False
        
        # 删除物理文件
        success = self.enhanced_storage.delete_file(file_metadata['file_path'])
        
        if success:
            # 删除元数据
            del self.metadata[file_id]
            self._save_metadata()
        
        return success
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        通过文件ID获取文件信息
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件信息字典或None
        """
        file_metadata = self.metadata.get(file_id)
        if not file_metadata:
            return None
        
        # 获取物理文件信息
        physical_info = self.enhanced_storage.get_file_info(file_metadata['file_path'])
        
        # 合并信息
        result = file_metadata.copy()
        if physical_info:
            result.update(physical_info)
        
        return result
    
    def update_file_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """
        更新文件元数据
        
        Args:
            file_id: 文件ID
            metadata: 要更新的元数据
            
        Returns:
            是否更新成功
        """
        file_metadata = self.metadata.get(file_id)
        if not file_metadata:
            return False
        
        # 更新元数据
        for key, value in metadata.items():
            if key in file_metadata:
                file_metadata[key] = value
        
        self._save_metadata()
        return True
    
    def search_files(self, query: Optional[str] = None, 
                    tags: Optional[List[str]] = None,
                    course_id: Optional[str] = None,
                    content_type: Optional[str] = None,
                    uploaded_by: Optional[str] = None,
                    is_public: Optional[bool] = None,
                    limit: int = 50,
                    offset: int = 0) -> Dict[str, Any]:
        """
        搜索文件
        
        Args:
            query: 搜索查询字符串
            tags: 标签列表
            course_id: 课程ID
            content_type: 内容类型
            uploaded_by: 上传者
            is_public: 是否公开
            limit: 返回结果数量限制
            offset: 偏移量
            
        Returns:
            搜索结果
        """
        results = []
        
        for file_id, file_metadata in self.metadata.items():
            # 应用过滤条件
            if query:
                search_text = f"{file_metadata['original_filename']} {file_metadata.get('description', '')}".lower()
                if query.lower() not in search_text:
                    continue
            
            if tags:
                if not any(tag in file_metadata.get('tags', []) for tag in tags):
                    continue
            
            if course_id and file_metadata.get('course_id') != course_id:
                continue
            
            if content_type and file_metadata.get('content_type') != content_type:
                continue
            
            if uploaded_by and file_metadata.get('uploaded_by') != uploaded_by:
                continue
            
            if is_public is not None and file_metadata.get('is_public') != is_public:
                continue
            
            results.append(file_metadata)
        
        # 排序（按上传日期降序）
        results.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
        
        # 应用分页
        total = len(results)
        paginated_results = results[offset:offset + limit]
        
        return {
            'success': True,
            'data': paginated_results,
            'pagination': {
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_next': offset + limit < total
            }
        }
    
    def get_file_url(self, file_id: str, expiration: int = 3600) -> Optional[str]:
        """
        通过文件ID获取文件访问URL
        
        Args:
            file_id: 文件ID
            expiration: URL过期时间（秒）
            
        Returns:
            文件URL或None
        """
        file_metadata = self.metadata.get(file_id)
        if not file_metadata:
            return None
        
        return self.enhanced_storage.get_file_url(file_metadata['file_path'], expiration)
    
    def get_files_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        """
        获取课程相关文件
        
        Args:
            course_id: 课程ID
            
        Returns:
            文件列表
        """
        result = self.search_files(course_id=course_id, limit=1000)
        return result.get('data', [])
    
    def get_files_by_user(self, uploaded_by: str) -> List[Dict[str, Any]]:
        """
        获取用户上传的文件
        
        Args:
            uploaded_by: 上传者ID
            
        Returns:
            文件列表
        """
        result = self.search_files(uploaded_by=uploaded_by, limit=1000)
        return result.get('data', [])
    
    def get_public_files(self) -> List[Dict[str, Any]]:
        """
        获取公开文件
        
        Returns:
            文件列表
        """
        result = self.search_files(is_public=True, limit=1000)
        return result.get('data', [])
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            存储统计信息
        """
        total_files = len(self.metadata)
        total_size = sum(meta.get('file_size', 0) for meta in self.metadata.values())
        
        # 按内容类型统计
        content_types = {}
        for meta in self.metadata.values():
            ct = meta.get('content_type', 'unknown')
            content_types[ct] = content_types.get(ct, 0) + 1
        
        # 按课程统计
        courses = {}
        for meta in self.metadata.values():
            course = meta.get('course_id', 'unknown')
            courses[course] = courses.get(course, 0) + 1
        
        # 按上传者统计
        uploaders = {}
        for meta in self.metadata.values():
            uploader = meta.get('uploaded_by', 'unknown')
            uploaders[uploader] = uploaders.get(uploader, 0) + 1
        
        return {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'content_types': content_types,
            'courses': courses,
            'uploaders': uploaders,
            'storage_type': self.enhanced_storage.storage_type
        }

# 创建全局存储实例
storage = FileStorage()