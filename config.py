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
    
    # 网络配置 - 使用系统默认网络设置
    # 系统代理通过环境变量自动识别: http_proxy, https_proxy, no_proxy
    
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

# 简化网络配置 - 使用系统环境变量
# aiohttp和requests会自动读取以下环境变量:
# - http_proxy: HTTP代理
# - https_proxy: HTTPS代理  
# - no_proxy: 不使用代理的地址列表
# 
# 使用示例:
# export https_proxy=http://proxy:3129
# export http_proxy=http://proxy:3129

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