#!/usr/bin/env python3
"""
用户管理模块 - Admin后台用户管理功能
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from collections import defaultdict
import asyncio

# 导入现有的用户活动数据
from admin import user_activities, system_stats

# 创建路由器
user_router = APIRouter(prefix="/admin/users", tags=["用户管理"])

class UserManager:
    """用户管理器"""
    
    def __init__(self):
        self.users_dir = Path("user_data")
        self.users_dir.mkdir(exist_ok=True)
    
    def get_all_users(self, page: int = 1, per_page: int = 20, sort_by: str = "last_activity", 
                     order: str = "desc", status_filter: str = "all", user_type_filter: str = "all") -> Dict:
        """
        获取所有用户列表
        
        Args:
            page: 页码
            per_page: 每页数量
            sort_by: 排序字段 (last_activity, first_seen, total_requests, api_calls_count)
            order: 排序方向 (asc, desc)
            status_filter: 状态筛选 (all, online, offline)
            user_type_filter: 用户类型筛选 (all, normal, temporary, other)
        """
        users = []
        current_time = datetime.now()
        
        # 如果用户活动数据为空，从项目数据中推断用户
        if not user_activities:
            users = self._infer_users_from_projects()
        else:
            users = self._get_users_from_activities(current_time)
        
        # 状态筛选
        if status_filter == "online":
            users = [u for u in users if u["status"] == "online"]
        elif status_filter == "offline":
            users = [u for u in users if u["status"] == "offline"]
        
        # 用户类型筛选
        if user_type_filter != "all":
            users = [u for u in users if u["user_type"] == user_type_filter]
        
        # 排序
        reverse = (order == "desc")
        if sort_by == "last_activity":
            users.sort(key=lambda x: x["last_activity"], reverse=reverse)
        elif sort_by == "first_seen":
            users.sort(key=lambda x: x["first_seen"], reverse=reverse)
        elif sort_by == "total_requests":
            users.sort(key=lambda x: x["total_requests"], reverse=reverse)
        elif sort_by == "api_calls_count":
            users.sort(key=lambda x: x["api_calls_count"], reverse=reverse)
        elif sort_by == "projects_count":
            users.sort(key=lambda x: x["projects_count"], reverse=reverse)
        
        # 分页
        total_count = len(users)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_users = users[start_idx:end_idx]
        
        # 统计信息
        total_users = len(users)
        online_users = sum(1 for u in users if u["status"] == "online")
        offline_users = total_users - online_users
        normal_users = sum(1 for u in users if u["user_type"] == "normal")
        temporary_users = sum(1 for u in users if u["user_type"] == "temporary")
        
        return {
            "users": page_users,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            },
            "statistics": {
                "total_users": total_users,
                "online_users": online_users,
                "offline_users": offline_users,
                "normal_users": normal_users,
                "temporary_users": temporary_users,
                "total_requests": sum(u["total_requests"] for u in users),
                "avg_requests_per_user": round(sum(u["total_requests"] for u in users) / max(total_users, 1), 2)
            }
        }
    
    def get_user_detail(self, client_id: str) -> Optional[Dict]:
        """获取用户详细信息"""
        if client_id not in user_activities:
            return None
        
        activity = user_activities[client_id]
        current_time = datetime.now()
        last_activity = activity.get("last_activity", current_time)
        first_seen = activity.get("first_seen", current_time)
        
        return {
            "client_id": client_id,
            "user_type": self._determine_user_type(client_id),
            "is_online": (current_time - last_activity) < timedelta(minutes=5),
            "first_seen": first_seen.isoformat(),
            "last_activity": last_activity.isoformat(),
            "total_requests": activity.get("total_requests", 0),
            "api_calls": dict(activity.get("api_calls", {})),
            "group_id": activity.get("group_id", ""),
            "session_duration": self._calculate_session_duration(first_seen, last_activity),
            "projects": self._get_user_projects(client_id),
            "activity_timeline": self._get_user_activity_timeline(client_id)
        }
    
    def get_user_statistics(self) -> Dict:
        """获取用户统计信息"""
        current_time = datetime.now()
        
        # 按用户类型统计
        user_types = {"normal": 0, "temporary": 0, "other": 0}
        
        # 按在线状态统计
        online_count = 0
        
        # 按活动时间统计
        activity_stats = {
            "today": 0,
            "this_week": 0,
            "this_month": 0
        }
        
        for client_id, activity in user_activities.items():
            # 用户类型统计
            user_type = self._determine_user_type(client_id)
            if user_type in user_types:
                user_types[user_type] += 1
            
            # 在线状态统计
            last_activity = activity.get("last_activity", current_time)
            if (current_time - last_activity) < timedelta(minutes=5):
                online_count += 1
            
            # 活动时间统计
            if (current_time - last_activity) < timedelta(days=1):
                activity_stats["today"] += 1
            if (current_time - last_activity) < timedelta(days=7):
                activity_stats["this_week"] += 1
            if (current_time - last_activity) < timedelta(days=30):
                activity_stats["this_month"] += 1
        
        return {
            "total_users": len(user_activities),
            "online_users": online_count,
            "user_types": user_types,
            "activity_stats": activity_stats,
            "top_apis": self._get_top_api_endpoints(),
            "peak_hours": self._analyze_peak_hours()
        }
    
    def _determine_user_type(self, client_id: str) -> str:
        """确定用户类型"""
        if client_id.startswith("parse_"):
            return "temporary"
        elif client_id.startswith("client_"):
            return "normal"
        else:
            return "other"
    
    def _calculate_session_duration(self, first_seen: datetime, last_activity: datetime) -> int:
        """计算会话时长（分钟）"""
        duration = last_activity - first_seen
        return int(duration.total_seconds() / 60)
    
    def _count_user_projects(self, client_id: str) -> int:
        """统计用户项目数量"""
        try:
            from subtitle_manager import subtitle_manager
            projects = subtitle_manager.list_projects()
            return len([p for p in projects if p.get("client_id") == client_id])
        except:
            return 0
    
    def _get_user_projects(self, client_id: str) -> List[Dict]:
        """获取用户项目列表"""
        try:
            from subtitle_manager import subtitle_manager
            projects = subtitle_manager.list_projects()
            user_projects = [p for p in projects if p.get("client_id") == client_id]
            return user_projects[:10]  # 限制返回最近10个项目
        except:
            return []
    
    def _get_user_activity_timeline(self, client_id: str) -> List[Dict]:
        """获取用户活动时间线（模拟数据，实际需要日志系统支持）"""
        # 这里返回基于API调用的简化时间线
        activity = user_activities.get(client_id, {})
        api_calls = activity.get("api_calls", {})
        
        timeline = []
        for api_endpoint, count in api_calls.items():
            timeline.append({
                "action": f"调用 {api_endpoint}",
                "count": count,
                "type": "api_call"
            })
        
        return timeline
    
    def _get_top_api_endpoints(self) -> List[Dict]:
        """获取最常用的API端点"""
        api_stats = system_stats.get("api_calls", {})
        sorted_apis = sorted(api_stats.items(), key=lambda x: x[1], reverse=True)
        return [{"endpoint": api, "calls": count} for api, count in sorted_apis[:10]]
    
    def _analyze_peak_hours(self) -> List[Dict]:
        """分析用户活跃时段（简化版本）"""
        # 这里返回模拟数据，实际需要详细的时间戳分析
        return [
            {"hour": hour, "active_users": max(0, 10 - abs(hour - 14))}
            for hour in range(24)
        ]
    
    def _infer_users_from_projects(self) -> List[Dict]:
        """从项目数据中推断用户列表"""
        users = []
        current_time = datetime.now()
        
        try:
            from pathlib import Path
            projects_dir = Path("projects")
            if not projects_dir.exists():
                return []
            
            user_project_map = {}
            
            # 遍历所有项目文件
            for project_file in projects_dir.glob("*.json"):
                try:
                    with open(project_file, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                    
                    client_id = project_data.get("client_id", "")
                    if not client_id:
                        continue
                    
                    created_at = datetime.fromisoformat(project_data.get("created_at", ""))
                    updated_at = datetime.fromisoformat(project_data.get("updated_at", ""))
                    
                    if client_id not in user_project_map:
                        user_project_map[client_id] = {
                            "first_seen": created_at,
                            "last_activity": updated_at,
                            "projects": [],
                            "total_segments": 0
                        }
                    else:
                        # 更新首次和最后活动时间
                        if created_at < user_project_map[client_id]["first_seen"]:
                            user_project_map[client_id]["first_seen"] = created_at
                        if updated_at > user_project_map[client_id]["last_activity"]:
                            user_project_map[client_id]["last_activity"] = updated_at
                    
                    user_project_map[client_id]["projects"].append({
                        "filename": project_data.get("filename", ""),
                        "total_segments": project_data.get("total_segments", 0),
                        "created_at": created_at.isoformat(),
                        "updated_at": updated_at.isoformat()
                    })
                    user_project_map[client_id]["total_segments"] += project_data.get("total_segments", 0)
                    
                except Exception as e:
                    continue
            
            # 转换为用户列表格式
            for client_id, data in user_project_map.items():
                last_activity = data["last_activity"]
                is_online = (current_time - last_activity) < timedelta(minutes=5)
                
                user_info = {
                    "client_id": client_id,
                    "user_type": self._determine_user_type(client_id),
                    "is_online": is_online,
                    "first_seen": data["first_seen"].isoformat(),
                    "last_activity": last_activity.isoformat(),
                    "total_requests": len(data["projects"]),  # 用项目数作为请求数的近似
                    "api_calls": {"parse_subtitle": len(data["projects"])},  # 推断API调用
                    "api_calls_count": 1,
                    "group_id": "",
                    "session_duration": self._calculate_session_duration(data["first_seen"], last_activity),
                    "status": "online" if is_online else "offline",
                    "projects_count": len(data["projects"]),
                    "last_activity_minutes": int((current_time - last_activity).total_seconds() / 60)
                }
                
                users.append(user_info)
                
        except Exception as e:
            print(f"推断用户数据失败: {e}")
        
        return users
    
    def _get_users_from_activities(self, current_time: datetime) -> List[Dict]:
        """从用户活动数据获取用户列表"""
        users = []
        
        for client_id, activity in user_activities.items():
            try:
                last_activity = activity.get("last_activity", current_time)
                first_seen = activity.get("first_seen", current_time)
                
                # 计算在线状态（5分钟内活动认为在线）
                is_online = (current_time - last_activity) < timedelta(minutes=5)
                
                # 确定用户类型
                user_type = self._determine_user_type(client_id)
                
                # 用户信息
                user_info = {
                    "client_id": client_id,
                    "user_type": user_type,
                    "is_online": is_online,
                    "first_seen": first_seen.isoformat(),
                    "last_activity": last_activity.isoformat(),
                    "total_requests": activity.get("total_requests", 0),
                    "api_calls": dict(activity.get("api_calls", {})),
                    "api_calls_count": len(activity.get("api_calls", {})),
                    "group_id": activity.get("group_id", ""),
                    "session_duration": self._calculate_session_duration(first_seen, last_activity),
                    "status": "online" if is_online else "offline",
                    "projects_count": self._count_user_projects(client_id),
                    "last_activity_minutes": int((current_time - last_activity).total_seconds() / 60)
                }
                
                users.append(user_info)
                
            except Exception as e:
                # 跳过有问题的用户数据
                continue
        
        return users

# 全局用户管理器实例
user_manager = UserManager()

@user_router.get("/", response_class=HTMLResponse)
async def users_page():
    """用户管理页面"""
    with open("admin_modules/templates/users.html", "r", encoding="utf-8") as f:
        return f.read()

@user_router.get("/api/list")
async def get_users_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("last_activity", regex="^(last_activity|first_seen|total_requests|api_calls_count|projects_count)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    status_filter: str = Query("all", regex="^(all|online|offline)$"),
    user_type_filter: str = Query("all", regex="^(all|normal|temporary|other)$")
):
    """获取用户列表API"""
    try:
        # 记录管理员活动
        from admin import record_user_activity
        record_user_activity("admin_user", "view_users")
        
        result = user_manager.get_all_users(page, per_page, sort_by, order, status_filter, user_type_filter)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户列表失败: {str(e)}")

@user_router.get("/api/detail/{client_id}")
async def get_user_detail(client_id: str):
    """获取用户详情API"""
    user_detail = user_manager.get_user_detail(client_id)
    
    if user_detail is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {"success": True, "data": user_detail}

@user_router.get("/api/statistics")
async def get_user_statistics():
    """获取用户统计信息API"""
    try:
        result = user_manager.get_user_statistics()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户统计失败: {str(e)}")