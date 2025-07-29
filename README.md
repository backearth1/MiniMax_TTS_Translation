# 🎬 FastAPI 多人配音生成器

基于 FastAPI 的智能多人配音 Web 服务，支持实时日志显示、高质量音频生成和字幕管理。

## ✨ 核心功能

- 🎤 **多人配音**: 支持多个角色的语音配置和批量生成
- 🌐 **Web界面**: 响应式设计，支持字幕编辑和实时预览
- 📊 **实时日志**: WebSocket实时日志显示，支持搜索和过滤
- 🎵 **高质量音频**: 基于先进的TTS技术生成高质量音频
- 📁 **字幕管理**: 完整的字幕解析、编辑和导出功能
- 🔄 **翻译功能**: 支持多语言字幕翻译
- 📦 **文件管理**: 支持样例文件下载和输出文件管理
- 🔧 **模块化设计**: 易于扩展和定制

## 🚀 快速开始

### 环境要求

- Python 3.8+
- FFmpeg (用于音频处理)
- 现代浏览器 (支持WebSocket)

### 1. 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd FastAPI.bak

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 方式1: 使用启动脚本 (推荐)
python start.py

# 方式2: 直接运行主程序
python main.py

# 方式3: 使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 访问服务

- **Web界面**: http://localhost:8000
- **字幕编辑器**: http://localhost:8000/subtitle-editor
- **API文档**: http://localhost:8000/docs
- **Redoc文档**: http://localhost:8000/redoc

## 📋 使用指南

### 1. 准备字幕文件

创建或上传 `.srt` 格式的字幕文件，格式如下：

```srt
1
00:00:01,000 --> 00:00:03,500
SPEAKER_00: 这是第一段对话

2
00:00:04,000 --> 00:00:06,500
SPEAKER_01: 这是第二段对话

3
00:00:07,000 --> 00:00:09,500
SPEAKER_02: 这是第三段对话
```

### 2. 配置语音映射

在Web界面中配置每个说话人对应的语音ID：

```json
{
  "SPEAKER_00": "ai_her_04",      // 女声
  "SPEAKER_01": "wumei_yujie",    // 温美语音
  "SPEAKER_02": "uk_oldwoman4",   // 英国老妇人
  "SPEAKER_03": "female-chengshu", // 成熟女声
  "SPEAKER_04": "Serene_Elder"    // 老年声音
}
```

### 3. 生成配音流程

1. **上传字幕文件**: 选择 `.srt` 格式的字幕文件
2. **选择模型**: 选择TTS模型和语言
3. **配置语音映射**: 为每个角色分配语音ID
4. **开始生成**: 点击"开始生成配音"
5. **实时监控**: 通过WebSocket查看实时日志
6. **下载结果**: 下载生成的音频文件

> ⚠️ **重要提示**: 为了优化系统资源，用户在10分钟内无任何操作将被自动重置，相关的字幕项目和音频文件将被清理。请及时保存您需要的文件。

## 🏗️ 项目结构

```
FastAPI.bak/
├── main.py                    # FastAPI主应用
├── config.py                  # 配置文件
├── audio_processor.py         # 音频处理模块
├── subtitle_manager.py        # 字幕管理模块
├── start.py                   # 启动脚本
├── requirements.txt           # Python依赖
├── README.md                 # 项目文档
├── utils/                    # 工具模块
│   ├── __init__.py
│   └── logger.py             # WebSocket日志系统
├── static/                   # 静态文件
│   ├── index.html            # 主页面
│   ├── subtitle-editor.html  # 字幕编辑器
│   ├── css/
│   │   └── style.css         # 样式文件
│   └── js/
│       └── app.js            # 前端JavaScript
├── samples/                  # 样例文件
│   ├── double_life_Chinese.srt
│   ├── double_life_English.srt
│   └── simple_format.srt
├── uploads/                  # 上传目录 (自动创建)
├── outputs/                  # 输出目录 (自动创建)
├── temp_audio/               # 临时音频目录
└── audio_files/              # 音频文件目录
```

