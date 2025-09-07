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
import aiofiles
import shutil

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
    
    def __init__(self, filename: str, client_id: str = None, session_id: str = None):
        self.id = str(uuid.uuid4())
        self.filename = filename
        self.client_id = client_id  # 添加client_id字段
        self.session_id = session_id  # 添加session_id字段用于用户隔离
        self.segments: List[SubtitleSegment] = []
        self.total_segments = 0
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def add_segment(self, segment: SubtitleSegment, insert_after_index: int = None):
        """添加段落"""
        print(f"🔥 DEBUG: add_segment调用 - insert_after_index={insert_after_index}, 当前段落数={len(self.segments)}")
        
        if insert_after_index is not None:
            # 在指定索引位置后插入
            # 由于索引是从1开始的，转换为列表位置（从0开始）
            insert_position = insert_after_index  # 在index后插入，所以位置就是index值
            print(f"🔥 DEBUG: 计算插入位置 insert_position={insert_position}")
            
            if insert_position <= len(self.segments):
                print(f"🔥 DEBUG: 在位置{insert_position}插入段落")
                self.segments.insert(insert_position, segment)
            else:
                # 如果位置超出范围，追加到末尾
                print(f"🔥 DEBUG: 位置超出范围，追加到末尾")
                self.segments.append(segment)
        else:
            # 追加到末尾
            print(f"🔥 DEBUG: insert_after_index为None，追加到末尾")
            self.segments.append(segment)
        
        print(f"🔥 DEBUG: 插入后段落数={len(self.segments)}")
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
            "session_id": self.session_id,
            "total_segments": self.total_segments,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_full_dict(self) -> Dict:
        """转换为完整字典格式（包含所有段落数据）"""
        return {
            "id": self.id,
            "filename": self.filename,
            "client_id": self.client_id,
            "session_id": self.session_id,
            "total_segments": self.total_segments,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "segments": [segment.to_dict() for segment in self.segments]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SubtitleProject':
        """从字典创建项目实例"""
        project = cls(data["filename"], data.get("client_id"), data.get("session_id"))
        project.id = data["id"]
        project.total_segments = data.get("total_segments", 0)
        project.created_at = data.get("created_at", datetime.now().isoformat())
        project.updated_at = data.get("updated_at", datetime.now().isoformat())
        
        # 恢复段落数据
        if "segments" in data:
            project.segments = [SubtitleSegment.from_dict(seg_data) for seg_data in data["segments"]]
            project.total_segments = len(project.segments)
        
        return project


class SubtitleManager:
    """字幕管理器"""
    
    def __init__(self):
        self.projects: Dict[str, SubtitleProject] = {}
        self.projects_dir = Path("projects")
        self.projects_dir.mkdir(exist_ok=True)
    
    async def parse_srt_file(self, file_content: str, filename: str, client_id: str = None, session_id: str = None) -> Tuple[bool, str, Optional[SubtitleProject]]:
        """
        解析SRT文件
        
        Args:
            file_content: SRT文件内容
            filename: 文件名
            client_id: 客户端ID
            session_id: 会话ID（用于用户隔离）
            
        Returns:
            (是否成功, 错误信息, 项目对象)
        """
        try:
            # 使用现有的SRT解析逻辑
            from audio_processor import SubtitleParser
            
            segments_data = SubtitleParser.parse_srt(file_content)
            
            if not segments_data:
                return False, "SRT文件格式无效或为空", None
            
            if len(segments_data) > 500:
                return False, f"字幕条目过多({len(segments_data)}条)，最多支持500条", None
            
            # 检查总时长限制（20分钟 = 1200秒）
            if segments_data:
                from audio_processor import SubtitleParser
                last_segment = segments_data[-1]
                last_end_time = SubtitleParser._time_to_seconds(last_segment['end'])
                if last_end_time > 1200:  # 20分钟限制
                    return False, f"字幕总时长过长({last_end_time:.1f}秒)，最多支持20分钟(1200秒)", None
            
            # 创建新项目，传入session_id
            project = SubtitleProject(filename, client_id, session_id)
            
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
    
    def list_projects(self, session_id: str = None) -> List[Dict]:
        """列出指定会话的项目"""
        if session_id:
            # 按会话过滤项目
            session_projects = [
                project.to_dict() for project in self.projects.values()
                if getattr(project, 'session_id', None) == session_id
            ]
            return session_projects
        else:
            # 兼容性：如果没有session_id，返回所有项目
            return [project.to_dict() for project in self.projects.values()]
    
    def save_project(self, project: SubtitleProject):
        """保存项目到内存"""
        if project and project.id:
            self.projects[project.id] = project
            project.updated_at = datetime.now().isoformat()
    
    async def save_project_to_disk(self, project: SubtitleProject):
        """保存项目到磁盘"""
        if not project or not project.id:
            return False
        
        try:
            project_file = self.projects_dir / f"{project.id}.json"
            project_data = project.to_full_dict()
            
            async with aiofiles.open(project_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(project_data, ensure_ascii=False, indent=2))
            
            # 同时保存到内存
            self.save_project(project)
            return True
        except Exception as e:
            print(f"保存项目到磁盘失败: {e}")
            return False
    
    async def load_project_from_disk(self, project_id: str) -> Optional[SubtitleProject]:
        """从磁盘加载项目"""
        try:
            project_file = self.projects_dir / f"{project_id}.json"
            if not project_file.exists():
                return None
            
            async with aiofiles.open(project_file, 'r', encoding='utf-8') as f:
                project_data = json.loads(await f.read())
            
            project = SubtitleProject.from_dict(project_data)
            # 加载到内存
            self.projects[project.id] = project
            return project
        except Exception as e:
            print(f"从磁盘加载项目失败: {e}")
            return None
    
    async def load_all_projects_from_disk(self):
        """从磁盘加载所有项目"""
        try:
            project_files = list(self.projects_dir.glob("*.json"))
            loaded_count = 0
            
            for project_file in project_files:
                try:
                    project_id = project_file.stem
                    project = await self.load_project_from_disk(project_id)
                    if project:
                        loaded_count += 1
                except Exception as e:
                    print(f"加载项目文件 {project_file} 失败: {e}")
            
            print(f"从磁盘加载了 {loaded_count} 个项目")
            return loaded_count
        except Exception as e:
            print(f"加载项目列表失败: {e}")
            return 0
    
    async def delete_project_from_disk(self, project_id: str) -> bool:
        """从磁盘删除项目"""
        try:
            project_file = self.projects_dir / f"{project_id}.json"
            if project_file.exists():
                project_file.unlink()
            
            # 同时从内存删除
            if project_id in self.projects:
                del self.projects[project_id]
            
            return True
        except Exception as e:
            print(f"删除项目文件失败: {e}")
            return False


# 全局字幕管理器实例
subtitle_manager = SubtitleManager() 