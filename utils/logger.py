"""
WebSocket 实时日志系统
"""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import WebSocket
from enum import Enum

class LogLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"
    DEBUG = "debug"

class WebSocketLogger:
    """WebSocket 日志管理器"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.logger = logging.getLogger("websocket_logger")
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """连接 WebSocket 客户端"""
        await websocket.accept()
        self.connections[client_id] = websocket
        self.logger.info(f"客户端连接: {client_id}")
        
        # 发送欢迎消息
        await self.send_log(
            client_id, 
            LogLevel.SUCCESS, 
            "连接成功",
            "WebSocket 实时日志已启动"
        )
        
    def disconnect(self, client_id: str):
        """断开 WebSocket 客户端"""
        if client_id in self.connections:
            del self.connections[client_id]
            self.logger.info(f"客户端断开: {client_id}")
            
            # 清理用户数据
            self._cleanup_user_data(client_id)
    
    def _cleanup_user_data(self, client_id: str):
        """清理用户相关数据"""
        try:
            # 日志通过WebSocket实时传输，无需清理存储
            
            # 清理字幕项目
            from subtitle_manager import subtitle_manager
            deleted_count = subtitle_manager.delete_projects_by_client_id(client_id)
            if deleted_count > 0:
                print(f"已清理用户字幕项目: {client_id}, 删除数量: {deleted_count}")
            
            # 清理音频文件
            self._cleanup_audio_files(client_id)
            
            # 清理管理员活动记录
            from admin import user_activities
            if client_id in user_activities:
                del user_activities[client_id]
                print(f"已清理用户活动记录: {client_id}")
                
        except Exception as e:
            print(f"清理用户数据时出错 {client_id}: {e}")
    
    def _cleanup_audio_files(self, client_id: str):
        """清理用户相关的音频文件"""
        try:
            from config import Config
            from pathlib import Path
            
            print(f"开始清理用户音频文件: {client_id}")
            
            # 定义需要清理的目录
            audio_directories = [
                Config.OUTPUT_DIR,  # outputs目录
                Path("audio_files"),  # audio_files目录
                Path("temp_audio")   # temp_audio目录
            ]
            
            total_deleted = 0
            
            for audio_dir in audio_directories:
                if not audio_dir.exists():
                    print(f"目录不存在，跳过: {audio_dir}")
                    continue
                    
                print(f"清理目录: {audio_dir}")
                deleted_files = []
                all_files = list(audio_dir.iterdir())
                print(f"  目录中共有 {len(all_files)} 个文件")
                
                for file_path in all_files:
                    if file_path.is_file() and file_path.suffix == '.mp3':
                        filename = file_path.name
                        print(f"  检查文件: {filename}")
                        
                        # 检查多种可能的文件名格式
                        should_delete = False
                        
                        # 格式1: 配音_20250729_184534_client_1.mp3 (client_id被截断)
                        if 'client_' in filename and client_id.startswith('client_'):
                            # 提取文件名中的client部分
                            import re
                            client_match = re.search(r'client_([a-zA-Z0-9]+)', filename)
                            if client_match:
                                file_client_id = client_match.group(1)
                                print(f"    文件中的client_id: {file_client_id}")
                                print(f"    用户client_id: {client_id}")
                                # 检查client_id是否匹配（支持部分匹配）
                                if client_id.startswith(f'client_{file_client_id}'):
                                    should_delete = True
                                    print(f"    匹配格式1: client_id匹配")
                        
                        # 格式2: 直接包含完整client_id
                        elif client_id in filename:
                            should_delete = True
                            print(f"    匹配格式2: 直接包含client_id")
                        
                        # 格式3: 包含client_id的前8位
                        elif len(client_id) > 8 and client_id[:8] in filename:
                            should_delete = True
                            print(f"    匹配格式3: 包含client_id前8位")
                        
                        # 格式4: 检查文件名中的时间戳（用于audio_files和temp_audio中的文件）
                        elif '_' in filename:
                            # 检查文件名中是否包含时间戳相关的信息
                            import re
                            # 修改正则表达式，匹配更多的时间戳格式
                            timestamp_matches = re.findall(r'_(\d{10,})_', filename)  # 匹配10位以上的时间戳
                            if not timestamp_matches:
                                timestamp_matches = re.findall(r'_(\d{10,})', filename)  # 匹配结尾的时间戳
                            
                            # 提取client_id中的时间戳
                            client_timestamps = re.findall(r'(\d{10,})', client_id)
                            
                            for file_timestamp in timestamp_matches:
                                print(f"    检查时间戳: {file_timestamp}")
                                for client_timestamp in client_timestamps:
                                    print(f"    对比client时间戳: {client_timestamp}")
                                    # 使用前8位进行匹配（相差几秒钟内的时间戳）
                                    if file_timestamp[:8] == client_timestamp[:8]:
                                        should_delete = True
                                        print(f"    匹配格式4: 时间戳前缀匹配 (文件:{file_timestamp[:8]}, 客户端:{client_timestamp[:8]})")
                                        break
                                if should_delete:
                                    break
                        
                        print(f"    是否删除: {should_delete}")
                        
                        if should_delete:
                            try:
                                file_path.unlink()
                                deleted_files.append(filename)
                                print(f"    ✅ 已删除音频文件: {filename}")
                            except Exception as e:
                                print(f"    ❌ 删除音频文件失败 {filename}: {e}")
                        else:
                            print(f"    跳过文件: {filename}")
                
                if deleted_files:
                    print(f"  目录 {audio_dir} 清理完成，删除了 {len(deleted_files)} 个文件")
                    total_deleted += len(deleted_files)
                else:
                    print(f"  目录 {audio_dir} 没有找到相关文件")
            
            if total_deleted > 0:
                print(f"用户 {client_id} 的音频文件清理完成，总共删除了 {total_deleted} 个文件")
            else:
                print(f"用户 {client_id} 没有找到任何相关的音频文件")
                            
        except Exception as e:
            print(f"清理音频文件时出错: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_log(
        self, 
        client_id: str, 
        level: LogLevel, 
        message: str, 
        details: str = "",
        progress: Optional[int] = None
    ):
        """发送日志到指定客户端"""
        if client_id not in self.connections:
            return
            
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
            "details": details,
            "progress": progress
        }
        
        try:
            websocket = self.connections[client_id]
            await websocket.send_text(json.dumps(log_data))
            
            # 同时输出到控制台
            console_msg = f"[{level.value.upper()}] {message}"
            if details:
                console_msg += f": {details}"
            print(console_msg)
            
        except Exception as e:
            self.logger.error(f"发送日志失败 {client_id}: {e}")
            self.disconnect(client_id)
    
    async def broadcast_log(
        self, 
        level: LogLevel, 
        message: str, 
        details: str = "",
        progress: Optional[int] = None
    ):
        """广播日志到所有客户端"""
        if not self.connections:
            return
            
        tasks = []
        for client_id in list(self.connections.keys()):
            task = self.send_log(client_id, level, message, details, progress)
            tasks.append(task)
            
        await asyncio.gather(*tasks, return_exceptions=True)

# 全局日志管理器实例
websocket_logger = WebSocketLogger()


class ProcessLogger:
    """处理过程日志记录器"""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.logger = websocket_logger
        
        
    async def info(self, message: str, details: str = ""):
        await self.logger.send_log(self.client_id, LogLevel.INFO, message, details)

    async def success(self, message: str, details: str = ""):
        await self.logger.send_log(self.client_id, LogLevel.SUCCESS, message, details)

    async def warning(self, message: str, details: str = ""):
        await self.logger.send_log(self.client_id, LogLevel.WARNING, message, details)

    async def error(self, message: str, details: str = ""):
        await self.logger.send_log(self.client_id, LogLevel.ERROR, message, details)

    async def progress(self, message: str, progress: int, details: str = ""):
        await self.logger.send_log(self.client_id, LogLevel.PROGRESS, message, details, progress)

    async def debug(self, message: str, details: str = ""):
        await self.logger.send_log(self.client_id, LogLevel.DEBUG, message, details)

def get_process_logger(client_id: str) -> ProcessLogger:
    """获取处理过程日志记录器"""
    return ProcessLogger(client_id) 