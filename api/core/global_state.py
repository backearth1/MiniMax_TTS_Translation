# -*- coding: utf-8 -*-
"""
全局状态管理
用于在迁移过程中共享main.py的全局变量
"""

class GlobalState:
    """全局状态管理器"""

    def __init__(self):
        self.running_tasks = {}
        self.task_cancellation_flags = {}
        self._initialized = False

    def set_global_state(self, running_tasks: dict, task_cancellation_flags: dict):
        """设置全局状态（从main.py注入）"""
        self.running_tasks = running_tasks
        self.task_cancellation_flags = task_cancellation_flags
        self._initialized = True

    def get_running_tasks(self) -> dict:
        """获取运行中的任务"""
        return self.running_tasks

    def get_task_cancellation_flags(self) -> dict:
        """获取任务取消标志"""
        return self.task_cancellation_flags

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

# 全局实例
global_state = GlobalState()