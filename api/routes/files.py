# -*- coding: utf-8 -*-
"""
文件管理路由
包含样例文件和输出文件的管理功能
"""
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse

from config import Config

router = APIRouter()

@router.get("/api/sample-files")
async def get_sample_files():
    """获取样例文件列表"""
    valid_files = []

    for file_info in Config.SAMPLE_FILES:
        file_path = Config.BASE_DIR / file_info["path"]
        if file_path.exists():
            valid_files.append({
                "name": file_info["name"],
                "description": file_info["description"],
                "size": file_path.stat().st_size,
                "url": f"/api/sample-files/{file_info['name']}"
            })
        else:
            print(f"⚠️ 样例文件不存在: {file_path}")

    return {"files": valid_files}

@router.get("/api/sample-files/{filename}")
async def download_sample_file(filename: str):
    """下载样例文件"""
    # 查找对应的文件信息
    file_info = None
    for sample in Config.SAMPLE_FILES:
        if sample["name"] == filename:
            file_info = sample
            break

    if not file_info:
        raise HTTPException(status_code=404, detail="样例文件不存在")

    file_path = Config.BASE_DIR / file_info["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件未找到")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="text/plain"
    )

@router.get("/api/outputs")
async def list_output_files():
    """列出输出文件"""
    try:
        output_files = []
        if Config.OUTPUT_DIR.exists():
            for file_path in Config.OUTPUT_DIR.glob("*.mp3"):
                stat = file_path.stat()
                output_files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "url": f"/outputs/{file_path.name}"
                })

        # 按创建时间降序排序
        output_files.sort(key=lambda x: x["created"], reverse=True)

        return {"files": output_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

@router.delete("/api/outputs/{filename}")
async def delete_output_file(filename: str):
    """删除输出文件"""
    try:
        file_path = Config.OUTPUT_DIR / filename

        # 安全检查
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")

        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="不是有效的文件")

        # 检查文件扩展名
        if not file_path.suffix.lower() in ['.mp3', '.wav']:
            raise HTTPException(status_code=400, detail="只能删除音频文件")

        file_path.unlink()
        return {"success": True, "message": f"文件 {filename} 已删除"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@router.post("/api/test-upload")
async def test_upload(
    file: UploadFile = File(...),
    groupId: str = Form(...),
    apiKey: str = Form(...)
):
    """测试文件上传功能"""
    print(f"🔥 TEST: 收到测试请求")
    print(f"🔥 TEST: 文件名: {file.filename}")
    print(f"🔥 TEST: Group ID: {groupId}")
    print(f"🔥 TEST: API Key: {apiKey}")

    content = await file.read()
    print(f"🔥 TEST: 文件大小: {len(content)} 字节")

    return {
        "success": True,
        "filename": file.filename,
        "size": len(content),
        "groupId": groupId,
        "apiKey": apiKey[:3] + "***"
    }