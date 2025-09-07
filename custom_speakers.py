"""
自定义角色管理模块
支持用户添加、删除和管理自定义说话人角色
"""
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Form
from pydantic import BaseModel

# 创建路由器
router = APIRouter()

# 自定义角色存储文件
CUSTOM_SPEAKERS_FILE = Path("custom_speakers.json")

class CustomSpeaker(BaseModel):
    """自定义角色模型"""
    id: str
    name: str  # 固定格式：SPEAKER_XX
    voice_id: str  # 语音ID，如 "ai_her_04"
    created_at: str
    updated_at: str

class CustomSpeakersManager:
    """自定义角色管理器"""
    
    def __init__(self):
        self.speakers_file = CUSTOM_SPEAKERS_FILE
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """确保存储文件存在"""
        if not self.speakers_file.exists():
            self._save_speakers({})
    
    def _load_speakers(self) -> Dict[str, dict]:
        """加载自定义角色"""
        try:
            with open(self.speakers_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_speakers(self, speakers: Dict[str, dict]):
        """保存自定义角色"""
        with open(self.speakers_file, 'w', encoding='utf-8') as f:
            json.dump(speakers, f, ensure_ascii=False, indent=2)
    
    def get_all_speakers(self) -> List[CustomSpeaker]:
        """获取所有自定义角色"""
        speakers_data = self._load_speakers()
        return [CustomSpeaker(**data) for data in speakers_data.values()]
    
    def get_speaker(self, speaker_id: str) -> Optional[CustomSpeaker]:
        """获取指定角色"""
        speakers_data = self._load_speakers()
        if speaker_id in speakers_data:
            return CustomSpeaker(**speakers_data[speaker_id])
        return None
    
    def add_speaker(self, voice_id: str) -> CustomSpeaker:
        """添加新角色，自动分配SPEAKER_XX名称"""
        speakers_data = self._load_speakers()
        
        # 获取下一个可用的SPEAKER_XX编号
        existing_numbers = set()
        
        # 检查默认角色编号 (00-05)
        for i in range(6):
            existing_numbers.add(f"{i:02d}")
        
        # 检查已有自定义角色编号
        for existing_speaker in speakers_data.values():
            speaker_name = existing_speaker['name']
            if speaker_name.startswith('SPEAKER_'):
                try:
                    number = speaker_name.split('_')[1]
                    existing_numbers.add(number)
                except (IndexError, ValueError):
                    continue
        
        # 找到下一个可用编号
        next_number = 6
        while f"{next_number:02d}" in existing_numbers:
            next_number += 1
        
        if next_number > 99:
            raise ValueError("已达到最大角色数量限制 (SPEAKER_99)")
        
        name = f"SPEAKER_{next_number:02d}"
        
        # 生成新角色
        speaker_id = str(uuid.uuid4())
        from datetime import datetime
        now = datetime.now().isoformat()
        
        new_speaker = CustomSpeaker(
            id=speaker_id,
            name=name,
            voice_id=voice_id,
            created_at=now,
            updated_at=now
        )
        
        speakers_data[speaker_id] = new_speaker.dict()
        self._save_speakers(speakers_data)
        
        return new_speaker
    
    def update_speaker(self, speaker_id: str, voice_id: str) -> Optional[CustomSpeaker]:
        """更新角色语音ID"""
        speakers_data = self._load_speakers()
        
        if speaker_id not in speakers_data:
            return None
        
        # 更新语音ID
        speakers_data[speaker_id]['voice_id'] = voice_id
        
        from datetime import datetime
        speakers_data[speaker_id]['updated_at'] = datetime.now().isoformat()
        
        self._save_speakers(speakers_data)
        return CustomSpeaker(**speakers_data[speaker_id])
    
    def delete_speaker(self, speaker_id: str) -> bool:
        """删除角色"""
        speakers_data = self._load_speakers()
        
        if speaker_id in speakers_data:
            del speakers_data[speaker_id]
            self._save_speakers(speakers_data)
            return True
        return False
    
    def get_all_speaker_names(self) -> List[str]:
        """获取所有角色名称（包括默认和自定义）"""
        # 默认角色
        default_speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03", "SPEAKER_04", "SPEAKER_05"]
        
        # 自定义角色
        custom_speakers = [speaker.name for speaker in self.get_all_speakers()]
        
        return default_speakers + custom_speakers
    
    def get_voice_mapping(self) -> Dict[str, str]:
        """获取完整的语音映射（默认+自定义）"""
        from config import Config
        
        # 从默认配置开始
        voice_mapping = Config.VOICE_MAPPING.copy()
        
        # 添加自定义角色
        custom_speakers = self.get_all_speakers()
        for speaker in custom_speakers:
            voice_mapping[speaker.name] = speaker.voice_id
        
        return voice_mapping

# 创建管理器实例
custom_speakers_manager = CustomSpeakersManager()

# API路由

@router.get("/api/custom-speakers")
async def get_custom_speakers():
    """获取所有自定义角色"""
    try:
        speakers = custom_speakers_manager.get_all_speakers()
        return {
            "success": True,
            "speakers": [speaker.dict() for speaker in speakers]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取自定义角色失败: {str(e)}")

@router.post("/api/custom-speakers")
async def add_custom_speaker(
    voice_id: str = Form(...)
):
    """添加新的自定义角色，自动分配SPEAKER_XX名称"""
    try:
        # 验证输入
        voice_id = voice_id.strip()
        
        if not voice_id:
            raise HTTPException(status_code=400, detail="语音ID不能为空")
        
        speaker = custom_speakers_manager.add_speaker(voice_id)
        
        return {
            "success": True,
            "message": f"成功添加自定义角色: {speaker.name}",
            "speaker": speaker.dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加自定义角色失败: {str(e)}")

@router.put("/api/custom-speakers/{speaker_id}")
async def update_custom_speaker(
    speaker_id: str,
    voice_id: str = Form(...)
):
    """更新自定义角色语音ID"""
    try:
        voice_id = voice_id.strip()
        if not voice_id:
            raise HTTPException(status_code=400, detail="语音ID不能为空")
            
        speaker = custom_speakers_manager.update_speaker(speaker_id, voice_id)
        
        if not speaker:
            raise HTTPException(status_code=404, detail="角色不存在")
        
        return {
            "success": True,
            "message": f"成功更新角色: {speaker.name}",
            "speaker": speaker.dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新自定义角色失败: {str(e)}")

@router.delete("/api/custom-speakers/{speaker_id}")
async def delete_custom_speaker(speaker_id: str):
    """删除自定义角色"""
    try:
        success = custom_speakers_manager.delete_speaker(speaker_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="角色不存在")
        
        return {
            "success": True,
            "message": "角色删除成功"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除自定义角色失败: {str(e)}")

@router.get("/api/all-speakers")
async def get_all_speakers():
    """获取所有角色（默认+自定义）"""
    try:
        # 默认角色信息
        from config import Config
        default_speakers = []
        for speaker_name, voice_id in Config.VOICE_MAPPING.items():
            default_speakers.append({
                "name": speaker_name,
                "voice_id": voice_id,
                "is_custom": False
            })
        
        # 自定义角色信息
        custom_speakers = []
        for speaker in custom_speakers_manager.get_all_speakers():
            custom_speakers.append({
                "name": speaker.name,
                "voice_id": speaker.voice_id,
                "is_custom": True,
                "id": speaker.id
            })
        
        return {
            "success": True,
            "default_speakers": default_speakers,
            "custom_speakers": custom_speakers,
            "all_speaker_names": custom_speakers_manager.get_all_speaker_names(),
            "voice_mapping": custom_speakers_manager.get_voice_mapping()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")