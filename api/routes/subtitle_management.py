# -*- coding: utf-8 -*-
"""
字幕管理路由
处理字幕解析、段落管理、导出等功能
"""
from fastapi import APIRouter, HTTPException, File, Form, UploadFile, Query, Request, Response
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

from config import Config
from subtitle_manager import subtitle_manager, SubtitleSegment, EmotionDetector
from admin import check_user_limit, record_user_activity

router = APIRouter()

# 获取或创建会话ID的工具函数
def get_or_create_session_id(request: Request, response: Response) -> str:
    """获取或创建会话ID"""
    import secrets

    session_id = request.cookies.get("session_id")

    # 导入全局会话管理
    from main import active_sessions

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

@router.post("/api/parse-subtitle")
async def parse_subtitle(
    file: UploadFile = File(...),
    clientId: str = Form(None),
    request: Request = None,
    response: Response = None
):
    """解析字幕文件"""
    # 检查用户数量限制
    if check_user_limit():
        raise HTTPException(
            status_code=503,
            detail="当前在线用户数过多，请稍后再试。当前限制：10个用户"
        )

    # 获取或创建会话ID
    session_id = get_or_create_session_id(request, response)

    # 检查项目数量限制（每个用户最多5个项目）
    can_create = await subtitle_manager.check_project_limit(session_id, max_projects=5)
    if not can_create:
        # 自动清理旧项目
        await subtitle_manager.cleanup_old_projects_if_needed(session_id, max_projects=5)

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

        # 解析字幕文件，传入session_id
        success, error_msg, project = await subtitle_manager.parse_srt_file(
            file_content, file.filename, temp_client_id, session_id
        )

        if not success:
            raise HTTPException(status_code=400, detail=error_msg)

        # 自动保存项目到磁盘
        await subtitle_manager.save_project_to_disk(project)

        return {
            "success": True,
            "project": project.to_dict(),
            "message": f"成功解析 {project.total_segments} 条字幕"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.get("/api/subtitle/{project_id}/segments")
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


@router.put("/api/subtitle/{project_id}/segment/{segment_id}")
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


@router.post("/api/subtitle/{project_id}/segment")
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

        # 获取插入位置参数（支持新旧两种方式）
        insert_after_index = segment_data.get("insert_after_index")
        insert_after_segment_id = segment_data.get("insert_after_segment_id")

        print(f"🔥 DEBUG: 接收到的段落数据: {segment_data}")
        print(f"🔥 DEBUG: insert_after_index = {insert_after_index}")
        print(f"🔥 DEBUG: insert_after_segment_id = {insert_after_segment_id}")
        print(f"🔥 DEBUG: 当前项目段落数: {len(project.segments)}")

        # 如果有segment_id，根据ID查找索引
        if insert_after_segment_id:
            target_index = None
            for i, segment in enumerate(project.segments):
                if segment.id == insert_after_segment_id:
                    target_index = i + 1  # +1 因为add_segment期望的是插入位置
                    break

            if target_index is not None:
                print(f"🔥 DEBUG: 根据segment_id找到插入位置: {target_index}")
                project.add_segment(new_segment, target_index)
            else:
                print(f"🔥 DEBUG: 未找到目标segment_id，追加到末尾")
                project.add_segment(new_segment)
        else:
            # 使用旧的index方式
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


@router.delete("/api/subtitle/{project_id}/segment/{segment_id}")
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


@router.get("/api/subtitle/{project_id}/export-srt")
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


@router.post("/api/subtitle/{project_id}/batch-update-speaker")
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

        # 验证说话人是否有效（包括自定义角色）
        from custom_speakers import custom_speakers_manager
        valid_speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03", "SPEAKER_04", "SPEAKER_05"]
        all_valid_speakers = custom_speakers_manager.get_all_speaker_names()

        if new_speaker not in all_valid_speakers:
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
        await subtitle_manager.save_project_to_disk(project)

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