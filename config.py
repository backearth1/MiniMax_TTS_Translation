"""
FastAPI 多人配音服务配置文件
"""
import os
from pathlib import Path

# 基础配置
class Config:
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 5215
    DEBUG = True
    
    # 目录配置
    BASE_DIR = Path(__file__).parent
    UPLOAD_DIR = BASE_DIR / "uploads"
    OUTPUT_DIR = BASE_DIR / "outputs" 
    SAMPLES_DIR = BASE_DIR / "samples"
    STATIC_DIR = BASE_DIR / "static"
    
    # 音频处理配置
    AUDIO_CONFIG = {
        "sample_rate": 32000,
        "batch_size": 20,
        "max_file_size": 10 * 1024 * 1024,  # 10MB
        "supported_formats": [".srt", ".txt"],
        "ffmpeg_path": "ffmpeg"  # 系统路径中的 ffmpeg
    }
    
    # 网络代理配置 - 智能代理管理
    PROXY_CONFIG = {
        # 代理模式: "auto"(自动检测), "manual"(手动配置), "disabled"(禁用代理)
        "mode": os.getenv("PROXY_MODE", "auto"),
        
        # 自动检测配置
        "auto_detect": True,
        "fallback_to_direct": True,
        
        # 手动配置代理
        "manual": {
            "http_proxy": os.getenv("http_proxy", "http://pac-internal.xaminim.com:3129"),
            "https_proxy": os.getenv("https_proxy", "http://pac-internal.xaminim.com:3129"),
            "ftp_proxy": os.getenv("ftp_proxy", "http://pac-internal.xaminim.com:3129"),
            "no_proxy": os.getenv("no_proxy", "localhost,127.0.0.1,*.xaminim.com,10.0.0.0/8")
        },
        
        # 检测配置
        "test_urls": [
            "https://api.minimaxi.com/health",
            "https://api.minimax.io/health", 
            "https://www.baidu.com",
            "https://httpbin.org/ip"
        ],
        "connection_timeout": 5,        # 连接超时（秒）
        "detection_cache_ttl": 300      # 检测缓存时间（秒）
    }
    
    # API 端点配置
    API_ENDPOINTS = {
        "tts": {
            "domestic": "https://api.minimaxi.com/v1/t2a_v2",
            "overseas": "https://api.minimax.io/v1/t2a_v2",
            "default": "domestic"  # 默认使用国内端点
        },
        "translation": {
            "domestic": "https://api.minimaxi.com/v1/text/chatcompletion_v2",
            "overseas": "https://api.minimax.io/v1/text/chatcompletion_v2", 
            "default": "domestic"  # 默认使用国内端点
        }
    }
    
    # TTS 配置
    TTS_CONFIG = {
        "default_model": "speech-02-hd",
        "default_language": "Chinese",
        "max_text_length": 1000,
        "timeout": 30,
        "supported_languages": [
            "Chinese",
            "Chinese,Yue", 
            "English",
            "Arabic",
            "Russian",
            "Spanish", 
            "French",
            "Portuguese",
            "German",
            "Turkish",
            "Dutch",
            "Ukrainian",
            "Vietnamese",
            "Indonesian",
            "Japanese",
            "Italian",
            "Korean",
            "Thai",
            "Polish",
            "Romanian",
            "Greek",
            "Czech",
            "Finnish",
            "Hindi",
            "Bulgarian",
            "Danish",
            "Hebrew",
            "Malay",
            "Persian",
            "Slovak",
            "Swedish",
            "Croatian",
            "Filipino",
            "Hungarian",
            "Norwegian",
            "Slovenian",
            "Catalan",
            "Nynorsk",
            "Tamil",
            "Afrikaans"
        ]
    }
    
    # 翻译配置
    TRANSLATION_CONFIG = {
        "model": "MiniMax-Text-01",
        "temperature": 0.01,
        "top_p": 0.95,
        "timeout": 30,
        "max_retries": 3,
        "translation_delay": 2,  # 翻译间隔（秒）
        "supported_target_languages": [
            "Chinese",
            "Chinese,Yue", 
            "English",
            "Arabic",
            "Russian",
            "Spanish", 
            "French",
            "Portuguese",
            "German",
            "Turkish",
            "Dutch",
            "Ukrainian",
            "Vietnamese",
            "Indonesian",
            "Japanese",
            "Italian",
            "Korean",
            "Thai",
            "Polish",
            "Romanian",
            "Greek",
            "Czech",
            "Finnish",
            "Hindi",
            "Bulgarian",
            "Danish",
            "Hebrew",
            "Malay",
            "Persian",
            "Slovak",
            "Swedish",
            "Croatian",
            "Filipino",
            "Hungarian",
            "Norwegian",
            "Slovenian",
            "Catalan",
            "Nynorsk",
            "Tamil",
            "Afrikaans"
        ]
    }
    
    # 语音映射配置
    VOICE_MAPPING = {
        "SPEAKER_00": "ai_her_04",
        "SPEAKER_01": "wumei_yujie", 
        "SPEAKER_02": "uk_oldwoman4",
        "SPEAKER_03": "female-chengshu",
        "SPEAKER_04": "Serene_Elder",
        "SPEAKER_05": "Serene_Elder"
    }
    
    # WebSocket 配置
    WEBSOCKET_CONFIG = {
        "ping_interval": 10,
        "ping_timeout": 5,
        "close_timeout": 10
    }
    
    # 样例文件配置
    SAMPLE_FILES = [
        {
            "name": "double_life_Chinese.srt",
            "description": "中文对话样例", 
            "path": "samples/double_life_Chinese.srt"
        },
        {
            "name": "double_life_English.srt",
            "description": "英文对话样例",
            "path": "samples/double_life_English.srt"
        }
    ]

# 获取代理设置 - 兼容旧版本
def get_proxy_settings():
    """
    获取代理设置用于HTTP请求（兼容函数）
    推荐使用 proxy_manager 模块的异步函数
    """
    proxy_mode = Config.PROXY_CONFIG.get("mode", "auto")
    
    if proxy_mode == "disabled":
        return None
    elif proxy_mode == "manual":
        manual_config = Config.PROXY_CONFIG.get("manual", {})
        if manual_config.get("http_proxy"):
            return {
                "http": manual_config.get("http_proxy"),
                "https": manual_config.get("https_proxy"),
                "ftp": manual_config.get("ftp_proxy")
            }
        return None
    else:
        # auto模式需要异步检测，这里返回手动配置作为fallback
        manual_config = Config.PROXY_CONFIG.get("manual", {})
        if manual_config.get("http_proxy"):
            return {
                "http": manual_config.get("http_proxy"),
                "https": manual_config.get("https_proxy"), 
                "ftp": manual_config.get("ftp_proxy")
            }
        return None

# 创建必要目录
def create_directories():
    """创建必要的目录结构"""
    directories = [
        Config.UPLOAD_DIR,
        Config.OUTPUT_DIR,
        Config.SAMPLES_DIR,
        Config.STATIC_DIR,
        Config.STATIC_DIR / "css",
        Config.STATIC_DIR / "js"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"📁 创建目录: {directory}")

if __name__ == "__main__":
    create_directories() 