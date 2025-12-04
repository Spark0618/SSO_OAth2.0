"""
数据备份和恢复模块
提供数据库备份、恢复和导出功能
"""

import os
import json
import shutil
import zipfile
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from connection_pool import get_pool_manager
from cache import get_default_cache_manager
from audit_logger import audit_logger, AuditEventType

logger = logging.getLogger(__name__)

class BackupManager:
    """数据备份和恢复管理器"""
    
    def __init__(self, pool_manager, cache_manager=None):
        self.pool_manager = pool_manager
        self.cache_manager = cache_manager
        self.backup_dir = os.environ.get("BACKUP_DIR", "backups")
        
        # 确保备份目录存在
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_database_backup(self, include_files: bool = True, 
                             compress: bool = True) -> Dict[str, Any]:
        """
        创建数据库备份
        
        Args:
            include_files: 是否包含上传的文件
            compress: 是否压缩备份
            
        Returns:
            备份结果信息
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_backup_dir = os.path.join(temp_dir, backup_name)
                os.makedirs(temp_backup_dir)
                
                # 备份数据库结构
                schema_file = os.path.join(temp_backup_dir, "schema.sql")
                self._export_database_schema(schema_file)
                
                # 备份数据
                data_file = os.path.join(temp_backup_dir, "data.json")
                self._export_database_data(data_file)
                
                # 备份元数据
                metadata_file = os.path.join(temp_backup_dir, "metadata.json")
                self._export_metadata(metadata_file, include_files)
                
                # 备份文件（如果需要）
                if include_files:
                    files_dir = os.path.join(temp_backup_dir, "files")
                    self._backup_files(files_dir)
                
                # 压缩备份（如果需要）
                if compress:
                    backup_file = os.path.join(self.backup_dir, f"{backup_name}.zip")
                    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(temp_backup_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, temp_dir)
                                zipf.write(file_path, arcname)
                    
                    backup_path = backup_file
                else:
                    # 复制临时目录到备份目录
                    shutil.copytree(temp_backup_dir, backup_path)
                
                # 记录审计日志
                audit_logger.log_event(
                    AuditEventType.SYSTEM_BACKUP,
                    f"Created database backup: {backup_name}",
                    {"backup_path": backup_path, "include_files": include_files, "compress": compress}
                )
                
                return {
                    "success": True,
                    "backup_name": backup_name,
                    "backup_path": backup_path,
                    "timestamp": timestamp,
                    "size_mb": round(os.path.getsize(backup_path) / (1024 * 1024), 2),
                    "include_files": include_files,
                    "compressed": compress
                }
                
        except Exception as e:
            logger.error(f"Failed to create database backup: {str(e)}")
            audit_logger.log_event(
                AuditEventType.SYSTEM_BACKUP,
                f"Failed to create database backup: {str(e)}",
                {"error": str(e)}
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    def restore_database_backup(self, backup_path: str, 
                              restore_files: bool = True) -> Dict[str, Any]:
        """
        从备份恢复数据库
        
        Args:
            backup_path: 备份文件路径
            restore_files: 是否恢复文件
            
        Returns:
            恢复结果信息
        """
        try:
            # 检查备份文件是否存在
            if not os.path.exists(backup_path):
                return {
                    "success": False,
                    "error": f"Backup file not found: {backup_path}"
                }
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 解压备份文件（如果是压缩的）
                if backup_path.endswith('.zip'):
                    with zipfile.ZipFile(backup_path, 'r') as zipf:
                        zipf.extractall(temp_dir)
                    # 找到解压后的备份目录
                    backup_dirs = [d for d in os.listdir(temp_dir) if d.startswith('backup_')]
                    if not backup_dirs:
                        return {
                            "success": False,
                            "error": "Invalid backup format: no backup directory found"
                        }
                    backup_dir = os.path.join(temp_dir, backup_dirs[0])
                else:
                    backup_dir = backup_path
                
                # 检查备份文件完整性
                schema_file = os.path.join(backup_dir, "schema.sql")
                data_file = os.path.join(backup_dir, "data.json")
                metadata_file = os.path.join(backup_dir, "metadata.json")
                
                if not all(os.path.exists(f) for f in [schema_file, data_file, metadata_file]):
                    return {
                        "success": False,
                        "error": "Invalid backup format: missing required files"
                    }
                
                # 读取元数据
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # 开始恢复过程
                with self.pool_manager.get_session() as session:
                    try:
                        # 恢复数据库结构
                        self._restore_database_schema(session, schema_file)
                        
                        # 恢复数据
                        self._restore_database_data(session, data_file)
                        
                        session.commit()
                        
                        # 恢复文件（如果需要）
                        if restore_files and metadata.get("include_files", False):
                            files_dir = os.path.join(backup_dir, "files")
                            if os.path.exists(files_dir):
                                self._restore_files(files_dir)
                        
                        # 清除缓存
                        if self.cache_manager:
                            self.cache_manager.clear()
                        
                        # 记录审计日志
                        audit_logger.log_event(
                            AuditEventType.SYSTEM_RESTORE,
                            f"Restored database from backup: {backup_path}",
                            {"backup_path": backup_path, "restore_files": restore_files}
                        )
                        
                        return {
                            "success": True,
                            "backup_name": metadata.get("backup_name", "unknown"),
                            "backup_timestamp": metadata.get("timestamp", "unknown"),
                            "restored_tables": metadata.get("tables", []),
                            "restored_files": restore_files and metadata.get("include_files", False)
                        }
                        
                    except Exception as e:
                        session.rollback()
                        raise e
                        
        except Exception as e:
            logger.error(f"Failed to restore database from backup: {str(e)}")
            audit_logger.log_event(
                AuditEventType.SYSTEM_RESTORE,
                f"Failed to restore database from backup: {str(e)}",
                {"backup_path": backup_path, "error": str(e)}
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的备份
        
        Returns:
            备份列表
        """
        backups = []
        
        try:
            for item in os.listdir(self.backup_dir):
                item_path = os.path.join(self.backup_dir, item)
                
                # 处理压缩备份
                if item.endswith('.zip') and item.startswith('backup_'):
                    try:
                        # 获取文件信息
                        stat = os.stat(item_path)
                        size_mb = round(stat.st_size / (1024 * 1024), 2)
                        created_time = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 尝试读取元数据
                        metadata = self._read_backup_metadata(item_path)
                        
                        backups.append({
                            "name": item,
                            "path": item_path,
                            "size_mb": size_mb,
                            "created_time": created_time,
                            "backup_name": metadata.get("backup_name", item.replace('.zip', '')),
                            "timestamp": metadata.get("timestamp", created_time),
                            "include_files": metadata.get("include_files", False),
                            "compressed": True,
                            "tables": metadata.get("tables", [])
                        })
                    except Exception as e:
                        logger.warning(f"Failed to read backup metadata for {item}: {str(e)}")
                        backups.append({
                            "name": item,
                            "path": item_path,
                            "size_mb": round(os.path.getsize(item_path) / (1024 * 1024), 2),
                            "created_time": datetime.fromtimestamp(os.path.getctime(item_path)).strftime("%Y-%m-%d %H:%M:%S"),
                            "error": "Failed to read metadata"
                        })
                
                # 处理未压缩备份
                elif os.path.isdir(item_path) and item.startswith('backup_'):
                    try:
                        # 计算目录大小
                        total_size = 0
                        for root, _, files in os.walk(item_path):
                            for file in files:
                                total_size += os.path.getsize(os.path.join(root, file))
                        
                        size_mb = round(total_size / (1024 * 1024), 2)
                        created_time = datetime.fromtimestamp(os.path.getctime(item_path)).strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 尝试读取元数据
                        metadata_file = os.path.join(item_path, "metadata.json")
                        metadata = {}
                        if os.path.exists(metadata_file):
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                        
                        backups.append({
                            "name": item,
                            "path": item_path,
                            "size_mb": size_mb,
                            "created_time": created_time,
                            "backup_name": metadata.get("backup_name", item),
                            "timestamp": metadata.get("timestamp", created_time),
                            "include_files": metadata.get("include_files", False),
                            "compressed": False,
                            "tables": metadata.get("tables", [])
                        })
                    except Exception as e:
                        logger.warning(f"Failed to read backup metadata for {item}: {str(e)}")
                        backups.append({
                            "name": item,
                            "path": item_path,
                            "error": "Failed to read metadata"
                        })
            
            # 按创建时间排序（最新的在前）
            backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list backups: {str(e)}")
        
        return backups
    
    def delete_backup(self, backup_path: str) -> Dict[str, Any]:
        """
        删除备份
        
        Args:
            backup_path: 备份文件或目录路径
            
        Returns:
            删除结果
        """
        try:
            if not os.path.exists(backup_path):
                return {
                    "success": False,
                    "error": f"Backup not found: {backup_path}"
                }
            
            if os.path.isfile(backup_path):
                os.remove(backup_path)
            else:
                shutil.rmtree(backup_path)
            
            # 记录审计日志
            audit_logger.log_event(
                AuditEventType.SYSTEM_BACKUP,
                f"Deleted backup: {backup_path}",
                {"backup_path": backup_path}
            )
            
            return {
                "success": True,
                "message": f"Backup deleted successfully: {backup_path}"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_path}: {str(e)}")
            audit_logger.log_event(
                AuditEventType.SYSTEM_BACKUP,
                f"Failed to delete backup: {str(e)}",
                {"backup_path": backup_path, "error": str(e)}
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    def _export_database_schema(self, schema_file: str) -> None:
        """导出数据库结构"""
        with self.pool_manager.get_session() as session:
            inspector = inspect(session.bind)
            
            with open(schema_file, 'w', encoding='utf-8') as f:
                # 写入表结构
                for table_name in inspector.get_table_names():
                    # 获取表创建语句
                    create_table_sql = self._get_table_create_sql(session, table_name)
                    if create_table_sql:
                        f.write(f"-- Table: {table_name}\n")
                        f.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                        f.write(f"{create_table_sql};\n\n")
    
    def _export_database_data(self, data_file: str) -> None:
        """导出数据库数据"""
        data = {}
        
        with self.pool_manager.get_session() as session:
            inspector = inspect(session.bind)
            
            # 获取所有表名
            table_names = inspector.get_table_names()
            
            # 导出每个表的数据
            for table_name in table_names:
                try:
                    # 获取表数据
                    rows = session.execute(text(f"SELECT * FROM {table_name}")).fetchall()
                    
                    # 转换为字典列表
                    table_data = []
                    columns = [column['name'] for column in inspector.get_columns(table_name)]
                    
                    for row in rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            # 处理日期时间类型
                            if hasattr(value, 'isoformat'):
                                row_dict[columns[i]] = value.isoformat()
                            else:
                                row_dict[columns[i]] = value
                        table_data.append(row_dict)
                    
                    data[table_name] = table_data
                    
                except Exception as e:
                    logger.warning(f"Failed to export data for table {table_name}: {str(e)}")
                    data[table_name] = []
        
        # 写入JSON文件
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _export_metadata(self, metadata_file: str, include_files: bool) -> None:
        """导出元数据"""
        with self.pool_manager.get_session() as session:
            inspector = inspect(session.bind)
            table_names = inspector.get_table_names()
        
        metadata = {
            "backup_name": os.path.basename(metadata_file).replace('.json', ''),
            "timestamp": datetime.now().isoformat(),
            "tables": table_names,
            "include_files": include_files,
            "version": "1.0"
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def _backup_files(self, files_dir: str) -> None:
        """备份上传的文件"""
        uploads_dir = os.environ.get("UPLOADS_DIR", "uploads")
        
        if os.path.exists(uploads_dir):
            shutil.copytree(uploads_dir, files_dir)
    
    def _get_table_create_sql(self, session, table_name: str) -> str:
        """获取表创建SQL语句"""
        try:
            # 使用SHOW CREATE TABLE获取创建语句
            result = session.execute(text(f"SHOW CREATE TABLE `{table_name}`")).fetchone()
            if result:
                return result[1]
        except Exception as e:
            logger.warning(f"Failed to get create SQL for table {table_name}: {str(e)}")
        
        return ""
    
    def _restore_database_schema(self, session, schema_file: str) -> None:
        """恢复数据库结构"""
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 分割SQL语句
        statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
        
        for statement in statements:
            if statement and not statement.startswith('--'):
                try:
                    session.execute(text(statement))
                except Exception as e:
                    logger.warning(f"Failed to execute SQL statement: {statement[:100]}... Error: {str(e)}")
    
    def _restore_database_data(self, session, data_file: str) -> None:
        """恢复数据库数据"""
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for table_name, rows in data.items():
            if not rows:
                continue
            
            try:
                # 获取表列信息
                inspector = inspect(session.bind)
                columns = [column['name'] for column in inspector.get_columns(table_name)]
                
                # 清空表数据
                session.execute(text(f"DELETE FROM `{table_name}`"))
                
                # 插入数据
                for row in rows:
                    # 过滤有效列
                    valid_columns = [col for col in columns if col in row]
                    valid_values = [row[col] for col in valid_columns]
                    
                    if valid_columns:
                        placeholders = ', '.join([f":{col}" for col in valid_columns])
                        insert_sql = f"INSERT INTO `{table_name}` ({', '.join([f'`{col}`' for col in valid_columns])}) VALUES ({placeholders})"
                        params = {col: row[col] for col in valid_columns}
                        session.execute(text(insert_sql), params)
                
            except Exception as e:
                logger.warning(f"Failed to restore data for table {table_name}: {str(e)}")
    
    def _restore_files(self, files_dir: str) -> None:
        """恢复上传的文件"""
        uploads_dir = os.environ.get("UPLOADS_DIR", "uploads")
        
        # 备份现有文件（如果存在）
        if os.path.exists(uploads_dir):
            backup_uploads_dir = f"{uploads_dir}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.move(uploads_dir, backup_uploads_dir)
        
        # 恢复文件
        shutil.copytree(files_dir, uploads_dir)
    
    def _read_backup_metadata(self, backup_path: str) -> Dict[str, Any]:
        """读取备份元数据"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # 解压备份文件
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
                
                # 找到元数据文件
                for root, _, files in os.walk(temp_dir):
                    if "metadata.json" in files:
                        metadata_file = os.path.join(root, "metadata.json")
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            return json.load(f)
            
            return {}
        except Exception as e:
            logger.warning(f"Failed to read backup metadata: {str(e)}")
            return {}


# 全局备份管理器实例
_backup_manager = None

def get_backup_manager() -> BackupManager:
    """获取全局备份管理器实例"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager(
            pool_manager=get_pool_manager(),
            cache_manager=get_default_cache_manager()
        )
    return _backup_manager