"""
用户偏好设置模块
"""
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from .storage import storage
from .validation import DataValidator, ValidationError

class UserPreferences:
    """用户偏好设置管理类"""
    
    # 默认偏好设置
    DEFAULT_PREFERENCES = {
        "theme": "light",  # light, dark
        "language": "zh-CN",  # zh-CN, en-US
        "notifications": {
            "email": True,
            "system": True,
            "course": True,
            "assignment": True
        },
        "dashboard": {
            "layout": "grid",  # grid, list
            "widgets": ["courses", "assignments", "announcements"]
        },
        "privacy": {
            "show_profile": True,
            "show_contact": False
        },
        "accessibility": {
            "font_size": "medium",  # small, medium, large
            "high_contrast": False
        }
    }
    
    @classmethod
    def get_user_preferences(cls, username: str) -> Dict:
        """
        获取用户偏好设置
        
        Args:
            username: 用户名
            
        Returns:
            用户偏好设置字典
        """
        # 验证用户名
        DataValidator.validate_username(username)
        
        # 获取用户偏好设置
        preferences = storage.get("user_preferences", username)
        
        # 如果没有偏好设置，返回默认设置
        if not preferences:
            return cls.DEFAULT_PREFERENCES.copy()
        
        # 合并默认设置和用户设置，确保所有必需字段都存在
        merged_preferences = cls.DEFAULT_PREFERENCES.copy()
        cls._deep_update(merged_preferences, preferences)
        
        return merged_preferences
    
    @classmethod
    def update_user_preferences(cls, username: str, preferences: Dict) -> Dict:
        """
        更新用户偏好设置
        
        Args:
            username: 用户名
            preferences: 偏好设置字典
            
        Returns:
            更新后的偏好设置
        """
        # 验证用户名
        DataValidator.validate_username(username)
        
        # 验证偏好设置
        cls._validate_preferences(preferences)
        
        # 获取当前偏好设置
        current_preferences = cls.get_user_preferences(username)
        
        # 更新偏好设置
        cls._deep_update(current_preferences, preferences)
        
        # 保存到存储
        storage.set("user_preferences", username, current_preferences)
        
        return current_preferences
    
    @classmethod
    def reset_user_preferences(cls, username: str) -> Dict:
        """
        重置用户偏好设置为默认值
        
        Args:
            username: 用户名
            
        Returns:
            重置后的偏好设置
        """
        # 验证用户名
        DataValidator.validate_username(username)
        
        # 保存默认设置
        storage.set("user_preferences", username, cls.DEFAULT_PREFERENCES.copy())
        
        return cls.DEFAULT_PREFERENCES.copy()
    
    @classmethod
    def get_preference(cls, username: str, key_path: str, default: Any = None) -> Any:
        """
        获取特定偏好设置
        
        Args:
            username: 用户名
            key_path: 键路径，如 "notifications.email"
            default: 默认值
            
        Returns:
            偏好设置值
        """
        # 验证用户名
        DataValidator.validate_username(username)
        
        # 获取用户偏好设置
        preferences = cls.get_user_preferences(username)
        
        # 解析键路径
        keys = key_path.split('.')
        value = preferences
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    @classmethod
    def set_preference(cls, username: str, key_path: str, value: Any) -> Dict:
        """
        设置特定偏好设置
        
        Args:
            username: 用户名
            key_path: 键路径，如 "notifications.email"
            value: 偏好设置值
            
        Returns:
            更新后的偏好设置
        """
        # 验证用户名
        DataValidator.validate_username(username)
        
        # 获取用户偏好设置
        preferences = cls.get_user_preferences(username)
        
        # 解析键路径并设置值
        keys = key_path.split('.')
        target = preferences
        
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # 验证偏好设置
        temp_preferences = {keys[-1]: value}
        cls._validate_preferences(temp_preferences, key_path)
        
        # 设置值
        target[keys[-1]] = value
        
        # 保存到存储
        storage.set("user_preferences", username, preferences)
        
        return preferences
    
    @classmethod
    def _deep_update(cls, base_dict: Dict, update_dict: Dict):
        """
        深度更新字典
        
        Args:
            base_dict: 基础字典
            update_dict: 更新字典
        """
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                cls._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    @classmethod
    def _validate_preferences(cls, preferences: Dict, key_path: str = ""):
        """
        验证偏好设置
        
        Args:
            preferences: 偏好设置字典
            key_path: 当前键路径，用于错误报告
        """
        # 验证主题
        if "theme" in preferences:
            theme = preferences["theme"]
            if theme not in ["light", "dark"]:
                raise ValidationError(f"无效的主题值: {theme}", f"{key_path}.theme" if key_path else "theme")
        
        # 验证语言
        if "language" in preferences:
            language = preferences["language"]
            if language not in ["zh-CN", "en-US"]:
                raise ValidationError(f"无效的语言值: {language}", f"{key_path}.language" if key_path else "language")
        
        # 验证通知设置
        if "notifications" in preferences:
            notifications = preferences["notifications"]
            if not isinstance(notifications, dict):
                raise ValidationError(f"通知设置必须是字典", f"{key_path}.notifications" if key_path else "notifications")
            
            for key, value in notifications.items():
                if key in ["email", "system", "course", "assignment"] and not isinstance(value, bool):
                    raise ValidationError(f"通知设置 {key} 必须是布尔值", f"{key_path}.notifications.{key}" if key_path else f"notifications.{key}")
        
        # 验证仪表板设置
        if "dashboard" in preferences:
            dashboard = preferences["dashboard"]
            if not isinstance(dashboard, dict):
                raise ValidationError(f"仪表板设置必须是字典", f"{key_path}.dashboard" if key_path else "dashboard")
            
            if "layout" in dashboard and dashboard["layout"] not in ["grid", "list"]:
                raise ValidationError(f"无效的仪表板布局: {dashboard['layout']}", f"{key_path}.dashboard.layout" if key_path else "dashboard.layout")
            
            if "widgets" in dashboard:
                widgets = dashboard["widgets"]
                if not isinstance(widgets, list):
                    raise ValidationError(f"仪表板小部件必须是列表", f"{key_path}.dashboard.widgets" if key_path else "dashboard.widgets")
                
                valid_widgets = ["courses", "assignments", "announcements", "schedule", "grades"]
                for widget in widgets:
                    if widget not in valid_widgets:
                        raise ValidationError(f"无效的仪表板小部件: {widget}", f"{key_path}.dashboard.widgets" if key_path else "dashboard.widgets")
        
        # 验证隐私设置
        if "privacy" in preferences:
            privacy = preferences["privacy"]
            if not isinstance(privacy, dict):
                raise ValidationError(f"隐私设置必须是字典", f"{key_path}.privacy" if key_path else "privacy")
            
            for key, value in privacy.items():
                if key in ["show_profile", "show_contact"] and not isinstance(value, bool):
                    raise ValidationError(f"隐私设置 {key} 必须是布尔值", f"{key_path}.privacy.{key}" if key_path else f"privacy.{key}")
        
        # 验证辅助功能设置
        if "accessibility" in preferences:
            accessibility = preferences["accessibility"]
            if not isinstance(accessibility, dict):
                raise ValidationError(f"辅助功能设置必须是字典", f"{key_path}.accessibility" if key_path else "accessibility")
            
            if "font_size" in accessibility and accessibility["font_size"] not in ["small", "medium", "large"]:
                raise ValidationError(f"无效的字体大小: {accessibility['font_size']}", f"{key_path}.accessibility.font_size" if key_path else "accessibility.font_size")
            
            if "high_contrast" in accessibility and not isinstance(accessibility["high_contrast"], bool):
                raise ValidationError(f"高对比度设置必须是布尔值", f"{key_path}.accessibility.high_contrast" if key_path else "accessibility.high_contrast")

