#!/usr/bin/env python3
"""
FastAPI 多人配音 Web 服务
"""
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
import secrets

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, Query, Request, Cookie, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from config import Config, create_directories
from audio_processor import AudioProcessor
from utils.logger import websocket_logger, get_process_logger
from subtitle_manager import subtitle_manager
from admin import admin_router, record_user_activity, start_cleanup_task
from admin_modules.project_manager import project_router
from admin_modules.user_manager import user_router
from admin_modules.system_manager import system_router
from project_manager import router as project_manager_router


from contextlib import asynccontextmanager

# 全局变量用于跟踪正在运行的任务
running_tasks = {}
task_cancellation_flags = {}

# 会话管理
active_sessions = {}  # session_id -> session_info

def get_dynamic_limits() -> Dict:
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
            "requestRateLimit": config.user_request_rate_per_minute,
            "batchApi": {
                "translationDelay": batch_config.translation_delay_seconds,
                "translationTimeout": batch_config.translation_timeout_seconds,
                "translationMaxRetries": batch_config.translation_max_retries,
                "ttsRequestInterval": batch_config.tts_request_interval_seconds,
                "ttsTimeout": batch_config.tts_timeout_seconds,
                "ttsMaxRetries": batch_config.tts_max_retries,
                "ttsRetryDelayBase": batch_config.tts_retry_delay_base,
                "ttsDownloadRetryDelay": batch_config.tts_download_retry_delay,
                "ttsBatchSize": batch_config.tts_batch_size
            }
        }
    except Exception as e:
        print(f"获取动态限制失败，使用默认值: {e}")
        return {
            "maxFileSize": 10 * 1024 * 1024,  # 10MB
            "maxSegments": 500,
            "maxDuration": 1200,
            "maxProjects": 5,
            "maxOnlineUsers": 10,
            "requestRateLimit": 10,
            "batchApi": {
                "translationDelay": 2.0,
                "translationTimeout": 30,
                "translationMaxRetries": 3,
                "ttsRequestInterval": 1.0,
                "ttsTimeout": 30,
                "ttsMaxRetries": 3,
                "ttsRetryDelayBase": 2.0,
                "ttsDownloadRetryDelay": 2.0,
                "ttsBatchSize": 20
            }
        }

def get_or_create_session_id(request: Request, response: Response) -> str:
    """获取或创建会话ID"""
    session_id = request.cookies.get("session_id")
    
    if not session_id or session_id not in active_sessions:
        # 生成新的会话ID
        session_id = secrets.token_urlsafe(32)
        active_sessions[session_id] = {
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "ip_address": request.client.host if request.client else "unknown"
        }
        
        # 设置cookie（1年有效期）
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=365 * 24 * 60 * 60,  # 1年
            httponly=True,
            secure=False,  # 开发环境设为False，生产环境应设为True
            samesite="lax"
        )
        
        print(f"🆔 创建新会话: {session_id[:8]}...")
    else:
        # 更新最后活跃时间
        active_sessions[session_id]["last_active"] = datetime.now().isoformat()
    
    return session_id

# 确保必要目录存在
def ensure_directories():
    """确保所有必要的目录存在"""
    import os
    
    # 只在目录不存在时才创建，避免重复日志
    directories = [
        Config.UPLOAD_DIR,
        Config.OUTPUT_DIR, 
        Config.SAMPLES_DIR,
        Config.STATIC_DIR,
        Config.STATIC_DIR / "css",
        Config.STATIC_DIR / "js",
        Path("audio_files"),
        Path("temp_audio")
    ]
    
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            print(f"📁 创建目录: {directory}")

# 在应用启动前创建目录
ensure_directories()

def get_api_endpoint(api_type: str, endpoint_type: str = "domestic") -> str:
    """
    获取API端点URL
    
    Args:
        api_type: API类型 ("tts" 或 "translation")
        endpoint_type: 端点类型 ("domestic" 或 "overseas")
    
    Returns:
        API端点URL
    """
    return Config.API_ENDPOINTS[api_type][endpoint_type]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时执行
    print("🚀 启动 FastAPI 多人配音服务...")
    
    # 创建必要目录
    create_directories()
    
    # 加载已保存的项目
    try:
        loaded_count = await subtitle_manager.load_all_projects_from_disk()
        print(f"📂 已加载 {loaded_count} 个保存的项目")
    except Exception as e:
        print(f"⚠️ 加载项目失败: {e}")
    
    # 启动管理员清理任务
    start_cleanup_task()
    
    print(f"🌐 服务地址: http://{Config.HOST}:{Config.PORT}")
    print(f"📁 上传目录: {Config.UPLOAD_DIR}")
    print(f"🎵 输出目录: {Config.OUTPUT_DIR}")
    print(f"📄 API 文档: http://{Config.HOST}:{Config.PORT}/docs")
    print(f"👨‍💼 管理员面板: http://{Config.HOST}:{Config.PORT}/admin/dashboard")
    
    yield
    
    # 应用关闭时执行 (可选)
    print("👋 FastAPI 服务正在关闭...")

