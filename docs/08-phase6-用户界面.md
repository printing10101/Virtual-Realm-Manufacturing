# Phase 6: 用户界面（全部页面完善）

> **预计工期**: 8-10 小时 | **前置依赖**: Phase 4, Phase 5 | **下一步**: Phase 7 - 数据持久化

## 目标

完善所有前端页面，实现完整的用户界面体验，包括全局样式、布局组件、首页、工作台、三视图生成、工艺规划、设置、关于等页面。

## 验证标准

- [ ] 全局样式和主题配置完整
- [ ] AppLayout 布局组件正常工作
- [ ] 首页展示欢迎信息和快速入口
- [ ] 工作台支持文件管理和 3D 查看
- [ ] 三视图生成页面完整功能
- [ ] 工艺规划页面完整功能
- [ ] 设置页面完整功能
- [ ] 关于页面展示版本信息

---

## 页面列表

| 页面 | 路由 | 组件 |
|------|------|------|
| 首页 | `/` | Home.vue |
| 工作台 | `/workspace` | Workspace.vue |
| 三视图生成 | `/multi-view-to-3d` | MultiViewTo3D.vue |
| 工艺规划 | `/process-plan` | ProcessPlan.vue |
| 设置 | `/settings` | Settings.vue |
| 关于 | `/about` | About.vue |

---

## 布局组件

### AppLayout.vue

主布局组件，包含：
- 左侧 Sidebar 导航
- 顶部 Header 标题栏
- 主内容区域
- 底部状态栏（可选）

### Sidebar.vue

侧边栏组件：
- Logo 区域
- 导航菜单项
- 折叠/展开功能
- 语言切换

### AppHeader.vue

顶部栏组件：
- 当前页面标题
- 操作按钮区域

---

## 全局样式

### CSS 变量

```css
:root {
  --lj-primary: #409eff;
  --lj-bg: #f5f7fa;
  --lj-bg-dark: #1a1a2e;
  --lj-text: #303133;
  --lj-sidebar-width: 220px;
  --lj-header-height: 56px;
}
```

---

## 验证清单

1. 所有页面组件完整实现
2. 路由切换正常
3. Element Plus 组件正常渲染
4. 深色/浅色主题切换正常
5. 响应式布局适配

---

## 相关文档

- [Phase 5 - AI 工作流](../07-Phase5-AI工作流.md)
- [Phase 7 - 数据持久化](../09-Phase7-数据持久化.md)
