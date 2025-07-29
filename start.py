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

if __name__ == "__main__":
    from main import main
    main() 