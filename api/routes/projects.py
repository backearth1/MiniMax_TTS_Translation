# -*- coding: utf-8 -*-
"""
项目管理路由
基础项目CRUD操作
"""
from fastapi import APIRouter, HTTPException, Request, Response

# 这里需要导入会话管理和字幕管理器
# 但为了保持兼容性，我们先导入现有的模块
from subtitle_manager import subtitle_manager

router = APIRouter()

def get_or_create_session_id(request: Request, response: Response) -> str:
    """获取或创建会话ID - 与main.py保持一致"""
    import secrets
    from fastapi import Cookie

    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = secrets.token_urlsafe(16)
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=24*3600,  # 24小时
            httponly=True
        )
    return session_id

@router.get("/api/projects")
async def get_projects(request: Request, response: Response):
    """获取当前会话的字幕项目列表"""
    try:
        session_id = get_or_create_session_id(request, response)
        projects = subtitle_manager.list_projects(session_id)
        return {
            "success": True,
            "projects": projects
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")

@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """删除整个字幕项目"""
    try:
        # 删除磁盘文件和内存数据
        success = await subtitle_manager.delete_project_from_disk(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目未找到")

        return {
            "success": True,
            "message": "项目删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除项目失败: {str(e)}")