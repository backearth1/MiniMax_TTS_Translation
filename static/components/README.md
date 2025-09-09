# HTML 组件化结构

此目录包含从 index.html 拆分出来的HTML组件，用于提高代码可维护性。

## 目录结构

- `sections/` - 主要页面区块组件
  - `usage-guide.html` - 使用说明区块
  - `log-display.html` - 日志显示区块
  - `audio-result.html` - 音频结果区块

- `widgets/` - 可复用的小组件
  - `project-panel.html` - 项目管理面板
  - `batch-panel.html` - 批量操作面板

- `modals/` - 模态框组件
  - `add-speaker-modal.html` - 添加说话人模态框

## 使用方式

组件通过JavaScript动态加载，保持向后兼容性：

```javascript
// 加载组件示例
ComponentLoader.load('sections/usage-guide.html', '#usageSection');
```

## 重构原则

1. **渐进式** - 逐步拆分，不破坏现有功能
2. **向后兼容** - 保持现有API和功能不变
3. **可回滚** - 任何时候都可以回到单文件模式