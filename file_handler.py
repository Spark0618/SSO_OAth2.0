"""
文件处理工具模块，提供安全的文件上传和处理功能
(修复版：添加 storage_type 参数)
"""
import os
import uuid
import hashlib
import time
import mimetypes
import shutil
from typing import Dict, List, Optional, Any, Tuple, BinaryIO
from dataclasses import dataclass, asdict
from datetime import datetime
from werkzeug.utils import secure_filename
import magic
from PIL import Image
import json

@dataclass
class FileMetadata:
    """文件元数据"""
    file_id: str
    original_filename: str
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    file_hash: str
    upload_time: datetime
    storage_type: str = "local"  # 新增
    user_id: Optional[str] = None
    course_id: Optional[str] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if isinstance(self.upload_time, str):
            self.upload_time = datetime.fromisoformat(self.upload_time)
        if self.last_accessed and isinstance(self.last_accessed, str):
            self.last_accessed = datetime.fromisoformat(self.last_accessed)

class FileProcessor:
    """文件处理器"""
    
    # === 修复：添加 storage_type 参数 ===
    def __init__(self, storage_type: str = "local", 
                 upload_folder: str = "uploads", 
                 max_content_length: int = 16 * 1024 * 1024,
                 allowed_extensions: List[str] = None, 
                 thumbnail_size: Tuple[int, int] = (200, 200)):
        """
        初始化文件处理器
        """
        self.storage_type = storage_type  # 保存存储类型
        self.upload_folder = upload_folder
        self.max_content_length = max_content_length
        self.allowed_extensions = allowed_extensions or [
            'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
            'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'mp3', 'mp4', 
            'avi', 'mov', 'py', 'js', 'html', 'css', 'json', 'xml'
        ]
        self.thumbnail_size = thumbnail_size
        
        # 仅在本地存储时创建文件夹
        if self.storage_type == "local":
            os.makedirs(upload_folder, exist_ok=True)
            self.thumbnail_folder = os.path.join(upload_folder, 'thumbnails')
            os.makedirs(self.thumbnail_folder, exist_ok=True)
            self.metadata_file = os.path.join(upload_folder, 'metadata.json')
            self.metadata = self._load_metadata()
        else:
            self.metadata = {}

    def _load_metadata(self) -> Dict[str, FileMetadata]:
        """加载文件元数据"""
        if self.storage_type != "local" or not os.path.exists(self.metadata_file):
            return {}
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            metadata = {}
            for file_id, meta_dict in data.items():
                # 兼容旧数据
                if 'storage_type' not in meta_dict:
                    meta_dict['storage_type'] = 'local'
                metadata[file_id] = FileMetadata(**meta_dict)
            return metadata
        except Exception as e:
            print(f"Error loading metadata: {e}")
            return {}
    
    def _save_metadata(self):
        """保存文件元数据"""
        if self.storage_type != "local":
            return False
        try:
            data = {}
            for file_id, meta in self.metadata.items():
                meta_dict = asdict(meta)
                meta_dict['upload_time'] = meta.upload_time.isoformat()
                if meta.last_accessed:
                    meta_dict['last_accessed'] = meta.last_accessed.isoformat()
                data[file_id] = meta_dict
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving metadata: {e}")
            return False
    
    def _generate_file_id(self) -> str:
        return str(uuid.uuid4())
    
    def _generate_filename(self, original_filename: str) -> str:
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{ext}"
    
    def _calculate_file_hash(self, file_path: str) -> str:
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _get_mime_type(self, file_path: str) -> str:
        try:
            return magic.from_file(file_path, mime=True)
        except:
            mime_type, _ = mimetypes.guess_type(file_path)
            return mime_type or 'application/octet-stream'
    
    def _create_thumbnail(self, file_path: str, file_id: str) -> Optional[str]:
        if self.storage_type != "local": return None
        try:
            mime_type = self._get_mime_type(file_path)
            if not mime_type.startswith('image/'):
                return None
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail(self.thumbnail_size)
                thumbnail_path = os.path.join(self.thumbnail_folder, f"{file_id}.jpg")
                img.save(thumbnail_path, 'JPEG', quality=85)
                return thumbnail_path
        except Exception as e:
            print(f"Error creating thumbnail: {e}")
            return None
    
    def _validate_file(self, file_path: str, original_filename: str) -> Tuple[bool, str]:
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        file_size = os.path.getsize(file_path)
        if file_size > self.max_content_length:
            return False, f"File size exceeds maximum allowed size ({self.max_content_length} bytes)"
        
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower().lstrip('.')
        if ext not in self.allowed_extensions:
            return False, f"File extension '{ext}' is not allowed"
        
        return True, ""
    
    def save_file(self, file: BinaryIO, original_filename: str, 
                 user_id: Optional[str] = None, 
                 course_id: Optional[str] = None,
                 tags: List[str] = None) -> Tuple[bool, Optional[str], Optional[FileMetadata]]:
        if self.storage_type != "local":
            return False, "Only local storage is currently implemented", None

        try:
            file_id = self._generate_file_id()
            filename = self._generate_filename(original_filename)
            file_path = os.path.join(self.upload_folder, filename)
            
            file.seek(0)
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(file, f)
            
            is_valid, error_msg = self._validate_file(file_path, original_filename)
            if not is_valid:
                os.remove(file_path)
                return False, error_msg, None
            
            file_hash = self._calculate_file_hash(file_path)
            file_size = os.path.getsize(file_path)
            mime_type = self._get_mime_type(file_path)
            self._create_thumbnail(file_path, file_id)
            
            metadata = FileMetadata(
                file_id=file_id,
                original_filename=original_filename,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                file_hash=file_hash,
                upload_time=datetime.now(),
                storage_type=self.storage_type,
                user_id=user_id,
                course_id=course_id,
                tags=tags or []
            )
            
            self.metadata[file_id] = metadata
            self._save_metadata()
            return True, None, metadata
        except Exception as e:
            return False, f"Error saving file: {str(e)}", None

    # (其他 get/delete/search 方法保持不变，为了节省篇幅我省略了，请确保保留它们)
    def get_file(self, file_id: str) -> Optional[FileMetadata]:
        metadata = self.metadata.get(file_id)
        if metadata:
            metadata.access_count += 1
            metadata.last_accessed = datetime.now()
            self._save_metadata()
        return metadata
    
    def delete_file(self, file_id: str) -> bool:
        # 简单实现
        if file_id in self.metadata:
            del self.metadata[file_id]
            self._save_metadata()
            return True
        return False