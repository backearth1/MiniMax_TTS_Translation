# -*- coding: utf-8 -*-
"""
翻译路由
处理批量翻译等翻译相关功能
"""
from fastapi import APIRouter, HTTPException, Form
from typing import Optional
import asyncio
import aiohttp
import uuid

from config import Config
from utils.logger import get_process_logger
from subtitle_manager import subtitle_manager

router = APIRouter()

# 全局任务管理
from api.core.global_state import global_state

def get_api_endpoint(api_type: str, endpoint_type: str = "domestic") -> str:
    """获取API端点URL"""
    return Config.API_ENDPOINTS[api_type][endpoint_type]

async def translate_text_with_minimax(text: str, target_language: str, group_id: str, api_key: str, logger=None, api_endpoint: str = "domestic") -> str:
    """使用MiniMax API翻译文本"""
    # 获取动态配置
    try:
        from admin_modules.system_manager import system_manager
        batch_config = system_manager.get_batch_api_config()
        timeout_seconds = batch_config.translation_timeout_seconds
        max_retries = batch_config.translation_max_retries
    except:
        # 回退到默认配置
        timeout_seconds = Config.TRANSLATION_CONFIG["timeout"]
        max_retries = Config.TRANSLATION_CONFIG["max_retries"]

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

        # 获取系统代理设置
        import os
        proxy_url = os.environ.get('https_proxy') or os.environ.get('http_proxy')

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                                  proxy=proxy_url) as response:
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

@router.post("/api/subtitle/{project_id}/batch-translate")
async def batch_translate_project(
    project_id: str,
    groupId: str = Form(...),
    apiKey: str = Form(...),
    target_language: str = Form(...),
    clientId: Optional[str] = Form(None),
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
        task_cancellation_flags = global_state.get_task_cancellation_flags()
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
                    await subtitle_manager.save_project_to_disk(project)
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

            # 添加延迟避免API限制 - 使用动态配置
            if i < total_segments:
                try:
                    from admin_modules.system_manager import system_manager
                    delay = system_manager.get_batch_api_config().translation_delay_seconds
                except:
                    delay = Config.TRANSLATION_CONFIG["translation_delay"]  # 回退到默认值
                await asyncio.sleep(delay)

        # 保存项目
        try:
            await subtitle_manager.save_project_to_disk(project)
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

        from datetime import datetime
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