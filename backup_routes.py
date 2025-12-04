"""
备份和恢复API路由
提供数据备份和恢复的REST API接口
"""

import os
import json
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file
from werkzeug.exceptions import BadRequest

from validation import validate_request, require_role, sanitize_input
from audit_logger import audit_logger, AuditEventType
from backup_manager import get_backup_manager

# 创建备份和恢复蓝图
backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

@backup_bp.route("/create", methods=["POST"])
@validate_request
@require_role("admin")
def create_backup():
    """创建数据库备份"""
    try:
        # 获取请求参数
        data = request.get_json() or {}
        include_files = data.get("include_files", True)
        compress = data.get("compress", True)
        
        # 创建备份
        backup_manager = get_backup_manager()
        result = backup_manager.create_database_backup(
            include_files=include_files,
            compress=compress
        )
        
        if result.get("success"):
            return jsonify({
                "message": "Backup created successfully",
                "backup": result
            })
        else:
            return jsonify({
                "error": "Failed to create backup",
                "details": result.get("error", "Unknown error")
            }), 500
            
    except Exception as e:
        audit_logger.log_error(
            "create_backup", 
            str(e), 
            {"include_files": data.get("include_files", True), "compress": data.get("compress", True)}
        )
        return jsonify({"error": "Failed to create backup", "details": str(e)}), 500


@backup_bp.route("/restore", methods=["POST"])
@validate_request
@require_role("admin")
def restore_backup():
    """从备份恢复数据库"""
    try:
        # 获取请求参数
        data = request.get_json() or {}
        backup_path = data.get("backup_path")
        restore_files = data.get("restore_files", True)
        
        if not backup_path:
            return jsonify({"error": "backup_path is required"}), 400
        
        # 恢复备份
        backup_manager = get_backup_manager()
        result = backup_manager.restore_database_backup(
            backup_path=backup_path,
            restore_files=restore_files
        )
        
        if result.get("success"):
            return jsonify({
                "message": "Database restored successfully",
                "restore": result
            })
        else:
            return jsonify({
                "error": "Failed to restore database",
                "details": result.get("error", "Unknown error")
            }), 500
            
    except Exception as e:
        audit_logger.log_error(
            "restore_backup", 
            str(e), 
            {"backup_path": data.get("backup_path"), "restore_files": data.get("restore_files", True)}
        )
        return jsonify({"error": "Failed to restore database", "details": str(e)}), 500


@backup_bp.route("/list", methods=["GET"])
@validate_request
@require_role("admin")
def list_backups():
    """列出所有可用的备份"""
    try:
        backup_manager = get_backup_manager()
        backups = backup_manager.list_backups()
        
        return jsonify({
            "backups": backups,
            "count": len(backups)
        })
        
    except Exception as e:
        audit_logger.log_error("list_backups", str(e), {})
        return jsonify({"error": "Failed to list backups", "details": str(e)}), 500


@backup_bp.route("/delete", methods=["POST"])
@validate_request
@require_role("admin")
def delete_backup():
    """删除备份"""
    try:
        # 获取请求参数
        data = request.get_json() or {}
        backup_path = data.get("backup_path")
        
        if not backup_path:
            return jsonify({"error": "backup_path is required"}), 400
        
        # 删除备份
        backup_manager = get_backup_manager()
        result = backup_manager.delete_backup(backup_path)
        
        if result.get("success"):
            return jsonify({
                "message": "Backup deleted successfully",
                "result": result
            })
        else:
            return jsonify({
                "error": "Failed to delete backup",
                "details": result.get("error", "Unknown error")
            }), 500
            
    except Exception as e:
        audit_logger.log_error(
            "delete_backup", 
            str(e), 
            {"backup_path": data.get("backup_path")}
        )
        return jsonify({"error": "Failed to delete backup", "details": str(e)}), 500


@backup_bp.route("/download/<backup_name>", methods=["GET"])
@validate_request
@require_role("admin")
def download_backup(backup_name):
    """下载备份文件"""
    try:
        # 安全检查备份名称
        backup_name = sanitize_input(backup_name)
        if not backup_name or ".." in backup_name or "/" in backup_name:
            return jsonify({"error": "Invalid backup name"}), 400
        
        # 构建备份文件路径
        backup_dir = os.environ.get("BACKUP_DIR", "backups")
        backup_path = os.path.join(backup_dir, backup_name)
        
        # 检查文件是否存在
        if not os.path.exists(backup_path):
            return jsonify({"error": "Backup not found"}), 404
        
        # 记录下载事件
        audit_logger.log_event(
            AuditEventType.SYSTEM_BACKUP,
            f"Downloaded backup: {backup_name}",
            {"backup_path": backup_path}
        )
        
        # 返回文件
        return send_file(
            backup_path,
            as_attachment=True,
            download_name=backup_name,
            mimetype='application/zip' if backup_name.endswith('.zip') else 'application/octet-stream'
        )
        
    except Exception as e:
        audit_logger.log_error(
            "download_backup", 
            str(e), 
            {"backup_name": backup_name}
        )
        return jsonify({"error": "Failed to download backup", "details": str(e)}), 500


@backup_bp.route("/info/<backup_name>", methods=["GET"])
@validate_request
@require_role("admin")
def get_backup_info(backup_name):
    """获取备份详细信息"""
    try:
        # 安全检查备份名称
        backup_name = sanitize_input(backup_name)
        if not backup_name or ".." in backup_name or "/" in backup_name:
            return jsonify({"error": "Invalid backup name"}), 400
        
        # 构建备份文件路径
        backup_dir = os.environ.get("BACKUP_DIR", "backups")
        backup_path = os.path.join(backup_dir, backup_name)
        
        # 检查文件是否存在
        if not os.path.exists(backup_path):
            return jsonify({"error": "Backup not found"}), 404
        
        # 获取备份信息
        backup_manager = get_backup_manager()
        backups = backup_manager.list_backups()
        
        # 查找匹配的备份
        backup_info = None
        for backup in backups:
            if backup.get("name") == backup_name:
                backup_info = backup
                break
        
        if not backup_info:
            return jsonify({"error": "Backup information not found"}), 404
        
        return jsonify({"backup": backup_info})
        
    except Exception as e:
        audit_logger.log_error(
            "get_backup_info", 
            str(e), 
            {"backup_name": backup_name}
        )
        return jsonify({"error": "Failed to get backup info", "details": str(e)}), 500


def create_backup_blueprint():
    """创建备份和恢复蓝图"""
    return backup_bp