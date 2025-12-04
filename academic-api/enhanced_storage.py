import os
import uuid
import shutil
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, BinaryIO
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

class EnhancedFileStorage:
    """增强型文件存储系统，支持本地存储和云存储"""
    
    def __init__(self, storage_type: str = 'local', storage_config: Optional[Dict] = None):
        """
        初始化文件存储系统
        
        Args:
            storage_type: 存储类型 ('local', 's3', 'azure', 'gcp')
            storage_config: 存储配置参数
        """
        self.storage_type = storage_type
        self.storage_config = storage_config or {}
        
        # 初始化存储配置
        if storage_type == 'local':
            self._init_local_storage()
        elif storage_type == 's3':
            self._init_s3_storage()
        elif storage_type == 'azure':
            self._init_azure_storage()
        elif storage_type == 'gcp':
            self._init_gcp_storage()
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
    
    def _init_local_storage(self):
        """初始化本地存储"""
        self.upload_folder = self.storage_config.get('upload_folder', 'uploads')
        self.max_content_length = self.storage_config.get('max_content_length', 16 * 1024 * 1024)  # 16MB
        self.allowed_extensions = self.storage_config.get('allowed_extensions', 
            ['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 
             'zip', 'rar', 'mp3', 'mp4', 'avi', 'mov', 'py', 'js', 'html', 'css', 'json', 'xml'])
        
        # 确保上传目录存在
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)
        
        # 创建子目录
        for subdir in ['documents', 'images', 'videos', 'audio', 'archives', 'others']:
            subdir_path = os.path.join(self.upload_folder, subdir)
            if not os.path.exists(subdir_path):
                os.makedirs(subdir_path)
    
    def _init_s3_storage(self):
        """初始化AWS S3存储"""
        try:
            import boto3
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.storage_config.get('aws_access_key_id'),
                aws_secret_access_key=self.storage_config.get('aws_secret_access_key'),
                region_name=self.storage_config.get('region', 'us-east-1')
            )
            self.s3_bucket = self.storage_config.get('bucket_name')
            if not self.s3_bucket:
                raise ValueError("S3 bucket name is required")
        except ImportError:
            raise ImportError("boto3 package is required for S3 storage. Install with: pip install boto3")
    
    def _init_azure_storage(self):
        """初始化Azure Blob存储"""
        try:
            from azure.storage.blob import BlobServiceClient
            connection_string = self.storage_config.get('connection_string')
            if not connection_string:
                raise ValueError("Azure connection string is required")
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            self.azure_container = self.storage_config.get('container_name')
            if not self.azure_container:
                raise ValueError("Azure container name is required")
        except ImportError:
            raise ImportError("azure-storage-blob package is required for Azure storage. Install with: pip install azure-storage-blob")
    
    def _init_gcp_storage(self):
        """初始化Google Cloud Storage"""
        try:
            from google.cloud import storage
            credentials_path = self.storage_config.get('credentials_path')
            if credentials_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            self.gcp_client = storage.Client()
            self.gcp_bucket = self.storage_config.get('bucket_name')
            if not self.gcp_bucket:
                raise ValueError("GCP bucket name is required")
        except ImportError:
            raise ImportError("google-cloud-storage package is required for GCP storage. Install with: pip install google-cloud-storage")
    
    def save_file(self, file: FileStorage, folder: Optional[str] = None, 
                  custom_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        保存文件
        
        Args:
            file: 文件对象
            folder: 文件夹路径
            custom_filename: 自定义文件名
            
        Returns:
            包含文件信息的字典
        """
        if not file or not file.filename:
            raise ValueError("No file provided")
        
        # 获取文件名和扩展名
        original_filename = secure_filename(file.filename)
        if not original_filename:
            raise ValueError("Invalid filename")
        
        # 检查文件扩展名
        file_ext = self._get_file_extension(original_filename)
        if self.storage_type == 'local' and file_ext not in self.allowed_extensions:
            raise ValueError(f"File extension '{file_ext}' is not allowed")
        
        # 生成唯一文件名
        if custom_filename:
            filename = secure_filename(custom_filename)
            if not filename.endswith(f".{file_ext}"):
                filename = f"{filename}.{file_ext}"
        else:
            unique_id = str(uuid.uuid4())
            filename = f"{unique_id}.{file_ext}"
        
        # 确定文件夹
        if not folder:
            folder = self._get_folder_by_extension(file_ext)
        
        # 保存文件
        if self.storage_type == 'local':
            return self._save_local(file, filename, folder, original_filename)
        elif self.storage_type == 's3':
            return self._save_s3(file, filename, folder, original_filename)
        elif self.storage_type == 'azure':
            return self._save_azure(file, filename, folder, original_filename)
        elif self.storage_type == 'gcp':
            return self._save_gcp(file, filename, folder, original_filename)
    
    def _save_local(self, file: FileStorage, filename: str, folder: str, 
                   original_filename: str) -> Dict[str, Any]:
        """保存到本地存储"""
        folder_path = os.path.join(self.upload_folder, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        file_path = os.path.join(folder_path, filename)
        
        # 保存文件
        file.save(file_path)
        
        # 获取文件信息
        file_size = os.path.getsize(file_path)
        file_hash = self._calculate_file_hash(file_path)
        
        # 构建相对路径
        relative_path = os.path.join(folder, filename)
        
        return {
            'success': True,
            'file_id': filename.split('.')[0],
            'filename': filename,
            'original_filename': original_filename,
            'file_path': file_path,
            'relative_path': relative_path,
            'file_size': file_size,
            'file_hash': file_hash,
            'content_type': file.content_type,
            'storage_type': self.storage_type,
            'upload_date': datetime.now().isoformat()
        }
    
    def _save_s3(self, file: FileStorage, filename: str, folder: str, 
                original_filename: str) -> Dict[str, Any]:
        """保存到S3存储"""
        key = f"{folder}/{filename}"
        
        # 计算文件哈希
        file_content = file.read()
        file_hash = hashlib.md5(file_content).hexdigest()
        file.seek(0)  # 重置文件指针
        
        # 上传到S3
        self.s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=key,
            Body=file_content,
            ContentType=file.content_type
        )
        
        return {
            'success': True,
            'file_id': filename.split('.')[0],
            'filename': filename,
            'original_filename': original_filename,
            'file_path': f"s3://{self.s3_bucket}/{key}",
            'relative_path': key,
            'file_size': len(file_content),
            'file_hash': file_hash,
            'content_type': file.content_type,
            'storage_type': self.storage_type,
            'upload_date': datetime.now().isoformat()
        }
    
    def _save_azure(self, file: FileStorage, filename: str, folder: str, 
                   original_filename: str) -> Dict[str, Any]:
        """保存到Azure Blob存储"""
        blob_name = f"{folder}/{filename}"
        blob_client = self.blob_service_client.get_blob_client(
            container=self.azure_container, blob=blob_name
        )
        
        # 计算文件哈希
        file_content = file.read()
        file_hash = hashlib.md5(file_content).hexdigest()
        file.seek(0)  # 重置文件指针
        
        # 上传到Azure
        blob_client.upload_blob(file_content, overwrite=True)
        
        return {
            'success': True,
            'file_id': filename.split('.')[0],
            'filename': filename,
            'original_filename': original_filename,
            'file_path': blob_client.url,
            'relative_path': blob_name,
            'file_size': len(file_content),
            'file_hash': file_hash,
            'content_type': file.content_type,
            'storage_type': self.storage_type,
            'upload_date': datetime.now().isoformat()
        }
    
    def _save_gcp(self, file: FileStorage, filename: str, folder: str, 
                original_filename: str) -> Dict[str, Any]:
        """保存到GCP存储"""
        blob_name = f"{folder}/{filename}"
        bucket = self.gcp_client.bucket(self.gcp_bucket)
        blob = bucket.blob(blob_name)
        
        # 计算文件哈希
        file_content = file.read()
        file_hash = hashlib.md5(file_content).hexdigest()
        file.seek(0)  # 重置文件指针
        
        # 上传到GCP
        blob.upload_from_string(file_content, content_type=file.content_type)
        
        return {
            'success': True,
            'file_id': filename.split('.')[0],
            'filename': filename,
            'original_filename': original_filename,
            'file_path': f"gs://{self.gcp_bucket}/{blob_name}",
            'relative_path': blob_name,
            'file_size': len(file_content),
            'file_hash': file_hash,
            'content_type': file.content_type,
            'storage_type': self.storage_type,
            'upload_date': datetime.now().isoformat()
        }
    
    def get_file(self, file_path: str) -> Optional[BinaryIO]:
        """
        获取文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件对象或None
        """
        if self.storage_type == 'local':
            full_path = os.path.join(self.upload_folder, file_path)
            if os.path.exists(full_path):
                return open(full_path, 'rb')
        elif self.storage_type == 's3':
            try:
                response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=file_path)
                return response['Body']
            except Exception:
                return None
        elif self.storage_type == 'azure':
            try:
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.azure_container, blob=file_path
                )
                return blob_client.download_blob().readinto()
            except Exception:
                return None
        elif self.storage_type == 'gcp':
            try:
                bucket = self.gcp_client.bucket(self.gcp_bucket)
                blob = bucket.blob(file_path)
                return blob.download_as_bytes()
            except Exception:
                return None
        
        return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否删除成功
        """
        try:
            if self.storage_type == 'local':
                full_path = os.path.join(self.upload_folder, file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    return True
            elif self.storage_type == 's3':
                self.s3_client.delete_object(Bucket=self.s3_bucket, Key=file_path)
                return True
            elif self.storage_type == 'azure':
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.azure_container, blob=file_path
                )
                blob_client.delete_blob()
                return True
            elif self.storage_type == 'gcp':
                bucket = self.gcp_client.bucket(self.gcp_bucket)
                blob = bucket.blob(file_path)
                blob.delete()
                return True
        except Exception:
            pass
        
        return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否存在
        """
        if self.storage_type == 'local':
            full_path = os.path.join(self.upload_folder, file_path)
            return os.path.exists(full_path)
        elif self.storage_type == 's3':
            try:
                self.s3_client.head_object(Bucket=self.s3_bucket, Key=file_path)
                return True
            except Exception:
                return False
        elif self.storage_type == 'azure':
            try:
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.azure_container, blob=file_path
                )
                blob_client.get_blob_properties()
                return True
            except Exception:
                return False
        elif self.storage_type == 'gcp':
            try:
                bucket = self.gcp_client.bucket(self.gcp_bucket)
                blob = bucket.blob(file_path)
                return blob.exists()
            except Exception:
                return False
        
        return False
    
    def get_file_url(self, file_path: str, expiration: int = 3600) -> Optional[str]:
        """
        获取文件访问URL
        
        Args:
            file_path: 文件路径
            expiration: URL过期时间（秒）
            
        Returns:
            文件URL或None
        """
        if self.storage_type == 'local':
            # 本地存储返回相对路径，由应用处理
            return f"/files/{file_path}"
        elif self.storage_type == 's3':
            try:
                return self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.s3_bucket, 'Key': file_path},
                    ExpiresIn=expiration
                )
            except Exception:
                return None
        elif self.storage_type == 'azure':
            try:
                from azure.storage.blob import generate_blob_sas, BlobSasPermissions
                sas_token = generate_blob_sas(
                    account_name=self.storage_config.get('account_name'),
                    account_key=self.storage_config.get('account_key'),
                    container_name=self.azure_container,
                    blob_name=file_path,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(seconds=expiration)
                )
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.azure_container, blob=file_path
                )
                return f"{blob_client.url}?{sas_token}"
            except Exception:
                return None
        elif self.storage_type == 'gcp':
            try:
                from google.cloud import storage
                from datetime import timedelta
                bucket = self.gcp_client.bucket(self.gcp_bucket)
                blob = bucket.blob(file_path)
                return blob.generate_signed_url(expiration=timedelta(seconds=expiration))
            except Exception:
                return None
        
        return None
    
    def _get_file_extension(self, filename: str) -> str:
        """获取文件扩展名"""
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    def _get_folder_by_extension(self, extension: str) -> str:
        """根据扩展名获取文件夹"""
        if extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg']:
            return 'images'
        elif extension in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm']:
            return 'videos'
        elif extension in ['mp3', 'wav', 'flac', 'aac', 'ogg']:
            return 'audio'
        elif extension in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']:
            return 'documents'
        elif extension in ['zip', 'rar', '7z', 'tar', 'gz']:
            return 'archives'
        else:
            return 'others'
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典或None
        """
        if self.storage_type == 'local':
            full_path = os.path.join(self.upload_folder, file_path)
            if os.path.exists(full_path):
                stat = os.stat(full_path)
                return {
                    'file_path': file_path,
                    'file_size': stat.st_size,
                    'created_date': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified_date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'storage_type': self.storage_type
                }
        elif self.storage_type == 's3':
            try:
                response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=file_path)
                return {
                    'file_path': file_path,
                    'file_size': response['ContentLength'],
                    'created_date': response['LastModified'].isoformat(),
                    'modified_date': response['LastModified'].isoformat(),
                    'content_type': response.get('ContentType'),
                    'storage_type': self.storage_type
                }
            except Exception:
                return None
        elif self.storage_type == 'azure':
            try:
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.azure_container, blob=file_path
                )
                properties = blob_client.get_blob_properties()
                return {
                    'file_path': file_path,
                    'file_size': properties.size,
                    'created_date': properties.creation_time.isoformat(),
                    'modified_date': properties.last_modified.isoformat(),
                    'content_type': properties.content_settings.content_type,
                    'storage_type': self.storage_type
                }
            except Exception:
                return None
        elif self.storage_type == 'gcp':
            try:
                bucket = self.gcp_client.bucket(self.gcp_bucket)
                blob = bucket.blob(file_path)
                if blob.exists():
                    blob.reload()
                    return {
                        'file_path': file_path,
                        'file_size': blob.size,
                        'created_date': blob.time_created.isoformat(),
                        'modified_date': blob.updated.isoformat(),
                        'content_type': blob.content_type,
                        'storage_type': self.storage_type
                    }
            except Exception:
                return None
        
        return None
    
    def list_files(self, folder: Optional[str] = None, 
                   prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出文件
        
        Args:
            folder: 文件夹路径
            prefix: 文件名前缀
            
        Returns:
            文件信息列表
        """
        files = []
        
        if self.storage_type == 'local':
            search_path = os.path.join(self.upload_folder, folder) if folder else self.upload_folder
            if os.path.exists(search_path):
                for root, _, filenames in os.walk(search_path):
                    for filename in filenames:
                        if prefix and not filename.startswith(prefix):
                            continue
                        
                        file_path = os.path.join(root, filename)
                        relative_path = os.path.relpath(file_path, self.upload_folder)
                        file_info = self.get_file_info(relative_path)
                        if file_info:
                            file_info['filename'] = filename
                            file_info['folder'] = os.path.dirname(relative_path)
                            files.append(file_info)
        elif self.storage_type == 's3':
            prefix = f"{folder}/" if folder else ""
            if prefix:
                prefix += prefix if prefix else ""
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if prefix and not obj['Key'].endswith(prefix):
                            continue
                        
                        file_info = {
                            'file_path': obj['Key'],
                            'file_size': obj['Size'],
                            'created_date': obj['LastModified'].isoformat(),
                            'modified_date': obj['LastModified'].isoformat(),
                            'storage_type': self.storage_type,
                            'filename': os.path.basename(obj['Key']),
                            'folder': os.path.dirname(obj['Key'])
                        }
                        files.append(file_info)
        elif self.storage_type == 'azure':
            prefix = f"{folder}/" if folder else ""
            if prefix:
                prefix += prefix if prefix else ""
            
            blobs = self.blob_service_client.get_container_client(self.azure_container).list_blobs(
                name_starts_with=prefix
            )
            
            for blob in blobs:
                if prefix and not blob.name.endswith(prefix):
                    continue
                
                file_info = {
                    'file_path': blob.name,
                    'file_size': blob.size,
                    'created_date': blob.creation_time.isoformat(),
                    'modified_date': blob.last_modified.isoformat(),
                    'content_type': blob.content_settings.content_type,
                    'storage_type': self.storage_type,
                    'filename': os.path.basename(blob.name),
                    'folder': os.path.dirname(blob.name)
                }
                files.append(file_info)
        elif self.storage_type == 'gcp':
            prefix = f"{folder}/" if folder else ""
            if prefix:
                prefix += prefix if prefix else ""
            
            blobs = self.gcp_client.bucket(self.gcp_bucket).list_blobs(prefix=prefix)
            
            for blob in blobs:
                if prefix and not blob.name.endswith(prefix):
                    continue
                
                file_info = {
                    'file_path': blob.name,
                    'file_size': blob.size,
                    'created_date': blob.time_created.isoformat(),
                    'modified_date': blob.updated.isoformat(),
                    'content_type': blob.content_type,
                    'storage_type': self.storage_type,
                    'filename': os.path.basename(blob.name),
                    'folder': os.path.dirname(blob.name)
                }
                files.append(file_info)
        
        return files