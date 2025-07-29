"""
字幕文件解析与优化模块
处理SRT文件解析、情绪识别、段落管理等功能
"""

import re
import json
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import asyncio

class EmotionDetector:
    """情绪识别器"""
    
    # 支持的情绪标签
    SUPPORTED_EMOTIONS = ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm"]
    
    # 情绪关键词映射
    EMOTION_KEYWORDS = {
        "happy": ["高兴", "开心", "快乐", "兴奋", "愉快", "笑", "哈哈", "嘿嘿", "欢喜", "喜悦"],
        "sad": ["难过", "悲伤", "哭", "眼泪", "伤心", "痛苦", "失望", "沮丧", "忧伤", "哀伤"],
        "angry": ["生气", "愤怒", "气愤", "恼火", "暴怒", "发火", "愤恨", "恼怒", "怒气", "火大"],
        "fearful": ["害怕", "恐惧", "担心", "紧张", "焦虑", "忧虑", "不安", "惊慌", "恐慌", "畏惧"],
        "disgusted": ["恶心", "厌恶", "讨厌", "反感", "恶心", "嫌弃", "厌烦", "憎恶", "排斥", "反胃"],
        "surprised": ["惊讶", "震惊", "意外", "吃惊", "惊奇", "惊愕", "惊诧", "诧异", "出乎意料", "想不到"],
        "calm": ["平静", "冷静", "淡定", "沉着", "安静", "宁静", "祥和", "安宁", "镇静", "平和"]
    }
    
    @classmethod
    def detect_emotion(cls, text: str) -> str:
        """
        检测文本中的情绪
        
        Args:
            text: 要分析的文本
            
        Returns:
            检测到的情绪标签，如果未识别则返回"auto"
        """
        if not text:
            return "auto"
            
        text = text.lower()
        
        # 计算每种情绪的得分
        emotion_scores = {}
        for emotion, keywords in cls.EMOTION_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                score += text.count(keyword)
            if score > 0:
                emotion_scores[emotion] = score
        
        # 返回得分最高的情绪，如果没有匹配则返回auto
        if emotion_scores:
            return max(emotion_scores, key=emotion_scores.get)
        
        return "auto"


