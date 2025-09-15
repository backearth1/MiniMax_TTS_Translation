# -*- coding: utf-8 -*-
"""
音频路由
处理音频拼接相关功能
"""
from fastapi import APIRouter, HTTPException, Form
from datetime import datetime
from pathlib import Path

from config import Config
from utils.logger import get_process_logger
from subtitle_manager import subtitle_manager

router = APIRouter()

@router.post("/api/subtitle/{project_id}/merge-audio")
async def merge_audio_for_project(
    project_id: str,
    clientId: str = Form(...)
):
    """合并项目中的所有音频段落，按绝对时间戳拼接输出完整音频"""
    try:
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")

        # 初始化日志
        logger = get_process_logger(f"merge_audio_{project_id}")

        await logger.info("开始音频合并", f"项目: {project.filename}, 段落数: {len(project.segments)}")

        # 检查是否有音频数据
        segments_with_audio = [seg for seg in project.segments if seg.audio_data and seg.audio_data != b'silence_placeholder']
        if not segments_with_audio:
            raise HTTPException(status_code=400, detail="没有可用的音频数据，请先生成TTS")

        await logger.info("音频数据检查", f"有音频的段落: {len(segments_with_audio)}/{len(project.segments)}")

        # 初始化音频处理器
        from audio_processor import AudioProcessor
        audio_processor = AudioProcessor(logger)

        # 准备音频段落数据 - 按绝对时间戳拼接
        audio_segments = []
        for segment in project.segments:
            if segment.audio_data and segment.audio_data != b'silence_placeholder':
                # 计算绝对时间戳（毫秒）
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

        # 构建音频时间轴 - 按绝对时间戳拼接
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
        logger = get_process_logger(f"merge_audio_{project_id}")
        await logger.error("❌ 音频合并失败", str(e))
        raise HTTPException(status_code=500, detail=f"音频合并失败: {str(e)}")