"""
多人配音音频处理器
"""
import asyncio
import json
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiofiles
import requests
from pydub import AudioSegment
import numpy as np
import time
import io

from config import Config
from utils.logger import ProcessLogger, LogLevel

class SubtitleParser:
    """字幕文件解析器"""
    
    @staticmethod
    def parse_srt(content: str) -> List[Dict]:
        """解析 SRT 格式字幕，支持三种格式：
        1. 有序号格式：序号 + 时间戳 + 文本
        2. 无序号格式：时间戳 + 文本
        3. 完整标注格式：序号 + [时间戳] SPEAKER [emotion: xxx] + 文本
        """
        segments = []
        
        try:
            # 预处理内容：统一换行符，去除多余空白
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            content = re.sub(r'\n\s*\n', '\n\n', content)  # 规范化空行
            
            # 使用更健壮的解析方法：按空行分割字幕块
            subtitle_blocks = re.split(r'\n\s*\n', content.strip())
            
            for i, block in enumerate(subtitle_blocks):
                if not block.strip():
                    continue
                    
                lines = block.strip().split('\n')
                if len(lines) < 2:  # 至少需要时间戳和内容
                    continue
                
                try:
                    # 默认值
                    index = i + 1  # 默认序号
                    speaker = "SPEAKER_00"  # 默认说话人
                    emotion = "neutral"     # 默认情绪
                    
                    # 检测格式类型
                    line_index = 0
                    
                    # 检查第一行是否为序号
                    if re.match(r'^\d+$', lines[0].strip()):
                        # 有序号格式
                        index = int(lines[0].strip())
                        line_index = 1
                    
                    # 解析时间戳行
                    if line_index >= len(lines):
                        continue
                    
                    time_line = lines[line_index].strip()
                    
                    # 格式1: 完整标注格式 [00:00:06.879 --> 00:00:11.039] SPEAKER_00 [emotion: happy]
                    extended_time_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(SPEAKER_\d+)?\s*(?:\[emotion:\s*(\w+)\])?', time_line)
                    
                    if extended_time_match:
                        # 完整标注格式
                        start_time, end_time, extracted_speaker, extracted_emotion = extended_time_match.groups()
                        if extracted_speaker:
                            speaker = extracted_speaker
                        if extracted_emotion:
                            emotion = extracted_emotion
                    else:
                        # 标准时间戳格式: 00:00:06,879 --> 00:00:11,039 或 00:00:06.879 --> 00:00:11.039
                        time_match = re.match(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})', time_line)
                        
                        if not time_match:
                            # 尝试方括号格式: [00:00:06.879 --> 00:00:11.039]
                            time_match = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\]', time_line)
                        
                        if not time_match:
                            continue
                            
                        start_time, end_time = time_match.groups()
                    
                    # 标准化时间格式：统一使用逗号作为毫秒分隔符
                    start_time = start_time.replace('.', ',')
                    end_time = end_time.replace('.', ',')
                    
                    # 解析文本内容（可能有多行）
                    text_lines = lines[line_index + 1:]
                    text = ' '.join(line.strip() for line in text_lines if line.strip())
                    
                    if text:  # 只处理非空内容
                        segments.append({
                            'index': index,
                            'start': start_time,
                            'end': end_time,
                            'text': text,
                            'speaker': speaker,
                            'emotion': emotion
                        })
                        
                except (ValueError, IndexError) as e:
                    # 跳过格式错误的字幕块
                    continue
            
            return segments
            
        except Exception as e:
            # 如果新方法失败，回退到原来的正则表达式方法
            pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\n\s*\d+\s*\n|\Z)'
            matches = re.findall(pattern, content, re.DOTALL)
            
            for match in matches:
                index, start_time, end_time, text = match
                
                # 清理文本内容
                text = text.strip().replace('\n', ' ')
                
                if text:  # 只处理非空内容
                    segments.append({
                        'index': int(index),
                        'start': start_time,
                        'end': end_time,
                        'text': text,
                        'speaker': "SPEAKER_00",
                        'emotion': "neutral"
                    })
            
            return segments
    
    @staticmethod
    def _extract_speaker(text: str) -> str:
        """从文本中提取说话人标识"""
        # 查找 SPEAKER_XX 模式
        speaker_match = re.search(r'(SPEAKER_\d+)', text)
        if speaker_match:
            return speaker_match.group(1)
        
        # 默认说话人
        return "SPEAKER_00"
    
    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        """将时间戳转换为秒数"""
        h, m, s = time_str.split(':')
        s, ms = s.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