class SubtitleSegment:
    """字幕段落类"""
    
    def __init__(self, index: int, start_time: str, end_time: str, 
                 speaker: str, text: str, emotion: str = "auto", speed: float = 1.0):
        self.id = str(uuid.uuid4())
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.speaker = speaker
        self.text = text
        self.emotion = emotion if emotion in EmotionDetector.SUPPORTED_EMOTIONS else "auto"
        self.speed = speed
        self.audio_data = None  # TTS生成的音频数据
        self.audio_duration = 0  # 音频时长(ms)
        self.trace_id = None  # TTS API的追踪ID
        self.audio_url = None  # 原始OSS音频URL
        self.translated_text = None  # 翻译后的文本
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "index": self.index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "speaker": self.speaker,
            "text": self.text,
            "emotion": self.emotion,
            "speed": self.speed,
            "has_audio": self.audio_data is not None,
            "audio_duration": self.audio_duration,
            "audio_url": self.audio_url,  # 使用实际的OSS URL
            "trace_id": getattr(self, 'trace_id', None),
            "translated_text": getattr(self, 'translated_text', None),  # 翻译文本
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SubtitleSegment':
        """从字典创建实例"""
        segment = cls(
            index=data["index"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            speaker=data["speaker"],
            text=data["text"],
            emotion=data.get("emotion", "auto"),
            speed=data.get("speed", 1.0)
        )
        segment.id = data.get("id", segment.id)
        segment.audio_duration = data.get("audio_duration", 0)
        segment.translated_text = data.get("translated_text", None)  # 加载翻译文本
        segment.created_at = data.get("created_at", segment.created_at)
        segment.updated_at = data.get("updated_at", segment.updated_at)
        return segment


class SubtitleProject:
    """字幕项目类"""
    
    def __init__(self, filename: str, client_id: str = None):
        self.id = str(uuid.uuid4())
        self.filename = filename
        self.client_id = client_id  # 添加client_id字段
        self.segments: List[SubtitleSegment] = []
        self.total_segments = 0
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def add_segment(self, segment: SubtitleSegment):
        """添加段落"""
        self.segments.append(segment)
        self.reindex_segments()
        self.updated_at = datetime.now().isoformat()
    
    def remove_segment(self, segment_id: str) -> bool:
        """删除段落"""
        original_count = len(self.segments)
        self.segments = [s for s in self.segments if s.id != segment_id]
        if len(self.segments) < original_count:
            self.reindex_segments()
            self.updated_at = datetime.now().isoformat()
            return True
        return False
    
    def update_segment(self, segment_id: str, updates: Dict) -> bool:
        """更新段落"""
        for segment in self.segments:
            if segment.id == segment_id:
                for key, value in updates.items():
                    if hasattr(segment, key):
                        setattr(segment, key, value)
                segment.updated_at = datetime.now().isoformat()
                self.updated_at = datetime.now().isoformat()
                return True
        return False
    
    def reindex_segments(self):
        """重新编号段落"""
        for i, segment in enumerate(self.segments, 1):
            segment.index = i
        self.total_segments = len(self.segments)
    
    def get_segments_page(self, page: int = 1, per_page: int = 20) -> Dict:
        """获取分页段落"""
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_segments = self.segments[start_idx:end_idx]
        
        return {
            "segments": [s.to_dict() for s in page_segments],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(self.segments),
                "pages": (len(self.segments) + per_page - 1) // per_page
            }
        }
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "filename": self.filename,
            "client_id": self.client_id,
            "total_segments": self.total_segments,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class SubtitleManager:
    """字幕管理器"""
    
    def __init__(self):
        self.projects: Dict[str, SubtitleProject] = {}
    
    async def parse_srt_file(self, file_content: str, filename: str, client_id: str = None) -> Tuple[bool, str, Optional[SubtitleProject]]:
        """
        解析SRT文件
        
        Args:
            file_content: SRT文件内容
            filename: 文件名
            client_id: 客户端ID
            
        Returns:
            (是否成功, 错误信息, 项目对象)
        """
        try:
            # 使用现有的SRT解析逻辑
            from audio_processor import SubtitleParser
            
            segments_data = SubtitleParser.parse_srt(file_content)
            
            if not segments_data:
                return False, "SRT文件格式无效或为空", None
            
            if len(segments_data) > 100:
                return False, f"字幕条目过多({len(segments_data)}条)，最多支持100条", None
            
            # 创建新项目
            project = SubtitleProject(filename, client_id)
            
            # 转换段落数据
            for i, seg_data in enumerate(segments_data, 1):
                # 使用解析结果中的emotion，如果没有则自动检测
                emotion = seg_data.get('emotion', 'auto')
                if emotion == 'auto':
                    emotion = EmotionDetector.detect_emotion(seg_data['text'])
                
                segment = SubtitleSegment(
                    index=i,
                    start_time=seg_data['start'],
                    end_time=seg_data['end'],
                    speaker=seg_data['speaker'],
                    text=seg_data['text'],
                    emotion=emotion,
                    speed=1.0
                )
                project.add_segment(segment)
            
            # 保存项目
            self.projects[project.id] = project
            
            return True, "", project
            
        except Exception as e:
            return False, f"解析失败: {str(e)}", None
    
    def get_project(self, project_id: str) -> Optional[SubtitleProject]:
        """获取项目"""
        return self.projects.get(project_id)
    
    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        if project_id in self.projects:
            del self.projects[project_id]
            return True
        return False
    
    def delete_projects_by_client_id(self, client_id: str) -> int:
        """根据client_id删除所有相关项目"""
        deleted_count = 0
        projects_to_delete = []
        
        for project_id, project in self.projects.items():
            if project.client_id == client_id:
                projects_to_delete.append(project_id)
        
        for project_id in projects_to_delete:
            del self.projects[project_id]
            deleted_count += 1
            
        return deleted_count
    
    def list_projects(self) -> List[Dict]:
        """列出所有项目"""
        return [project.to_dict() for project in self.projects.values()]
    
    def save_project(self, project: SubtitleProject):
        """保存项目到内存"""
        if project and project.id:
            self.projects[project.id] = project
            project.updated_at = datetime.now().isoformat()


# 全局字幕管理器实例
subtitle_manager = SubtitleManager() 