# -*- coding: utf-8 -*-
"""
批量TTS生成路由
处理项目级别的批量TTS音频生成，包含核心时间戳对齐算法
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from fastapi import APIRouter, HTTPException, Form

from config import Config
from subtitle_manager import subtitle_manager
from admin import check_user_limit, record_user_activity
from utils.logger import get_process_logger

router = APIRouter()

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

async def optimize_translation_for_audio_length(
    original_text: str,
    current_translation: str,
    target_language: str,
    current_audio_length: float,
    target_audio_length: float,
    group_id: str,
    api_key: str,
    logger=None,
    api_endpoint: str = "domestic",
    custom_terms: str = ""
) -> str:
    """优化翻译以适应目标音频长度"""
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

    # 构建翻译优化提示词（按照用户提供的格式）
    user_prompt = f"""你的任务是翻译优化，原文"{original_text_for_optimization}"当前"{target_language}"翻译"{current_translation}"，要求：
1. 保持口语化表达
2. 如果包含以下专有词汇，请按照词表翻译，词表{custom_terms}
3. 当前字符数是{current_char_count}个字，需要精简成少于{target_char_count}个字，
请直接输出新的"{target_language}"翻译如下："""

    payload = {
        "model": Config.TRANSLATION_CONFIG["model"],
        "temperature": Config.TRANSLATION_CONFIG["temperature"],
        "top_p": Config.TRANSLATION_CONFIG["top_p"],
        "messages": [
            {
                "role": "system",
                "content": "你是一个翻译优化专家，你必须严格按照指定的字符数要求进行文本缩短，不能超出范围。"
            },
            {
                "role": "user",
                "content": user_prompt
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

        # 获取系统代理设置
        import os
        proxy_url = os.environ.get('https_proxy') or os.environ.get('http_proxy')

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=Config.TRANSLATION_CONFIG["timeout"]),
                                  proxy=proxy_url) as response:
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

@router.post("/api/subtitle/{project_id}/batch-generate-tts")
async def batch_generate_tts_for_project(
    project_id: str,
    groupId: str = Form(...),
    apiKey: str = Form(...),
    model: str = Form(Config.TTS_CONFIG["default_model"]),
    language: str = Form(Config.TTS_CONFIG["default_language"]),
    voiceMapping: str = Form(...),
    clientId: str = Form(None),
    apiEndpoint: str = Form("domestic"),
    custom_terms: Optional[str] = Form("")
):
    """为项目中的所有字幕段落批量生成TTS音频（包含时间戳匹配和speed调整）"""
    # 检查用户数量限制
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

        # 使用传入的clientId或生成新的
        log_client_id = clientId if clientId else f"batch_tts_{project_id}"
        logger = get_process_logger(log_client_id)

        # 获取全局状态管理
        from api.core.global_state import global_state
        task_cancellation_flags = global_state.task_cancellation_flags

        # 清除之前的中断标志
        task_cancellation_flags[log_client_id] = False

        tts_service = TTSService(logger, api_endpoint=apiEndpoint)
        await tts_service.initialize(groupId, apiKey)

        # 创建audio_files目录
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
                    await subtitle_manager.save_project_to_disk(project)
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
                    # 确定下一步行动
                    if attempt == 0:
                        next_action = "首次TTS生成"
                    else:
                        next_action = f"TTS生成(speed={current_speed})"

                    # 优化前日志：TTS原始音频时长，去除前后静音后时长，比例ratio，是否≤1.0，是否已翻译优化，当前speed，下一步
                    await logger.info(f"段落 {i+1} [步骤{attempt + 1}] 优化前",
                                    f"原始音频: 未知ms, 去静音后: 未知ms, "
                                    f"比例: 未知, ≤1.0: 未知, "
                                    f"已翻译优化: {translation_optimization_count > 0}, 当前speed: {current_speed}, "
                                    f"下一步: {next_action}")

                    # 优先使用译文，当译文为空时使用原文
                    text_to_use = segment.translated_text if segment.translated_text else segment.text
                    is_using_translation = bool(segment.translated_text)

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

                    # 计算时长比例（无论是否成功都要计算）
                    duration_ratio = t_tts_ms / t_srt_ms if t_srt_ms > 0 else 0
                    ratio_ok = duration_ratio <= 1.0

                    # 决定下一步行动
                    if ratio_ok:
                        next_action = "成功：比例≤1.0"
                    elif duration_ratio > 1.0 and translation_optimization_count < 1 and is_using_translation:
                        next_action = "调用翻译优化"
                    elif translation_optimization_count > 0 and duration_ratio <= 1.0:
                        next_action = "成功：翻译优化后比例≤1.0"
                    elif attempt < max_retries - 1:
                        if duration_ratio > 1.0 or translation_optimization_count >= 1:
                            if current_speed < 2.0:
                                next_speed = min(current_speed + 0.2, 2.0)
                                next_action = f"提高speed={next_speed:.1f}"
                            else:
                                next_action = "失败：speed=2.0仍>1.0，置静音"
                        else:
                            next_speed = min(current_speed + 0.2, 2.0)
                            next_action = f"提高speed={next_speed:.1f}"
                    else:
                        if current_speed >= 2.0 and duration_ratio > 1.0:
                            next_action = "失败：speed=2.0仍>1.0，置静音"
                        else:
                            next_action = "继续重试至speed=2.0"

                    # 优化后日志：LLM和TTS的trace_id，TTS原始音频时长，去除前后静音后时长，比例ratio，是否≤1.0，是否已翻译优化，当前speed，下一步
                    trace_display = trace_id if trace_id else 'None'
                    await logger.info(f"段落 {i+1} [步骤{attempt + 1}] 优化后",
                                    f"Trace: {trace_display}, 原始音频: {t_tts_ms}ms, 去静音后: {t_tts_ms}ms, "
                                    f"比例: {duration_ratio:.2f}, ≤1.0: {ratio_ok}, "
                                    f"已翻译优化: {translation_optimization_count > 0}, 当前speed: {current_speed}, "
                                    f"下一步: {next_action}")

                    # 判断是否需要调整速度
                    if duration_ratio <= 1.0:
                        await logger.success(f"段落 {i+1} 时长合适", f"使用速度: {current_speed}, 比例: {duration_ratio:.2f} <= 1.0")
                        final_audio_data = audio_data
                        final_duration_ms = t_tts_ms
                        final_trace_id = trace_id
                        break

                    # 需要加速
                    if attempt < max_retries - 1:  # 还有重试机会
                        # 翻译优化成功后，如果重试的ratio<=1.0则直接成功
                        if translation_optimization_count > 0 and duration_ratio <= 1.0:
                            await logger.success(f"段落 {i+1} 翻译优化成功", f"重试后比例: {duration_ratio:.2f} <= 1.0，直接成功")
                            final_audio_data = audio_data
                            final_duration_ms = t_tts_ms
                            final_trace_id = trace_id
                            break

                        if duration_ratio > 1.0 and translation_optimization_count < 1:  # 只翻译优化一次
                            # 时长比例 > 1.0，重新翻译优化
                            await logger.warning(f"段落 {i+1} 需要翻译优化", f"时长比例: {duration_ratio:.2f} > 1.0, 优化次数: {translation_optimization_count}")

                            if is_using_translation:
                                # 使用译文，进行翻译优化
                                optimized_text = await optimize_translation_for_audio_length(
                                    original_text=segment.text,
                                    current_translation=segment.translated_text,
                                    target_language=language,
                                    current_audio_length=t_tts_ms / 1000.0,
                                    target_audio_length=t_srt_ms / 1000.0,
                                    group_id=groupId,
                                    api_key=apiKey,
                                    logger=logger, # 传递logger
                                    api_endpoint=apiEndpoint,
                                    custom_terms=custom_terms
                                )

                                if optimized_text:
                                    # 检查优化后的文本是否确实变短了
                                    original_length = len(segment.translated_text)
                                    optimized_length = len(optimized_text)

                                    if optimized_length < original_length:
                                        # 更新段落的译文
                                        segment.translated_text = optimized_text
                                        translation_optimization_count += 1
                                        await logger.info(f"段落 {i+1} 翻译优化成功", f"原长度: {original_length}, 新长度: {optimized_length}")
                                        # 翻译优化成功后，继续使用当前speed重试，看优化后的效果
                                        # 翻译优化成功后，如果重试的ratio<=1.0则直接成功，只有ratio>1.0才继续speed调整
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
                            # 时长比例 <= 1.0 或 翻译优化次数已达上限，修改speed参数
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

        # 增强的最终总结信息 - 按用户要求的格式
        await logger.info("=== 批量TTS最终总结 ===", "")
        await logger.info("总体统计", f"成功: {successful_segments}条, 失败: {failed_segments}条")

        # 失败段落的序号
        if failed_silent_segments:
            await logger.warning("失败段落序号", f"段落: {', '.join(map(str, failed_silent_segments))}")
        else:
            await logger.info("失败段落序号", "无失败段落")

        # 成功加速后的效果：段落编号: speed=X, ratio=X
        if accelerated_segments:
            await logger.info("成功加速效果", f"共 {len(accelerated_segments)} 个段落需要加速:")
            for seg in updated_segments:
                if seg.get('final_speed', 1.0) > 1.0:
                    # 获取段落序号
                    segment_obj = next((s for s in project.segments if s.id == seg['segment_id']), None)
                    if segment_obj:
                        # 计算最终比例（假设比例为音频时长/字幕时长）
                        segment_duration = seg.get('duration_ms', 0)
                        if segment_obj.start_time and segment_obj.end_time:
                            from audio_processor import SubtitleParser
                            start_seconds = SubtitleParser._time_to_seconds(segment_obj.start_time)
                            end_seconds = SubtitleParser._time_to_seconds(segment_obj.end_time)
                            subtitle_duration_ms = int((end_seconds - start_seconds) * 1000)
                            final_ratio = segment_duration / subtitle_duration_ms if subtitle_duration_ms > 0 else 0
                            await logger.info("加速段落详情",
                                            f"段落 {segment_obj.index}: speed={seg.get('final_speed', 1.0):.1f}, ratio={final_ratio:.2f}")
        else:
            await logger.info("成功加速效果", "无需加速的段落")

        # 优化类型统计
        await logger.info("优化类型统计",
                         f"正常生成: {len(normal_segments)}个, 翻译优化: {len(translation_optimized_segments)}个, "
                         f"速度优化: {len(speed_optimized_segments)}个, 失败静音: {len(failed_silent_segments)}个")

        # 详细分类展示
        if translation_optimized_segments:
            await logger.info("翻译优化段落", f"段落编号: {', '.join(map(str, translation_optimized_segments))}")

        if speed_optimized_segments:
            await logger.info("速度优化段落", f"段落编号: {', '.join(map(str, speed_optimized_segments))}")

        if normal_segments:
            await logger.info("正常生成段落", f"段落编号: {', '.join(map(str, normal_segments))}")

        # 最大加速统计
        if max_speed_segments:
            await logger.warning("最大加速段落", f"达到speed=2.0的段落: {len(max_speed_segments)}个")

        # 成功率统计
        success_rate = (successful_segments / total_segments) * 100
        await logger.info("批量TTS成功率", f"成功率: {success_rate:.1f}% ({successful_segments}/{total_segments})")

        # 处理完成时间
        await logger.info("批量TTS任务完成", f"完成时间: {datetime.now().strftime('%H:%M:%S')}, 模型: {model}, 语言: {language}")

        await logger.info("=== 批量TTS总结结束 ===", "")

        # 保存项目，确保翻译优化能够持久化
        try:
            await subtitle_manager.save_project_to_disk(project)
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