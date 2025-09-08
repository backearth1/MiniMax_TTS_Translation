"""
Admin模块 - 管理员后台功能
"""

from .project_manager import project_router
from .user_manager import user_router
from .system_manager import system_router

__all__ = ["project_router", "user_router", "system_router"]