## 🔧 API 接口

### 主要端点

#### 音频生成
- `POST /api/generate-audio` - 生成配音
- `POST /api/test-upload` - 测试文件上传

#### 字幕管理
- `POST /api/parse-subtitle` - 解析字幕文件
- `GET /api/projects` - 获取项目列表
- `GET /api/subtitle/{project_id}/segments` - 获取字幕段落
- `PUT /api/subtitle/{project_id}/segment/{segment_id}` - 更新字幕段落
- `POST /api/subtitle/{project_id}/segment` - 添加字幕段落
- `DELETE /api/subtitle/{project_id}/segment/{segment_id}` - 删除字幕段落
- `DELETE /api/projects/{project_id}` - 删除项目
- `GET /api/subtitle/{project_id}/export-srt` - 导出SRT文件

#### 翻译功能
- `POST /api/subtitle/{project_id}/segment/{segment_id}/translate` - 翻译单个段落
- `POST /api/subtitle/{project_id}/batch-translate` - 批量翻译

#### 文件管理
- `GET /api/sample-files` - 获取样例文件列表
- `GET /api/sample-files/{filename}` - 下载样例文件
- `GET /api/outputs` - 列出输出文件
- `DELETE /api/outputs/{filename}` - 删除输出文件

#### 实时通信
- `WS /ws/{client_id}` - WebSocket日志连接
- `GET /api/logs/{client_id}` - 获取日志历史

#### 系统信息
- `GET /api/health` - 健康检查
- `GET /api/config` - 获取配置信息

### 示例请求

#### 生成配音
```bash
curl -X POST "http://localhost:8000/api/generate-audio" \
  -F "file=@subtitle.srt" \
  -F "groupId=your_group_id" \
  -F "apiKey=your_api_key" \
  -F "model=speech-02-hd" \
  -F "language=Chinese" \
  -F 'voiceMapping={"SPEAKER_00":"ai_her_04","SPEAKER_01":"wumei_yujie"}' \
  -F "clientId=client_123"
```

#### 解析字幕
```bash
curl -X POST "http://localhost:8000/api/parse-subtitle" \
  -F "file=@subtitle.srt"
```

## ⚙️ 配置说明

### 服务器配置 (config.py)

```python
# 服务器配置
HOST = "0.0.0.0"
PORT = 8000
DEBUG = True

# 目录配置
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
SAMPLES_DIR = BASE_DIR / "samples"
STATIC_DIR = BASE_DIR / "static"
```

### 音频配置

```python
AUDIO_CONFIG = {
    "sample_rate": 32000,                    # 采样率
    "batch_size": 20,                        # 批处理大小
    "max_file_size": 10 * 1024 * 1024,      # 最大文件大小 (10MB)
    "supported_formats": [".srt", ".txt"],   # 支持的格式
    "ffmpeg_path": "ffmpeg"                  # FFmpeg路径
}
```

### TTS配置

```python
TTS_CONFIG = {
    "default_model": "speech-02-hd",         # 默认模型
    "default_language": "Chinese",           # 默认语言
    "max_text_length": 1000,                 # 最大文本长度
    "timeout": 30,                           # 超时时间
    "supported_languages": [                 # 支持的语言
        "Chinese", "English", "Japanese", "Korean", ...
    ]
}
```

### 翻译配置

```python
TRANSLATION_CONFIG = {
    "model": "MiniMax-Text-01",             # 翻译模型
    "temperature": 0.01,                     # 温度参数
    "top_p": 0.95,                          # Top-p参数
    "timeout": 30,                           # 超时时间
    "max_retries": 3,                        # 最大重试次数
    "translation_delay": 2                   # 翻译间隔（秒）
}
```

## 🎯 功能特性对比

