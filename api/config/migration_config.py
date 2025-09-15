# -*- coding: utf-8 -*-
"""
迁移配置 - 控制重构过程中的功能开关
确保安全的渐进式迁移
"""

class MigrationFlags:
    """迁移功能开关"""

    # Phase 2.1 - 基础架构
    ENABLE_NEW_API_STRUCTURE = True

    # Phase 2.2 - 路由迁移开关
    USE_NEW_HEALTH_ENDPOINT = True   # 测试通过，已启用
    USE_NEW_FILE_ROUTES = False      # 文件管理路由
    USE_NEW_PROJECT_ROUTES = False   # 项目管理路由
    USE_NEW_SUBTITLE_ROUTES = False  # 字幕操作路由
    USE_NEW_AUDIO_ROUTES = False     # 音频处理路由

    # Phase 2.3 - 服务层开关
    USE_NEW_TTS_SERVICE = False
    USE_NEW_AUDIO_SERVICE = False
    USE_NEW_SUBTITLE_SERVICE = False

    # Phase 2.4 - 数据层开关
    USE_NEW_FILE_REPOSITORY = False
    USE_NEW_CACHE_MANAGER = False

    # 安全机制
    ENABLE_MIGRATION_LOGGING = True  # 记录迁移过程
    ENABLE_ROLLBACK_MODE = True      # 支持快速回滚

    @classmethod
    def is_feature_enabled(cls, feature_name: str) -> bool:
        """检查功能是否启用"""
        return getattr(cls, feature_name, False)

    @classmethod
    def enable_feature(cls, feature_name: str):
        """启用指定功能"""
        if hasattr(cls, feature_name):
            setattr(cls, feature_name, True)
            if cls.ENABLE_MIGRATION_LOGGING:
                print(f"🟢 启用功能: {feature_name}")

    @classmethod
    def disable_feature(cls, feature_name: str):
        """禁用指定功能（回滚用）"""
        if hasattr(cls, feature_name):
            setattr(cls, feature_name, False)
            if cls.ENABLE_MIGRATION_LOGGING:
                print(f"🔴 禁用功能: {feature_name}")


# 迁移步骤定义
MIGRATION_STEPS = [
    {
        "phase": "2.1",
        "name": "基础架构",
        "status": "completed",
        "features": ["ENABLE_NEW_API_STRUCTURE"]
    },
    {
        "phase": "2.2.1",
        "name": "健康检查路由迁移",
        "status": "ready",
        "features": ["USE_NEW_HEALTH_ENDPOINT"],
        "risk_level": "low"
    },
    {
        "phase": "2.2.2",
        "name": "文件管理路由迁移",
        "status": "pending",
        "features": ["USE_NEW_FILE_ROUTES"],
        "risk_level": "medium"
    },
    {
        "phase": "2.2.3",
        "name": "项目管理路由迁移",
        "status": "pending",
        "features": ["USE_NEW_PROJECT_ROUTES"],
        "risk_level": "medium"
    },
    {
        "phase": "2.2.4",
        "name": "字幕操作路由迁移",
        "status": "pending",
        "features": ["USE_NEW_SUBTITLE_ROUTES"],
        "risk_level": "high"  # 涉及时间戳对齐
    },
    {
        "phase": "2.2.5",
        "name": "音频处理路由迁移",
        "status": "pending",
        "features": ["USE_NEW_AUDIO_ROUTES"],
        "risk_level": "high"  # 涉及trace_id显示
    }
]