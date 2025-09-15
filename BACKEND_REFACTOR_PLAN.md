# 后端重构架构设计 (Phase 2.1)

## 🎯 重构目标
- main.py: 2,024行 → ~200行 (90%减少)
- 28个API路由分离到专业模块
- 创建现代化分层架构

## 📊 当前架构分析

### main.py 路由分布 (28个API)
1. **核心服务** (4个): /, /api/health, /api/config, /ws/{client_id}
2. **文件管理** (6个): /api/sample-files, /api/outputs, /api/parse-subtitle, /api/test-upload
3. **项目管理** (3个): /api/projects, /api/subtitle/{project_id}
4. **字幕操作** (8个): segments CRUD, batch operations
5. **音频处理** (7个): TTS generation, audio merging

### 关键文件规模
- main.py: 2,024行 (28个路由 + 业务逻辑)
- audio_processor.py: 1,071行 (3个大类)
- subtitle_manager.py: 501行
- admin.py: 493行

## 🏗️ 新架构设计

### 安全重构原则
1. **渐进式迁移**: 一次移动一个功能模块
2. **向后兼容**: 保持所有现有API不变
3. **双写模式**: 新旧代码同时存在，逐步切换
4. **随时回滚**: 每步都可以安全回退

### 目标目录结构
```
/api/                     # 新的API层
├── __init__.py
├── core/                 # 核心服务
│   ├── __init__.py
│   ├── health.py         # 健康检查
│   ├── websocket.py      # WebSocket处理
│   └── startup.py        # 应用启动逻辑
├── routes/               # API路由层
│   ├── __init__.py
│   ├── file_routes.py    # 文件管理路由
│   ├── project_routes.py # 项目管理路由
│   ├── subtitle_routes.py# 字幕操作路由
│   └── audio_routes.py   # 音频处理路由
├── services/             # 业务逻辑层
│   ├── __init__.py
│   ├── file_service.py   # 文件操作服务
│   ├── project_service.py# 项目管理服务
│   ├── subtitle_service.py# 字幕处理服务
│   ├── tts_service.py    # TTS生成服务
│   └── audio_service.py  # 音频合成服务
├── repositories/         # 数据访问层
│   ├── __init__.py
│   ├── file_repository.py
│   ├── project_repository.py
│   └── cache_manager.py
├── middleware/           # 中间件
│   ├── __init__.py
│   ├── session_middleware.py
│   ├── rate_limiter.py
│   └── error_handler.py
├── config/              # 配置管理
│   ├── __init__.py
│   ├── app_config.py
│   ├── api_config.py
│   └── environments/
│       ├── development.py
│       ├── production.py
│       └── testing.py
└── models/              # 数据模型
    ├── __init__.py
    ├── project.py
    ├── subtitle.py
    └── audio.py
```

## 📋 迁移步骤

### Phase 2.1 - 基础架构 ✅
1. 创建新目录结构
2. 设计接口契约
3. 准备迁移工具

### Phase 2.2 - 路由迁移
1. **Step 1**: 健康检查路由 (最安全)
2. **Step 2**: 文件管理路由 (6个API)
3. **Step 3**: 项目管理路由 (3个API)
4. **Step 4**: 字幕操作路由 (8个API)
5. **Step 5**: 音频处理路由 (7个API)

### Phase 2.3 - 服务层提取
1. 从audio_processor.py提取服务
2. 创建专业服务类
3. 重构业务逻辑

### Phase 2.4 - 数据层优化
1. 统一文件操作
2. 缓存管理
3. 状态管理

### Phase 2.5 - 配置和中间件
1. 环境配置分离
2. 中间件优化
3. 错误处理统一

## 🛡️ 安全机制

### 兼容性保证
- 所有现有API路径保持不变
- 响应格式完全兼容
- 错误处理行为一致

### 回滚机制
- 每个迁移步骤都有独立的git commit
- 功能开关控制新旧代码
- 详细的迁移日志

### 测试策略
- 每步迁移后进行功能测试
- API兼容性验证
- 性能回归测试

## 📈 预期效果

| 指标 | 当前 | 目标 | 改善 |
|------|------|------|------|
| main.py行数 | 2,024 | ~200 | -90% |
| 代码模块化 | 单文件混杂 | 分层架构 | 质的飞跃 |
| 可维护性 | 困难 | 优秀 | 大幅提升 |
| 可测试性 | 复杂 | 简单 | 单元测试友好 |
| 团队协作 | 冲突频繁 | 模块独立 | 并行开发 |

## ⚠️ 风险控制

### 高风险操作
- WebSocket连接处理
- 音频处理流程
- 实时日志系统

### 低风险操作 (优先迁移)
- 健康检查
- 静态文件服务
- 配置读取

### 监控指标
- API响应时间
- 错误率
- 用户会话稳定性