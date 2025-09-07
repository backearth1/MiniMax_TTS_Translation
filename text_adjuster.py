#!/usr/bin/env python3
"""
文本长度调整模块
基于MiniMax翻译API的文本缩短/加长功能
"""
import asyncio
import json
import uuid
import aiohttp
from datetime import datetime
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, Form
from utils.logger import get_process_logger
from config import Config, get_proxy_settings
from subtitle_manager import subtitle_manager

# 获取API端点的函数
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

# 创建路由器
router = APIRouter()

async def adjust_text_length(
    original_text: str,
    current_text: str, 
    target_language: str,
    adjustment_type: str,  # "shorten" 或 "lengthen"
    adjustment_ratio: float,  # 调整比例，如0.8表示缩短20%，1.2表示加长20%
    group_id: str,
    api_key: str,
    logger=None,
    api_endpoint: str = "domestic"
) -> Optional[str]:
    """
    调整文本长度
    
    Args:
        original_text: 原文
        current_text: 当前译文 
        target_language: 目标语言
        adjustment_type: 调整类型 ("shorten" 或 "lengthen")
        adjustment_ratio: 调整比例
        group_id: API Group ID
        api_key: API Key
        logger: 日志器
        api_endpoint: API端点类型
        
    Returns:
        调整后的文本，失败时返回None
    """
    
    # 生成trace_id
    trace_id = str(uuid.uuid4())
    
    # 计算当前字符数和目标字符数
    current_char_count = len(current_text)
    target_char_count = int(current_char_count * adjustment_ratio)
    
    # 构建提示词
    if adjustment_type == "shorten":
        task_description = f"缩短文本，保持核心意思，使用更简洁的表达方式"
        length_instruction = f"需要从当前{current_char_count}个字精简到约{target_char_count}个字（减少约{int((1-adjustment_ratio)*100)}%）"
    else:  # lengthen
        task_description = f"扩展文本，保持原意的基础上增加细节或使用更丰富的表达"
        length_instruction = f"需要从当前{current_char_count}个字扩展到约{target_char_count}个字（增加约{int((adjustment_ratio-1)*100)}%）"
    
    # 使用配置的翻译API端点
    base_url = get_api_endpoint("translation", api_endpoint)
    url = f"{base_url}?GroupId={group_id}"
    
    # 处理原文为空的情况
    original_context = f"，原文参考：\"{original_text}\"" if original_text.strip() else ""
    
    payload = {
        "model": Config.TRANSLATION_CONFIG["model"],
        "temperature": Config.TRANSLATION_CONFIG["temperature"], 
        "top_p": Config.TRANSLATION_CONFIG["top_p"],
        "messages": [
            {
                "role": "system",
                "content": "你是一个专业的文本调整专家，擅长在保持原意的基础上调整文本长度。请确保调整后的文本自然流畅，适合口语表达。"
            },
            {
                "role": "user", 
                "content": f"请{task_description}。当前{target_language}文本：\"{current_text}\"{original_context}。{length_instruction}。请直接输出调整后的{target_language}文本："
            }
        ],
    }
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        if logger:
            await logger.info(f"调用文本{adjustment_type}API", f"目标语言: {target_language}, 调整比例: {adjustment_ratio}, Trace: {trace_id}")
            await logger.info("发送API请求", f"当前长度: {current_char_count}字 → 目标长度: {target_char_count}字")
        
        # 获取代理设置
        proxy_settings = get_proxy_settings()
        
        # 创建连接器，支持代理
        connector = None
        if proxy_settings:
            connector = aiohttp.TCPConnector()
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=Config.TRANSLATION_CONFIG["timeout"]),
                                  proxy=proxy_settings.get('https') if proxy_settings else None) as response:
                response_data = await response.json()
                
                # 尝试从响应头或响应体中获取trace_id
                api_trace_id = response.headers.get('X-Trace-Id') or response.headers.get('Trace-Id') or trace_id
                
                # 如果响应体中有trace_id，也尝试获取
                if isinstance(response_data, dict) and 'trace_id' in response_data:
                    api_trace_id = response_data['trace_id']
                elif isinstance(response_data, dict) and 'traceId' in response_data:
                    api_trace_id = response_data['traceId']
                
                if logger:
                    await logger.info(f"文本{adjustment_type}API调用成功", f"Trace: {api_trace_id}")
                
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    adjusted_text = response_data['choices'][0]['message']['content'].strip()
                    
                    # 验证调整结果
                    adjusted_length = len(adjusted_text)
                    actual_ratio = adjusted_length / current_char_count
                    
                    if logger:
                        await logger.success(f"文本{adjustment_type}成功", 
                                           f"长度变化: {current_char_count} → {adjusted_length} 字 (比例: {actual_ratio:.2f})")
                        await logger.info("调整结果", f"新文本: {adjusted_text}")
                    
                    return adjusted_text
                else:
                    if logger:
                        await logger.error(f"文本{adjustment_type}API响应格式异常", f"响应: {response_data}, Trace: {api_trace_id}")
                    return None
                    
    except Exception as e:
        if logger:
            await logger.error(f"文本{adjustment_type}API调用失败", f"错误: {str(e)}, Trace: {trace_id}")
        return None

