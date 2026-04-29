# Phase 0: 项目初始化与脚手架

> **预计工期**: 2-3 小时 | **前置依赖**: 无 | **下一步**: Phase 1 - Tauri 桌面壳与 Rust 后端

## 目标

搭建完整的前端项目骨架，包括 Tauri 2 应用壳、Vue 3 + TypeScript 前端、路由、状态管理、国际化、UI 组件库，确保 `pnpm tauri dev` 可以正常启动并显示带侧边栏导航的桌面窗口。

## 验证标准

- [ ] `pnpm tauri dev` 成功启动桌面窗口（1400x900）
- [ ] 窗口标题显示"灵境制造"
- [ ] 左侧侧边栏显示 6 个导航项（首页、工作台、三视图生成、工艺规划、设置、关于）
- [ ] 点击导航项可切换页面，URL 正确变化
- [ ] Element Plus 组件正常渲染（按钮、菜单等）
- [ ] 中英文切换功能正常
- [ ] TypeScript 编译无报错
- [ ] `pnpm vitest run` 测试通过

---

## 步骤概览

| 步骤 | 内容 |
|------|------|
| 1 | 创建 Tauri 项目 |
| 2 | 安装前端依赖 |
| 3 | 配置 Tauri |
| 4 | 配置 Tauri 权限 |
| 5 | 创建前端目录结构 |
| 6 | 配置 TypeScript 路径别名 |
| 7 | 配置 Vite |
| 8 | 配置 Vue Router |
| 9 | 配置 Pinia 状态管理 |
| 10 | 配置国际化（i18n） |
| 11 | 更新 main.ts（应用入口） |
| 12 | 创建根组件 App.vue |
| 13 | 创建布局组件 |
| 14 | 创建页面视图 |
| 15 | 更新 index.html |
| 16 | 添加基础测试 |
| 17 | 更新 package.json scripts |

---

## 步骤 1：创建 Tauri 项目

```bash
pnpm create tauri-app lingjing-v4 --template vue-ts
cd lingjing-v4
```

## 步骤 2：安装前端依赖

```bash
# 核心依赖
pnpm add pinia pinia-plugin-persistedstate vue-router@4 axios element-plus @element-plus/icons-vue three vue-i18n@9

# 开发依赖
pnpm add -D vitest @vue/test-utils happy-dom @types/three sass unplugin-auto-import unplugin-vue-components
```

## 步骤 3-17：详细配置

详细配置请参考源文档 [灵境制造V4_TraeCode开发指南_完整版.md](./灵境制造V4_TraeCode开发指南_完整版.md) 第 219-2026 行。

主要内容包括：
- Tauri 配置 (`tauri.conf.json`)
- TypeScript 配置 (`tsconfig.json`)
- Vite 配置 (`vite.config.ts`)
- Vue Router 配置 (`src/router/index.ts`)
- Pinia 状态管理 (`src/stores/`)
- 国际化配置 (`src/i18n/`)
- 布局组件 (`AppLayout.vue`, `Sidebar.vue`, `AppHeader.vue`)
- 页面视图 (`Home.vue`, `Workspace.vue`, `MultiViewTo3D.vue`, `ProcessPlan.vue`, `Settings.vue`, `About.vue`)

---

## 验证清单

1. **项目结构验证**：确认所有目录和文件已正确创建
2. **编译验证**：执行 `pnpm build`，确认无 TypeScript 编译错误
3. **测试验证**：执行 `pnpm test`，确认所有测试通过
4. **启动验证**：执行 `pnpm tauri dev`，确认：
   - 桌面窗口正常启动
   - 窗口大小为 1400x900
   - 窗口标题包含"灵境制造"
   - 左侧深色侧边栏显示 6 个导航项
   - 点击导航项可切换页面
   - Element Plus 组件正常渲染

---

## 相关文档

- [全局上下文](../01-全局上下文.md)
- [Phase 1 - Tauri 桌面壳与 Rust 后端](../03-Phase1-Tauri桌面壳与Rust后端.md)