class TTSService:
    """TTS 服务调用器"""
    
    def __init__(self, logger: ProcessLogger, group_id: str = None, api_key: str = None, api_endpoint: str = "domestic"):
        self.logger = logger
        self.session = None
        self.group_id = group_id
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self._last_request_time = 0  # 添加请求时间控制
        self._request_interval = 1.0  # 请求间隔1秒
        
    async def initialize(self, group_id: str = None, api_key: str = None):
        """初始化 TTS 服务"""
        self.group_id = group_id
        self.api_key = api_key
        # 这里可以初始化 TTS API 连接
        await self.logger.info("初始化 TTS 服务", f"Group ID: {group_id[:8] if group_id else 'None'}***")
        
    async def generate_audio_with_info(
        self, 
        text: str, 
        voice: str, 
        model: str = "speech-02-hd",
        language: str = "auto",
        speed: float = 1.0,
        emotion: str = "neutral"
    ) -> Dict:
        """
        生成语音音频并返回详细信息
        
        Returns:
            Dict containing 'audio_data' and 'duration_ms'
        """
        # 添加请求间隔控制，避免频率限制
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._request_interval:
            wait_time = self._request_interval - time_since_last
            await self.logger.info("请求间隔控制", f"等待 {wait_time:.1f} 秒避免频率限制")
            await asyncio.sleep(wait_time)
        
        self._last_request_time = time.time()
        
        await self.logger.info(f"生成语音", f"文本: {text[:30]}..., 语音: {voice}, 速度: {speed}")
        
        try:
            # 检查API配置
            if self.group_id and self.api_key:
                await self.logger.info("调用MiniMax API", f"Group ID: {self.group_id[:8]}***, 文本长度: {len(text)} 字符")
                
                # 根据配置选择API端点
                api_url = Config.API_ENDPOINTS["tts"][self.api_endpoint]
                await self.logger.info("使用API端点", f"端点类型: {self.api_endpoint}, URL: {api_url}")
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                # 验证emotion参数，只传递支持的emotion
                supported_emotions = ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm"]
                voice_setting = {
                    "voice_id": voice,
                    "speed": speed
                }
                
                # 只有当emotion在支持列表中且不是"auto"时才添加到voice_setting中
                if emotion and emotion.lower() in supported_emotions and emotion.lower() != "auto":
                    voice_setting["emotion"] = emotion.lower()
                    await self.logger.info("使用情绪", f"情绪: {emotion.lower()}")
                else:
                    await self.logger.info("跳过情绪参数", f"不支持的emotion或auto: {emotion}")
                
                api_data = {
                    "group_id": self.group_id,
                    "text": text,
                    "model": model,
                    "voice_setting": voice_setting,
                    "audio_setting": {
                        "sample_rate": 32000,
                        "bitrate": 128000,
                        "format": "mp3"
                    },
                    "language_boost": language,
                    "output_format": "url"
                }
                
                await self.logger.info("发送API请求", f"URL: {api_url}, 模型: {model}, 语音设置: {api_data['voice_setting']}, Emotion: {emotion}")
                
                # 添加重试逻辑处理rate limit
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        # 如果不是第一次请求，添加延迟避免rate limit
                        if retry > 0:
                            delay = 2 ** retry  # 指数退避: 2s, 4s, 8s
                            await self.logger.info("等待重试", f"延迟 {delay} 秒避免频率限制")
                            await asyncio.sleep(delay)
                        
                        # 发送真实的HTTP请求
                        api_response = None
                        try:
                            # 优先使用aiohttp进行异步请求
                            try:
                                import aiohttp
                                
                                timeout = aiohttp.ClientTimeout(total=30)  # 30秒超时
                                
                                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                                    async with session.post(api_url, json=api_data) as response:
                                        response_text = await response.text()
                                        
                                        if response.status == 200:
                                            api_response = await response.json()
                                            trace_id = response.headers.get("Trace-Id", "")
                                            await self.logger.success("MiniMax API调用成功", f"状态码: {response.status}, Trace-ID: {trace_id}")
                                        else:
                                            await self.logger.error("MiniMax API调用失败", f"状态码: {response.status}, 响应: {response_text[:200]}...")
                                            raise Exception(f"API错误: {response.status} - {response_text}")
                                            
                            except ImportError:
                                await self.logger.info("使用requests库", "aiohttp未安装，使用同步请求")
                                
                                # 使用requests库的同步请求
                                import requests
                                import json
                                
                                response = requests.post(
                                    api_url, 
                                    json=api_data, 
                                    headers=headers, 
                                    timeout=30
                                )
                                
                                if response.status_code == 200:
                                    api_response = response.json()
                                    trace_id = response.headers.get("Trace-Id", "")
                                    await self.logger.success("MiniMax API调用成功", f"状态码: {response.status_code}, Trace-ID: {trace_id}")
                                else:
                                    await self.logger.error("MiniMax API调用失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}...")
                                    raise Exception(f"API错误: {response.status_code} - {response.text}")
                            
                            # 解析API响应
                            if api_response.get("base_resp", {}).get("status_code") == 0:
                                audio_url = api_response["data"]["audio"]
                                api_audio_length_ms = api_response["extra_info"]["audio_length"]
                                
                                await self.logger.success("API响应解析成功", f"音频URL获取成功, API报告时长: {api_audio_length_ms}ms")
                                
                                # 下载音频文件并处理（去除静音）
                                raw_audio_data, _ = await self._download_audio_from_url(audio_url, api_audio_length_ms)
                                
                                if raw_audio_data:
                                    processed_audio_data, actual_duration_ms = await self._process_audio_remove_silence(raw_audio_data)
                                    
                                    await self.logger.success(f"音频处理完成", f"实际语音时长: {actual_duration_ms}ms, 处理后文件大小: {len(processed_audio_data)} bytes")
                                    
                                    return {
                                        'audio_data': processed_audio_data,  # 返回处理后的音频数据
                                        'duration_ms': actual_duration_ms,  # 使用处理后的实际时长
                                        'trace_id': trace_id,
                                        'audio_url': audio_url,  # 保留原始URL用于调试
                                        'extra_info': {
                                            **api_response['extra_info'],
                                            'actual_audio_length': actual_duration_ms,
                                            'api_audio_length': api_audio_length_ms
                                        }
                                    }
                                else:
                                    await self.logger.error("音频下载失败", f"URL: {audio_url}")
                                    # 下载失败时返回None，让调用方处理
                                    return {
                                        'audio_data': None,
                                        'duration_ms': 0,
                                        'trace_id': trace_id,
                                        'audio_url': audio_url,
                                        'extra_info': {
                                            'error': 'audio_download_failed',
                                            'api_audio_length': api_audio_length_ms
                                        }
                                    }
                            else:
                                error_msg = api_response.get("base_resp", {}).get("status_msg", "未知错误")
                                
                                # 检查是否是rate limit错误
                                if "rate limit" in error_msg.lower():
                                    await self.logger.warning("频率限制", f"第{retry+1}次尝试遇到频率限制")
                                    if retry < max_retries - 1:
                                        continue  # 继续重试
                                    else:
                                        await self.logger.error("达到最大重试次数", "频率限制无法解决，使用备用音频")
                                        break
                                else:
                                    await self.logger.error("API返回错误", f"错误信息: {error_msg}")
                                    raise Exception(f"API返回错误: {error_msg}")
                                    
                        except Exception as api_error:
                            error_str = str(api_error)
                            if "rate limit" in error_str.lower() and retry < max_retries - 1:
                                await self.logger.warning("API请求遇到频率限制", f"第{retry+1}次尝试失败，准备重试")
                                continue
                            else:
                                await self.logger.error("API请求异常", error_str)
                                break
                    
                    except Exception as retry_error:
                        await self.logger.error("重试过程异常", str(retry_error))
                        break
                
                # 所有重试都失败，回退到模拟音频
                await self.logger.warning("API调用最终失败", "使用备用静音音频")
                duration_ms = int(max(len(text) * 80, 300) / speed)
                audio_data = await self._generate_mock_audio(duration_ms)
                
                return {
                    'audio_data': audio_data,
                    'duration_ms': duration_ms,
                    'audio_url': '',  # fallback情况下没有OSS URL
                    'trace_id': '',  # API失败时不显示trace_id
                    'extra_info': {
                        'audio_length': duration_ms,
                        'word_count': len(text),
                        'usage_characters': len(text),
                        'fallback': True
                    }
                }
                
            else:
                await self.logger.warning("缺少API配置", "使用模拟音频")
                # 生成基于文本长度的模拟音频
                duration_ms = int(max(len(text) * 80, 300) / speed)
                audio_data = await self._generate_mock_audio(duration_ms)
                
                return {
                    'audio_data': audio_data,
                    'duration_ms': duration_ms,
                    'audio_url': '',  # 模拟音频没有OSS URL
                    'trace_id': '',  # 缺少API配置时不显示trace_id
                    'extra_info': {
                        'audio_length': duration_ms,
                        'word_count': len(text),
                        'usage_characters': len(text)
                    }
                }
            
        except Exception as e:
            await self.logger.error(f"TTS 生成失败", str(e))
            # 返回错误时的默认数据
            duration_ms = 1000  # 1秒
            return {
                'audio_data': await self._generate_mock_audio(duration_ms),
                'duration_ms': duration_ms,
                'audio_url': '',  # 错误情况下没有OSS URL
                'trace_id': '',  # 异常情况下不显示trace_id
                'extra_info': {'audio_length': duration_ms, 'error': str(e)}
            }
        
    async def generate_audio(
        self, 
        text: str, 
        voice: str, 
        model: str = "speech-02-hd",
        language: str = "auto",
        speed: float = 1.0
    ) -> bytes:
        """
        生成语音音频（保持兼容性）
        """
        result = await self.generate_audio_with_info(text, voice, model, language, speed)
        return result['audio_data']
    
    async def _download_audio_from_url(self, audio_url: str, expected_duration_ms: int) -> Tuple[bytes, int]:
        """
        从URL下载音频文件，并分析实际音频时长
        
        Args:
            audio_url: 音频文件的URL
            expected_duration_ms: API返回的期望时长（包含静音）
            
        Returns:
            Tuple[音频文件的二进制数据, 去除静音后的实际时长(ms)]
        """
        await self.logger.info("下载音频", f"URL: {audio_url[:50]}...")
        
        # 重试机制
        max_retries = 3
        for retry_count in range(max_retries):
            try:
                # 设置请求头，模拟浏览器访问
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'audio/mpeg, audio/*, */*',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'audio',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'cross-site'
                }
                
                # 尝试使用aiohttp进行异步下载
                audio_data = None
                try:
                    import aiohttp
                    
                    timeout = aiohttp.ClientTimeout(total=60)  # 增加超时时间到60秒
                    
                    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                        await self.logger.info("使用aiohttp下载", f"重试 {retry_count + 1}/{max_retries}")
                        
                        async with session.get(audio_url) as response:
                            await self.logger.info("HTTP响应", f"状态码: {response.status}")
                            
                            if response.status == 200:
                                audio_data = await response.read()
                                await self.logger.success("音频下载成功", f"文件大小: {len(audio_data)} bytes")
                            else:
                                await self.logger.warning("下载失败", f"HTTP状态码: {response.status}")
                                # 获取错误响应内容
                                error_text = await response.text()
                                await self.logger.info("错误详情", f"响应: {error_text[:200]}...")
                                raise Exception(f"HTTP错误: {response.status}")
                                
                except ImportError:
                    await self.logger.info("aiohttp不可用", "使用requests库下载")
                    
                    # 使用requests进行同步下载
                    import requests
                    
                    response = requests.get(audio_url, headers=headers, timeout=60, stream=True)
                    await self.logger.info("HTTP响应", f"状态码: {response.status_code}")
                    
                    if response.status_code == 200:
                        audio_data = response.content
                        await self.logger.success("音频下载成功", f"文件大小: {len(audio_data)} bytes")
                    else:
                        await self.logger.warning("下载失败", f"HTTP状态码: {response.status_code}")
                        await self.logger.info("错误详情", f"响应: {response.text[:200]}...")
                        raise Exception(f"HTTP错误: {response.status_code}")
                
                # 分析音频，去除静音获取真实时长
                if audio_data:
                    await self.logger.info("分析音频", "检测并去除开头结尾静音")
                    actual_duration_ms = await self._analyze_audio_duration(audio_data)
                    await self.logger.success("音频分析完成", f"原始时长: {expected_duration_ms}ms, 实际语音时长: {actual_duration_ms}ms")
                    return audio_data, actual_duration_ms
                else:
                    raise Exception("音频数据为空")
                    
            except Exception as download_error:
                await self.logger.error("音频下载失败", f"重试 {retry_count + 1}/{max_retries}, 错误: {str(download_error)}")
                
                if retry_count < max_retries - 1:
                    # 还有重试机会，等待后重试
                    import asyncio
                    await asyncio.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    # 最后一次重试失败
                    await self.logger.error("音频下载最终失败", f"已重试 {max_retries} 次，返回None")
                    return None, 0
        
        # 不应该到达这里，但为了安全起见
        return None, 0
    
    async def _analyze_audio_duration(self, audio_data: bytes) -> int:
        """
        分析音频数据，去除开头和结尾的静音，返回实际语音时长
        
        Args:
            audio_data: 音频文件的二进制数据
            
        Returns:
            去除静音后的实际语音时长(毫秒)
        """
        try:
            # 将字节数据转换为AudioSegment
            audio_io = io.BytesIO(audio_data)
            audio = AudioSegment.from_file(audio_io, format="mp3")
            
            await self.logger.info("音频属性", f"原始时长: {len(audio)}ms, 采样率: {audio.frame_rate}Hz")
            
            # 静音检测阈值（dBFS）
            silence_threshold = -50  # 低于-50dB认为是静音
            min_silence_len = 100    # 最小静音长度100ms
            
            # 去除开头的静音
            start_pos = 0
            chunk_size = 50  # 每次检查50ms
            
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i + chunk_size]
                if len(chunk) > 0 and chunk.dBFS > silence_threshold:
                    start_pos = i
                    break
            
            # 去除结尾的静音  
            end_pos = len(audio)
            for i in range(len(audio) - chunk_size, 0, -chunk_size):
                chunk = audio[i:i + chunk_size]
                if len(chunk) > 0 and chunk.dBFS > silence_threshold:
                    end_pos = i + chunk_size
                    break
            
            # 计算实际语音时长
            actual_duration_ms = max(end_pos - start_pos, 100)  # 最少100ms
            
            await self.logger.info("静音检测结果", 
                f"开头静音: {start_pos}ms, 结尾静音: {len(audio) - end_pos}ms, 实际语音: {actual_duration_ms}ms")
            
            return actual_duration_ms
            
        except Exception as e:
            await self.logger.warning("音频分析失败", f"错误: {str(e)}, 使用预估时长")
            # 分析失败时，返回基于文件大小的估算时长
            # MP3文件大约128kbps，计算估算时长
            estimated_duration = int(len(audio_data) * 8 / 128)  # 秒
            return max(estimated_duration * 1000, 500)  # 转为毫秒，最少500ms

    async def _process_audio_remove_silence(self, audio_data: bytes) -> Tuple[bytes, int]:
        """
        处理音频数据，去除开头和结尾的静音，返回处理后的音频和实际时长
        
        Args:
            audio_data: 音频文件的二进制数据
            
        Returns:
            Tuple[处理后的音频数据, 实际语音时长(毫秒)]
        """
        try:
            # 将字节数据转换为AudioSegment
            audio_io = io.BytesIO(audio_data)
            audio = AudioSegment.from_file(audio_io, format="mp3")
            
            await self.logger.info("音频属性", f"原始时长: {len(audio)}ms, 采样率: {audio.frame_rate}Hz")
            
            # 静音检测阈值（dBFS）
            silence_threshold = -50  # 低于-50dB认为是静音
            chunk_size = 50  # 每次检查50ms
            
            # 去除开头的静音
            start_pos = 0
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i + chunk_size]
                if len(chunk) > 0 and chunk.dBFS > silence_threshold:
                    start_pos = i
                    break
            
            # 去除结尾的静音  
            end_pos = len(audio)
            for i in range(len(audio) - chunk_size, 0, -chunk_size):
                chunk = audio[i:i + chunk_size]
                if len(chunk) > 0 and chunk.dBFS > silence_threshold:
                    end_pos = i + chunk_size
                    break
            
            # 提取实际语音部分
            processed_audio = audio[start_pos:end_pos]
            
            # 确保最少100ms
            if len(processed_audio) < 100:
                processed_audio = audio[:100]
            
            # 导出处理后的音频
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
                
            try:
                processed_audio.export(temp_path, format="mp3")
                
                # 读取处理后的音频数据
                async with aiofiles.open(temp_path, "rb") as f:
                    processed_audio_data = await f.read()
                
                actual_duration_ms = len(processed_audio)
                
                await self.logger.info("音频处理完成", 
                    f"开头静音: {start_pos}ms, 结尾静音: {len(audio) - end_pos}ms, 实际语音: {actual_duration_ms}ms")
                
                return processed_audio_data, actual_duration_ms
                
            finally:
                # 清理临时文件
                try:
                    if Path(temp_path).exists():
                        Path(temp_path).unlink()
                except Exception:
                    pass
                    
        except Exception as e:
            await self.logger.warning("音频处理失败", f"错误: {str(e)}, 返回原始音频")
            # 处理失败时，返回原始音频和估算时长
            estimated_duration = int(len(audio_data) * 8 / 128)  # 秒
            actual_duration_ms = max(estimated_duration * 1000, 500)  # 转为毫秒，最少500ms
            return audio_data, actual_duration_ms
    
    async def _generate_mock_audio(self, duration_ms: int) -> bytes:
        """
        生成模拟音频数据（临时实现）
        在实际环境中，这个方法应该被移除，直接使用下载的真实音频
        """
        try:
            # 生成指定时长的静音音频
            silent_audio = AudioSegment.silent(duration=duration_ms)
            
            # 导出为 MP3 格式
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
                
            try:
                silent_audio.export(temp_path, format="mp3")
                
                # 读取文件
                async with aiofiles.open(temp_path, "rb") as f:
                    audio_data = await f.read()
                
            finally:
                # 清理临时文件
                try:
                    if Path(temp_path).exists():
                        Path(temp_path).unlink()
                except Exception:
                    pass
                    
            return audio_data
            
        except Exception as e:
            # 如果无法生成音频，返回最小的有效 MP3 头部
            # 这是一个包含有效 MP3 头的最小字节序列
            return b'\xff\xfb\x90\x00' + b'\x00' * 100

