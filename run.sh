#!/bin/bash
# FastAPI 多人配音服务启动脚本

echo "🚀 启动 MiniMax TTS 翻译服务..."

# 检查 Python 版本
python_cmd="python3"
if ! command -v $python_cmd &> /dev/null; then
    python_cmd="python"
    if ! command -v $python_cmd &> /dev/null; then
        echo "❌ 错误: 未找到 Python 解释器"
        exit 1
    fi
fi

echo "🐍 使用 Python: $python_cmd"

# 检查依赖
echo "📦 检查依赖..."
$python_cmd -c "import fastapi, uvicorn, aiofiles, aiohttp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  警告: 某些依赖可能缺失，尝试安装..."
    $python_cmd -m pip install -r requirements.txt
fi

# 启动服务
echo "🎵 启动配音服务..."
$python_cmd start.py