class UserProfile:
    """用户个人资料管理类"""
    
    @classmethod
    def get_user_profile(cls, username: str) -> Dict:
        """
        获取用户个人资料
        
        Args:
            username: 用户名
            
        Returns:
            用户个人资料字典
        """
        # 验证用户名
        DataValidator.validate_username(username)
        
        # 获取用户个人资料
        profile = storage.get("user_profiles", username)
        
        if not profile:
            return {}
        
        return profile
    
    @classmethod
    def update_user_profile(cls, username: str, profile: Dict) -> Dict:
        """
        更新用户个人资料
        
        Args:
            username: 用户名
            profile: 个人资料字典
            
        Returns:
            更新后的个人资料
        """
        # 验证用户名
        DataValidator.validate_username(username)
        
        # 验证个人资料
        cls._validate_profile(profile)
        
        # 获取当前个人资料
        current_profile = cls.get_user_profile(username)
        
        # 更新个人资料
        current_profile.update(profile)
        current_profile["updated_at"] = datetime.now().isoformat()
        
        # 保存到存储
        storage.set("user_profiles", username, current_profile)
        
        return current_profile
    
    @classmethod
    def _validate_profile(cls, profile: Dict):
        """
        验证个人资料
        
        Args:
            profile: 个人资料字典
        """
        # 验证邮箱
        if "email" in profile:
            DataValidator.validate_email(profile["email"])
        
        # 验证电话号码
        if "phone" in profile and profile["phone"]:
            phone = profile["phone"]
            if not re.match(r'^\+?[\d\s\-()]+$', phone):
                raise ValidationError("电话号码格式不正确", "phone")
        
        # 验证个人简介
        if "bio" in profile:
            DataValidator.validate_text_field(profile["bio"], "个人简介", max_length=500)
        
        # 验证其他字段
        text_fields = ["first_name", "last_name", "title", "department", "office"]
        for field in text_fields:
            if field in profile:
                DataValidator.validate_text_field(profile[field], field, max_length=100)