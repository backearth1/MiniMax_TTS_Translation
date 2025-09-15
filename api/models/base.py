"""
基础数据模型
"""
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class BaseResponse(BaseModel):
    """统一响应格式"""
    success: bool
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success_response(cls, data: Dict[str, Any] = None, message: str = "操作成功"):
        return cls(success=True, message=message, data=data)
    
    @classmethod
    def error_response(cls, message: str, data: Dict[str, Any] = None):
        return cls(success=False, message=message, data=data)


class HealthStatus(BaseModel):
    """健康检查状态"""
    status: str
    timestamp: datetime
    version: str
    uptime: float


class FileInfo(BaseModel):
    """文件信息"""
    filename: str
    size: int
    mime_type: str
    created_at: datetime
    
    
class APIConfig(BaseModel):
    """API配置信息"""
    version: str
    max_file_size: int
    supported_formats: list
    rate_limits: Dict[str, int]