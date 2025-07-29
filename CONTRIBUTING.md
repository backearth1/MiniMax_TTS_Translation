# 贡献指南

感谢您对 FastAPI 多人配音生成器项目的关注！我们欢迎所有形式的贡献。

## 🤝 如何贡献

### 报告问题 (Issues)

如果您发现了bug或有新功能建议，请：

1. 检查 [现有Issues](https://github.com/your-username/fastapi-voice-generator/issues) 是否已有相似问题
2. 如果没有，请创建新Issue，包含：
   - 清晰的标题和描述
   - 重现步骤（如果是bug）
   - 期望的行为
   - 实际的行为
   - 系统环境信息（Python版本、操作系统等）
   - 相关的错误日志或截图

### 提交代码 (Pull Requests)

1. **Fork 项目**
   ```bash
   git clone https://github.com/your-username/fastapi-voice-generator.git
   cd fastapi-voice-generator
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/amazing-feature
   # 或
   git checkout -b fix/bug-fix
   ```

3. **设置开发环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或 venv\Scripts\activate  # Windows
   
   pip install -r requirements.txt
   ```

4. **进行开发**
   - 确保代码风格一致
   - 添加必要的注释
   - 编写测试（如果适用）

5. **测试您的更改**
   ```bash
   # 启动服务测试
   python start.py
   
   # 访问 http://localhost:8000 测试功能
   ```

6. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   # 或
   git commit -m "fix: resolve bug in audio processing"
   ```

7. **推送到您的Fork**
   ```bash
   git push origin feature/amazing-feature
   ```

8. **创建 Pull Request**
   - 访问 GitHub 仓库
   - 点击 "New Pull Request"
   - 填写详细的描述

## 📝 代码规范

### Python 代码风格

- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/) 规范
- 使用 4 个空格缩进
- 行长度不超过 88 字符
- 使用有意义的变量和函数名

### 提交信息规范

使用约定式提交格式：

```
<类型>(<范围>): <描述>

[可选的正文]

[可选的脚注]
```

类型包括：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 重构代码
- `test`: 添加测试
- `chore`: 构建过程或辅助工具变动

示例：
```
feat(audio): add batch processing for TTS generation
fix(websocket): resolve connection timeout issue
docs(readme): update installation instructions
```

### 文件组织

- 新功能应放在适当的模块中
- 保持文件结构清晰
- 添加必要的注释和文档字符串

## 🧪 测试

### 手动测试

1. **基础功能测试**
   - 上传字幕文件
   - 配置语音映射
   - 生成配音
   - 下载音频

2. **WebSocket 测试**
   - 实时日志显示
   - 连接断开重连
   - 多客户端同时使用

3. **管理员功能测试**
   - 访问管理员面板
   - 查看系统状态
   - 用户活动监控

### 添加自动化测试

如果您要添加测试，请：

1. 在 `tests/` 目录下创建测试文件
2. 使用 pytest 框架
3. 确保测试覆盖主要功能

```python
# tests/test_audio_processor.py
import pytest
from audio_processor import AudioProcessor

def test_audio_generation():
    # 测试音频生成功能
    pass
```

## 🐛 调试指南

### 常见问题排查

1. **WebSocket 连接问题**
   - 检查浏览器控制台
   - 确认端口没有被占用
   - 检查防火墙设置

2. **音频生成失败**
   - 验证 API 密钥配置
   - 检查字幕文件格式
   - 查看后端日志输出

3. **依赖安装问题**
   - 确保 Python 版本兼容
   - 使用虚拟环境
   - 检查网络连接

### 日志和调试

- 启用详细日志：在 `config.py` 中设置 `DEBUG = True`
- 查看实时日志：使用 WebSocket 连接
- 检查文件权限：确保输出目录可写

## 🔄 开发工作流

1. **选择Issue**：从 [Issues 列表](https://github.com/your-username/fastapi-voice-generator/issues) 选择感兴趣的问题

2. **讨论方案**：在Issue中讨论实现方案

3. **开始开发**：Fork 项目并开始编码

4. **定期同步**：定期从主仓库拉取最新更改
   ```bash
   git remote add upstream https://github.com/original-owner/fastapi-voice-generator.git
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

5. **提交PR**：完成开发后提交 Pull Request

## 🎯 优先级功能

目前我们特别欢迎以下方面的贡献：

- **性能优化**：提高音频处理速度
- **用户体验**：改进前端界面和交互
- **错误处理**：增强错误恢复机制
- **文档完善**：补充使用说明和示例
- **国际化**：支持多语言界面
- **测试覆盖**：添加自动化测试

## 📞 联系我们

如果您有任何问题或需要帮助：

- 📧 邮箱：your-email@example.com
- 💬 GitHub Issues：[提交问题](https://github.com/your-username/fastapi-voice-generator/issues)
- 📖 Wiki：[项目文档](https://github.com/your-username/fastapi-voice-generator/wiki)

## 🙏 致谢

感谢所有为项目做出贡献的开发者！您的贡献让这个项目变得更好。

---

**让我们一起构建更好的 AI 配音工具！** 🎭✨ 