class AudioProcessor:
    """音频处理器"""
    
    def __init__(self, logger, group_id: str = None, api_key: str = None, api_endpoint: str = "domestic"):
        """
        初始化音频处理器
        
        Args:
            logger: 日志记录器
            group_id: MiniMax Group ID
            api_key: MiniMax API Key
            api_endpoint: API端点选择 ("domestic" 或 "overseas")
        """
        self.logger = logger
        self.group_id = group_id
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.tts_service = TTSService(logger, group_id, api_key, api_endpoint)
        self._last_request_time = 0  # 添加请求时间控制
        self._request_interval = 1.0  # 请求间隔1秒
        
    async def initialize(self, group_id: str = None, api_key: str = None, api_endpoint: str = None):
        """初始化音频处理器"""
        if api_endpoint:
            self.api_endpoint = api_endpoint
            self.tts_service.api_endpoint = api_endpoint
        await self.tts_service.initialize(group_id, api_key)
        await self.logger.info("音频处理器初始化完成", f"使用API端点: {self.api_endpoint}")
        
    async def process_subtitle_file(
        self,
        file_content: str,
        voice_mapping: Dict[str, str],
        output_path: Path,
        model: str = "speech-02-hd",
        language: str = "auto"
    ) -> Dict:
        """
        处理字幕文件并生成多人配音
        
        Args:
            file_content: 字幕文件内容
            voice_mapping: 说话人到语音的映射
            output_path: 输出文件路径
            model: TTS 模型
            language: 语言设置
            
        Returns:
            处理结果
        """
        try:
            await self.logger.info("开始处理字幕文件")
            
            # 1. 解析字幕
            await self.logger.info("解析字幕文件", f"文件大小: {len(file_content)} 字符")
            
            segments = SubtitleParser.parse_srt(file_content)
            
            if not segments:
                await self.logger.error("字幕解析失败", "未找到有效的字幕内容，请检查文件格式")
                raise ValueError("未找到有效的字幕内容")
                
            await self.logger.success(f"解析完成", f"共找到 {len(segments)} 个字幕段落")
            
            # 显示解析的字幕信息
            for i, segment in enumerate(segments[:3]):  # 只显示前3个段落
                await self.logger.info(f"段落 {i+1}", f"{segment['start']} -> {segment['end']}: {segment['text'][:50]}...")
            
            if len(segments) > 3:
                await self.logger.info("更多段落", f"还有 {len(segments) - 3} 个段落...")
            
            # 2. 按说话人分组
            speaker_groups = self._group_by_speaker(segments)
            await self.logger.info(f"识别到 {len(speaker_groups)} 个说话人")
            
            # 3. 处理每个音频段落，包含重试逻辑
            audio_segments = []
            speed_stats = {}  # 统计加速情况
            total_segments = len(segments)
            
            for i, segment in enumerate(segments, 1):
                progress = int((i / total_segments) * 85)  # 85% 用于音频生成
                
                speaker = segment['speaker']
                voice = voice_mapping.get(speaker, "default_voice")
                text = segment['text']
                
                # 计算字幕时间长度 T_srt (毫秒)
                start_seconds = SubtitleParser._time_to_seconds(segment['start'])
                end_seconds = SubtitleParser._time_to_seconds(segment['end'])
                t_srt_ms = int((end_seconds - start_seconds) * 1000)
                
                await self.logger.progress(
                    f"处理段落 {i}/{total_segments}",
                    progress,
                    f"说话人: {speaker}, 时长: {t_srt_ms}ms"
                )
                
                # 尝试生成合适的音频，最多3次重试
                final_audio_data, used_speed = await self._generate_audio_with_retry(
                    text, voice, model, language, t_srt_ms, i, segment.get('emotion', 'neutral')
                )
                
                # 记录速度统计
                if used_speed > 1.0:
                    if used_speed >= 2.0 and final_audio_data == b'silence_placeholder':
                        speed_stats[i] = "加速失败，请简化文本"
                    else:
                        speed_stats[i] = f"speed={used_speed}"
                
                audio_segments.append({
                    'audio_data': final_audio_data,
                    'start_time': int(start_seconds * 1000),  # 转换为毫秒
                    'end_time': int(end_seconds * 1000),      # 转换为毫秒  
                    'speaker': speaker,
                    'text': text,
                    'index': i,
                    'speed': used_speed
                })
            
            # 4. 按时间戳拼接音频
            await self.logger.progress("拼接音频", 90, "按时间戳组合音频段落")
            final_audio_path = await self._build_timeline_audio(audio_segments, output_path)
            
            # 5. 生成统计报告
            await self.logger.progress("生成报告", 95, "统计处理结果")
            stats = self._generate_statistics(segments, speaker_groups, speed_stats)
            
            await self.logger.success("配音生成完成", f"输出文件: {final_audio_path}")
            
            return {
                "success": True,
                "output_file": str(final_audio_path),
                "statistics": stats,
                "segments_count": len(segments),
                "speakers_count": len(speaker_groups),
                "speed_adjustments": speed_stats
            }
            
        except Exception as e:
            await self.logger.error("处理失败", str(e))
            raise
    
    def _group_by_speaker(self, segments: List[Dict]) -> Dict[str, List[Dict]]:
        """按说话人分组字幕段落"""
        groups = {}
        for segment in segments:
            speaker = segment['speaker']
            if speaker not in groups:
                groups[speaker] = []
            groups[speaker].append(segment)
        return groups
    
    async def _generate_audio_with_retry(
        self, 
        text: str, 
        voice: str, 
        model: str, 
        language: str, 
        t_srt_ms: int,
        segment_index: int,
        emotion: str = "neutral"
    ) -> Tuple[bytes, float, str, str]:
        """
        带重试机制的音频生成
        
        Returns:
            (audio_data, final_speed, trace_id, audio_url)
        """
        max_retries = 3
        current_speed = 1.0
        
        for attempt in range(max_retries):
            await self.logger.info(f"段落{segment_index} 尝试{attempt + 1}", 
                                 f"速度: {current_speed}, 目标时长: {t_srt_ms}ms")
            
            # 生成音频并获取时长信息
            audio_result = await self.tts_service.generate_audio_with_info(
                text, voice, model, language, current_speed, emotion
            )
            
            audio_data = audio_result['audio_data']
            t_tts_ms = audio_result['duration_ms']
            
            await self.logger.info(f"段落{segment_index} 音频分析", 
                                 f"TTS时长: {t_tts_ms}ms, 字幕时长: {t_srt_ms}ms")
            
            # 判断是否需要调整速度
            if t_tts_ms <= t_srt_ms:
                await self.logger.success(f"段落{segment_index} 时长合适", f"使用速度: {current_speed}")
                return audio_data, current_speed, audio_result.get('trace_id', ''), audio_result.get('audio_url', '')
            
            # 需要加速
            if attempt < max_retries - 1:  # 还有重试机会
                new_speed = t_tts_ms / t_srt_ms
                if attempt == 1:  # 第二次重试加0.2
                    new_speed += 0.2
                
                # 限制最大速度
                new_speed = min(new_speed, 2.0)
                
                if new_speed >= 2.0 and attempt == 0:  # 第一次就达到最大速度
                    await self.logger.warning(f"段落{segment_index} 需要最大加速", "直接使用speed=2.0")
                    current_speed = 2.0
                    continue
                elif new_speed >= 2.0:  # 后续重试达到最大速度
                    await self.logger.error(f"段落{segment_index} 加速失败", "超出最大速度限制")
                    return b'silence_placeholder', 2.0, '', ''
                else:
                    current_speed = round(new_speed, 1)
                    await self.logger.warning(f"段落{segment_index} 重试", f"新速度: {current_speed}")
            else:
                # 最后一次重试仍然失败
                await self.logger.error(f"段落{segment_index} 加速失败", "3次重试后仍超时，使用静音")
                return b'silence_placeholder', current_speed, '', ''
        
        return audio_data, current_speed, '', ''
    
    async def _build_timeline_audio(self, audio_segments: List[Dict], output_path: Path) -> Path:
        """
        构建音频时间轴，按时间戳合并音频段落
        
        Args:
            audio_segments: 音频段落列表，每个包含 start_time, end_time, audio_data
            output_path: 输出文件路径
            
        Returns:
            生成的音频文件路径
        """
        await self.logger.info("构建音频时间轴", f"共 {len(audio_segments)} 个段落")
        
        # 按开始时间排序
        sorted_segments = sorted(audio_segments, key=lambda x: x['start_time'])
        
        # 创建空的音频轨道
        final_audio = AudioSegment.empty()
        current_time = 0
            
        for i, segment in enumerate(sorted_segments):
            start_time = segment['start_time']
            end_time = segment['end_time']
            audio_data = segment['audio_data']
            
            # 如果需要添加静音间隔
            if start_time > current_time:
                silence_duration = start_time - current_time
                await self.logger.info("添加静音", f"位置: {current_time}ms, 时长: {silence_duration}ms")
                silence = AudioSegment.silent(duration=silence_duration)
                final_audio += silence
                current_time = start_time
            
            # 处理音频段落
            if audio_data == b'silence_placeholder':
                # 使用静音替换失败的段落
                segment_duration = end_time - start_time
                await self.logger.warning(f"段落{i+1} 使用静音", f"时长: {segment_duration}ms")
                silence = AudioSegment.silent(duration=segment_duration)
                final_audio += silence
                current_time = end_time
            else:
                # 处理真实音频数据
                try:
                    await self.logger.info(f"添加段落{i+1}", f"位置: {start_time}ms, 说话人: {segment.get('speaker', 'Unknown')}")
                    
                    # 将音频数据转换为AudioSegment
                    audio_io = io.BytesIO(audio_data)
                    segment_audio = AudioSegment.from_file(audio_io, format="mp3")
                    
                    # 获取段落要求的时长
                    required_duration = end_time - start_time
                    actual_duration = len(segment_audio)
                    
                    # 保持原始音频格式，不修改音调，仅做时间戳对齐
                    if actual_duration != required_duration:
                        await self.logger.info("音频时长不匹配", f"原始: {actual_duration}ms, 目标: {required_duration}ms")
                        
                        if actual_duration > required_duration:
                            # 音频太长，截取到目标时长
                            segment_audio = segment_audio[:required_duration]
                            await self.logger.info("音频截取", f"截取至 {required_duration}ms")
                        else:
                            # 音频太短，用静音填充到目标时长
                            padding = AudioSegment.silent(duration=required_duration - actual_duration)
                            segment_audio = segment_audio + padding
                            await self.logger.info("音频填充", f"填充至 {required_duration}ms")
                    
                    final_audio += segment_audio
                    current_time = end_time
                    
                except Exception as e:
                    await self.logger.error(f"段落{i+1} 音频处理失败", f"错误: {str(e)}, 使用静音替代")
                    # 处理失败时使用静音
                    segment_duration = end_time - start_time
                    silence = AudioSegment.silent(duration=segment_duration)
                    final_audio += silence
                    current_time = end_time
            
            # 导出最终音频
        await self.logger.info("导出音频文件", f"总时长: {len(final_audio)}ms")
        final_audio.export(str(output_path), format="mp3", bitrate="128k")
            
        return output_path
            
    def _generate_statistics(self, segments: List[Dict], speaker_groups: Dict, speed_stats: Dict) -> Dict:
        """生成统计报告，包含加速信息"""
        total_segments = len(segments)
        total_speakers = len(speaker_groups)
        
        # 计算平均段落长度
        if segments:
            avg_length = sum(len(seg['text']) for seg in segments) / len(segments)
        else:
            avg_length = 0
        
        # 统计加速情况
        speed_adjustments = len(speed_stats)
        failed_segments = sum(1 for v in speed_stats.values() if "失败" in v)
        
        stats = {
            'total_segments': total_segments,
            'total_speakers': total_speakers,
            'average_segment_length': round(avg_length, 1),
            'speed_adjustments': speed_adjustments,
            'failed_segments': failed_segments,
            'speed_details': speed_stats
        }
        
        return stats 