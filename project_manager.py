"""
项目管理模块
处理项目的创建、删除、切换等管理功能
"""

from fastapi import APIRouter, HTTPException, Request, Response, Query
from typing import Optional
from subtitle_manager import subtitle_manager

# 创建项目管理路由器
router = APIRouter(prefix="/api/projects", tags=["项目管理"])

def get_session_id_from_request(request: Request) -> str:
    """从请求中获取会话ID"""
    return request.cookies.get("session_id", "")

@router.get("/count")
async def get_project_count(request: Request):
    """获取当前会话的项目数量"""
    try:
        session_id = get_session_id_from_request(request)
        if not session_id:
            return {"success": True, "count": 0, "limit": 5}
        
        count = subtitle_manager.count_projects_by_session(session_id)
        return {
            "success": True,
            "count": count,
            "limit": 5,
            "can_create_more": count < 5
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目数量失败: {str(e)}")

@router.get("/{project_id}/info")
async def get_project_info(project_id: str, request: Request):
    """获取指定项目的详细信息"""
    try:
        session_id = get_session_id_from_request(request)
        project = subtitle_manager.get_project(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 检查项目是否属于当前会话
        if getattr(project, 'session_id', None) != session_id:
            raise HTTPException(status_code=403, detail="无权访问此项目")
        
        return {
            "success": True,
            "project": project.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目信息失败: {str(e)}")

@router.post("/{project_id}/switch")
async def switch_to_project(project_id: str, request: Request):
    """切换到指定项目"""
    try:
        session_id = get_session_id_from_request(request)
        project = subtitle_manager.get_project(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 检查项目是否属于当前会话
        if getattr(project, 'session_id', None) != session_id:
            raise HTTPException(status_code=403, detail="无权访问此项目")
        
        return {
            "success": True,
            "message": "项目切换成功",
            "project": project.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换项目失败: {str(e)}")

@router.delete("/{project_id}")
async def delete_project(project_id: str, request: Request):
    """删除指定项目"""
    try:
        session_id = get_session_id_from_request(request)
        project = subtitle_manager.get_project(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 检查项目是否属于当前会话
        if getattr(project, 'session_id', None) != session_id:
            raise HTTPException(status_code=403, detail="无权删除此项目")
        
        # 删除项目
        success = await subtitle_manager.delete_project_from_disk(project_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除项目失败")
        
        return {
            "success": True,
            "message": f"项目 '{project.filename}' 删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除项目失败: {str(e)}")

@router.post("/cleanup")
async def cleanup_old_projects(request: Request, keep_count: int = Query(5, description="保留的项目数量")):
    """清理旧项目，只保留最近的几个"""
    try:
        session_id = get_session_id_from_request(request)
        if not session_id:
            return {"success": True, "message": "无会话信息，无需清理"}
        
        await subtitle_manager.cleanup_old_projects_if_needed(session_id, max_projects=keep_count)
        
        # 获取清理后的项目数量
        remaining_count = subtitle_manager.count_projects_by_session(session_id)
        
        return {
            "success": True,
            "message": f"项目清理完成，当前保留 {remaining_count} 个项目"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理项目失败: {str(e)}")