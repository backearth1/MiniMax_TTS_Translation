#!/usr/bin/env python3
"""
系统配置模块 - Admin后台系统配置管理功能
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import asyncio

# 创建路由器
system_router = APIRouter(prefix="/admin/system", tags=["系统配置"])

class RateLimitConfig(BaseModel):
    """限流配置模型"""
    max_online_users: int = Field(default=10, ge=1, le=100, description="最大在线用户数")
    max_projects_per_user: int = Field(default=5, ge=1, le=50, description="每用户最大项目数")
    max_segments_per_file: int = Field(default=500, ge=1, le=2000, description="每文件最大段落数")
    max_duration_seconds: int = Field(default=1200, ge=60, le=7200, description="最大时长(秒)")
    file_size_limit_mb: int = Field(default=10, ge=1, le=100, description="文件大小限制(MB)")
    user_request_rate_per_minute: int = Field(default=10, ge=1, le=100, description="用户每分钟请求限制")

class BatchAPIConfig(BaseModel):
    """批量API配置模型"""
    # 批量翻译配置
    translation_delay_seconds: float = Field(default=2.0, ge=0.1, le=10.0, description="翻译请求间隔(秒)")
    translation_timeout_seconds: int = Field(default=30, ge=10, le=120, description="翻译请求超时(秒)")
    translation_max_retries: int = Field(default=3, ge=1, le=10, description="翻译最大重试次数")
    
    # 批量TTS配置
    tts_request_interval_seconds: float = Field(default=1.0, ge=0.1, le=5.0, description="TTS请求间隔(秒)")
    tts_timeout_seconds: int = Field(default=30, ge=10, le=120, description="TTS请求超时(秒)")
    tts_max_retries: int = Field(default=3, ge=1, le=10, description="TTS最大重试次数")
    tts_retry_delay_base: float = Field(default=2.0, ge=1.0, le=5.0, description="TTS重试延迟基数(秒)")
    tts_download_retry_delay: float = Field(default=2.0, ge=0.5, le=10.0, description="TTS下载重试延迟(秒)")
    tts_batch_size: int = Field(default=20, ge=1, le=100, description="TTS批处理大小")

class SystemConfig(BaseModel):
    """系统配置模型"""
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    batch_api: BatchAPIConfig = Field(default_factory=BatchAPIConfig)
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_by: str = Field(default="admin")

class SystemConfigManager:
    """系统配置管理器"""
    
    def __init__(self):
        self.config_dir = Path("config_data")
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "system_config.json"
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                self._config = SystemConfig(**config_data)
            else:
                # 使用默认配置
                self._config = SystemConfig()
                self._save_config()
        except Exception as e:
            print(f"加载系统配置失败，使用默认配置: {e}")
            self._config = SystemConfig()
    
    def _save_config(self):
        """保存配置"""
        try:
            config_data = self._config.dict()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存系统配置失败: {e}")
            return False
    
    def get_config(self) -> SystemConfig:
        """获取当前配置"""
        if self._config is None:
            self._load_config()
        return self._config
    
    def update_rate_limit_config(self, new_config: RateLimitConfig, updated_by: str = "admin") -> bool:
        """更新限流配置"""
        try:
            self._config.rate_limit = new_config
            self._config.updated_at = datetime.now().isoformat()
            self._config.updated_by = updated_by
            return self._save_config()
        except Exception as e:
            print(f"更新限流配置失败: {e}")
            return False
    
    def update_batch_api_config(self, new_config: BatchAPIConfig, updated_by: str = "admin") -> bool:
        """更新批量API配置"""
        try:
            self._config.batch_api = new_config
            self._config.updated_at = datetime.now().isoformat()
            self._config.updated_by = updated_by
            return self._save_config()
        except Exception as e:
            print(f"更新批量API配置失败: {e}")
            return False
    
    def get_rate_limit_config(self) -> RateLimitConfig:
        """获取限流配置"""
        return self.get_config().rate_limit
    
    def get_batch_api_config(self) -> BatchAPIConfig:
        """获取批量API配置"""
        return self.get_config().batch_api
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        try:
            self._config = SystemConfig()
            return self._save_config()
        except Exception as e:
            print(f"重置配置失败: {e}")
            return False
    
    def get_config_history(self) -> Dict:
        """获取配置历史信息"""
        config = self.get_config()
        return {
            "last_updated": config.updated_at,
            "updated_by": config.updated_by,
            "file_size": self.config_file.stat().st_size if self.config_file.exists() else 0,
            "file_path": str(self.config_file)
        }
    
    def validate_limits(self, **kwargs) -> Dict[str, bool]:
        """验证当前请求是否符合限流配置"""
        config = self.get_rate_limit_config()
        
        validation_results = {}
        
        # 验证在线用户数
        if 'current_online_users' in kwargs:
            validation_results['online_users_ok'] = kwargs['current_online_users'] < config.max_online_users
        
        # 验证用户项目数
        if 'user_projects_count' in kwargs:
            validation_results['user_projects_ok'] = kwargs['user_projects_count'] < config.max_projects_per_user
        
        # 验证文件段落数
        if 'file_segments_count' in kwargs:
            validation_results['file_segments_ok'] = kwargs['file_segments_count'] <= config.max_segments_per_file
        
        # 验证文件时长
        if 'file_duration_seconds' in kwargs:
            validation_results['file_duration_ok'] = kwargs['file_duration_seconds'] <= config.max_duration_seconds
        
        # 验证文件大小
        if 'file_size_mb' in kwargs:
            validation_results['file_size_ok'] = kwargs['file_size_mb'] <= config.file_size_limit_mb
        
        return validation_results

# 全局系统配置管理器实例
system_manager = SystemConfigManager()

@system_router.get("/", response_class=HTMLResponse)
async def system_config_page():
    """系统配置页面"""
    with open("admin_modules/templates/system.html", "r", encoding="utf-8") as f:
        return f.read()

@system_router.get("/api/config")
async def get_system_config():
    """获取系统配置API"""
    try:
        config = system_manager.get_config()
        history = system_manager.get_config_history()
        
        return {
            "success": True, 
            "data": {
                "config": config.dict(),
                "history": history
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统配置失败: {str(e)}")

@system_router.post("/api/rate-limit")
async def update_rate_limit_config(config: RateLimitConfig):
    """更新限流配置API"""
    try:
        success = system_manager.update_rate_limit_config(config, "admin_user")
        
        if success:
            # 记录管理员活动
            from admin import record_user_activity
            record_user_activity("admin_user", "update_rate_limit_config")
            
            return {"success": True, "message": "限流配置更新成功"}
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新限流配置失败: {str(e)}")

@system_router.post("/api/batch-api")
async def update_batch_api_config(config: BatchAPIConfig):
    """更新批量API配置API"""
    try:
        success = system_manager.update_batch_api_config(config, "admin_user")
        
        if success:
            # 记录管理员活动
            from admin import record_user_activity
            record_user_activity("admin_user", "update_batch_api_config")
            
            return {"success": True, "message": "批量API配置更新成功"}
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新批量API配置失败: {str(e)}")

@system_router.post("/api/reset")
async def reset_system_config():
    """重置系统配置API"""
    try:
        success = system_manager.reset_to_default()
        
        if success:
            # 记录管理员活动
            from admin import record_user_activity
            record_user_activity("admin_user", "reset_system_config")
            
            return {"success": True, "message": "系统配置已重置为默认值"}
        else:
            raise HTTPException(status_code=500, detail="重置配置失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置系统配置失败: {str(e)}")

@system_router.post("/api/validate")
async def validate_request_limits(**kwargs):
    """验证请求限制API"""
    try:
        validation_results = system_manager.validate_limits(**kwargs)
        return {"success": True, "data": validation_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证限制失败: {str(e)}")

@system_router.get("/api/current-limits")
async def get_current_limits():
    """获取当前限制值API"""
    try:
        config = system_manager.get_rate_limit_config()
        
        # 获取当前系统状态
        from admin import get_active_users_count
        from subtitle_manager import subtitle_manager
        
        current_online_users = get_active_users_count()
        total_projects = len(subtitle_manager.projects)
        
        return {
            "success": True,
            "data": {
                "limits": config.dict(),
                "current_status": {
                    "online_users": current_online_users,
                    "total_projects": total_projects,
                    "online_users_usage": f"{current_online_users}/{config.max_online_users}",
                    "is_at_user_limit": current_online_users >= config.max_online_users
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取当前限制失败: {str(e)}")