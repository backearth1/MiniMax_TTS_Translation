#!/usr/bin/env python3
"""
项目管理模块 - Admin后台项目管理功能
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
import asyncio

from config import Config

# 创建路由器
project_router = APIRouter(prefix="/admin/projects", tags=["项目管理"])

class ProjectManager:
    """项目管理器"""
    
    def __init__(self):
        self.projects_dir = Path("projects")
        self.projects_dir.mkdir(exist_ok=True)
    
    def get_all_projects(self, page: int = 1, per_page: int = 20, sort_by: str = "created_at", 
                        order: str = "desc", status_filter: str = "all") -> Dict:
        """
        获取所有项目列表
        
        Args:
            page: 页码
            per_page: 每页数量
            sort_by: 排序字段 (created_at, updated_at, filename, segments)
            order: 排序方向 (asc, desc)
            status_filter: 状态筛选 (all, active, expired)
        """
        projects = []
        
        # 遍历所有项目文件
        for project_file in self.projects_dir.glob("*.json"):
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                
                # 计算项目状态
                created_at = datetime.fromisoformat(project_data.get("created_at", ""))
                updated_at = datetime.fromisoformat(project_data.get("updated_at", ""))
                days_since_update = (datetime.now() - updated_at).days
                
                # 项目基本信息
                project_info = {
                    "id": project_data.get("id", ""),
                    "filename": project_data.get("filename", ""),
                    "client_id": project_data.get("client_id", ""),
                    "session_id": project_data.get("session_id", ""),
                    "total_segments": project_data.get("total_segments", 0),
                    "created_at": project_data.get("created_at", ""),
                    "updated_at": project_data.get("updated_at", ""),
                    "days_since_update": days_since_update,
                    "file_size": project_file.stat().st_size,
                    "status": "expired" if days_since_update > 7 else "active",
                    "has_audio": any(seg.get("has_audio", False) for seg in project_data.get("segments", [])),
                    "audio_count": sum(1 for seg in project_data.get("segments", []) if seg.get("has_audio", False))
                }
                
                projects.append(project_info)
                
            except Exception as e:
                # 跳过损坏的项目文件
                continue
        
        # 状态筛选
        if status_filter == "active":
            projects = [p for p in projects if p["status"] == "active"]
        elif status_filter == "expired":
            projects = [p for p in projects if p["status"] == "expired"]
        
        # 排序
        reverse = (order == "desc")
        if sort_by == "created_at":
            projects.sort(key=lambda x: x["created_at"], reverse=reverse)
        elif sort_by == "updated_at":
            projects.sort(key=lambda x: x["updated_at"], reverse=reverse)
        elif sort_by == "filename":
            projects.sort(key=lambda x: x["filename"], reverse=reverse)
        elif sort_by == "segments":
            projects.sort(key=lambda x: x["total_segments"], reverse=reverse)
        elif sort_by == "file_size":
            projects.sort(key=lambda x: x["file_size"], reverse=reverse)
        
        # 分页
        total_count = len(projects)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_projects = projects[start_idx:end_idx]
        
        # 统计信息
        total_size = sum(p["file_size"] for p in projects)
        active_count = sum(1 for p in projects if p["status"] == "active")
        expired_count = sum(1 for p in projects if p["status"] == "expired")
        
        return {
            "projects": page_projects,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            },
            "statistics": {
                "total_projects": total_count,
                "active_projects": active_count,
                "expired_projects": expired_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2)
            }
        }
    
    def get_project_detail(self, project_id: str) -> Optional[Dict]:
        """获取项目详细信息"""
        project_file = self.projects_dir / f"{project_id}.json"
        
        if not project_file.exists():
            return None
        
        try:
            with open(project_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # 计算额外信息
            created_at = datetime.fromisoformat(project_data.get("created_at", ""))
            updated_at = datetime.fromisoformat(project_data.get("updated_at", ""))
            
            project_data["days_since_update"] = (datetime.now() - updated_at).days
            project_data["file_size"] = project_file.stat().st_size
            project_data["segments_with_audio"] = sum(1 for seg in project_data.get("segments", []) if seg.get("has_audio", False))
            
            return project_data
            
        except Exception as e:
            return None
    
    def delete_projects(self, project_ids: List[str]) -> Dict:
        """批量删除项目"""
        deleted_count = 0
        failed_count = 0
        freed_space = 0
        
        for project_id in project_ids:
            project_file = self.projects_dir / f"{project_id}.json"
            
            try:
                if project_file.exists():
                    freed_space += project_file.stat().st_size
                    project_file.unlink()
                    deleted_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
        
        return {
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "freed_space_bytes": freed_space,
            "freed_space_mb": round(freed_space / 1024 / 1024, 2)
        }
    
    def cleanup_expired_projects(self, days_threshold: int = 7) -> Dict:
        """清理过期项目"""
        expired_projects = []
        
        for project_file in self.projects_dir.glob("*.json"):
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                
                updated_at = datetime.fromisoformat(project_data.get("updated_at", ""))
                days_since_update = (datetime.now() - updated_at).days
                
                if days_since_update > days_threshold:
                    expired_projects.append(project_data.get("id", ""))
                    
            except Exception:
                continue
        
        if expired_projects:
            return self.delete_projects(expired_projects)
        else:
            return {
                "deleted_count": 0,
                "failed_count": 0,
                "freed_space_bytes": 0,
                "freed_space_mb": 0
            }

# 全局项目管理器实例
project_manager = ProjectManager()

@project_router.get("/", response_class=HTMLResponse)
async def projects_page():
    """项目管理页面"""
    with open("admin_modules/templates/projects.html", "r", encoding="utf-8") as f:
        return f.read()

@project_router.get("/api/list")
async def get_projects_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("updated_at", regex="^(created_at|updated_at|filename|segments|file_size)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    status_filter: str = Query("all", regex="^(all|active|expired)$")
):
    """获取项目列表API"""
    try:
        # 记录管理员活动
        from admin import record_user_activity
        record_user_activity("admin_user", "view_projects")
        
        result = project_manager.get_all_projects(page, per_page, sort_by, order, status_filter)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")

@project_router.get("/api/detail/{project_id}")
async def get_project_detail(project_id: str):
    """获取项目详情API"""
    project_detail = project_manager.get_project_detail(project_id)
    
    if project_detail is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return {"success": True, "data": project_detail}

@project_router.post("/api/delete")
async def delete_projects(project_ids: List[str]):
    """批量删除项目API"""
    if not project_ids:
        raise HTTPException(status_code=400, detail="未指定要删除的项目")
    
    try:
        result = project_manager.delete_projects(project_ids)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除项目失败: {str(e)}")

@project_router.post("/api/cleanup")
async def cleanup_expired_projects(days_threshold: int = Query(7, ge=1)):
    """清理过期项目API"""
    try:
        result = project_manager.cleanup_expired_projects(days_threshold)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理过期项目失败: {str(e)}")

@project_router.get("/api/statistics")
async def get_project_statistics():
    """获取项目统计信息API"""
    try:
        result = project_manager.get_all_projects(page=1, per_page=9999)  # 获取所有项目进行统计
        return {"success": True, "data": result["statistics"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")