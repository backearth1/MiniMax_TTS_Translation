# -*- coding: utf-8 -*-
"""
新的API层 - Phase 2重构
渐进式迁移现有main.py功能

⚠️ 重要约束：
- 时间戳对齐是项目核心，不能轻易改动
- 前端日志显示要保留原始格式，不过度包装  
- API请求的trace_id必须完整显示
"""
from fastapi import APIRouter

# 导入各个模块的路由
from api.core.health import router as health_router

# 创建主路由器
api_router = APIRouter()

# 注册路由 - 渐进式添加
api_router.include_router(health_router, tags=["health"])

# 这里将逐步添加更多路由：
# api_router.include_router(file_router, tags=["files"])  # Phase 2.2
# api_router.include_router(project_router, tags=["projects"])  # Phase 2.2  
# api_router.include_router(subtitle_router, tags=["subtitles"])  # Phase 2.2
# api_router.include_router(audio_router, tags=["audio"])  # Phase 2.2