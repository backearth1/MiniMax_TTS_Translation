# -*- coding: utf-8 -*-
"""
基础路由
包含主页和配置等基础功能
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from config import Config

router = APIRouter()

# 需要导入动态限制配置函数
def get_dynamic_limits():
    """获取动态配置限制"""
    try:
        from admin_modules.system_manager import system_manager
        config = system_manager.get_rate_limit_config()
        batch_config = system_manager.get_batch_api_config()
        return {
            "maxFileSize": config.file_size_limit_mb * 1024 * 1024,  # 转换为字节
            "maxSegments": config.max_segments_per_file,
            "maxDuration": config.max_duration_seconds,
            "maxProjects": config.max_projects_per_user,
            "maxOnlineUsers": config.max_online_users,
            "requestRateLimit": {
                "translationDelay": batch_config.translation_delay_seconds,
                "translationTimeout": batch_config.translation_timeout_seconds,
                "translationMaxRetries": batch_config.translation_max_retries,
                "ttsRequestInterval": batch_config.tts_request_interval_seconds,
                "ttsTimeout": batch_config.tts_timeout_seconds,
                "ttsMaxRetries": batch_config.tts_max_retries,
                "ttsRetryDelayBase": batch_config.tts_retry_delay_base_seconds,
                "ttsDownloadRetryDelay": batch_config.tts_download_retry_delay_seconds,
                "ttsBatchSize": batch_config.tts_batch_size
            }
        }
    except Exception as e:
        # 如果系统管理器不可用，返回默认配置
        return {
            "maxFileSize": 10 * 1024 * 1024,  # 10MB
            "maxSegments": 1000,
            "maxDuration": 3600,  # 1小时
            "maxProjects": 50,
            "maxOnlineUsers": 10,
            "requestRateLimit": {
                "translationDelay": 1,
                "translationTimeout": 30,
                "translationMaxRetries": 3,
                "ttsRequestInterval": 0.5,
                "ttsTimeout": 30,
                "ttsMaxRetries": 3,
                "ttsRetryDelayBase": 2,
                "ttsDownloadRetryDelay": 1,
                "ttsBatchSize": 5
            }
        }

@router.get("/")
async def read_root():
    """主页重定向到静态文件"""
    return FileResponse(Config.STATIC_DIR / "index.html")

@router.get("/api/config")
async def get_config():
    """获取前端配置信息"""
    return {
        "voices": Config.VOICE_MAPPING,
        "models": ["speech-02-hd", "speech-01"],
        "languages": Config.TTS_CONFIG["supported_languages"],
        "limits": get_dynamic_limits(),
        "supportedFormats": Config.AUDIO_CONFIG["supported_formats"]
    }