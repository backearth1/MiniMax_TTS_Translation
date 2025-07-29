"""
FastAPI 管理员监控页面
提供用户使用情况监控、系统统计等功能
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import asyncio
from collections import defaultdict
import psutil
import os
from pathlib import Path

# 导入配置
from config import Config
from utils.logger import get_process_logger

# 创建路由器
admin_router = APIRouter(prefix="/admin", tags=["管理员"])

# 全局变量存储用户活动数据
user_activities = defaultdict(dict)
system_stats = {
    "start_time": datetime.now(),
    "total_requests": 0,
    "active_users": set(),
    "api_calls": defaultdict(int)
}

# 用户数量限制
MAX_ONLINE_USERS = 10

@admin_router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """管理员仪表板页面"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>管理员监控面板</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                text-align: center;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                transition: transform 0.2s;
            }
            .stat-card:hover {
                transform: translateY(-2px);
            }
            .stat-title {
                font-size: 14px;
                color: #666;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .stat-value {
                font-size: 32px;
                font-weight: bold;
                color: #333;
                margin-bottom: 5px;
            }
            .stat-change {
                font-size: 12px;
                color: #28a745;
            }
            .users-section {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .users-title {
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 15px;
                color: #333;
            }
            .user-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            .user-item:last-child {
                border-bottom: none;
            }
            .user-info {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .user-avatar {
                width: 40px;
                height: 40px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
            }
            .user-details h4 {
                margin: 0;
                color: #333;
            }
            .user-details p {
                margin: 0;
                color: #666;
                font-size: 12px;
            }
            .user-status {
                padding: 5px 10px;
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
            }
            .status-online {
                background: #d4edda;
                color: #155724;
            }
            .status-offline {
                background: #f8d7da;
                color: #721c24;
            }
            .api-stats {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .api-title {
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 15px;
                color: #333;
            }
            .api-item {
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #eee;
            }
            .api-item:last-child {
                border-bottom: none;
            }
            .refresh-btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
                margin-bottom: 20px;
            }
            .refresh-btn:hover {
                opacity: 0.9;
            }
            .loading {
                text-align: center;
                padding: 20px;
                color: #666;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 管理员监控面板</h1>
                <p>实时监控系统运行状态和用户活动</p>
            </div>
            
            <button class="refresh-btn" onclick="refreshData()">🔄 刷新数据</button>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-title">在线用户</div>
                    <div class="stat-value" id="online-users">-</div>
                    <div class="stat-change">实时更新</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">总请求数</div>
                    <div class="stat-value" id="total-requests">-</div>
                    <div class="stat-change">累计统计</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">系统运行时间</div>
                    <div class="stat-value" id="uptime">-</div>
                    <div class="stat-change">自动计算</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">CPU 使用率</div>
                    <div class="stat-value" id="cpu-usage">-</div>
                    <div class="stat-change">实时监控</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">内存使用率</div>
                    <div class="stat-value" id="memory-usage">-</div>
                    <div class="stat-change">实时监控</div>
                </div>
                <div class="stat-card">
                    <div class="stat-title">磁盘使用率</div>
                    <div class="stat-value" id="disk-usage">-</div>
                    <div class="stat-change">实时监控</div>
                </div>
            </div>
            
            <div class="users-section">
                <div class="users-title">👥 活跃用户</div>
                <div id="users-list">
                    <div class="loading">加载中...</div>
                </div>
            </div>
            
            <div class="api-stats">
                <div class="api-title">📊 API 调用统计</div>
                <div id="api-stats-list">
                    <div class="loading">加载中...</div>
                </div>
            </div>
        </div>
        
        <script>
            // 刷新数据
            async function refreshData() {
                try {
                    // 获取系统统计
                    const statsResponse = await fetch('/admin/api/system-stats');
                    const stats = await statsResponse.json();
                    
                    // 更新统计卡片
                    document.getElementById('online-users').textContent = stats.online_users;
                    document.getElementById('total-requests').textContent = stats.total_requests;
                    document.getElementById('uptime').textContent = stats.uptime;
                    document.getElementById('cpu-usage').textContent = stats.cpu_usage + '%';
                    document.getElementById('memory-usage').textContent = stats.memory_usage + '%';
                    document.getElementById('disk-usage').textContent = stats.disk_usage + '%';
                    
                    // 获取在线用户
                    const usersResponse = await fetch('/admin/api/online-users');
                    const users = await usersResponse.json();
                    
                    // 更新用户列表
                    const usersList = document.getElementById('users-list');
                    if (users.length === 0) {
                        usersList.innerHTML = '<div class="loading">暂无活跃用户</div>';
                    } else {
                        usersList.innerHTML = users.map(user => `
                            <div class="user-item">
                                <div class="user-info">
                                    <div class="user-avatar">${user.client_id.charAt(0).toUpperCase()}</div>
                                    <div class="user-details">
                                        <h4>${user.client_id}</h4>
                                        <p>Group ID: ${user.group_id}</p>
                                        <p>最后活动: ${user.last_activity}</p>
                                    </div>
                                </div>
                                <div class="user-status status-online">在线</div>
                            </div>
                        `).join('');
                    }
                    
                    // 获取API统计
                    const apiResponse = await fetch('/admin/api/api-stats');
                    const apiStats = await apiResponse.json();
                    
                    // 更新API统计
                    const apiStatsList = document.getElementById('api-stats-list');
                    apiStatsList.innerHTML = Object.entries(apiStats).map(([api, count]) => `
                        <div class="api-item">
                            <span>${api}</span>
                            <span>${count} 次</span>
                        </div>
                    `).join('');
                    
                } catch (error) {
                    console.error('刷新数据失败:', error);
                }
            }
            
            // 页面加载时刷新数据
            document.addEventListener('DOMContentLoaded', refreshData);
            
            // 每30秒自动刷新
            setInterval(refreshData, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@admin_router.get("/api/system-stats")
async def get_system_stats():
    """获取系统统计信息"""
    try:
        # 计算运行时间
        uptime = datetime.now() - system_stats["start_time"]
        uptime_str = f"{uptime.days}天 {uptime.seconds // 3600}小时 {(uptime.seconds % 3600) // 60}分钟"
        
        # 获取系统资源使用情况
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "online_users": len(system_stats["active_users"]),
            "total_requests": system_stats["total_requests"],
            "uptime": uptime_str,
            "cpu_usage": round(cpu_usage, 1),
            "memory_usage": round(memory.percent, 1),
            "disk_usage": round(disk.percent, 1),
            "memory_total": f"{memory.total // (1024**3):.1f}GB",
            "memory_used": f"{memory.used // (1024**3):.1f}GB",
            "disk_total": f"{disk.total // (1024**3):.1f}GB",
            "disk_used": f"{disk.used // (1024**3):.1f}GB"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统统计失败: {str(e)}")

@admin_router.get("/api/online-users")
async def get_online_users():
    """获取在线用户列表"""
    try:
        current_time = datetime.now()
        online_users = []
        
        for client_id, activity in user_activities.items():
            # 如果用户在过去5分钟内有活动，认为是在线
            if current_time - activity.get("last_activity", current_time) < timedelta(minutes=5):
                online_users.append({
                    "client_id": client_id,
                    "group_id": activity.get("group_id", "未知"),
                    "last_activity": activity.get("last_activity", current_time).strftime("%H:%M:%S"),
                    "total_requests": activity.get("total_requests", 0),
                    "api_calls": activity.get("api_calls", {})
                })
        
        # 按最后活动时间排序
        online_users.sort(key=lambda x: x["last_activity"], reverse=True)
        
        return online_users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取在线用户失败: {str(e)}")

@admin_router.get("/api/api-stats")
async def get_api_stats():
    """获取API调用统计"""
    try:
        return dict(system_stats["api_calls"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取API统计失败: {str(e)}")

@admin_router.get("/api/user-details/{client_id}")
async def get_user_details(client_id: str):
    """获取特定用户的详细信息"""
    try:
        if client_id not in user_activities:
            raise HTTPException(status_code=404, detail="用户未找到")
        
        activity = user_activities[client_id]
        current_time = datetime.now()
        
        return {
            "client_id": client_id,
            "is_online": current_time - activity.get("last_activity", current_time) < timedelta(minutes=5),
            "last_activity": activity.get("last_activity", current_time).isoformat(),
            "total_requests": activity.get("total_requests", 0),
            "api_calls": activity.get("api_calls", {}),
            "first_seen": activity.get("first_seen", current_time).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户详情失败: {str(e)}")

# 工具函数
def record_user_activity(client_id: str, api_endpoint: str = None, group_id: str = None):
    """记录用户活动"""
    current_time = datetime.now()
    
    if client_id not in user_activities:
        user_activities[client_id] = {
            "first_seen": current_time,
            "total_requests": 0,
            "api_calls": defaultdict(int),
            "group_id": group_id
        }
    
    user_activities[client_id]["last_activity"] = current_time
    user_activities[client_id]["total_requests"] += 1
    
    if group_id:
        user_activities[client_id]["group_id"] = group_id
    
    if api_endpoint:
        user_activities[client_id]["api_calls"][api_endpoint] += 1
        system_stats["api_calls"][api_endpoint] += 1
    
    system_stats["total_requests"] += 1
    system_stats["active_users"].add(client_id)

def get_active_users_count():
    """获取活跃用户数量"""
    current_time = datetime.now()
    active_count = 0
    
    for client_id, activity in user_activities.items():
        if current_time - activity.get("last_activity", current_time) < timedelta(minutes=5):
            active_count += 1
    
    return active_count

def check_user_limit():
    """检查用户数量是否超过限制"""
    return get_active_users_count() >= MAX_ONLINE_USERS

def can_accept_new_user():
    """检查是否可以接受新用户"""
    return not check_user_limit()

def cleanup_old_activities():
    """清理过期的用户活动数据（超过24小时）"""
    current_time = datetime.now()
    expired_clients = []
    
    for client_id, activity in user_activities.items():
        if current_time - activity.get("last_activity", current_time) > timedelta(hours=24):
            expired_clients.append(client_id)
    
    for client_id in expired_clients:
        del user_activities[client_id]
        system_stats["active_users"].discard(client_id)

# 定期清理任务
async def cleanup_task():
    """定期清理过期数据"""
    while True:
        try:
            cleanup_old_activities()
            await asyncio.sleep(3600)  # 每小时清理一次
        except Exception as e:
            logger = get_process_logger("admin_cleanup")
            await logger.error("清理过期数据失败", f"错误: {str(e)}")
            await asyncio.sleep(3600)

# 启动清理任务
def start_cleanup_task():
    """启动清理任务"""
    asyncio.create_task(cleanup_task()) 