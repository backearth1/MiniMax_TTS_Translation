# -*- coding: utf-8 -*-
"""
WebSocket和日志路由
保持原始日志格式，不做任何总结或修改
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse

# 导入全局状态变量和日志系统
from utils.logger import websocket_logger, get_process_logger

router = APIRouter()

# 全局状态管理器 - 将由main.py注入
class GlobalStateManager:
    def __init__(self):
        self.running_tasks = {}
        self.task_cancellation_flags = {}

    def set_global_state(self, running_tasks, task_cancellation_flags):
        """设置全局状态"""
        self.running_tasks = running_tasks
        self.task_cancellation_flags = task_cancellation_flags

# 全局实例
global_state = GlobalStateManager()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket 连接处理"""
    try:
        await websocket_logger.connect(websocket, client_id)

        # 保持连接
        while True:
            try:
                # 等待客户端消息 (ping/pong)
                data = await websocket.receive_text()

                # 可以处理客户端发送的消息
                if data == "ping":
                    await websocket.send_text("pong")

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket 错误: {e}")
                break

    except Exception as e:
        print(f"WebSocket 连接错误: {e}")
    finally:
        websocket_logger.disconnect(client_id)

@router.get("/api/logs/{client_id}")
async def get_logs(client_id: str):
    """获取指定客户端的日志 - 保持原始格式"""
    try:
        logger = get_process_logger(client_id)

        # 获取最新的日志条目 - 保持原始日志，不做任何总结
        logs = logger.get_recent_logs(50)  # 获取最近50条日志

        return logs  # 直接返回日志数组，前端期望这种格式
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")

@router.post("/api/interrupt/{client_id}")
async def interrupt_task(client_id: str):
    """中断指定客户端的当前任务"""
    try:
        # 设置中断标志
        global_state.task_cancellation_flags[client_id] = True

        # 记录中断日志 - 保持原始日志格式
        logger = get_process_logger(client_id)
        await logger.warning("用户请求中断", "正在尝试中断当前任务...")

        # 如果有正在运行的任务，尝试取消
        if client_id in global_state.running_tasks:
            task = global_state.running_tasks[client_id]
            if not task.done():
                task.cancel()
                await logger.info("任务中断", "已发送任务取消信号")
            else:
                await logger.info("任务状态", "任务已完成，无需中断")
        else:
            await logger.info("任务状态", "没有找到正在运行的任务")

        return {
            "success": True,
            "message": "中断请求已发送",
            "client_id": client_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"中断失败: {str(e)}",
            "client_id": client_id
        }

@router.get("/api/task-status/{client_id}")
async def get_task_status(client_id: str):
    """获取指定客户端的任务状态"""
    try:
        is_running = client_id in global_state.running_tasks and not global_state.running_tasks[client_id].done()
        is_cancelled = global_state.task_cancellation_flags.get(client_id, False)

        return {
            "success": True,
            "client_id": client_id,
            "is_running": is_running,
            "is_cancelled": is_cancelled
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取任务状态失败: {str(e)}",
            "client_id": client_id
        }

@router.get("/test-logs")
async def test_logs():
    """日志测试页面"""
    return FileResponse("test_logs.html")