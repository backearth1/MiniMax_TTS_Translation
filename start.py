#!/usr/bin/env python3
"""
FastAPI 多人配音服务启动脚本
"""
import sys
import os
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def ensure_directories():
    """确保所有必要的目录存在"""
    print("🔧 检查并创建必要目录...")
    
    # 导入配置
    from config import create_directories
    
    # 创建基础目录
    create_directories()
    
    # 创建其他可能需要的目录
    additional_dirs = [
        current_dir / "audio_files",
        current_dir / "temp_audio",
        current_dir / "__pycache__"
    ]
    
    for directory in additional_dirs:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            print(f"📁 创建目录: {directory}")
    
    print("✅ 目录检查完成")

if __name__ == "__main__":
    # 确保目录存在
    ensure_directories()
    
    # 启动主程序
    from main import main
    main() 