| 特性 | 当前版本 | 优势 |
|------|----------|------|
| **后端技术** | Python + FastAPI | 高性能、类型安全、自动文档 |
| **WebSocket** | 原生WebSocket | 轻量级、低延迟 |
| **字幕管理** | 完整CRUD操作 | 支持编辑、翻译、导出 |
| **音频处理** | pydub + librosa | 高质量音频处理 |
| **实时日志** | WebSocket + 搜索过滤 | 实时监控、易于调试 |
| **翻译功能** | MiniMax API集成 | 多语言支持、智能优化 |

## 🔍 实时日志功能

### 特性
- 📡 **WebSocket连接**: 自动重连机制，断线重连
- 🔍 **日志搜索**: 实时搜索日志内容，支持关键词过滤
- 🏷️ **分类过滤**: 按日志类型过滤 (错误/警告/成功/信息)
- 🎨 **语法高亮**: 数字、时间戳、URL等关键信息高亮显示
- 📊 **进度显示**: 实时显示处理进度和状态
- 📱 **响应式设计**: 支持移动端和桌面端

### 日志类型
- `INFO`: 一般信息
- `SUCCESS`: 成功操作
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `PROGRESS`: 进度信息

## 🛠️ 扩展和定制

### 添加新的TTS服务

1. 修改 `audio_processor.py` 中的 `TTSService` 类
2. 实现实际的API调用逻辑
3. 配置API密钥和端点
4. 添加错误处理和重试机制

### 自定义语音配置

在 `config.py` 中修改 `VOICE_MAPPING` 配置：

```python
VOICE_MAPPING = {
    "SPEAKER_00": "your_voice_id_1",
    "SPEAKER_01": "your_voice_id_2",
    "SPEAKER_02": "your_voice_id_3",
    # 添加更多语音映射
}
```

### 添加新的翻译服务

1. 在 `main.py` 中添加新的翻译函数
2. 实现翻译API调用
3. 添加语言检测和优化功能

## 🚨 注意事项

1. **API密钥**: 需要配置有效的TTS和翻译API密钥
2. **文件大小**: 默认限制10MB，可在配置中调整
3. **并发处理**: 支持多客户端同时使用，注意资源管理
4. **资源清理**: 系统会自动清理临时文件，定期清理输出目录
5. **网络连接**: 确保服务器能够访问TTS和翻译API

## 📈 性能优化建议

1. **异步处理**: 所有I/O操作都是异步的，提高并发性能
2. **内存管理**: 及时清理临时文件和音频数据，避免内存泄漏
3. **缓存策略**: 可添加Redis缓存常用音频和翻译结果
4. **负载均衡**: 使用Nginx反向代理处理静态文件和负载均衡
5. **数据库**: 考虑使用数据库存储项目信息和字幕数据
6. **CDN**: 使用CDN加速静态文件访问

## 🆘 常见问题

### Q: 无法连接WebSocket
A: 检查防火墙设置，确保8000端口可访问，检查浏览器控制台错误信息

### Q: 音频生成失败
A: 检查字幕文件格式，确保包含SPEAKER标识，检查API密钥配置

### Q: 依赖安装失败
A: 使用虚拟环境，更新pip到最新版本，确保Python版本兼容

### Q: FFmpeg相关错误
A: 确保系统已安装FFmpeg，并添加到PATH环境变量

### Q: 翻译功能不工作
A: 检查翻译API密钥配置，确保网络连接正常

## 📞 技术支持

### 调试方法
1. 查看控制台日志输出
2. 使用WebSocket实时日志监控
3. 查看API文档 (http://localhost:8000/docs)
4. 检查浏览器开发者工具

### 日志位置
- 应用日志: 控制台输出
- 实时日志: WebSocket连接
- 错误日志: 浏览器控制台

---

**FastAPI多人配音生成器** - 让AI配音更简单！ 🎭✨

*版本: 2.0.0 | 最后更新: 2024年* 