"""
教师课程资源管理模块
实现课件、参考资料等课程资源的上传、管理和下载功能
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union
import uuid
import mimetypes

from .storage import FileStorage
from .validation import DataValidator, SecurityChecker

logger = logging.getLogger(__name__)


class CourseResourceManager:
    """课程资源管理器"""
    
    def __init__(self, file_storage: FileStorage):
        """
        初始化课程资源管理器
        
        Args:
            file_storage: 文件存储实例
        """
        self.file_storage = file_storage
        self.validator = DataValidator()
        self.security_checker = SecurityChecker()
        
        # 资源元数据存储文件名
        self.metadata_file = "course_resources_metadata.json"
        
        # 支持的文件类型
        self.allowed_file_types = {
            # 文档类型
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'txt': 'text/plain',
            'rtf': 'application/rtf',
            
            # 图片类型
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'svg': 'image/svg+xml',
            
            # 音频类型
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            
            # 视频类型
            'mp4': 'video/mp4',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'wmv': 'video/x-ms-wmv',
            
            # 压缩文件
            'zip': 'application/zip',
            'rar': 'application/x-rar-compressed',
            '7z': 'application/x-7z-compressed',
            
            # 代码文件
            'py': 'text/x-python',
            'js': 'text/javascript',
            'html': 'text/html',
            'css': 'text/css',
            'java': 'text/x-java-source',
            'cpp': 'text/x-c++src',
            'c': 'text/x-csrc',
        }
        
        # 资源类型分类
        self.resource_categories = {
            '课件': ['ppt', 'pptx', 'pdf'],
            '文档': ['doc', 'docx', 'pdf', 'txt', 'rtf'],
            '图片': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg'],
            '音频': ['mp3', 'wav', 'ogg'],
            '视频': ['mp4', 'avi', 'mov', 'wmv'],
            '代码': ['py', 'js', 'html', 'css', 'java', 'cpp', 'c'],
            '其他': ['zip', 'rar', '7z']
        }
    
    def _get_resource_category(self, file_extension: str) -> str:
        """
        根据文件扩展名获取资源类型
        
        Args:
            file_extension: 文件扩展名
            
        Returns:
            资源类型
        """
        file_extension = file_extension.lower()
        
        for category, extensions in self.resource_categories.items():
            if file_extension in extensions:
                return category
        
        return '其他'
    
    def _get_file_type(self, file_extension: str) -> Optional[str]:
        """
        根据文件扩展名获取MIME类型
        
        Args:
            file_extension: 文件扩展名
            
        Returns:
            MIME类型
        """
        file_extension = file_extension.lower()
        return self.allowed_file_types.get(file_extension)
    
    def _is_allowed_file(self, file_extension: str) -> bool:
        """
        检查文件类型是否允许上传
        
        Args:
            file_extension: 文件扩展名
            
        Returns:
            是否允许上传
        """
        file_extension = file_extension.lower()
        return file_extension in self.allowed_file_types
    
    def _generate_file_id(self) -> str:
        """生成唯一的文件ID"""
        return str(uuid.uuid4())
    
    def _get_resource_metadata(self) -> List[Dict]:
        """
        获取所有资源元数据
        
        Returns:
            资源元数据列表
        """
        return self.file_storage.read(self.metadata_file, [])
    
    def _save_resource_metadata(self, metadata: List[Dict]) -> bool:
        """
        保存资源元数据
        
        Args:
            metadata: 资源元数据列表
            
        Returns:
            是否保存成功
        """
        return self.file_storage.write(self.metadata_file, metadata)
    
    def upload_resource(self, course_code: str, title: str, description: str, 
                      file_data: bytes, file_name: str, 
                      uploader: str, tags: List[str] = None) -> Dict:
        """
        上传课程资源
        
        Args:
            course_code: 课程代码
            title: 资源标题
            description: 资源描述
            file_data: 文件数据
            file_name: 文件名
            uploader: 上传者
            tags: 标签列表
            
        Returns:
            上传结果
        """
        try:
            # 验证课程代码
            if not self.validator.validate_course_code(course_code):
                return {"success": False, "message": "无效的课程代码"}
            
            # 验证标题和描述
            if not title or not title.strip():
                return {"success": False, "message": "资源标题不能为空"}
            
            # 获取文件扩展名
            file_extension = os.path.splitext(file_name)[1][1:]  # 去掉点号
            if not file_extension:
                return {"success": False, "message": "无法确定文件类型"}
            
            # 检查文件类型是否允许上传
            if not self._is_allowed_file(file_extension):
                return {"success": False, "message": f"不支持的文件类型: {file_extension}"}
            
            # 获取MIME类型
            mime_type = self._get_file_type(file_extension)
            
            # 获取资源类型
            resource_category = self._get_resource_category(file_extension)
            
            # 生成文件ID和文件路径
            file_id = self._generate_file_id()
            file_path = f"courses/{course_code}/resources/{file_id}.{file_extension}"
            
            # 保存文件
            if not self.file_storage.write_binary(file_path, file_data):
                return {"success": False, "message": "文件保存失败"}
            
            # 创建资源元数据
            resource_metadata = {
                "id": file_id,
                "course_code": course_code,
                "title": self.security_checker.sanitize_input(title),
                "description": self.security_checker.sanitize_input(description),
                "file_name": file_name,
                "file_path": file_path,
                "file_size": len(file_data),
                "file_type": mime_type,
                "file_extension": file_extension,
                "category": resource_category,
                "uploader": uploader,
                "upload_time": datetime.now().isoformat(),
                "download_count": 0,
                "tags": tags or []
            }
            
            # 获取现有元数据
            all_metadata = self._get_resource_metadata()
            
            # 添加新资源元数据
            all_metadata.append(resource_metadata)
            
            # 保存元数据
            if not self._save_resource_metadata(all_metadata):
                # 如果元数据保存失败，删除已上传的文件
                self.file_storage.delete(file_path)
                return {"success": False, "message": "元数据保存失败"}
            
            return {
                "success": True, 
                "message": "资源上传成功",
                "resource": resource_metadata
            }
            
        except Exception as e:
            logger.error(f"上传资源时出错: {str(e)}")
            return {"success": False, "message": f"上传失败: {str(e)}"}
    
    def get_course_resources(self, course_code: str, category: str = None, 
                           tags: List[str] = None, page: int = 1, 
                           per_page: int = 20) -> Dict:
        """
        获取课程资源列表
        
        Args:
            course_code: 课程代码
            category: 资源类型筛选
            tags: 标签筛选
            page: 页码
            per_page: 每页数量
            
        Returns:
            资源列表和分页信息
        """
        try:
            # 验证课程代码
            if not self.validator.validate_course_code(course_code):
                return {"success": False, "message": "无效的课程代码"}
            
            # 获取所有资源元数据
            all_metadata = self._get_resource_metadata()
            
            # 筛选课程资源
            course_resources = [
                resource for resource in all_metadata 
                if resource.get("course_code") == course_code
            ]
            
            # 按类型筛选
            if category:
                course_resources = [
                    resource for resource in course_resources 
                    if resource.get("category") == category
                ]
            
            # 按标签筛选
            if tags:
                course_resources = [
                    resource for resource in course_resources 
                    if any(tag in resource.get("tags", []) for tag in tags)
                ]
            
            # 按上传时间降序排序
            course_resources.sort(
                key=lambda x: x.get("upload_time", ""), 
                reverse=True
            )
            
            # 计算分页
            total = len(course_resources)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_resources = course_resources[start:end]
            
            return {
                "success": True,
                "resources": paginated_resources,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"获取课程资源时出错: {str(e)}")
            return {"success": False, "message": f"获取资源失败: {str(e)}"}
    
    def get_resource(self, resource_id: str) -> Dict:
        """
        获取资源详情
        
        Args:
            resource_id: 资源ID
            
        Returns:
            资源详情
        """
        try:
            # 获取所有资源元数据
            all_metadata = self._get_resource_metadata()
            
            # 查找指定资源
            for resource in all_metadata:
                if resource.get("id") == resource_id:
                    return {"success": True, "resource": resource}
            
            return {"success": False, "message": "资源不存在"}
            
        except Exception as e:
            logger.error(f"获取资源详情时出错: {str(e)}")
            return {"success": False, "message": f"获取资源详情失败: {str(e)}"}
    
    def download_resource(self, resource_id: str) -> Dict:
        """
        下载资源
        
        Args:
            resource_id: 资源ID
            
        Returns:
            资源文件数据和元数据
        """
        try:
            # 获取资源详情
            result = self.get_resource(resource_id)
            if not result["success"]:
                return result
            
            resource = result["resource"]
            file_path = resource.get("file_path")
            
            # 读取文件数据
            file_data = self.file_storage.read_binary(file_path)
            if file_data is None:
                return {"success": False, "message": "文件不存在或已损坏"}
            
            # 更新下载次数
            self._increment_download_count(resource_id)
            
            return {
                "success": True,
                "file_data": file_data,
                "file_name": resource.get("file_name"),
                "file_type": resource.get("file_type"),
                "resource": resource
            }
            
        except Exception as e:
            logger.error(f"下载资源时出错: {str(e)}")
            return {"success": False, "message": f"下载失败: {str(e)}"}
    
    def _increment_download_count(self, resource_id: str) -> bool:
        """
        增加资源下载次数
        
        Args:
            resource_id: 资源ID
            
        Returns:
            是否更新成功
        """
        try:
            # 获取所有资源元数据
            all_metadata = self._get_resource_metadata()
            
            # 查找并更新资源
            for resource in all_metadata:
                if resource.get("id") == resource_id:
                    resource["download_count"] = resource.get("download_count", 0) + 1
                    break
            else:
                return False
            
            # 保存更新后的元数据
            return self._save_resource_metadata(all_metadata)
            
        except Exception as e:
            logger.error(f"更新下载次数时出错: {str(e)}")
            return False
    
    def update_resource(self, resource_id: str, title: str = None, 
                      description: str = None, tags: List[str] = None,
                      updater: str = None) -> Dict:
        """
        更新资源信息
        
        Args:
            resource_id: 资源ID
            title: 新标题
            description: 新描述
            tags: 新标签列表
            updater: 更新者
            
        Returns:
            更新结果
        """
        try:
            # 获取所有资源元数据
            all_metadata = self._get_resource_metadata()
            
            # 查找并更新资源
            for resource in all_metadata:
                if resource.get("id") == resource_id:
                    if title is not None:
                        resource["title"] = self.security_checker.sanitize_input(title)
                    if description is not None:
                        resource["description"] = self.security_checker.sanitize_input(description)
                    if tags is not None:
                        resource["tags"] = tags
                    if updater is not None:
                        resource["updater"] = updater
                        resource["update_time"] = datetime.now().isoformat()
                    break
            else:
                return {"success": False, "message": "资源不存在"}
            
            # 保存更新后的元数据
            if not self._save_resource_metadata(all_metadata):
                return {"success": False, "message": "更新失败"}
            
            return {"success": True, "message": "资源信息更新成功"}
            
        except Exception as e:
            logger.error(f"更新资源信息时出错: {str(e)}")
            return {"success": False, "message": f"更新失败: {str(e)}"}
    
    def delete_resource(self, resource_id: str) -> Dict:
        """
        删除资源
        
        Args:
            resource_id: 资源ID
            
        Returns:
            删除结果
        """
        try:
            # 获取所有资源元数据
            all_metadata = self._get_resource_metadata()
            
            # 查找资源
            resource_to_delete = None
            for i, resource in enumerate(all_metadata):
                if resource.get("id") == resource_id:
                    resource_to_delete = resource
                    all_metadata.pop(i)
                    break
            
            if not resource_to_delete:
                return {"success": False, "message": "资源不存在"}
            
            # 删除文件
            file_path = resource_to_delete.get("file_path")
            if file_path:
                self.file_storage.delete(file_path)
            
            # 保存更新后的元数据
            if not self._save_resource_metadata(all_metadata):
                return {"success": False, "message": "删除失败"}
            
            return {"success": True, "message": "资源删除成功"}
            
        except Exception as e:
            logger.error(f"删除资源时出错: {str(e)}")
            return {"success": False, "message": f"删除失败: {str(e)}"}
    
    def get_resource_categories(self) -> Dict:
        """
        获取资源类型列表
        
        Returns:
            资源类型列表
        """
        return {
            "success": True,
            "categories": list(self.resource_categories.keys())
        }
    
    def get_resource_tags(self, course_code: str = None) -> Dict:
        """
        获取资源标签列表
        
        Args:
            course_code: 课程代码，如果指定则只返回该课程的标签
            
        Returns:
            标签列表
        """
        try:
            # 获取所有资源元数据
            all_metadata = self._get_resource_metadata()
            
            # 筛选课程资源
            if course_code:
                all_metadata = [
                    resource for resource in all_metadata 
                    if resource.get("course_code") == course_code
                ]
            
            # 收集所有标签
            tags_set = set()
            for resource in all_metadata:
                tags_set.update(resource.get("tags", []))
            
            return {
                "success": True,
                "tags": sorted(list(tags_set))
            }
            
        except Exception as e:
            logger.error(f"获取资源标签时出错: {str(e)}")
            return {"success": False, "message": f"获取标签失败: {str(e)}"}
    
    def search_resources(self, course_code: str, query: str, page: int = 1, 
                        per_page: int = 20) -> Dict:
        """
        搜索课程资源
        
        Args:
            course_code: 课程代码
            query: 搜索关键词
            page: 页码
            per_page: 每页数量
            
        Returns:
            搜索结果和分页信息
        """
        try:
            # 验证课程代码
            if not self.validator.validate_course_code(course_code):
                return {"success": False, "message": "无效的课程代码"}
            
            # 获取课程资源
            result = self.get_course_resources(course_code, page=1, per_page=1000)
            if not result["success"]:
                return result
            
            resources = result["resources"]
            
            # 搜索资源
            query = query.lower()
            search_results = []
            
            for resource in resources:
                # 在标题、描述、文件名和标签中搜索
                title = resource.get("title", "").lower()
                description = resource.get("description", "").lower()
                file_name = resource.get("file_name", "").lower()
                tags = [tag.lower() for tag in resource.get("tags", [])]
                
                if (query in title or query in description or 
                    query in file_name or any(query in tag for tag in tags)):
                    search_results.append(resource)
            
            # 计算分页
            total = len(search_results)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_results = search_results[start:end]
            
            return {
                "success": True,
                "resources": paginated_results,
                "query": query,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"搜索资源时出错: {str(e)}")
            return {"success": False, "message": f"搜索失败: {str(e)}"}