# 创建 FastAPI 应用
app = FastAPI(
    title="多人配音 Web 服务",
    description="基于 FastAPI 的智能多人配音生成服务",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=Config.STATIC_DIR), name="static")
app.mount("/outputs", StaticFiles(directory=Config.OUTPUT_DIR), name="outputs")
app.mount("/samples", StaticFiles(directory=Config.SAMPLES_DIR), name="samples")
app.mount("/temp_audio", StaticFiles(directory="temp_audio"), name="temp_audio")
app.mount("/audio", StaticFiles(directory="audio_files"), name="audio")

# 注册管理员路由
app.include_router(admin_router)
app.include_router(project_router)
app.include_router(user_router)
app.include_router(system_router)

# 注册项目管理路由
app.include_router(project_manager_router)

# 注册文本调整路由
from text_adjuster import router as text_adjuster_router
app.include_router(text_adjuster_router)

# 注册自定义角色路由
from custom_speakers import router as custom_speakers_router
app.include_router(custom_speakers_router)

# 健康检查端点
from api.core.health import router as health_router
app.include_router(health_router)

# 文件管理路由
from api.routes.files import router as files_router
app.include_router(files_router)


@app.post("/api/generate-audio")
async def generate_audio(
    file: UploadFile = File(...),
    groupId: str = Form(...),
    apiKey: str = Form(...),
    model: str = Form(Config.TTS_CONFIG["default_model"]),
    language: str = Form(Config.TTS_CONFIG["default_language"]),
    voiceMapping: str = Form(...),
    clientId: str = Form(...),
    apiEndpoint: str = Form("domestic")
):
    """生成音频文件"""
    # 检查用户数量限制
    from admin import check_user_limit, record_user_activity
    if check_user_limit():
        raise HTTPException(
            status_code=503, 
            detail="当前在线用户数过多，请稍后再试。当前限制：10个用户"
        )
    
    # 记录用户活动
    record_user_activity(clientId, "generate_audio", groupId)
    
    try:
        print(f"🔥 DEBUG: API被调用，文件名: {file.filename}")
        
        # 使用前端传递的客户端 ID
        logger = get_process_logger(clientId)
        
        # 立即输出开始日志
        print(f"🔥 DEBUG: 使用客户端ID: {clientId}")
        await logger.info("收到配音生成请求", f"客户端ID: {clientId[:8]}***")
        
        print(f"🔥 DEBUG: 开始处理，文件名: {file.filename}")
        
        # 验证文件类型
        await logger.info("📋 验证文件类型", f"文件名: {file.filename}")
        print(f"🔥 DEBUG: 文件类型验证")
        if not file.filename.endswith(('.srt', '.txt')):
            print(f"🔥 DEBUG: 文件类型错误")
            await logger.error("❌ 文件类型错误", f"不支持的文件类型: {file.filename}")
            raise HTTPException(status_code=400, detail="只支持 .srt 或 .txt 格式的字幕文件")
        print(f"🔥 DEBUG: 文件类型验证通过")
        
        # 验证文件大小
        print(f"🔥 DEBUG: 开始读取文件")
        content = await file.read()
        print(f"🔥 DEBUG: 文件读取完成，大小: {len(content)} 字节")
        # 使用动态文件大小限制
        limits = get_dynamic_limits()
        if len(content) > limits["maxFileSize"]:
            print(f"🔥 DEBUG: 文件过大")
            max_size_mb = limits["maxFileSize"] // (1024 * 1024)
            raise HTTPException(status_code=400, detail=f"文件过大，请上传小于 {max_size_mb}MB 的文件")
        print(f"🔥 DEBUG: 文件大小验证通过")
        
        print(f"🔥 DEBUG: 准备创建logger日志")
        await logger.info("🎬 开始多人配音生成", "解析请求参数...")
        await logger.info("📁 文件信息", f"文件名: {file.filename}, 大小: {len(content)} 字节")
        print(f"🔥 DEBUG: logger日志创建完成")
        
        # 解析语音映射
        print(f"🔥 DEBUG: 开始解析语音映射")
        try:
            voice_mapping = json.loads(voiceMapping)
            print(f"🔥 DEBUG: 语音映射解析成功")
        except json.JSONDecodeError as e:
            print(f"🔥 DEBUG: 语音映射解析失败: {e}")
            raise HTTPException(status_code=400, detail="语音映射格式错误")
        
        print(f"🔥 DEBUG: 开始记录配置信息")
        await logger.info("📋 配置信息", f"模型: {model}, 语言: {language}")
        await logger.info("🔑 API配置", f"Group ID: {groupId[:8]}***, API Key: ***{apiKey[-4:]}")
        await logger.info("🎤 语音映射", json.dumps(voice_mapping, ensure_ascii=False, indent=2))
        print(f"🔥 DEBUG: 配置信息记录完成")
        
        # 解码文件内容
        await logger.info("🔍 开始解码文件内容", f"原始字节数: {len(content)}")
        try:
            file_content = content.decode('utf-8')
            await logger.info("✅ UTF-8 解码成功", f"内容长度: {len(file_content)} 字符")
        except UnicodeDecodeError as e:
            await logger.warning("⚠️ UTF-8 解码失败", f"尝试 GBK 编码: {str(e)}")
            try:
                file_content = content.decode('gbk')
                await logger.info("✅ GBK 解码成功", f"内容长度: {len(file_content)} 字符")
            except UnicodeDecodeError:
                await logger.error("❌ 编码解析失败", "文件编码不支持")
                raise HTTPException(status_code=400, detail="文件编码不支持，请使用 UTF-8 或 GBK 编码")
        
        # 显示文件内容预览
        preview = file_content[:200] + "..." if len(file_content) > 200 else file_content
        await logger.info("📄 文件内容预览", preview)
        
        # 创建输出文件路径
        print(f"🔥 DEBUG: 创建输出路径")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"配音_{timestamp}_{clientId[:8]}.mp3"
        output_path = Config.OUTPUT_DIR / output_filename
        print(f"🔥 DEBUG: 输出路径: {output_path}")
        
        # 初始化音频处理器
        print(f"🔥 DEBUG: 初始化音频处理器")
        audio_processor = AudioProcessor(logger, api_endpoint=apiEndpoint)
        await audio_processor.initialize(groupId, apiKey, apiEndpoint)
        print(f"🔥 DEBUG: 音频处理器初始化完成")
        
        # 处理音频
        print(f"🔥 DEBUG: 开始处理音频文件")
        result = await audio_processor.process_subtitle_file(
            file_content=file_content,
            voice_mapping=voice_mapping,
            output_path=output_path,
            model=model,
            language=language
        )
        print(f"🔥 DEBUG: 音频处理完成")
        
        await logger.progress("✅ 处理完成", 100, "音频文件已生成")
        
        return {
            "success": True,
            "message": "配音生成成功",
            "client_id": clientId,
            "output_file": output_filename,
            "download_url": f"/outputs/{output_filename}",
            "statistics": result["statistics"]
        }
        
    except HTTPException as he:
        print(f"🔥 DEBUG: HTTP异常: {he.detail}")
        raise
    except Exception as e:
        print(f"🔥 DEBUG: 未处理异常: {str(e)}")
        await logger.error("❌ 处理失败", str(e))
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


# 字幕解析与管理相关API - 已迁移到新路由模块

# 项目管理路由
from api.routes.projects import router as projects_router
app.include_router(projects_router)

# WebSocket和日志路由
from api.routes.websocket_logs import router as websocket_router, global_state
# 注入全局状态
global_state.set_global_state(running_tasks, task_cancellation_flags)
app.include_router(websocket_router)

# 基础路由
from api.routes.basic import router as basic_router
app.include_router(basic_router)

# 翻译路由
from api.routes.translation import router as translation_router
from api.core.global_state import global_state
# 注入全局状态
global_state.set_global_state(running_tasks, task_cancellation_flags)
app.include_router(translation_router)

# 音频拼接路由
from api.routes.audio import router as audio_router
app.include_router(audio_router)

# 字幕管理路由
from api.routes.subtitle_management import router as subtitle_management_router
app.include_router(subtitle_management_router)

# 单段落TTS路由
from api.routes.single_tts import router as single_tts_router
app.include_router(single_tts_router)

# 批量TTS路由
from api.routes.batch_tts import router as batch_tts_router
app.include_router(batch_tts_router)


def main():
    """主函数"""
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=Config.DEBUG,
        log_level="info"
    )

if __name__ == "__main__":
    main() 