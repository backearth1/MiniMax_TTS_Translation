# 🚀 快速启动指南

## 一键启动

```bash
# 克隆项目
git clone https://github.com/backearth1/MiniMax_TTS_Translation.git
cd MiniMax_TTS_Translation

# 安装依赖
pip install -r requirements.txt

# 启动服务（自动创建所需目录）
python3 start.py
# 或者使用启动脚本
./run.sh
```

## 访问服务

- **主界面**: http://localhost:5215
- **API文档**: http://localhost:5215/docs
- **管理面板**: http://localhost:5215/admin/dashboard

## 必要配置

1. **MiniMax API**：在界面中配置您的 Group ID 和 API Key
2. **选择语言**：选择翻译目标语言
3. **上传字幕**：上传 SRT 格式字幕文件

## 功能特性

- ✅ **中断功能**：点击日志区的"中断"按钮随时停止操作
- ✅ **进度保存**：中断时自动保存已完成的工作
- ✅ **批量处理**：支持批量翻译和TTS生成
- ✅ **一键流程**：自动执行翻译→TTS→合并音频

## 项目结构

```
MiniMax_TTS_Translation/
├── main.py              # 主程序
├── start.py             # 启动脚本（自动创建目录）
├── run.sh               # Bash启动脚本
├── config.py            # 配置文件
├── uploads/             # 上传文件目录（自动创建）
├── outputs/             # 输出音频目录（自动创建）
├── audio_files/         # TTS音频文件（自动创建）
├── temp_audio/          # 临时音频文件（自动创建）
├── samples/             # 示例文件
└── static/              # 前端文件
```

## 注意事项

- 所有必要目录会在启动时自动创建
- 如果遇到权限问题，请确保有创建文件夹的权限
- 建议使用 Python 3.8+ 版本