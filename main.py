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

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from config import Config, create_directories
from audio_processor import AudioProcessor
from utils.logger import websocket_logger, get_process_logger
from subtitle_manager import subtitle_manager
from admin import admin_router, record_user_activity, start_cleanup_task

from contextlib import asynccontextmanager

# 全局变量用于跟踪正在运行的任务
running_tasks = {}
task_cancellation_flags = {}

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

@app.get("/")
async def read_root():
    """主页重定向到静态文件"""
    return FileResponse(Config.STATIC_DIR / "index.html")

@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "多人配音 Web 服务",
        "version": "2.0.0"
    }

@app.get("/api/sample-files")
async def get_sample_files():
    """获取样例文件列表"""
    valid_files = []
    
    for file_info in Config.SAMPLE_FILES:
        file_path = Config.BASE_DIR / file_info["path"]
        if file_path.exists():
            valid_files.append({
                "name": file_info["name"],
                "description": file_info["description"],
                "size": file_path.stat().st_size,
                "url": f"/api/sample-files/{file_info['name']}"
            })
        else:
            print(f"⚠️ 样例文件不存在: {file_path}")
    
    return {"files": valid_files}

@app.get("/api/sample-files/{filename}")
async def download_sample_file(filename: str):
    """下载样例文件"""
    # 查找对应的文件信息
    file_info = None
    for sample in Config.SAMPLE_FILES:
        if sample["name"] == filename:
            file_info = sample
            break
    
    if not file_info:
        raise HTTPException(status_code=404, detail="样例文件不存在")
    
    file_path = Config.BASE_DIR / file_info["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件未找到")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="text/plain"
    )

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
        if len(content) > Config.AUDIO_CONFIG["max_file_size"]:
            print(f"🔥 DEBUG: 文件过大")
            raise HTTPException(status_code=400, detail="文件过大，请上传小于 10MB 的文件")
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

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket 连接处理"""
    try:
        await websocket_logger.connect(websocket, client_id)
        
        # 保持连接
        while True:
            try:
                # 等待客户端消息 (ping/pong)
                data = await websocket.receive_text()
                
                # 可以处理客户端发送的消息
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket 错误: {e}")
                break
                
    except Exception as e:
        print(f"WebSocket 连接错误: {e}")
    finally:
        websocket_logger.disconnect(client_id)

@app.post("/api/test-upload")
async def test_upload(
    file: UploadFile = File(...),
    groupId: str = Form(...),
    apiKey: str = Form(...)
):
    """测试文件上传功能"""
    print(f"🔥 TEST: 收到测试请求")
    print(f"🔥 TEST: 文件名: {file.filename}")
    print(f"🔥 TEST: Group ID: {groupId}")
    print(f"🔥 TEST: API Key: {apiKey}")
    
    content = await file.read()
    print(f"🔥 TEST: 文件大小: {len(content)} 字节")
    
    return {
        "success": True,
        "filename": file.filename,
        "size": len(content),
        "groupId": groupId,
        "apiKey": apiKey[:3] + "***"
    }

@app.get("/api/config")
async def get_config():
    """获取前端配置信息"""
    return {
        "voices": Config.VOICE_MAPPING,
        "models": ["speech-02-hd", "speech-01"],
        "languages": Config.TTS_CONFIG["supported_languages"],
        "maxFileSize": Config.AUDIO_CONFIG["max_file_size"],
        "supportedFormats": Config.AUDIO_CONFIG["supported_formats"]
    }

@app.get("/api/outputs")
async def list_output_files():
    """列出输出文件"""
    try:
        output_files = []
        if Config.OUTPUT_DIR.exists():
            for file_path in Config.OUTPUT_DIR.glob("*.mp3"):
                stat = file_path.stat()
                output_files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "url": f"/outputs/{file_path.name}"
                })
        
        # 按创建时间降序排序
        output_files.sort(key=lambda x: x["created"], reverse=True)
        
        return {"files": output_files}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

@app.delete("/api/outputs/{filename}")
async def delete_output_file(filename: str):
    """删除输出文件"""
    try:
        file_path = Config.OUTPUT_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        file_path.unlink()
        return {"success": True, "message": f"文件 {filename} 已删除"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

# 字幕解析与管理相关API
@app.post("/api/parse-subtitle")
async def parse_subtitle(file: UploadFile = File(...), clientId: str = Form(None)):
    """解析字幕文件"""
    # 检查用户数量限制
    from admin import check_user_limit, record_user_activity
    if check_user_limit():
        raise HTTPException(
            status_code=503, 
            detail="当前在线用户数过多，请稍后再试。当前限制：10个用户"
        )
    
    # 记录用户活动（使用文件名作为临时clientId）
    temp_client_id = f"parse_{file.filename}"
    if clientId:
        temp_client_id = clientId
    record_user_activity(temp_client_id, "parse_subtitle")
    
    try:
        # 验证文件类型
        if not file.filename.lower().endswith('.srt'):
            raise HTTPException(status_code=400, detail="仅支持SRT格式的字幕文件")
        
        # 读取文件内容
        content = await file.read()
        file_content = content.decode('utf-8', errors='ignore')
        
        # 解析字幕文件
        success, error_msg, project = await subtitle_manager.parse_srt_file(
            file_content, file.filename, temp_client_id
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=error_msg)
        
        return {
            "success": True,
            "project": project.to_dict(),
            "message": f"成功解析 {project.total_segments} 条字幕"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@app.get("/api/projects")
async def get_projects():
    """获取所有字幕项目列表"""
    try:
        projects = subtitle_manager.list_projects()
        return {
            "success": True,
            "projects": projects
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")


@app.get("/api/subtitle/{project_id}/segments")
async def get_subtitle_segments(
    project_id: str, 
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=1000, description="每页条目数")
):
    """获取字幕段落（分页）"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        result = project.get_segments_page(page, per_page)
        return {
            "success": True,
            "project_info": project.to_dict(),
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取段落失败: {str(e)}")


@app.put("/api/subtitle/{project_id}/segment/{segment_id}")
async def update_subtitle_segment(
    project_id: str,
    segment_id: str,
    updates: Dict
):
    """更新字幕段落"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 验证更新字段
        allowed_fields = ["start_time", "end_time", "speaker", "text", "translated_text", "emotion", "speed"]
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            raise HTTPException(status_code=400, detail="没有有效的更新字段")
        
        success = project.update_segment(segment_id, filtered_updates)
        if not success:
            raise HTTPException(status_code=404, detail="段落未找到")
        
        return {
            "success": True,
            "message": "段落更新成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新段落失败: {str(e)}")


@app.post("/api/subtitle/{project_id}/segment")
async def add_subtitle_segment(
    project_id: str,
    segment_data: Dict
):
    """添加新的字幕段落"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 验证必需字段
        required_fields = ["start_time", "end_time", "speaker", "text"]
        for field in required_fields:
            if field not in segment_data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        # 创建新段落
        from subtitle_manager import SubtitleSegment, EmotionDetector
        
        # 自动检测情绪
        emotion = segment_data.get("emotion", "auto")
        if emotion == "auto":
            emotion = EmotionDetector.detect_emotion(segment_data["text"])
        
        new_segment = SubtitleSegment(
            index=len(project.segments) + 1,  # 临时索引，会在add_segment中重新计算
            start_time=segment_data["start_time"],
            end_time=segment_data["end_time"],
            speaker=segment_data["speaker"],
            text=segment_data["text"],
            emotion=emotion,
            speed=segment_data.get("speed", 1.0)
        )
        
        # 获取插入位置参数
        insert_after_index = segment_data.get("insert_after_index")
        print(f"🔥 DEBUG: 接收到的段落数据: {segment_data}")
        print(f"🔥 DEBUG: insert_after_index = {insert_after_index}")
        print(f"🔥 DEBUG: 当前项目段落数: {len(project.segments)}")
        project.add_segment(new_segment, insert_after_index)
        
        return {
            "success": True,
            "message": "段落添加成功",
            "segment": new_segment.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加段落失败: {str(e)}")


@app.delete("/api/subtitle/{project_id}/segment/{segment_id}")
async def delete_subtitle_segment(project_id: str, segment_id: str):
    """删除字幕段落"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        success = project.remove_segment(segment_id)
        if not success:
            raise HTTPException(status_code=404, detail="段落未找到")
        
        return {
            "success": True,
            "message": "段落删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除段落失败: {str(e)}")


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """删除整个字幕项目"""
    try:
        success = subtitle_manager.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        return {
            "success": True,
            "message": "项目删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除项目失败: {str(e)}")

@app.get("/api/subtitle/{project_id}/export-srt")
async def export_subtitle_srt(project_id: str):
    """导出SRT格式字幕文件（包含speaker和emotion）"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 生成SRT格式内容（包含speaker和emotion）
        srt_content = ""
        for segment in project.segments:
            # 将逗号转换为点号以匹配原始格式
            start_time = segment.start_time.replace(',', '.')
            end_time = segment.end_time.replace(',', '.')
            
            # 优先使用译文，当译文为空时使用原文
            text_to_export = segment.translated_text if segment.translated_text else segment.text
            
            srt_content += f"{segment.index}\n"
            srt_content += f"[{start_time} --> {end_time}] {segment.speaker} [emotion: {segment.emotion}]\n"
            srt_content += f"{text_to_export}\n\n"
        
        # 返回SRT内容
        return {
            "success": True,
            "srt_content": srt_content,
            "filename": f"{project.filename}_edited.srt"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出SRT失败: {str(e)}")

@app.post("/api/subtitle/{project_id}/segment/{segment_id}/generate-tts")
async def generate_tts_for_segment(
    project_id: str,
    segment_id: str,
    groupId: str = Form(...),
    apiKey: str = Form(...),
    model: str = Form(Config.TTS_CONFIG["default_model"]),
    language: str = Form(Config.TTS_CONFIG["default_language"]),
    voiceMapping: str = Form(...),
    apiEndpoint: str = Form("domestic")
):
    """为单个字幕段落生成TTS音频"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 查找段落
        segment = None
        for seg in project.segments:
            if seg.id == segment_id:
                segment = seg
                break
        
        if not segment:
            raise HTTPException(status_code=404, detail="段落未找到")
        
        # 解析语音映射
        try:
            voice_mapping = json.loads(voiceMapping)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="语音映射格式错误")
        
        # 获取对应的语音ID
        voice = voice_mapping.get(segment.speaker, "ai_her_04")
        
        # 初始化音频处理器
        from audio_processor import TTSService
        from utils.logger import get_process_logger
        
        logger = get_process_logger(f"tts_{project_id}_{segment_id}")
        tts_service = TTSService(logger, api_endpoint=apiEndpoint)
        await tts_service.initialize(groupId, apiKey)
        
        # 计算字幕时间长度 T_srt (毫秒)
        from audio_processor import SubtitleParser
        start_seconds = SubtitleParser._time_to_seconds(segment.start_time)
        end_seconds = SubtitleParser._time_to_seconds(segment.end_time)
        t_srt_ms = int((end_seconds - start_seconds) * 1000)
        
        await logger.info(f"开始生成TTS", f"段落ID: {segment_id}, 说话人: {segment.speaker}, 目标时长: {t_srt_ms}ms")
        
        # 优先使用译文，当译文为空时使用原文
        text_to_use = segment.translated_text if segment.translated_text else segment.text
        is_using_translation = bool(segment.translated_text)
        await logger.info(f"TTS参数", f"文本: {text_to_use}, 文本类型: {'译文' if is_using_translation else '原文'}, 语音: {voice}, 情绪: {segment.emotion}, 速度: {segment.speed}")
        
        # 生成音频
        result = await tts_service.generate_audio_with_info(
            text=text_to_use,
            voice=voice,
            model=model,
            language=language,
            speed=segment.speed,
            emotion=segment.emotion
        )
        
        audio_data = result['audio_data']
        t_tts_ms = result['duration_ms']
        trace_id = result.get('trace_id', '')
        
        # 检查音频下载是否失败
        if audio_data is None:
            # 显示完整的Trace ID
            trace_display = trace_id if trace_id else 'None'
            await logger.error(f"音频下载失败", f"Trace: {trace_display}")
            return {
                "success": False,
                "message": "音频下载失败",
                "segment_id": segment_id,
                "trace_id": trace_id,
                "audio_url": "",
                "duration_ms": 0
            }
        
        # 显示完整的Trace ID
        trace_display = trace_id if trace_id else 'None'
        await logger.info(f"音频生成完成", f"TTS时长: {t_tts_ms}ms, 字幕时长: {t_srt_ms}ms, Trace: {trace_display}")
        
        # 计算时长比例
        duration_ratio = t_tts_ms / t_srt_ms if t_srt_ms > 0 else 0
        ratio_info = f"比例: {duration_ratio:.2f} (TTS: {t_tts_ms}ms, 字幕: {t_srt_ms}ms)"
        await logger.info(f"时长比例", ratio_info)
        
        # 判断是否成功（ratio <= 1.0）
        if duration_ratio <= 1.0:
            await logger.success(f"TTS生成成功", f"比例: {duration_ratio:.2f} <= 1.0")
            
            # 保存处理后的音频文件用于播放
            import os
            from pathlib import Path
            
            # 创建audio_files目录
            audio_dir = Path("audio_files")
            audio_dir.mkdir(exist_ok=True)
            
            # 生成唯一的音频文件名
            audio_filename = f"segment_{segment_id}_{int(datetime.now().timestamp())}.mp3"
            audio_path = audio_dir / audio_filename
            
            # 保存处理后的音频数据到文件
            with open(audio_path, "wb") as f:
                f.write(audio_data)
            
            # 更新段落信息
            segment.audio_data = audio_data  # 存储处理后的音频数据
            segment.audio_duration = t_tts_ms
            segment.trace_id = trace_id
            segment.audio_url = f"/audio/{audio_filename}"  # 存储本地音频URL用于播放
            segment.updated_at = datetime.now().isoformat()
            
            return {
                "success": True,
                "message": "TTS生成成功",
                "segment_id": segment_id,
                "trace_id": trace_id,
                "audio_url": f"/audio/{audio_filename}",  # 返回本地音频URL用于播放
                "duration_ms": t_tts_ms,
                "duration_ratio": duration_ratio,
                "extra_info": result.get('extra_info', {})
            }
        else:
            # ratio > 1.0，生成失败
            await logger.error(f"TTS生成失败", f"比例: {duration_ratio:.2f} > 1.0, 目标时长: {t_srt_ms}ms, 当前音频时长: {t_tts_ms}ms, Trace: {trace_display}")
            
            return {
                "success": False,
                "message": f"TTS生成失败: 音频时长超出字幕时长 (比例: {duration_ratio:.2f})",
                "segment_id": segment_id,
                "trace_id": trace_id,
                "audio_url": "",
                "duration_ms": t_tts_ms,
                "duration_ratio": duration_ratio,
                "target_duration": t_srt_ms,
                "current_duration": t_tts_ms
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS生成失败: {str(e)}")

@app.post("/api/subtitle/{project_id}/batch-generate-tts")
async def batch_generate_tts_for_project(
    project_id: str,
    groupId: str = Form(...),
    apiKey: str = Form(...),
    model: str = Form(Config.TTS_CONFIG["default_model"]),
    language: str = Form(Config.TTS_CONFIG["default_language"]),
    voiceMapping: str = Form(...),
    clientId: str = Form(None),
    apiEndpoint: str = Form("domestic")
):
    """为项目中的所有字幕段落批量生成TTS音频（包含时间戳匹配和speed调整）"""
    # 检查用户数量限制
    from admin import check_user_limit, record_user_activity
    if check_user_limit():
        raise HTTPException(
            status_code=503, 
            detail="当前在线用户数过多，请稍后再试。当前限制：10个用户"
        )
    
    # 记录用户活动
    if clientId:
        record_user_activity(clientId, "batch_generate_tts", groupId)
    else:
        record_user_activity(f"batch_tts_{project_id}", "batch_generate_tts", groupId)
    
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 解析语音映射
        try:
            voice_mapping = json.loads(voiceMapping)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="语音映射格式错误")
        
        # 初始化TTS服务
        from audio_processor import TTSService
        from utils.logger import get_process_logger
        
        # 使用传入的clientId或生成新的
        log_client_id = clientId if clientId else f"batch_tts_{project_id}"
        logger = get_process_logger(log_client_id)
        
        # 清除之前的中断标志
        task_cancellation_flags[log_client_id] = False
        
        tts_service = TTSService(logger, api_endpoint=apiEndpoint)
        await tts_service.initialize(groupId, apiKey)
        
        # 创建audio_files目录
        import os
        from pathlib import Path
        audio_dir = Path("audio_files")
        audio_dir.mkdir(exist_ok=True)
        
        updated_segments = []
        speed_adjustments = []
        
        # 添加统计变量
        translation_optimized_segments = []  # 通过翻译优化的段落
        speed_optimized_segments = []       # 通过speed优化的段落
        failed_silent_segments = []         # 失败使用静音的段落
        normal_segments = []                # 正常生成无需优化的段落
        
        await logger.info("开始批量TTS生成", f"共 {len(project.segments)} 个段落")
        
        # 为每个段落生成TTS
        for i, segment in enumerate(project.segments):
            # 检查中断标志
            if task_cancellation_flags.get(log_client_id, False):
                await logger.warning("任务被中断", f"已处理 {i}/{len(project.segments)} 个段落，正在保存进度...")
                
                # 保存当前进度
                try:
                    subtitle_manager.save_project(project)
                    await logger.success("进度保存成功", f"已生成 {len(updated_segments)} 个音频文件")
                except Exception as save_error:
                    await logger.error("进度保存失败", f"错误: {str(save_error)}")
                
                # 返回中断状态
                return {
                    "success": True,
                    "message": f"任务已中断，成功处理 {len(updated_segments)}/{i} 个段落",
                    "updated_segments": updated_segments,
                    "speed_adjustments": speed_adjustments,
                    "interrupted": True,
                    "statistics": {
                        "total_segments": len(project.segments),
                        "successful_segments": len(updated_segments),
                        "failed_segments": i - len(updated_segments),
                        "accelerated_segments": len([seg for seg in updated_segments if seg.get('final_speed', 1.0) > 1.0]),
                        "max_speed_segments": len([seg for seg in updated_segments if seg.get('final_speed', 1.0) >= 2.0]),
                        "translation_optimized_segments": len(translation_optimized_segments),
                        "speed_optimized_segments": len(speed_optimized_segments),
                        "failed_silent_segments": len(failed_silent_segments),
                        "normal_segments": len(normal_segments)
                    }
                }
            try:
                # 计算字幕时间长度 T_srt (毫秒)
                from audio_processor import SubtitleParser
                start_seconds = SubtitleParser._time_to_seconds(segment.start_time)
                end_seconds = SubtitleParser._time_to_seconds(segment.end_time)
                t_srt_ms = int((end_seconds - start_seconds) * 1000)
                
                await logger.info(f"处理段落 {i+1}/{len(project.segments)}", 
                                f"说话人: {segment.speaker}, 目标时长: {t_srt_ms}ms, 当前speed: {segment.speed}")
                
                # 获取对应的语音ID
                voice = voice_mapping.get(segment.speaker, "ai_her_04")
                
                # 使用重试机制生成合适的音频
                max_retries = 4  # 增加到4次，确保能到达speed=2.0
                current_speed = segment.speed
                final_audio_data = None
                final_duration_ms = 0
                final_trace_id = ""
                translation_optimization_count = 0  # 翻译优化次数计数
                
                for attempt in range(max_retries):
                    await logger.info(f"段落 {i+1} 尝试 {attempt + 1}", 
                                    f"速度: {current_speed}, 目标时长: {t_srt_ms}ms")
                    
                    # 优先使用译文，当译文为空时使用原文
                    text_to_use = segment.translated_text if segment.translated_text else segment.text
                    is_using_translation = bool(segment.translated_text)
                    await logger.info(f"段落 {i+1} 使用文本", f"文本类型: {'译文' if is_using_translation else '原文'}")
                    
                    # 生成TTS
                    result = await tts_service.generate_audio_with_info(
                        text=text_to_use,
                        voice=voice,
                        model=model,
                        language=language,
                        speed=current_speed,
                        emotion=segment.emotion
                    )
                    
                    audio_data = result['audio_data']
                    t_tts_ms = result['duration_ms']
                    trace_id = result.get('trace_id', '')
                    
                    # 检查音频下载是否失败
                    if audio_data is None:
                        # 显示完整的Trace ID
                        trace_display = trace_id if trace_id else 'None'
                        await logger.error(f"段落 {i+1} 音频下载失败", f"Trace: {trace_display}")
                        if attempt < max_retries - 1:
                            await logger.warning(f"段落 {i+1} 重试", f"音频下载失败，尝试重新生成")
                            continue
                        else:
                            await logger.error(f"段落 {i+1} 最终失败", f"音频下载失败，使用静音占位符")
                            final_audio_data = b'silence_placeholder'
                            final_duration_ms = t_srt_ms
                            final_trace_id = trace_id
                            break
                    
                    # 显示完整的Trace ID
                    trace_display = trace_id if trace_id else 'None'
                    await logger.info(f"段落 {i+1} 音频分析", 
                                    f"TTS时长: {t_tts_ms}ms, 字幕时长: {t_srt_ms}ms, Trace: {trace_display}")
                    
                    # 计算时长比例（无论是否成功都要计算）
                    duration_ratio = t_tts_ms / t_srt_ms if t_srt_ms > 0 else 0
                    ratio_info = f"比例: {duration_ratio:.2f} (TTS: {t_tts_ms}ms, 字幕: {t_srt_ms}ms)"
                    await logger.info(f"段落 {i+1} 时长比例", ratio_info)
                    
                    # 判断是否需要调整速度
                    if duration_ratio <= 1.0:
                        await logger.success(f"段落 {i+1} 时长合适", f"使用速度: {current_speed}, 比例: {duration_ratio:.2f} <= 1.0")
                        final_audio_data = audio_data
                        final_duration_ms = t_tts_ms
                        final_trace_id = trace_id
                        break
                    
                    # 需要加速
                    if attempt < max_retries - 1:  # 还有重试机会
                        # 翻译优化成功后，如果重试的ratio<=1.3则直接成功
                        if translation_optimization_count > 0 and duration_ratio <= 1.3:
                            await logger.success(f"段落 {i+1} 翻译优化成功", f"重试后比例: {duration_ratio:.2f} <= 1.3，直接成功")
                            final_audio_data = audio_data
                            final_duration_ms = t_tts_ms
                            final_trace_id = trace_id
                            break
                        
                        if duration_ratio > 1.3 and translation_optimization_count < 1:  # 只翻译优化一次
                            # 时长比例 > 1.3，重新翻译优化
                            await logger.warning(f"段落 {i+1} 需要翻译优化", f"时长比例: {duration_ratio:.2f} > 1.3, 优化次数: {translation_optimization_count}")
                            
                            if is_using_translation:
                                # 使用译文，进行翻译优化
                                optimized_text = await optimize_translation_for_audio_length(
                                    original_text=segment.text,
                                    current_translation=segment.translated_text,
                                    target_language="中文",
                                    current_audio_length=t_tts_ms / 1000.0,
                                    target_audio_length=t_srt_ms / 1000.0,
                                    group_id=groupId,
                                    api_key=apiKey,
                                    logger=logger # 传递logger
                                )
                                
                                if optimized_text:
                                    # 检查优化后的文本是否确实变短了
                                    original_length = len(segment.translated_text)
                                    optimized_length = len(optimized_text)
                                    
                                    if optimized_length < original_length:
                                        # 更新段落的译文
                                        segment.translated_text = optimized_text
                                        translation_optimization_count += 1
                                        await logger.info(f"段落 {i+1} 翻译优化成功", f"原长度: {original_length}, 新长度: {optimized_length}, 新译文: {optimized_text}")
                                        # 翻译优化成功后，继续使用当前speed重试，看优化后的效果
                                        await logger.info(f"段落 {i+1} 重试", f"翻译优化成功，使用当前speed={current_speed}重试")
                                        # 翻译优化成功后，如果重试的ratio<=1.3则直接成功，只有ratio>1.3才继续speed调整
                                        attempt += 1  # 增加重试计数
                                        continue  # 重新尝试生成TTS
                                    else:
                                        await logger.warning(f"段落 {i+1} 翻译优化无效", f"优化后长度未减少: {original_length} -> {optimized_length}，丢弃新翻译")
                                        # 翻译优化无效，增加计数避免重复尝试，继续使用原翻译进行speed调整
                                        translation_optimization_count += 1
                                        new_speed = duration_ratio
                                        new_speed = min(new_speed, 2.0)
                                        current_speed = round(new_speed, 1)
                                        await logger.warning(f"段落 {i+1} 重试", f"新速度: {current_speed}, 当前比例: {duration_ratio:.2f}")
                                        attempt += 1  # 增加重试计数
                                        continue  # 继续重试
                                else:
                                    await logger.error(f"段落 {i+1} 翻译优化失败", "使用speed调整")
                                    # 翻译优化失败，增加计数避免重复尝试，回退到speed调整
                                    translation_optimization_count += 1
                                    new_speed = duration_ratio
                                    new_speed = min(new_speed, 2.0)
                                    current_speed = round(new_speed, 1)
                                    await logger.warning(f"段落 {i+1} 重试", f"新速度: {current_speed}, 当前比例: {duration_ratio:.2f}")
                                    attempt += 1  # 增加重试计数
                                    continue  # 继续重试
                            else:
                                # 使用原文，无法进行翻译优化，直接使用speed调整
                                new_speed = duration_ratio
                                new_speed = min(new_speed, 2.0)
                                current_speed = round(new_speed, 1)
                                await logger.warning(f"段落 {i+1} 重试", f"新速度: {current_speed}, 当前比例: {duration_ratio:.2f}")
                                attempt += 1  # 增加重试计数
                                continue  # 继续重试
                        else:
                            # 时长比例 <= 1.3 或 翻译优化次数已达上限，修改speed参数
                            if translation_optimization_count >= 1:
                                await logger.warning(f"段落 {i+1} 翻译优化次数已达上限", f"已优化 {translation_optimization_count} 次，改用speed调整")
                            
                            # 根据尝试次数调整speed
                            if attempt == 0:  # 第一次重试
                                new_speed = duration_ratio
                            elif attempt == 1:  # 第二次重试
                                new_speed = duration_ratio + 0.2
                            elif attempt == 2:  # 第三次重试
                                new_speed = duration_ratio + 0.4
                            else:  # 第四次重试，使用最大速度
                                new_speed = 2.0
                            
                            # 限制最大速度
                            new_speed = min(new_speed, 2.0)
                            current_speed = round(new_speed, 1)
                            
                            # 显示完整的Trace ID
                            trace_display = trace_id if trace_id else 'None'
                            await logger.warning(f"段落 {i+1} 重试", f"新速度: {current_speed}, 当前比例: {duration_ratio:.2f}, Trace: {trace_display}")
                            attempt += 1  # 增加重试计数
                            continue  # 继续重试
                    else:
                        # 最后一次重试，只有speed=2.0时ratio>1.0才计为失败
                        if current_speed >= 2.0 and duration_ratio > 1.0:
                            # 显示完整的Trace ID
                            trace_display = trace_id if trace_id else 'None'
                            await logger.error(f"段落 {i+1} 加速失败", f"speed=2.0时比例仍为{duration_ratio:.2f}，使用静音, Trace: {trace_display}")
                            final_audio_data = b'silence_placeholder'
                            final_duration_ms = t_srt_ms
                            final_trace_id = trace_id
                        else:
                            # 其他情况继续重试，直到speed=2.0
                            # 显示完整的Trace ID
                            trace_display = trace_id if trace_id else 'None'
                            await logger.warning(f"段落 {i+1} 继续重试", f"当前speed={current_speed} < 2.0，继续尝试, Trace: {trace_display}")
                            # 继续重试，增加speed
                            new_speed = min(current_speed + 0.2, 2.0)
                            current_speed = round(new_speed, 1)
                            attempt += 1  # 增加重试计数
                            continue
                        break
                
                # 保存处理后的音频文件
                if final_audio_data and final_audio_data != b'silence_placeholder':
                    audio_filename = f"segment_{segment.id}_{int(datetime.now().timestamp())}_{i}.mp3"
                    audio_path = audio_dir / audio_filename
                    
                    try:
                        with open(audio_path, "wb") as f:
                            f.write(final_audio_data)
                        
                        audio_url = f"/audio/{audio_filename}"
                        await logger.info(f"段落 {i+1} 音频保存成功", f"文件: {audio_filename}, 大小: {len(final_audio_data)} bytes")
                    except Exception as e:
                        await logger.error(f"段落 {i+1} 音频保存失败", f"错误: {str(e)}")
                        audio_url = ""
                else:
                    audio_url = ""
                    if not final_audio_data:
                        await logger.error(f"段落 {i+1} 音频数据为空", "API可能返回了空数据")
                    else:
                        await logger.warning(f"段落 {i+1} 使用静音", "API调用失败或加速失败")
                
                # 更新段落信息
                segment.audio_data = final_audio_data
                segment.audio_duration = final_duration_ms
                segment.trace_id = final_trace_id
                segment.audio_url = audio_url
                segment.speed = current_speed  # 更新最终使用的speed
                segment.updated_at = datetime.now().isoformat()
                
                # 记录统计信息
                if final_audio_data == b'silence_placeholder':
                    failed_silent_segments.append(i+1)
                elif translation_optimization_count > 0:
                    translation_optimized_segments.append(i+1)
                elif current_speed > 1.0:
                    speed_optimized_segments.append(i+1)
                else:
                    normal_segments.append(i+1)
                
                updated_segments.append({
                    "segment_id": segment.id,
                    "trace_id": final_trace_id,
                    "audio_url": audio_url,
                    "duration_ms": final_duration_ms,
                    "final_speed": current_speed
                })
                
                # 记录速度调整
                if current_speed > 1.0:
                    if current_speed >= 2.0 and final_audio_data == b'silence_placeholder':
                        speed_adjustments.append(f"段落 {i+1}: 加速失败，请简化文本")
                    else:
                        speed_adjustments.append(f"段落 {i+1}: speed={current_speed}")
                
                await logger.success(f"段落 {i+1}/{len(project.segments)} 完成", 
                                  f"ID: {segment.id}, 最终speed: {current_speed}, Trace: {final_trace_id if final_trace_id else 'None'}")
                
            except Exception as e:
                await logger.error(f"段落 {i+1} 生成失败", str(e))
                # 继续处理其他段落
                continue
        
        # 生成详细的总结报告
        total_segments = len(project.segments)
        successful_segments = len(updated_segments)
        failed_segments = total_segments - successful_segments
        
        # 统计加速情况
        accelerated_segments = [seg for seg in updated_segments if seg.get('final_speed', 1.0) > 1.0]
        max_speed_segments = [seg for seg in updated_segments if seg.get('final_speed', 1.0) >= 2.0]
        
        await logger.success("批量TTS生成完成", 
                           f"总段落: {total_segments}, 成功: {successful_segments}, 失败: {failed_segments}")
        
        # 输出详细的优化统计
        await logger.info("优化统计详情", 
                         f"正常生成: {len(normal_segments)}个, 翻译优化: {len(translation_optimized_segments)}个, "
                         f"速度优化: {len(speed_optimized_segments)}个, 失败静音: {len(failed_silent_segments)}个")
        
        if translation_optimized_segments:
            await logger.info("翻译优化段落", f"段落编号: {translation_optimized_segments}")
        
        if speed_optimized_segments:
            await logger.info("速度优化段落", f"段落编号: {speed_optimized_segments}")
        
        if failed_silent_segments:
            await logger.warning("失败静音段落", f"段落编号: {failed_silent_segments}")
        
        if accelerated_segments:
            await logger.info("加速统计", f"加速段落: {len(accelerated_segments)}/{successful_segments}")
            if max_speed_segments:
                await logger.warning("最大加速", f"达到最大速度的段落: {len(max_speed_segments)}")
        
        if speed_adjustments:
            await logger.info("速度调整详情", f"调整段落: {len(speed_adjustments)}")
            for adjustment in speed_adjustments:
                await logger.info("调整详情", adjustment)
        
        # 添加成功率统计
        success_rate = (successful_segments / total_segments) * 100
        await logger.info("批量TTS成功率", f"成功率: {success_rate:.1f}% ({successful_segments}/{total_segments})")
        
        # 添加处理时间统计
        await logger.info("批量TTS任务总结", f"处理时间: {datetime.now().strftime('%H:%M:%S')}, 模型: {model}, 语言: {language}")
        
        # 添加详细统计信息
        await logger.info("批量TTS详细统计", f"总段落: {total_segments}, 成功: {successful_segments}, 失败: {failed_segments}")
        if translation_optimized_segments:
            await logger.info("批量TTS翻译优化统计", f"翻译优化段落: {len(translation_optimized_segments)}")
        if speed_optimized_segments:
            await logger.info("批量TTS速度优化统计", f"速度优化段落: {len(speed_optimized_segments)}")
        if failed_silent_segments:
            await logger.info("批量TTS失败静音统计", f"失败静音段落: {len(failed_silent_segments)}")
        
        # 保存项目，确保翻译优化能够持久化
        try:
            subtitle_manager.save_project(project)
            await logger.info("批量TTS项目保存", "项目保存成功: 翻译优化已持久化")
        except Exception as e:
            await logger.error("批量TTS项目保存失败", f"错误: {str(e)}")
        
        return {
            "success": True,
            "message": f"批量TTS生成完成，成功处理 {successful_segments}/{total_segments} 个段落",
            "updated_segments": updated_segments,
            "speed_adjustments": speed_adjustments,
            "statistics": {
                "total_segments": total_segments,
                "successful_segments": successful_segments,
                "failed_segments": failed_segments,
                "accelerated_segments": len(accelerated_segments),
                "max_speed_segments": len(max_speed_segments),
                "translation_optimized_segments": len(translation_optimized_segments),
                "speed_optimized_segments": len(speed_optimized_segments),
                "failed_silent_segments": len(failed_silent_segments),
                "normal_segments": len(normal_segments)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量TTS生成失败: {str(e)}")

@app.post("/api/subtitle/{project_id}/merge-audio")
async def merge_audio_for_project(
    project_id: str,
    clientId: str = Form(...)
):
    """合并项目中的所有音频段落，按时间戳对齐输出完整音频"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 初始化日志
        from utils.logger import get_process_logger
        logger = get_process_logger(f"merge_audio_{project_id}")
        
        await logger.info("开始音频合并", f"项目: {project.filename}, 段落数: {len(project.segments)}")
        
        # 检查是否有音频数据
        segments_with_audio = [seg for seg in project.segments if seg.audio_data and seg.audio_data != b'silence_placeholder']
        if not segments_with_audio:
            raise HTTPException(status_code=400, detail="没有可用的音频数据，请先生成TTS")
        
        await logger.info("音频数据检查", f"有音频的段落: {len(segments_with_audio)}/{len(project.segments)}")
        
        # 初始化音频处理器
        from audio_processor import AudioProcessor
        # 从请求中获取API端点配置
        audio_processor = AudioProcessor(logger)
        
        # 准备音频段落数据
        audio_segments = []
        for segment in project.segments:
            if segment.audio_data and segment.audio_data != b'silence_placeholder':
                # 计算时间戳（毫秒）
                from audio_processor import SubtitleParser
                start_seconds = SubtitleParser._time_to_seconds(segment.start_time)
                end_seconds = SubtitleParser._time_to_seconds(segment.end_time)
                
                audio_segments.append({
                    'audio_data': segment.audio_data,
                    'start_time': int(start_seconds * 1000),  # 转换为毫秒
                    'end_time': int(end_seconds * 1000),      # 转换为毫秒  
                    'speaker': segment.speaker,
                    'text': segment.text,
                    'index': segment.index,
                    'speed': segment.speed
                })
        
        await logger.info("音频段落准备完成", f"共 {len(audio_segments)} 个有效音频段落")
        
        # 创建输出文件路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"配音_{timestamp}_{clientId[:8]}.mp3"
        output_path = Config.OUTPUT_DIR / output_filename
        
        await logger.info("开始构建音频时间轴", f"输出文件: {output_filename}")
        
        # 构建音频时间轴
        final_audio_path = await audio_processor._build_timeline_audio(audio_segments, output_path)
        
        await logger.success("音频合并完成", f"输出文件: {final_audio_path}")
        
        return {
            "success": True,
            "message": "音频合并完成",
            "output_file": output_filename,
            "download_url": f"/outputs/{output_filename}",
            "segments_count": len(audio_segments),
            "total_duration_ms": sum(seg['end_time'] - seg['start_time'] for seg in audio_segments)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"音频合并失败: {str(e)}")

@app.get("/api/logs/{client_id}")
async def get_logs(client_id: str):
    """获取指定客户端的日志"""
    try:
        from utils.logger import get_process_logger
        logger = get_process_logger(client_id)
        
        # 获取最新的日志条目
        logs = logger.get_recent_logs(50)  # 获取最近50条日志
        
        return logs  # 直接返回日志数组，前端期望这种格式
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")

@app.post("/api/interrupt/{client_id}")
async def interrupt_task(client_id: str):
    """中断指定客户端的当前任务"""
    try:
        # 设置中断标志
        task_cancellation_flags[client_id] = True
        
        # 记录中断日志
        from utils.logger import get_process_logger
        logger = get_process_logger(client_id)
        await logger.warning("用户请求中断", "正在尝试中断当前任务...")
        
        # 如果有正在运行的任务，尝试取消
        if client_id in running_tasks:
            task = running_tasks[client_id]
            if not task.done():
                task.cancel()
                await logger.info("任务中断", "已发送任务取消信号")
            else:
                await logger.info("任务状态", "任务已完成，无需中断")
        else:
            await logger.info("任务状态", "没有找到正在运行的任务")
        
        return {
            "success": True,
            "message": "中断请求已发送",
            "client_id": client_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"中断失败: {str(e)}",
            "client_id": client_id
        }

@app.get("/api/task-status/{client_id}")
async def get_task_status(client_id: str):
    """获取指定客户端的任务状态"""
    try:
        is_running = client_id in running_tasks and not running_tasks[client_id].done()
        is_cancelled = task_cancellation_flags.get(client_id, False)
        
        return {
            "success": True,
            "client_id": client_id,
            "is_running": is_running,
            "is_cancelled": is_cancelled
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取任务状态失败: {str(e)}",
            "client_id": client_id
        }


@app.get("/test-logs")
async def test_logs():
    """日志测试页面"""
    return FileResponse("test_logs.html")

@app.post("/api/subtitle/{project_id}/segment/{segment_id}/translate")
async def translate_segment(
    project_id: str,
    segment_id: str,
    groupId: str = Form(...),
    apiKey: str = Form(...),
    target_language: str = Form(...),
    apiEndpoint: str = Form("domestic")
):
    """翻译单个字幕段落"""
    try:
        # 获取项目
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取段落
        segment = project.get_segment(segment_id)
        if not segment:
            raise HTTPException(status_code=404, detail="段落不存在")
        
        # 检查目标语言是否支持
        if target_language not in Config.TRANSLATION_CONFIG["supported_target_languages"]:
            raise HTTPException(status_code=400, detail=f"不支持的目标语言: {target_language}")
        
        # 调用翻译API
        translated_text = await translate_text_with_minimax(
            segment.text, 
            target_language, 
            groupId, 
            apiKey,
            api_endpoint=apiEndpoint
        )
        
        if translated_text:
            # 更新段落的翻译文本
            segment.translated_text = translated_text
            subtitle_manager.save_project(project)
            
            return {
                "success": True,
                "message": "翻译成功",
                "original_text": segment.text,
                "translated_text": translated_text,
                "target_language": target_language
            }
        else:
            raise HTTPException(status_code=500, detail="翻译失败")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")

@app.post("/api/subtitle/{project_id}/batch-translate")
async def batch_translate_project(
    project_id: str,
    groupId: str = Form(...),
    apiKey: str = Form(...),
    target_language: str = Form(...),
    clientId: str = Form(None),
    apiEndpoint: str = Form("domestic")
):
    """为项目中的所有字幕段落批量翻译"""
    # 检查用户数量限制
    from admin import check_user_limit, record_user_activity
    if check_user_limit():
        raise HTTPException(
            status_code=503, 
            detail="当前在线用户数过多，请稍后再试。当前限制：10个用户"
        )
    
    # 记录用户活动
    if clientId:
        record_user_activity(clientId, "batch_translate", groupId)
    else:
        record_user_activity(f"batch_translate_{project_id}", "batch_translate", groupId)
    
    try:
        # 获取项目
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 检查目标语言是否支持
        if target_language not in Config.TRANSLATION_CONFIG["supported_target_languages"]:
            raise HTTPException(status_code=400, detail=f"不支持的目标语言: {target_language}")
        
        # 设置日志客户端ID
        log_client_id = clientId if clientId else f"batch_translate_{project_id}"
        logger = get_process_logger(log_client_id)
        
        # 清除之前的中断标志
        task_cancellation_flags[log_client_id] = False
        
        await logger.info("开始批量翻译", f"项目: {project.filename}, 目标语言: {target_language}")
        
        total_segments = len(project.segments)
        successful_translations = 0
        failed_translations = 0
        
        for i, segment in enumerate(project.segments, 1):
            # 检查中断标志
            if task_cancellation_flags.get(log_client_id, False):
                await logger.warning("任务被中断", f"已处理 {i-1}/{total_segments} 个段落，正在保存进度...")
                # 保存当前进度
                try:
                    subtitle_manager.save_project(project)
                    await logger.success("进度保存成功", f"已保存 {successful_translations} 个翻译结果")
                except Exception as save_error:
                    await logger.error("进度保存失败", f"错误: {str(save_error)}")
                
                return {
                    "success": True,
                    "message": f"任务已中断，成功翻译 {successful_translations}/{i-1} 个段落",
                    "total_segments": total_segments,
                    "successful_translations": successful_translations,
                    "failed_translations": failed_translations,
                    "target_language": target_language,
                    "updated_segments": [{"id": seg.id, "translated_text": seg.translated_text} for seg in project.segments if seg.translated_text],
                    "interrupted": True,
                    "statistics": {
                        "total_segments": total_segments,
                        "successful_segments": successful_translations,
                        "failed_segments": failed_translations
                    }
                }
            # 显示完整的文本内容，不截断
            display_text = segment.text if len(segment.text) <= 100 else segment.text[:100] + "..."
            await logger.info(f"翻译进度", f"处理段落 {i}/{total_segments}: {display_text}")
            
            try:
                # 调用翻译API
                translated_text = await translate_text_with_minimax(
                    segment.text, 
                    target_language, 
                    groupId, 
                    apiKey,
                    logger,
                    api_endpoint=apiEndpoint
                )
                
                if translated_text:
                    segment.translated_text = translated_text
                    successful_translations += 1
                    # 显示完整的原文和译文，不截断
                    original_display = segment.text if len(segment.text) <= 50 else segment.text[:50] + "..."
                    translated_display = translated_text if len(translated_text) <= 50 else translated_text[:50] + "..."
                    await logger.success(f"段落 {i} 翻译成功", f"原文: {original_display} → 译文: {translated_display}")
                else:
                    failed_translations += 1
                    await logger.error(f"段落 {i} 翻译失败", f"原文: {display_text}")
                    
            except Exception as e:
                failed_translations += 1
                await logger.error(f"段落 {i} 翻译异常", f"错误: {str(e)}")
            
            # 添加延迟避免API限制
            if i < total_segments:
                await asyncio.sleep(Config.TRANSLATION_CONFIG["translation_delay"])
        
        # 保存项目
        try:
            subtitle_manager.save_project(project)
            await logger.info("项目保存成功", f"项目ID: {project_id}")
        except Exception as save_error:
            await logger.error("项目保存失败", f"错误: {str(save_error)}")
            raise HTTPException(status_code=500, detail=f"项目保存失败: {str(save_error)}")
        
        # 生成详细的总结报告
        await logger.success("批量翻译完成", 
                            f"总段落: {total_segments}, 成功: {successful_translations}, 失败: {failed_translations}")
        
        # 添加更详细的统计信息
        if successful_translations > 0:
            success_rate = (successful_translations / total_segments) * 100
            await logger.info("翻译成功率", f"成功率: {success_rate:.1f}% ({successful_translations}/{total_segments})")
        
        if failed_translations > 0:
            await logger.warning("翻译失败统计", f"失败段落数: {failed_translations}, 失败率: {(failed_translations/total_segments)*100:.1f}%")
        
        await logger.info("翻译任务总结", f"目标语言: {target_language}, 处理时间: {datetime.now().strftime('%H:%M:%S')}")
        
        return {
            "success": True,
            "message": "批量翻译完成",
            "total_segments": total_segments,
            "successful_translations": successful_translations,
            "failed_translations": failed_translations,
            "target_language": target_language,
            "updated_segments": [{"id": seg.id, "translated_text": seg.translated_text} for seg in project.segments if seg.translated_text],
            "statistics": {
                "total_segments": total_segments,
                "successful_segments": successful_translations,
                "failed_segments": failed_translations
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # 确保异常情况下也返回完整结构
        error_logger = get_process_logger("error_logger")
        await error_logger.error("批量翻译异常", f"错误: {str(e)}")
        return {
            "success": False,
            "message": f"批量翻译失败: {str(e)}",
            "total_segments": 0,
            "successful_translations": 0,
            "failed_translations": 0,
            "target_language": target_language,
            "updated_segments": [],
            "statistics": {
                "total_segments": 0,
                "successful_segments": 0,
                "failed_segments": 0
            }
        }

@app.post("/api/subtitle/{project_id}/batch-update-speaker")
async def batch_update_speaker(
    project_id: str,
    request: Request
):
    """批量修改字幕段落的说话人"""
    try:
        # 获取项目
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 解析请求数据
        request_data = await request.json()
        segment_ids = request_data.get("segment_ids", [])
        new_speaker = request_data.get("speaker", "")
        
        if not segment_ids:
            raise HTTPException(status_code=400, detail="缺少要修改的段落ID列表")
        
        if not new_speaker:
            raise HTTPException(status_code=400, detail="缺少新的说话人信息")
        
        # 验证说话人是否有效
        valid_speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03", "SPEAKER_04", "SPEAKER_05"]
        if new_speaker not in valid_speakers:
            raise HTTPException(status_code=400, detail=f"无效的说话人: {new_speaker}")
        
        # 执行批量修改
        updated_count = 0
        for segment in project.segments:
            if segment.id in segment_ids:
                segment.speaker = new_speaker
                updated_count += 1
        
        if updated_count == 0:
            raise HTTPException(status_code=404, detail="没有找到要修改的段落")
        
        # 保存项目
        subtitle_manager.save_project(project)
        
        return {
            "success": True,
            "message": f"成功修改 {updated_count} 个段落的说话人",
            "updated_count": updated_count,
            "new_speaker": new_speaker,
            "segment_ids": segment_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量修改说话人失败: {str(e)}")

async def translate_text_with_minimax(text: str, target_language: str, group_id: str, api_key: str, logger=None, api_endpoint: str = "domestic") -> str:
    """使用MiniMax API翻译文本"""
    import aiohttp
    import json
    import uuid
    
    # 生成trace_id
    trace_id = str(uuid.uuid4())
    
    # 使用配置的翻译API端点
    base_url = get_api_endpoint("translation", api_endpoint)
    url = f"{base_url}?GroupId={group_id}"
    
    payload = {
        "model": Config.TRANSLATION_CONFIG["model"],
        "temperature": Config.TRANSLATION_CONFIG["temperature"],
        "top_p": Config.TRANSLATION_CONFIG["top_p"],
        "messages": [
            {
                "role": "system",
                "content": "你是一个专业的翻译助手，擅长翻译视频字幕。请保持翻译的自然流畅，适合口语表达。"
            },
            {
                "role": "user",
                "content": f"请将以下文本翻译成{target_language}，保持自然流畅的表达方式，直接输出翻译结果：\n\n{text}"
            }
        ],
    }
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        if logger:
            await logger.info("调用翻译API", f"目标语言: {target_language}, Trace: {trace_id}")
            await logger.info("发送API请求", f"Trace: {trace_id}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=Config.TRANSLATION_CONFIG["timeout"])) as response:
                response_data = await response.json()
                
                # 调试：打印完整的响应头信息
                print(f"[翻译API] 响应头信息: {dict(response.headers)}")
                
                # 尝试从响应头或响应体中获取trace_id
                api_trace_id = response.headers.get('X-Trace-Id') or response.headers.get('Trace-Id') or trace_id
                
                # 如果响应体中有trace_id，也尝试获取
                if isinstance(response_data, dict) and 'trace_id' in response_data:
                    api_trace_id = response_data['trace_id']
                elif isinstance(response_data, dict) and 'traceId' in response_data:
                    api_trace_id = response_data['traceId']
                
                # 调试：打印响应体信息
                print(f"[翻译API] 响应体结构: {list(response_data.keys()) if isinstance(response_data, dict) else 'not dict'}")
                
                if logger:
                    await logger.info("翻译API调用成功", f"Trace: {api_trace_id}")
                    await logger.info("API响应解析成功", f"Trace: {api_trace_id}")
                
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    translation_result = response_data['choices'][0]['message']['content'].strip()
                    if logger:
                        await logger.success("翻译成功", f"Trace: {api_trace_id}")
                    return translation_result
                else:
                    if logger:
                        await logger.error("翻译API响应格式异常", f"响应: {response_data}, Trace: {api_trace_id}")
                    return None
                    
    except Exception as e:
        if logger:
            await logger.error("翻译API调用失败", f"错误: {str(e)}, Trace: {trace_id}")
        return None

async def optimize_translation_for_audio_length(
    original_text: str, 
    current_translation: str, 
    target_language: str, 
    current_audio_length: float, 
    target_audio_length: float,
    group_id: str, 
    api_key: str,
    logger=None,
    api_endpoint: str = "domestic"
) -> str:
    """优化翻译以适应目标音频长度"""
    import aiohttp
    import json
    import uuid
    
    # 生成trace_id
    trace_id = str(uuid.uuid4())
    
    # 计算字符数和目标字符数
    current_char_count = len(current_translation)
    target_char_count = int(current_char_count * target_audio_length / current_audio_length)
    
    # 使用配置的翻译API端点
    base_url = get_api_endpoint("translation", api_endpoint)
    url = f"{base_url}?GroupId={group_id}"
    
    # 如果是原文生成，则ORIGINAL_TEXT为空
    original_text_for_optimization = original_text if original_text else ""
    
    payload = {
        "model": Config.TRANSLATION_CONFIG["model"],
        "temperature": Config.TRANSLATION_CONFIG["temperature"],
        "top_p": Config.TRANSLATION_CONFIG["top_p"],
        "messages": [
            {
                "role": "system",
                "content": "你是一个翻译优化专家"
            },
            {
                "role": "user",
                "content": f"你的任务是翻译优化，原文\"{original_text_for_optimization}\"当前\"{target_language}\"翻译\"{current_translation}\"，你需要缩短翻译的文字，同时保持口语化表达，当前字符数是{current_char_count}个字，需要精简成少于{target_char_count}个字，新的\"{target_language}\"翻译如下："
            }
        ],
    }
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        if logger:
            await logger.info("调用翻译优化API", f"目标语言: {target_language}, Trace: {trace_id}")
            await logger.info("发送API请求", f"Trace: {trace_id}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=Config.TRANSLATION_CONFIG["timeout"])) as response:
                response_data = await response.json()
                
                # 尝试从响应头或响应体中获取trace_id
                api_trace_id = response.headers.get('X-Trace-Id') or response.headers.get('Trace-Id') or trace_id
                
                # 如果响应体中有trace_id，也尝试获取
                if isinstance(response_data, dict) and 'trace_id' in response_data:
                    api_trace_id = response_data['trace_id']
                elif isinstance(response_data, dict) and 'traceId' in response_data:
                    api_trace_id = response_data['traceId']
                
                if logger:
                    await logger.info("翻译优化API调用成功", f"Trace: {api_trace_id}")
                    await logger.info("API响应解析成功", f"Trace: {api_trace_id}")
                
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    optimized_translation = response_data['choices'][0]['message']['content'].strip()
                    if logger:
                        await logger.success("翻译优化成功", f"Trace: {api_trace_id}")
                    return optimized_translation
                else:
                    if logger:
                        await logger.error("翻译优化API响应格式异常", f"响应: {response_data}, Trace: {api_trace_id}")
                    return None
                    
    except Exception as e:
        if logger:
            await logger.error("翻译优化API调用失败", f"错误: {str(e)}, Trace: {trace_id}")
        return None


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