@router.post("/api/subtitle/{project_id}/segment/{segment_id}/adjust-text")
async def adjust_segment_text(
    project_id: str,
    segment_id: str,
    adjustment_type: str = Form(...),  # "shorten" 或 "lengthen"
    groupId: str = Form(...),
    apiKey: str = Form(...),
    target_language: str = Form(...),
    apiEndpoint: str = Form("domestic")
):
    """
    调整字幕段落文本长度
    
    Args:
        project_id: 项目ID
        segment_id: 段落ID
        adjustment_type: 调整类型 ("shorten" 或 "lengthen")
        groupId: API Group ID
        apiKey: API Key
        target_language: 目标语言
        apiEndpoint: API端点类型
    """
    try:
        # 验证调整类型
        if adjustment_type not in ["shorten", "lengthen"]:
            raise HTTPException(status_code=400, detail="无效的调整类型，必须是 'shorten' 或 'lengthen'")
        
        # 获取项目
        project = subtitle_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取段落
        segment = project.get_segment(segment_id)
        if not segment:
            raise HTTPException(status_code=404, detail="段落不存在")
        
        # 检查是否有译文
        if not segment.translated_text:
            raise HTTPException(status_code=400, detail="段落没有译文，无法调整长度")
        
        # 设置调整比例
        adjustment_ratio = 0.8 if adjustment_type == "shorten" else 1.2
        
        # 创建日志器
        logger = get_process_logger(f"text_adjust_{segment_id}")
        
        await logger.info(f"开始文本长度调整", 
                         f"段落ID: {segment_id}, 类型: {adjustment_type}, 当前长度: {len(segment.translated_text)}字")
        
        # 调用文本调整API
        adjusted_text = await adjust_text_length(
            original_text=segment.text,
            current_text=segment.translated_text,
            target_language=target_language,
            adjustment_type=adjustment_type,
            adjustment_ratio=adjustment_ratio,
            group_id=groupId,
            api_key=apiKey,
            logger=logger,
            api_endpoint=apiEndpoint
        )
        
        if adjusted_text and adjusted_text != segment.translated_text:
            # 备份原译文
            original_translation = segment.translated_text
            
            # 更新段落译文
            segment.translated_text = adjusted_text
            segment.updated_at = datetime.now().isoformat()
            
            # 保存项目
            await subtitle_manager.save_project_to_disk(project)
            
            # 计算长度变化
            original_length = len(original_translation)
            new_length = len(adjusted_text)
            change_ratio = new_length / original_length
            
            await logger.success("文本调整完成", 
                               f"长度变化: {original_length} → {new_length} 字 (变化: {change_ratio:.2f}倍)")
            
            return {
                "success": True,
                "message": f"文本{adjustment_type}成功",
                "segment_id": segment_id,
                "adjustment_type": adjustment_type,
                "original_text": original_translation,
                "adjusted_text": adjusted_text,
                "length_change": {
                    "original_length": original_length,
                    "new_length": new_length,
                    "change_ratio": round(change_ratio, 2),
                    "change_percentage": round((change_ratio - 1) * 100, 1)
                }
            }
        else:
            await logger.error("文本调整失败", "API返回空结果或结果与原文相同")
            raise HTTPException(status_code=500, detail="文本调整失败")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文本调整失败: {str(e)}")

@router.get("/api/text-adjuster/config")
async def get_text_adjuster_config():
    """获取文本调整器配置信息"""
    return {
        "adjustment_types": [
            {
                "type": "shorten",
                "name": "缩短",
                "description": "缩短文本约20%，使表达更简洁",
                "ratio": 0.8
            },
            {
                "type": "lengthen", 
                "name": "加长",
                "description": "加长文本约20%，使表达更丰富",
                "ratio": 1.2
            }
        ],
        "supported_languages": Config.TRANSLATION_CONFIG["supported_target_languages"]
    }