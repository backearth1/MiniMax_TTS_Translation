# -*- coding: utf-8 -*-
"""
健康检查服务
第一个要迁移的安全模块

⚠️ 保持完全向后兼容，不改变任何响应格式
"""
import time
from datetime import datetime
from fastapi import APIRouter

# 记录应用启动时间
START_TIME = time.time()

router = APIRouter()

@router.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "多人配音 Web 服务",
        "version": "2.0.0"
    }