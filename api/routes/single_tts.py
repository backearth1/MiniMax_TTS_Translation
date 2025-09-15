# -*- coding: utf-8 -*-
"""
单段落TTS生成路由
处理单个字幕段落的TTS音频生成，简单的时长检查机制
"""
from fastapi import APIRouter, HTTPException, Form
from datetime import datetime
from pathlib import Path
import json

from config import Config
from subtitle_manager import subtitle_manager
from utils.logger import get_process_logger

router = APIRouter()

@router.post("/api/subtitle/{project_id}/segment/{segment_id}/generate-tts")
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
        logger = get_process_logger(f"tts_{project_id}_{segment_id}")
        await logger.error("❌ TTS生成失败", str(e))
        raise HTTPException(status_code=500, detail=f"TTS生成失败: {str(e)}")