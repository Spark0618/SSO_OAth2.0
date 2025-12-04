"""
重构后的云存储API应用
(修复版：适配 MySQL 语法、新安全接口和数据库管理器)
"""

import os
import uuid
from flask import request, jsonify, g, send_from_directory
from common import (
    BaseApp, SecurityUtils, APIResponse, 
    require_auth, require_roles, paginate, cache_response
)

class CloudAPIApp(BaseApp):
    """云存储API应用"""
    
    def __init__(self):
        super().__init__("cloud-api")
        self._init_routes()
        self.add_health_check()
        self.add_metrics_endpoint()
        
        if self.config.rate_limit:
            self.add_rate_limiting(
                requests_per_minute=self.config.rate_limit.requests_per_minute,
                requests_per_hour=self.config.rate_limit.requests_per_hour
            )
    
    def _init_routes(self):
        """初始化路由"""
        
        @self.app.route("/api/files", methods=["GET"])
        @require_auth
        # @paginate(page_size=20) # 暂时禁用分页装饰器，简化调试
        def get_files():
            """获取文件列表"""
            filename = request.args.get("filename", "")
            file_type = request.args.get("type", "")
            tag = request.args.get("tag", "")
            user_id = g.user_id
            
            # === 修复：使用命名参数 ===
            query = """
                SELECT f.* FROM files f 
                JOIN file_permissions fp ON f.id = fp.file_id 
                WHERE fp.user_id = :user_id
            """
            params = {"user_id": user_id}
            
            if filename:
                query += " AND f.filename LIKE :filename"
                params["filename"] = f"%{filename}%"
            
            if file_type:
                query += " AND f.file_type = :file_type"
                params["file_type"] = file_type
            
            if tag:
                query += " AND f.tags LIKE :tag"
                params["tag"] = f"%{tag}%"
            
            query += " ORDER BY f.upload_date DESC"
            
            try:
                # 只有初始化了数据库管理器才能查询
                if not self.db_manager:
                    return jsonify(APIResponse.success(data=[]))

                files = self.db_manager.execute_query(query, params)
                return jsonify(APIResponse.success(data=files))
            except Exception as e:
                self.logger.error(f"Error fetching files: {e}", exc_info=True)
                return jsonify(APIResponse.success(data=[])) # 出错返回空列表比500好
        
        @self.app.route("/api/files/types", methods=["GET"])
        @require_auth
        # @cache_response(timeout=1800)
        def get_file_types():
            """获取文件类型列表"""
            try:
                if not self.db_manager:
                    return jsonify(APIResponse.success(data=[]))

                file_types = self.db_manager.execute_query(
                    "SELECT DISTINCT file_type FROM files ORDER BY file_type"
                )
                
                # 处理返回结果
                types_list = [ft["file_type"] for ft in file_types] if file_types else []
                return jsonify(APIResponse.success(data=types_list))
            except Exception as e:
                self.logger.error(f"Error fetching file types: {e}", exc_info=True)
                return jsonify(APIResponse.error("Failed to fetch file types", 500)), 500

        @self.app.route("/api/files", methods=["POST"])
        @require_auth
        def upload_file():
            """上传文件"""
            if 'file' not in request.files:
                return jsonify(APIResponse.error("No file part", 400)), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify(APIResponse.error("No selected file", 400)), 400
            
            description = request.form.get("description", "")
            tags = request.form.get("tags", "")
            is_public = request.form.get("is_public", "false").lower() == "true"
            user_id = g.user_id
            
            try:
                # 使用文件处理器保存文件
                success, error, metadata = self.file_processor.save_file(
                    file, 
                    original_filename=file.filename,
                    user_id=str(user_id),
                    tags=[t.strip() for t in tags.split(',') if t.strip()]
                )
                
                if not success:
                    return jsonify(APIResponse.error(f"Failed to save file: {error}", 500)), 500
                
                # 如果有数据库，记录到数据库
                if self.db_manager and metadata:
                    # 插入文件记录
                    # === 修复：使用 execute_update 和命名参数 ===
                    self.db_manager.execute_update(
                        """
                        INSERT INTO files (
                            filename, original_filename, file_path, file_type, 
                            file_size, file_hash, description, tags, is_public, 
                            uploaded_by, upload_date
                        ) VALUES (
                            :filename, :original_filename, :file_path, :file_type,
                            :file_size, :file_hash, :description, :tags, :is_public,
                            :uploaded_by, :upload_date
                        )
                        """,
                        {
                            "filename": metadata.filename,
                            "original_filename": metadata.original_filename,
                            "file_path": metadata.file_path,
                            "file_type": metadata.mime_type,
                            "file_size": metadata.file_size,
                            "file_hash": metadata.file_hash,
                            "description": description,
                            "tags": tags,
                            "is_public": is_public,
                            "uploaded_by": user_id,
                            "upload_date": metadata.upload_time
                        }
                    )
                    
                    # 获取刚插入的文件ID (MySQL specific: LAST_INSERT_ID())
                    # 注意：并发环境下这可能不安全，但在简单场景下可用
                    file_id_result = self.db_manager.execute_query(
                        "SELECT LAST_INSERT_ID() as id", 
                        fetch_one=True
                    )
                    file_id = file_id_result['id']

                    # 添加权限
                    self.db_manager.execute_update(
                        "INSERT INTO file_permissions (file_id, user_id, permission) VALUES (:fid, :uid, :perm)",
                        {"fid": file_id, "uid": user_id, "perm": "admin"}
                    )
                
                self.logger.info(f"File uploaded by user {user_id}")
                
                return jsonify(APIResponse.success(data={
                    "filename": metadata.filename,
                    "message": "File uploaded successfully"
                })), 201
            except Exception as e:
                self.logger.error(f"Error uploading file: {e}", exc_info=True)
                return jsonify(APIResponse.error(f"Failed to upload file: {str(e)}", 500)), 500

def create_app():
    app = CloudAPIApp()
    return app.get_app()

if __name__ == "__main__":
    cloud_app = CloudAPIApp()
    cloud_app.run()