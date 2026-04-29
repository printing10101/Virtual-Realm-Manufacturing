# 灵境制造 V4 — Trae Code 全流程开发指南

> **文档版本**: v1.1（集成论文成果）
> **更新日期**: 2026-04-28
> **目标**: 使用 Trae Code 模式从零构建商业化桌面应用，最终上架微软商店
> **适用团队**: 2-5 人小团队
> **预计工期**: 16-20 周（分 9 个 Phase）

---

## 文档目录

- [文档使用说明](#文档使用说明)
- [全局上下文（所有 Phase 共享）](#全局上下文所有-phase-共享)
  - [产品定位](#产品定位)
  - [技术架构](#技术架构)
  - [技术栈](#技术栈)
  - [隐私设计原则](#隐私设计原则)
  - [AI 模型路由策略](#ai-模型路由策略)
  - [项目目录结构](#项目目录结构)
- [Phase 总览](#phase-总览)
- [Phase 0: 项目初始化与脚手架](#phase-0-项目初始化与脚手架)
- [Phase 1: Tauri 桌面壳与 Rust 后端](#phase-1-tauri-桌面壳与-rust-后端)
- [Phase 2: Python AI 后端（Sidecar）](#phase-2-python-ai-后端sidecar)
- [Phase 3: 本地 LLM 集成（Ollama）](#phase-3-本地-llm-集成ollama)
- [Phase 4: 3D/CAD 引擎](#phase-43dcad-引擎)
- [Phase 5: PhyCo-Agent 架构（论文成果集成）](#phase-5-phyco-agent-架构论文成果集成)
- [Phase 6: 用户界面（全部页面完善）](#phase-6-用户界面全部页面完善)
- [Phase 7: 数据持久化与设置系统](#phase-7-数据持久化与设置系统)
- [Phase 8: 测试、打包与微软商店发布](#phase-8-测试打包与微软商店发布)
- [Phase 9: 高级特性（论文完整实现预留）](#phase-9-高级特性论文完整实现预留)
- [附录](#附录)
  - [A. 常见问题排查](#a-常见问题排查)
  - [B. Trae Code 使用技巧](#b-trae-code-使用技巧)
  - [C. 后续扩展方向](#c-后续扩展方向)

---


## 文档使用说明

本文档专为 **Trae Code 模式** 设计。每个 Phase 都是一个独立的、可直接粘贴到 Trae Code 对话框的完整 Prompt。按顺序执行即可完成整个项目搭建。

**执行方式**：
1. 打开 Trae Code 模式
2. 复制对应 Phase 的完整 Prompt（包括 `---PROMPT START---` 和 `---PROMPT END---` 之间的所有内容）
3. 粘贴到 Trae Code 对话框并执行
4. 等待完成后，验证输出，再进入下一个 Phase

**重要约定**：
- 每个 Prompt 都是自包含的，包含所有必要的上下文
- 每个 Phase 结束时会生成验证清单
- 如果某个 Phase 执行失败，修复后重新执行该 Phase 即可

---

## 全局上下文（所有 Phase 共享）

以下是项目的核心设计决策，所有 Phase 的 Prompt 都基于这些决策：

### 产品定位

- **名称**: 灵境制造 (LingJing Manufacturing)
- **定位**: 面向制造行业的 AI 驱动 3D 模型生成与工艺管理桌面应用
- **核心卖点**: 数据不出本地设备，AI 全流程辅助（三视图→3D→工艺→NC代码）
- **目标平台**: Windows（首发），后续扩展 macOS/Linux
- **分发渠道**: 微软商店 + 官网直接下载

### 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                   Tauri 2 桌面应用壳                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Vue 3 前端 (WebView2)                 │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │  │
│  │  │ 3D 查看 │ │ 工作台  │ │ 设置页  │ │ 模型库 │ │  │
│  │  │ Three.js│ │         │ │         │ │        │ │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Rust 后端 (Tauri Core)                │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │  │
│  │  │ 文件系统│ │ 进程管理│ │ 窗口控制│ │ 自动更新│ │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │          Python Sidecar (FastAPI)                  │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │  │
│  │  │ AI 引擎 │ │ CAD 引擎│ │ RAG 知识│ │ 任务队列│ │  │
│  │  │ (Agent) │ │(CadQuery)│ │  库     │ │(Celery)│ │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │          Ollama Sidecar (本地 LLM)                 │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 桌面框架 | Tauri 2 | 2.10+ |
| 前端框架 | Vue 3 + TypeScript | 3.5+ |
| 构建工具 | Vite | 6.x |
| 状态管理 | Pinia | 2.x |
| UI 组件库 | Element Plus | 2.9+ |
| 3D 渲染 | Three.js | 0.170+ |
| 桌面后端 | Rust (Tauri Core) | stable-msvc |
| AI 后端 | Python + FastAPI | 3.11+ |
| 任务队列 | Celery + Redis | 5.x / 7.x |
| 本地 LLM | Ollama (sidecar) | latest |
| 向量数据库 | ChromaDB | 0.4+ |
| 数据库 | SQLite (本地) | 内置 |
| 桌面打包 | PyInstaller | 6.x |

### 隐私设计原则

**核心原则：数据不出本地设备**

1. **默认本地模式**：所有 AI 推理默认使用本地 Ollama，无需联网
2. **可选云端模式**：用户可自行配置云端 API（OpenAI/DeepSeek 等），但必须满足：
   - 用户显式同意并配置 API Key
   - CAD 设计文件、专有工艺参数等敏感数据**永不上传**
   - 仅非敏感的文本查询允许走云端
   - 每次云端调用前显示数据预览和确认
3. **完全离线模式**：提供开关，关闭所有网络请求
4. **数据存储**：所有用户数据存储在本地 `%APPDATA%/lingjing/` 目录
5. **无遥测**：不收集任何用户行为数据，无遥测

### AI 模型路由策略

```
用户请求
    │
    ├── 敏感操作（CAD 文件分析、工艺参数生成）
    │   └── 强制本地 Ollama（即使配置了云端也不上传）
    │
    ├── 一般操作（文本理解、文档查询）
    │   ├── 用户选择"本地" → Ollama
    │   └── 用户选择"云端" → 云端 API（需确认）
    │
    └── 离线模式
        └── 仅 Ollama（不可用时降级为规则引擎）
```

### 项目目录结构

```
lingjing-v4/
├── src/                          # Vue 3 前端源码
│   ├── main.ts                   # 应用入口
│   ├── App.vue                   # 根组件
│   ├── components/               # 通用组件
│   │   ├── layout/               # 布局组件
│   │   ├── three/                # 3D 相关组件
│   │   └── common/               # 通用 UI 组件
│   ├── views/                    # 页面视图
│   │   ├── Home.vue              # 首页/模型库
│   │   ├── Workspace.vue         # 工作台
│   │   ├── MultiViewTo3D.vue     # 三视图生成
│   │   ├── ProcessPlan.vue       # 工艺规划
│   │   ├── Settings.vue          # 设置页
│   │   └── About.vue             # 关于页
│   ├── stores/                   # Pinia 状态管理
│   ├── composables/              # Vue Composables
│   ├── services/                 # API 调用封装
│   ├── utils/                    # 工具函数
│   ├── types/                    # TypeScript 类型定义
│   ├── i18n/                     # 国际化
│   └── assets/                   # 静态资源
├── src-tauri/                    # Tauri/Rust 后端
│   ├── Cargo.toml
│   ├── tauri.conf.json           # Tauri 主配置
│   ├── capabilities/             # 权限配置
│   ├── binaries/                 # Sidecar 二进制
│   └── src/
│       ├── main.rs               # 入口
│       └── lib.rs                # Rust 命令
├── python/                       # Python AI 后端
│   ├── app/
│   │   ├── main.py               # FastAPI 入口
│   │   ├── ai/                   # AI Agent 模块
│   │   ├── cad/                  # CAD 引擎模块
│   │   ├── rag/                  # RAG 知识库模块
│   │   ├── core/                 # 核心工具
│   │   └── models/               # 数据模型
│   ├── requirements.txt
│   └── pyproject.toml
├── public/                       # 前端静态资源
├── tests/                        # 测试
├── docs/                         # 文档
├── package.json
├── tsconfig.json
├── vite.config.ts
└── index.html
```

---

## Phase 总览

| Phase | 名称 | 预计耗时 | 依赖 |
|-------|------|---------|------|
| 0 | 项目初始化与脚手架 | 2-3 小时 | 无 |
| 1 | Tauri 桌面壳与 Rust 后端 | 3-4 小时 | Phase 0 |
| 2 | Python AI 后端（Sidecar） | 4-5 小时 | Phase 1 |
| 3 | 本地 LLM 集成（Ollama） | 3-4 小时 | Phase 2 |
| 4 | 3D/CAD 引擎 | 5-6 小时 | Phase 2 |
| 5 | PhyCo-Agent 架构（论文成果集成） | 6-8 小时 | Phase 3 |
| 6 | 用户界面（全部页面） | 8-10 小时 | Phase 4, 5 |
| 7 | 数据持久化与设置系统 | 3-4 小时 | Phase 6 |
| 8 | 测试、打包与微软商店发布 | 4-6 小时 | Phase 7 |
| 9 | 高级特性（论文完整实现预留） | 后续迭代 | Phase 5 |

---

## Phase 0: 项目初始化与脚手架

### 目标

搭建完整的前端项目骨架，包括 Tauri 2 应用壳、Vue 3 + TypeScript 前端、路由、状态管理、国际化、UI 组件库，确保 `pnpm tauri dev` 可以正常启动并显示带侧边栏导航的桌面窗口。

### 验证标准

- [ ] `pnpm tauri dev` 成功启动桌面窗口（1400x900）
- [ ] 窗口标题显示"灵境制造"
- [ ] 左侧侧边栏显示 6 个导航项（首页、工作台、三视图生成、工艺规划、设置、关于）
- [ ] 点击导航项可切换页面，URL 正确变化
- [ ] Element Plus 组件正常渲染（按钮、菜单等）
- [ ] 中英文切换功能正常
- [ ] TypeScript 编译无报错
- [ ] `pnpm vitest run` 测试通过

---

---PROMPT START---

## 任务：初始化灵境制造 V4 项目（Phase 0）

你是一个资深全栈工程师。请按照以下步骤，从零搭建一个 Tauri 2 + Vue 3 + TypeScript 桌面应用项目。项目名称为"灵境制造"（LingJing Manufacturing），面向制造行业。

### 重要约定
- 所有注释使用中文
- 代码风格遵循 Vue 3 Composition API + `<script setup lang="ts">`
- 使用 pnpm 作为包管理器
- 项目根目录名为 `lingjing-v4`

---

### 步骤 1：创建 Tauri 项目

在当前目录下执行：

```bash
pnpm create tauri-app lingjing-v4 --template vue-ts
```

如果交互式命令不可用，请手动创建项目结构。

进入项目目录：

```bash
cd lingjing-v4
```

---

### 步骤 2：安装前端依赖

```bash
# 核心依赖
pnpm add pinia pinia-plugin-persistedstate vue-router@4 axios element-plus @element-plus/icons-vue three vue-i18n@9

# 开发依赖
pnpm add -D vitest @vue/test-utils happy-dom @types/three sass unplugin-auto-import unplugin-vue-components
```

---

### 步骤 3：配置 Tauri

修改 `src-tauri/tauri.conf.json`：

```json
{
  "$schema": "https://raw.githubusercontent.com/nicehash/Tauri/dev/crates/tauri-cli/schema.json",
  "productName": "灵境制造",
  "version": "4.0.0",
  "identifier": "com.lingjing.manufacturing",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "pnpm dev",
    "beforeBuildCommand": "pnpm build"
  },
  "app": {
    "title": "灵境制造",
    "windows": [
      {
        "title": "灵境制造 - AI驱动3D模型生成与工艺管理",
        "width": 1400,
        "height": 900,
        "minWidth": 1024,
        "minHeight": 680,
        "resizable": true,
        "center": true,
        "decorations": true,
        "fullscreen": false
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "windows": {
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "timestampUrl": "",
      "wix": {
        "language": "zh-CN"
      }
    }
  }
}
```

---

### 步骤 4：配置 Tauri 权限

创建 `src-tauri/capabilities/default.json`：

```json
{
  "identifier": "default",
  "description": "默认权限配置 - 灵境制造桌面应用",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "shell:allow-open",
    "shell:allow-execute",
    "shell:allow-spawn",
    "shell:allow-kill",
    "fs:default",
    "fs:allow-app-data-read-recursive",
    "fs:allow-app-data-write-recursive",
    "fs:allow-app-cache-read-recursive",
    "fs:allow-app-cache-write-recursive",
    "dialog:default",
    "dialog:allow-open",
    "dialog:allow-save",
    "dialog:allow-message",
    "dialog:allow-ask",
    "dialog:allow-confirm",
    "path:default",
    "os:default",
    "process:default",
    "updater:default",
    "opener:default"
  ]
}
```

---

### 步骤 5：创建前端目录结构

请创建以下目录结构（空目录用 `.gitkeep` 占位）：

```
src/
├── components/
│   ├── layout/          # 布局组件
│   │   └── .gitkeep
│   ├── three/           # 3D 相关组件
│   │   └── .gitkeep
│   └── common/          # 通用 UI 组件
│       └── .gitkeep
├── views/               # 页面视图
│   └── .gitkeep
├── stores/              # Pinia 状态管理
│   └── .gitkeep
├── composables/         # Vue Composables
│   └── .gitkeep
├── services/            # API 调用封装
│   └── .gitkeep
├── utils/               # 工具函数
│   └── .gitkeep
├── types/               # TypeScript 类型定义
│   └── .gitkeep
├── i18n/                # 国际化
│   └── .gitkeep
└── assets/              # 静态资源
    └── .gitkeep
```

---

### 步骤 6：配置 TypeScript 路径别名

修改 `tsconfig.json`：

```json
{
  "compilerOptions": {
    "target": "ES2021",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2021", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "preserve",
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "types": ["vitest/globals"]
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue", "env.d.ts"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

修改 `tsconfig.app.json`：

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo"
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue", "env.d.ts"]
}
```

修改 `tsconfig.node.json`：

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

---

### 步骤 7：配置 Vite

修改 `vite.config.ts`：

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需自动导入
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router', 'pinia'],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  // 开发服务器配置
  server: {
    port: 1420,
    strictPort: true,
  },
  // 构建配置
  build: {
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: true,
  },
  // 测试配置
  test: {
    globals: true,
    environment: 'happy-dom',
  },
})
```

---

### 步骤 8：配置 Vue Router

创建 `src/router/index.ts`：

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

/**
 * 路由配置
 * 灵境制造 V4 - 共 6 个主要页面
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: {
      title: '首页',
      icon: 'HomeFilled',
    },
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('@/views/Workspace.vue'),
    meta: {
      title: '工作台',
      icon: 'Monitor',
    },
  },
  {
    path: '/multi-view-to-3d',
    name: 'MultiViewTo3D',
    component: () => import('@/views/MultiViewTo3D.vue'),
    meta: {
      title: '三视图生成',
      icon: 'PictureFilled',
    },
  },
  {
    path: '/process-plan',
    name: 'ProcessPlan',
    component: () => import('@/views/ProcessPlan.vue'),
    meta: {
      title: '工艺规划',
      icon: 'List',
    },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: {
      title: '设置',
      icon: 'Setting',
    },
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('@/views/About.vue'),
    meta: {
      title: '关于',
      icon: 'InfoFilled',
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫 - 更新页面标题
router.beforeEach((to, _from, next) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} - 灵境制造` : '灵境制造'
  next()
})

export default router
```

---

### 步骤 9：配置 Pinia 状态管理

创建 `src/stores/index.ts`：

```typescript
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

/**
 * Pinia 状态管理实例
 * 集成 persistedstate 插件实现状态持久化
 */
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

export default pinia
```

创建 `src/stores/app.ts`：

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 应用全局状态
 * 管理侧边栏折叠、语言、主题等全局 UI 状态
 */
export const useAppStore = defineStore(
  'app',
  () => {
    // 侧边栏是否折叠
    const sidebarCollapsed = ref(false)

    // 当前语言
    const locale = ref<'zh-CN' | 'en'>('zh-CN')

    // 当前主题
    const theme = ref<'light' | 'dark'>('light')

    // 计算属性：是否为中文
    const isZhCN = computed(() => locale.value === 'zh-CN')

    // 切换侧边栏
    function toggleSidebar() {
      sidebarCollapsed.value = !sidebarCollapsed.value
    }

    // 切换语言
    function setLocale(lang: 'zh-CN' | 'en') {
      locale.value = lang
    }

    // 切换主题
    function setTheme(t: 'light' | 'dark') {
      theme.value = t
    }

    return {
      sidebarCollapsed,
      locale,
      theme,
      isZhCN,
      toggleSidebar,
      setLocale,
      setTheme,
    }
  },
  {
    persist: {
      pick: ['locale', 'theme', 'sidebarCollapsed'],
    },
  }
)
```

---

### 步骤 10：配置国际化（i18n）

创建 `src/i18n/index.ts`：

```typescript
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import en from './locales/en'

/**
 * 国际化配置
 * 默认语言：简体中文
 * 支持语言：zh-CN, en
 */
const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    en: en,
  },
})

export default i18n
```

创建 `src/i18n/locales/zh-CN.ts`：

```typescript
export default {
  common: {
    confirm: '确认',
    cancel: '取消',
    save: '保存',
    delete: '删除',
    edit: '编辑',
    add: '添加',
    search: '搜索',
    loading: '加载中...',
    success: '操作成功',
    error: '操作失败',
    warning: '警告',
    info: '提示',
    back: '返回',
    close: '关闭',
    refresh: '刷新',
    export: '导出',
    import: '导入',
    upload: '上传',
    download: '下载',
  },
  nav: {
    home: '首页',
    workspace: '工作台',
    multiViewTo3D: '三视图生成',
    processPlan: '工艺规划',
    settings: '设置',
    about: '关于',
  },
  home: {
    title: '欢迎使用灵境制造',
    subtitle: 'AI 驱动的 3D 模型生成与工艺管理系统',
    description: '数据不出本地设备，AI 全流程辅助制造',
    quickStart: '快速开始',
    recentProjects: '最近项目',
    newProject: '新建项目',
  },
  workspace: {
    title: '工作台',
    modelLibrary: '模型库',
    processManagement: '工艺管理',
    ncCode: 'NC 代码',
  },
  multiViewTo3D: {
    title: '三视图生成 3D 模型',
    uploadViews: '上传三视图',
    frontView: '主视图',
    topView: '俯视图',
    sideView: '侧视图',
    generate: '生成 3D 模型',
    generating: '生成中...',
  },
  processPlan: {
    title: '工艺规划',
    generateRoute: '生成工艺路线',
    processSteps: '工序步骤',
    parameters: '工艺参数',
  },
  settings: {
    title: '设置',
    general: '通用设置',
    aiSettings: 'AI 设置',
    language: '语言',
    theme: '主题',
    localModel: '本地模型',
    cloudApi: '云端 API',
    offlineMode: '离线模式',
  },
  about: {
    title: '关于',
    version: '版本',
    description: '灵境制造是一款面向制造行业的 AI 驱动桌面应用，提供从三视图到 3D 模型、从工艺规划到 NC 代码的全流程智能化解决方案。',
    privacy: '隐私承诺',
    privacyText: '所有数据均存储在本地设备，不会上传至任何云端服务器。',
  },
}
```

创建 `src/i18n/locales/en.ts`：

```typescript
export default {
  common: {
    confirm: 'Confirm',
    cancel: 'Cancel',
    save: 'Save',
    delete: 'Delete',
    edit: 'Edit',
    add: 'Add',
    search: 'Search',
    loading: 'Loading...',
    success: 'Success',
    error: 'Error',
    warning: 'Warning',
    info: 'Info',
    back: 'Back',
    close: 'Close',
    refresh: 'Refresh',
    export: 'Export',
    import: 'Import',
    upload: 'Upload',
    download: 'Download',
  },
  nav: {
    home: 'Home',
    workspace: 'Workspace',
    multiViewTo3D: '3D from Views',
    processPlan: 'Process Plan',
    settings: 'Settings',
    about: 'About',
  },
  home: {
    title: 'Welcome to LingJing Manufacturing',
    subtitle: 'AI-Driven 3D Model Generation & Process Management',
    description: 'All data stays on your local device, AI-assisted manufacturing',
    quickStart: 'Quick Start',
    recentProjects: 'Recent Projects',
    newProject: 'New Project',
  },
  workspace: {
    title: 'Workspace',
    modelLibrary: 'Model Library',
    processManagement: 'Process Management',
    ncCode: 'NC Code',
  },
  multiViewTo3D: {
    title: 'Generate 3D from Three Views',
    uploadViews: 'Upload Three Views',
    frontView: 'Front View',
    topView: 'Top View',
    sideView: 'Side View',
    generate: 'Generate 3D Model',
    generating: 'Generating...',
  },
  processPlan: {
    title: 'Process Planning',
    generateRoute: 'Generate Process Route',
    processSteps: 'Process Steps',
    parameters: 'Process Parameters',
  },
  settings: {
    title: 'Settings',
    general: 'General',
    aiSettings: 'AI Settings',
    language: 'Language',
    theme: 'Theme',
    localModel: 'Local Model',
    cloudApi: 'Cloud API',
    offlineMode: 'Offline Mode',
  },
  about: {
    title: 'About',
    version: 'Version',
    description: 'LingJing Manufacturing is an AI-driven desktop application for the manufacturing industry, providing intelligent solutions from three-view drawings to 3D models, from process planning to NC code.',
    privacy: 'Privacy Commitment',
    privacyText: 'All data is stored on your local device and will never be uploaded to any cloud server.',
  },
}
```

---

### 步骤 11：更新 main.ts（应用入口）

修改 `src/main.ts`：

```typescript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'

import App from './App.vue'
import router from './router'
import pinia from './stores'
import i18n from './i18n'

import './assets/styles/global.scss'

/**
 * 灵境制造 V4 应用入口
 * 集成 Element Plus、Vue Router、Pinia、i18n
 */
const app = createApp(App)

// 注册全局插件
app.use(pinia)
app.use(router)
app.use(i18n)

// 注册 Element Plus（全量引入，后续可优化为按需引入）
app.use(ElementPlus, {
  // 根据当前语言动态切换 Element Plus 语言包
  locale: i18n.global.locale.value === 'zh-CN' ? zhCn : en,
})

// 挂载应用
app.mount('#app')
```

创建 `src/assets/styles/global.scss`：

```scss
/* 灵境制造 V4 全局样式 */

/* CSS 变量 */
:root {
  --lj-primary: #409eff;
  --lj-primary-dark: #337ecc;
  --lj-bg: #f5f7fa;
  --lj-bg-dark: #1a1a2e;
  --lj-text: #303133;
  --lj-text-light: #909399;
  --lj-border: #dcdfe6;
  --lj-sidebar-width: 220px;
  --lj-sidebar-collapsed-width: 64px;
  --lj-header-height: 56px;

  /* Element Plus 覆盖 */
  --el-color-primary: var(--lj-primary);
}

/* 暗色主题 */
.dark {
  --lj-bg: var(--lj-bg-dark);
  --lj-text: #e5eaf3;
  --lj-text-light: #a3a6ad;
  --lj-border: #4c4d4f;
}

/* 全局重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
  font-family:
    'Microsoft YaHei',
    'PingFang SC',
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    sans-serif;
  color: var(--lj-text);
  background-color: var(--lj-bg);
}

/* 禁止文本选中（桌面应用体验） */
.no-select {
  user-select: none;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #909399;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from {
  transform: translateX(-20px);
}

.slide-leave-to {
  transform: translateX(20px);
}
```

---

### 步骤 12：创建根组件 App.vue

修改 `src/App.vue`：

```vue
<script setup lang="ts">
/**
 * 灵境制造 V4 根组件
 * 包含侧边栏布局和主内容区域
 */
import AppLayout from '@/components/layout/AppLayout.vue'
</script>

<template>
  <AppLayout />
</template>

<style>
/* 全局样式已在 main.ts 中引入 */
</style>
```

---

### 步骤 13：创建布局组件

创建 `src/components/layout/AppLayout.vue`：

```vue
<script setup lang="ts">
/**
 * 应用主布局组件
 * 左侧固定侧边栏 + 右侧内容区域
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Sidebar from './Sidebar.vue'
import AppHeader from './AppHeader.vue'

const route = useRoute()
const { t } = useI18n()

// 当前页面标题
const pageTitle = computed(() => {
  return t(`nav.${route.name as string}`) || t('nav.home')
})
</script>

<template>
  <el-container class="app-layout">
    <!-- 侧边栏 -->
    <Sidebar />
    <!-- 右侧区域 -->
    <el-container class="main-container">
      <!-- 顶部栏 -->
      <AppHeader :title="pageTitle" />
      <!-- 内容区域 -->
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped lang="scss">
.app-layout {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.main-container {
  flex-direction: column;
  overflow: hidden;
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: var(--lj-bg);
}
</style>
```

创建 `src/components/layout/Sidebar.vue`：

```vue
<script setup lang="ts">
/**
 * 侧边栏导航组件
 * 包含 Logo、导航菜单、语言切换
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import {
  HomeFilled,
  Monitor,
  PictureFilled,
  List,
  Setting,
  InfoFilled,
  Fold,
  Expand,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const appStore = useAppStore()

// 导航菜单项
const menuItems = computed(() => [
  { index: '/', title: t('nav.home'), icon: HomeFilled },
  { index: '/workspace', title: t('nav.workspace'), icon: Monitor },
  { index: '/multi-view-to-3d', title: t('nav.multiViewTo3D'), icon: PictureFilled },
  { index: '/process-plan', title: t('nav.processPlan'), icon: List },
  { index: '/settings', title: t('nav.settings'), icon: Setting },
  { index: '/about', title: t('nav.about'), icon: InfoFilled },
])

// 当前激活的菜单项
const activeMenu = computed(() => route.path)

// 侧边栏宽度
const sidebarWidth = computed(() =>
  appStore.sidebarCollapsed ? 'var(--lj-sidebar-collapsed-width)' : 'var(--lj-sidebar-width)'
)

// 切换侧边栏折叠
function toggleCollapse() {
  appStore.toggleSidebar()
}

// 导航点击
function handleMenuSelect(index: string) {
  router.push(index)
}

// 切换语言
function toggleLanguage() {
  const newLocale = locale.value === 'zh-CN' ? 'en' : 'zh-CN'
  locale.value = newLocale
  appStore.setLocale(newLocale as 'zh-CN' | 'en')
}
</script>

<template>
  <el-aside class="sidebar" :width="sidebarWidth">
    <!-- Logo 区域 -->
    <div class="sidebar-logo">
      <span class="logo-icon">LJ</span>
      <span v-show="!appStore.sidebarCollapsed" class="logo-text">灵境制造</span>
    </div>

    <!-- 导航菜单 -->
    <el-menu
      :default-active="activeMenu"
      :collapse="appStore.sidebarCollapsed"
      :collapse-transition="true"
      class="sidebar-menu"
      @select="handleMenuSelect"
    >
      <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <template #title>{{ item.title }}</template>
      </el-menu-item>
    </el-menu>

    <!-- 底部操作区 -->
    <div class="sidebar-footer">
      <!-- 折叠按钮 -->
      <el-button class="collapse-btn" text @click="toggleCollapse">
        <el-icon :size="18">
          <Fold v-if="!appStore.sidebarCollapsed" />
          <Expand v-else />
        </el-icon>
      </el-button>

      <!-- 语言切换 -->
      <el-button class="lang-btn" text @click="toggleLanguage">
        {{ locale === 'zh-CN' ? 'EN' : '中' }}
      </el-button>
    </div>
  </el-aside>
</template>

<style scoped lang="scss">
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #001529;
  color: #ffffff;
  transition: width 0.3s ease;
  overflow: hidden;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--lj-header-height);
  padding: 0 16px;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  border-radius: 8px;
  font-size: 14px;
  font-weight: bold;
  color: #ffffff;
  flex-shrink: 0;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  background-color: transparent;

  :deep(.el-menu-item) {
    color: rgba(255, 255, 255, 0.7);
    height: 48px;
    line-height: 48px;

    &:hover {
      color: #ffffff;
      background-color: rgba(255, 255, 255, 0.08);
    }

    &.is-active {
      color: #ffffff;
      background-color: var(--lj-primary);
    }
  }
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.collapse-btn,
.lang-btn {
  color: rgba(255, 255, 255, 0.7);

  &:hover {
    color: #ffffff;
  }
}
</style>
```

创建 `src/components/layout/AppHeader.vue`：

```vue
<script setup lang="ts">
/**
 * 顶部栏组件
 * 显示当前页面标题和全局操作
 */
defineProps<{
  title: string
}>()
</script>

<template>
  <el-header class="app-header">
    <div class="header-left">
      <h2 class="page-title">{{ title }}</h2>
    </div>
    <div class="header-right">
      <!-- 后续 Phase 添加更多操作按钮 -->
      <slot name="actions" />
    </div>
  </el-header>
</template>

<style scoped lang="scss">
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--lj-header-height);
  padding: 0 24px;
  background-color: #ffffff;
  border-bottom: 1px solid var(--lj-border);
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--lj-text);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
```

---

### 步骤 14：创建页面视图

创建 `src/views/Home.vue`：

```vue
<script setup lang="ts">
/**
 * 首页视图
 * 展示欢迎信息、快速入口、最近项目
 */
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="home-page">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <h1 class="welcome-title">{{ t('home.title') }}</h1>
      <p class="welcome-subtitle">{{ t('home.subtitle') }}</p>
      <p class="welcome-desc">{{ t('home.description') }}</p>
      <el-button type="primary" size="large">
        {{ t('home.quickStart') }}
      </el-button>
    </div>

    <!-- 最近项目 -->
    <div class="recent-section">
      <h3>{{ t('home.recentProjects') }}</h3>
      <el-empty :description="'暂无项目'" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-section {
  text-align: center;
  padding: 60px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: #ffffff;
  margin-bottom: 32px;
}

.welcome-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 12px;
}

.welcome-subtitle {
  font-size: 18px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.welcome-desc {
  font-size: 14px;
  opacity: 0.7;
  margin-bottom: 24px;
}

.recent-section {
  padding: 24px;
  background-color: #ffffff;
  border-radius: 8px;

  h3 {
    font-size: 18px;
    margin-bottom: 16px;
    color: var(--lj-text);
  }
}
</style>
```

创建 `src/views/Workspace.vue`：

```vue
<script setup lang="ts">
/**
 * 工作台视图
 * 模型管理、工艺管理、NC 代码编辑
 */
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="workspace-page">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>{{ t('workspace.modelLibrary') }}</span>
          </template>
          <el-empty :description="'暂无模型'" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>{{ t('workspace.processManagement') }}</span>
          </template>
          <el-empty :description="'暂无工艺'" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>{{ t('workspace.ncCode') }}</span>
          </template>
          <el-empty :description="'暂无代码'" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.workspace-page {
  max-width: 1400px;
}
</style>
```

创建 `src/views/MultiViewTo3D.vue`：

```vue
<script setup lang="ts">
/**
 * 三视图生成 3D 模型视图
 * 上传三视图图片，AI 生成 3D 模型
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Upload } from '@element-plus/icons-vue'

const { t } = useI18n()

const isGenerating = ref(false)

// 模拟生成操作
async function handleGenerate() {
  isGenerating.value = true
  // 后续 Phase 接入真实 API
  setTimeout(() => {
    isGenerating.value = false
  }, 3000)
}
</script>

<template>
  <div class="multi-view-page">
    <el-row :gutter="20">
      <!-- 三视图上传区域 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>{{ t('multiViewTo3D.uploadViews') }}</span>
          </template>
          <div class="upload-grid">
            <div class="upload-item">
              <el-upload drag :show-file-list="false" accept="image/*">
                <el-icon :size="40"><Upload /></el-icon>
                <div>{{ t('multiViewTo3D.frontView') }}</div>
              </el-upload>
            </div>
            <div class="upload-item">
              <el-upload drag :show-file-list="false" accept="image/*">
                <el-icon :size="40"><Upload /></el-icon>
                <div>{{ t('multiViewTo3D.topView') }}</div>
              </el-upload>
            </div>
            <div class="upload-item">
              <el-upload drag :show-file-list="false" accept="image/*">
                <el-icon :size="40"><Upload /></el-icon>
                <div>{{ t('multiViewTo3D.sideView') }}</div>
              </el-upload>
            </div>
          </div>
          <div class="action-bar">
            <el-button
              type="primary"
              size="large"
              :loading="isGenerating"
              @click="handleGenerate"
            >
              {{ isGenerating ? t('multiViewTo3D.generating') : t('multiViewTo3D.generate') }}
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 3D 预览区域 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>3D 预览</span>
          </template>
          <div class="preview-area">
            <el-empty :description="'等待生成...'" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.upload-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.upload-item {
  :deep(.el-upload) {
    width: 100%;
  }

  :deep(.el-upload-dragger) {
    width: 100%;
    height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
}

.action-bar {
  text-align: center;
}

.preview-area {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f7fa;
  border-radius: 8px;
}
</style>
```

创建 `src/views/ProcessPlan.vue`：

```vue
<script setup lang="ts">
/**
 * 工艺规划视图
 * AI 生成工艺路线和工序步骤
 */
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="process-plan-page">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>{{ t('processPlan.processSteps') }}</span>
          </template>
          <el-empty :description="'请先选择模型'" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>{{ t('processPlan.parameters') }}</span>
          </template>
          <el-empty :description="'暂无参数'" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.process-plan-page {
  max-width: 1400px;
}
</style>
```

创建 `src/views/Settings.vue`：

```vue
<script setup lang="ts">
/**
 * 设置视图
 * 通用设置、AI 设置、语言切换
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'

const { t, locale } = useI18n()
const appStore = useAppStore()

// 当前语言
const currentLocale = computed({
  get: () => locale.value,
  set: (val: string) => {
    locale.value = val
    appStore.setLocale(val as 'zh-CN' | 'en')
  },
})

// 当前主题
const currentTheme = computed({
  get: () => appStore.theme,
  set: (val: 'light' | 'dark') => {
    appStore.setTheme(val)
  },
})
</script>

<template>
  <div class="settings-page">
    <el-form label-width="120px" style="max-width: 600px">
      <!-- 通用设置 -->
      <el-divider>{{ t('settings.general') }}</el-divider>

      <el-form-item :label="t('settings.language')">
        <el-radio-group v-model="currentLocale">
          <el-radio-button value="zh-CN">中文</el-radio-button>
          <el-radio-button value="en">English</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item :label="t('settings.theme')">
        <el-radio-group v-model="currentTheme">
          <el-radio-button value="light">
            {{ $t('common.confirm') === '确认' ? '浅色' : 'Light' }}
          </el-radio-button>
          <el-radio-button value="dark">
            {{ $t('common.confirm') === '确认' ? '深色' : 'Dark' }}
          </el-radio-button>
        </el-radio-group>
      </el-form-item>

      <!-- AI 设置 -->
      <el-divider>{{ t('settings.aiSettings') }}</el-divider>

      <el-form-item :label="t('settings.offlineMode')">
        <el-switch />
      </el-form-item>

      <el-form-item :label="t('settings.localModel')">
        <el-select placeholder="选择本地模型" style="width: 100%">
          <el-option label="Ollama (qwen2.5)" value="ollama-qwen2.5" />
          <el-option label="Ollama (llama3)" value="ollama-llama3" />
        </el-select>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped lang="scss">
.settings-page {
  max-width: 800px;
}
</style>
```

创建 `src/views/About.vue`：

```vue
<script setup lang="ts">
/**
 * 关于页面
 * 显示版本信息、隐私承诺
 */
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="about-page">
    <el-card>
      <div class="about-content">
        <div class="app-icon">LJ</div>
        <h1>灵境制造</h1>
        <p class="version">{{ t('about.version') }}: 4.0.0</p>
        <el-divider />
        <p class="description">{{ t('about.description') }}</p>
        <el-divider />
        <div class="privacy-section">
          <h3>{{ t('about.privacy') }}</h3>
          <p>{{ t('about.privacyText') }}</p>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.about-page {
  max-width: 600px;
  margin: 0 auto;
}

.about-content {
  text-align: center;
  padding: 20px;
}

.app-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  border-radius: 20px;
  font-size: 32px;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 16px;
}

h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.version {
  color: var(--lj-text-light);
  margin-bottom: 16px;
}

.description {
  color: var(--lj-text);
  line-height: 1.8;
  text-align: left;
}

.privacy-section {
  text-align: left;

  h3 {
    margin-bottom: 8px;
    color: var(--lj-text);
  }

  p {
    color: var(--lj-text-light);
    line-height: 1.6;
  }
}
</style>
```

---

### 步骤 15：更新 index.html

修改 `index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>灵境制造</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

---

### 步骤 16：添加基础测试

创建 `tests/setup.ts`：

```typescript
/**
 * 测试全局配置
 */
import { config } from '@vue/test-utils'

// 全局配置 Vue Test Utils
config.global.stubs = {
  // 按需添加全局 stub
}
```

创建 `tests/router.test.ts`：

```typescript
/**
 * 路由配置测试
 */
import { describe, it, expect } from 'vitest'
import routes from '@/router'

describe('路由配置', () => {
  it('应包含 6 个路由', () => {
    expect(routes.length).toBe(6)
  })

  it('应包含首页路由', () => {
    const home = routes.find((r) => r.path === '/')
    expect(home).toBeDefined()
    expect(home?.name).toBe('Home')
  })

  it('应包含工作台路由', () => {
    const workspace = routes.find((r) => r.path === '/workspace')
    expect(workspace).toBeDefined()
    expect(workspace?.name).toBe('Workspace')
  })

  it('应包含三视图生成路由', () => {
    const multiView = routes.find((r) => r.path === '/multi-view-to-3d')
    expect(multiView).toBeDefined()
    expect(multiView?.name).toBe('MultiViewTo3D')
  })

  it('应包含工艺规划路由', () => {
    const processPlan = routes.find((r) => r.path === '/process-plan')
    expect(processPlan).toBeDefined()
    expect(processPlan?.name).toBe('ProcessPlan')
  })

  it('应包含设置路由', () => {
    const settings = routes.find((r) => r.path === '/settings')
    expect(settings).toBeDefined()
    expect(settings?.name).toBe('Settings')
  })

  it('应包含关于路由', () => {
    const about = routes.find((r) => r.path === '/about')
    expect(about).toBeDefined()
    expect(about?.name).toBe('About')
  })

  it('所有路由应使用懒加载', () => {
    routes.forEach((route) => {
      expect(typeof route.component).toBe('function')
    })
  })
})
```

创建 `tests/stores/app.test.ts`：

```typescript
/**
 * App Store 测试
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '@/stores/app'

describe('AppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认语言应为中文', () => {
    const store = useAppStore()
    expect(store.locale).toBe('zh-CN')
  })

  it('默认主题应为浅色', () => {
    const store = useAppStore()
    expect(store.theme).toBe('light')
  })

  it('应能切换侧边栏状态', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('应能切换语言', () => {
    const store = useAppStore()
    store.setLocale('en')
    expect(store.locale).toBe('en')
    expect(store.isZhCN).toBe(false)
    store.setLocale('zh-CN')
    expect(store.locale).toBe('zh-CN')
    expect(store.isZhCN).toBe(true)
  })

  it('应能切换主题', () => {
    const store = useAppStore()
    store.setTheme('dark')
    expect(store.theme).toBe('dark')
    store.setTheme('light')
    expect(store.theme).toBe('light')
  })
})
```

---

### 步骤 17：更新 package.json scripts

确保 `package.json` 中的 scripts 配置如下：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview",
    "tauri": "tauri",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "lint": "eslint . --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --fix"
  }
}
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

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
   - 中英文切换按钮正常工作

如果以上验证全部通过，Phase 0 完成。

---PROMPT END---

---

## Phase 1: Tauri 桌面壳与 Rust 后端

### 目标

实现 Tauri Rust 后端核心功能，包括文件系统操作、Sidecar 进程管理、应用信息查询，并提供前端 TypeScript 类型定义和服务封装层。

### 验证标准

- [ ] `cargo build` 在 `src-tauri/` 目录下编译通过
- [ ] `pnpm tauri dev` 正常启动
- [ ] 前端可调用 `get_app_data_dir` 获取应用数据目录路径
- [ ] 前端可调用 `get_app_info` 获取应用版本信息
- [ ] 前端可调用 `open_external_url` 打开外部链接
- [ ] TypeScript 类型定义完整，无编译错误
- [ ] Tauri 服务封装层可正常导入

---

---PROMPT START---

## 任务：实现 Tauri 桌面壳与 Rust 后端（Phase 1）

你是一个资深 Rust + Tauri 工程师。请在已有的灵境制造 V4 项目（Phase 0 已完成）基础上，实现 Tauri Rust 后端核心功能。

### 重要约定
- 所有注释使用中文
- Rust 代码遵循 Tauri 2 API 规范
- 使用 `#[tauri::command]` 宏注册命令
- 错误处理使用 `Result<T, String>` 格式（Tauri 命令要求）

### 项目信息
- 项目根目录：`lingjing-v4`
- Tauri 配置：`src-tauri/tauri.conf.json`
- 产品名：灵境制造
- Identifier：`com.lingjing.manufacturing`

---

### 步骤 1：添加 Rust 依赖

修改 `src-tauri/Cargo.toml`，在 `[dependencies]` 中添加：

```toml
[package]
name = "lingjing-v4"
version = "4.0.0"
description = "灵境制造 - AI驱动3D模型生成与工艺管理"
authors = ["LingJing Team"]
edition = "2021"

[lib]
name = "lingjing_v4_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
# Tauri 核心
tauri = { version = "2", features = [] }
tauri-plugin-shell = "2"
tauri-plugin-fs = "2"
tauri-plugin-dialog = "2"
tauri-plugin-path = "2"
tauri-plugin-os = "2"
tauri-plugin-process = "2"
tauri-plugin-updater = "2"
tauri-plugin-opener = "2"

# 序列化
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# 异步运行时
tokio = { version = "1", features = ["full"] }

# 文件系统
dirs = "6"

# 时间处理
chrono = { version = "0.4", features = ["serde"] }

# UUID 生成
uuid = { version = "1", features = ["v4", "serde"] }

# 日志
log = "0.4"
env_logger = "0.11"

# 进程管理（用于 sidecar）
shared_child = "1"

# 主机名
hostname = "0.4"
```

---

### 步骤 2：创建 Rust 模块结构

在 `src-tauri/src/` 下创建以下模块结构：

```
src-tauri/src/
├── main.rs           # Tauri 入口
├── lib.rs            # 库入口，注册命令
├── commands/         # Tauri 命令模块
│   ├── mod.rs        # 模块导出
│   ├── file.rs       # 文件系统命令
│   ├── process.rs    # 进程管理命令
│   └── app.rs        # 应用信息命令
└── state/            # 应用状态
    ├── mod.rs        # 模块导出
    └── process_manager.rs  # 进程管理器
```

---

### 步骤 3：实现进程管理器状态

创建 `src-tauri/src/state/mod.rs`：

```rust
//! 应用状态模块
//! 管理 Tauri 应用的全局状态

pub mod process_manager;

use std::sync::Mutex;
use process_manager::ProcessManager;

/// 应用全局状态
/// 包含进程管理器等需要在命令间共享的状态
pub struct AppState {
    /// Sidecar 进程管理器
    pub process_manager: Mutex<ProcessManager>,
}

impl AppState {
    /// 创建新的应用状态
    pub fn new() -> Self {
        Self {
            process_manager: Mutex::new(ProcessManager::new()),
        }
    }
}
```

创建 `src-tauri/src/state/process_manager.rs`：

```rust
//! Sidecar 进程管理器
//! 管理 Python FastAPI 后端进程的生命周期

use shared_child::SharedChild;
use std::process::{Command, Stdio};
use log::{info, warn};

/// Sidecar 进程信息
#[derive(Debug, Clone)]
pub struct ProcessInfo {
    /// 进程 ID
    pub pid: u32,
    /// 进程名称
    pub name: String,
    /// 启动时间
    pub started_at: String,
    /// 端口号
    pub port: u16,
}

/// Sidecar 进程状态
#[derive(Debug, Clone, PartialEq)]
pub enum ProcessStatus {
    /// 未运行
    Stopped,
    /// 正在启动
    Starting,
    /// 运行中
    Running,
    /// 已停止（异常）
    Error(String),
}

/// 进程管理器
/// 负责管理所有 sidecar 进程的启动、停止和状态查询
pub struct ProcessManager {
    /// Python FastAPI 后端进程
    python_process: Option<SharedChild>,
    /// Python 后端状态
    python_status: ProcessStatus,
    /// Python 后端端口
    python_port: u16,
}

impl ProcessManager {
    /// 创建新的进程管理器
    pub fn new() -> Self {
        Self {
            python_process: None,
            python_status: ProcessStatus::Stopped,
            python_port: 8765,
        }
    }

    /// 启动 Python FastAPI 后端
    ///
    /// # 参数
    /// - `sidecar_path`: Python 后端可执行文件路径
    /// - `port`: 监听端口号
    ///
    /// # 返回
    /// 成功返回进程 PID，失败返回错误信息
    pub fn start_python_backend(
        &mut self,
        sidecar_path: &str,
        port: u16,
    ) -> Result<u32, String> {
        // 如果已经在运行，先停止
        if self.python_status == ProcessStatus::Running {
            self.stop_python_backend()?;
        }

        self.python_status = ProcessStatus::Starting;
        self.python_port = port;

        info!("正在启动 Python 后端: {} (端口: {})", sidecar_path, port);

        // 启动 Python 进程
        let child = Command::new(sidecar_path)
            .arg("--port")
            .arg(port.to_string())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("启动 Python 后端失败: {}", e))?
            .into();

        let pid = child.id();
        self.python_process = Some(child);
        self.python_status = ProcessStatus::Running;

        info!("Python 后端已启动, PID: {}", pid);
        Ok(pid)
    }

    /// 停止 Python FastAPI 后端
    pub fn stop_python_backend(&mut self) -> Result<(), String> {
        if let Some(ref child) = self.python_process {
            info!("正在停止 Python 后端 (PID: {})", child.id());

            match child.kill() {
                Ok(_) => {
                    info!("Python 后端已停止");
                }
                Err(e) => {
                    warn!("停止 Python 后端失败（进程可能已退出）: {}", e);
                }
            }
        }

        self.python_process = None;
        self.python_status = ProcessStatus::Stopped;
        Ok(())
    }

    /// 获取 Python 后端状态
    pub fn get_python_status(&self) -> ProcessStatus {
        // 检查进程是否仍然存活
        if let Some(ref child) = self.python_process {
            match child.try_wait() {
                Ok(Some(_status)) => {
                    // 进程已退出
                    return ProcessStatus::Error("进程已意外退出".to_string());
                }
                Ok(None) => {
                    // 进程仍在运行
                    return ProcessStatus::Running;
                }
                Err(_) => {
                    return ProcessStatus::Error("无法查询进程状态".to_string());
                }
            }
        }
        ProcessStatus::Stopped
    }

    /// 获取 Python 后端进程信息
    pub fn get_python_info(&self) -> Option<ProcessInfo> {
        self.python_process.as_ref().map(|child| ProcessInfo {
            pid: child.id(),
            name: "lingjing-python-backend".to_string(),
            started_at: chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            port: self.python_port,
        })
    }

    /// 获取 Python 后端端口
    pub fn get_python_port(&self) -> u16 {
        self.python_port
    }

    /// 设置 Python 后端端口
    pub fn set_python_port(&mut self, port: u16) {
        self.python_port = port;
    }
}
```

---

### 步骤 4：实现文件系统命令

创建 `src-tauri/src/commands/mod.rs`：

```rust
//! Tauri 命令模块
//! 包含所有从前端调用的 Rust 命令

pub mod file;
pub mod process;
pub mod app;
```

创建 `src-tauri/src/commands/file.rs`：

```rust
//! 文件系统命令
//! 提供文件和目录的读写操作

use std::fs;
use std::path::PathBuf;
use serde::{Deserialize, Serialize};
use tauri::State;
use crate::state::AppState;

/// 文件信息
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FileInfo {
    /// 文件名
    pub name: String,
    /// 文件路径
    pub path: String,
    /// 是否为目录
    pub is_dir: bool,
    /// 文件大小（字节）
    pub size: u64,
    /// 最后修改时间
    pub modified_at: String,
    /// 文件扩展名
    pub extension: Option<String>,
}

/// 获取应用数据目录
///
/// 返回应用专属数据存储目录的路径
#[tauri::command]
pub fn get_app_data_dir(app_handle: tauri::AppHandle) -> Result<String, String> {
    let path = app_handle
        .path()
        .app_data_dir()
        .map_err(|e| format!("获取应用数据目录失败: {}", e))?;

    // 确保目录存在
    fs::create_dir_all(&path)
        .map_err(|e| format!("创建应用数据目录失败: {}", e))?;

    Ok(path.to_string_lossy().to_string())
}

/// 保存文件
///
/// # 参数
/// - `file_path`: 文件完整路径
/// - `content`: 文件内容
#[tauri::command]
pub fn save_file(file_path: String, content: String) -> Result<(), String> {
    let path = PathBuf::from(&file_path);

    // 确保父目录存在
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("创建目录失败: {}", e))?;
    }

    fs::write(&path, &content)
        .map_err(|e| format!("保存文件失败: {}", e))?;

    Ok(())
}

/// 读取文件内容
///
/// # 参数
/// - `file_path`: 文件完整路径
///
/// # 返回
/// 文件的文本内容
#[tauri::command]
pub fn read_file(file_path: String) -> Result<String, String> {
    fs::read_to_string(&file_path)
        .map_err(|e| format!("读取文件失败: {}", e))
}

/// 列出目录下的文件
///
/// # 参数
/// - `dir_path`: 目录路径
/// - `extension`: 可选的文件扩展名过滤（如 "json", "stl"）
///
/// # 返回
/// 文件信息列表
#[tauri::command]
pub fn list_files(dir_path: String, extension: Option<String>) -> Result<Vec<FileInfo>, String> {
    let path = PathBuf::from(&dir_path);

    if !path.exists() {
        return Err(format!("目录不存在: {}", dir_path));
    }

    if !path.is_dir() {
        return Err(format!("路径不是目录: {}", dir_path));
    }

    let entries = fs::read_dir(&path)
        .map_err(|e| format!("读取目录失败: {}", e))?;

    let mut files: Vec<FileInfo> = Vec::new();

    for entry in entries {
        let entry = entry.map_err(|e| format!("读取目录条目失败: {}", e))?;
        let metadata = entry.metadata().map_err(|e| format!("读取文件元数据失败: {}", e))?;

        let file_name = entry.file_name().to_string_lossy().to_string();
        let file_path = entry.path().to_string_lossy().to_string();
        let is_dir = metadata.is_dir();
        let size = metadata.len();
        let modified_at = metadata
            .modified()
            .ok()
            .map(|t| {
                let datetime: chrono::DateTime<chrono::Local> = t.into();
                datetime.format("%Y-%m-%d %H:%M:%S").to_string()
            })
            .unwrap_or_default();
        let ext = entry
            .path()
            .extension()
            .map(|e| e.to_string_lossy().to_string());

        // 扩展名过滤
        if let Some(ref filter_ext) = extension {
            if ext.as_ref().map(|e| e.to_lowercase()).as_deref()
                != Some(&filter_ext.to_lowercase())
            {
                continue;
            }
        }

        files.push(FileInfo {
            name: file_name,
            path: file_path,
            is_dir,
            size,
            modified_at,
            extension: ext,
        });
    }

    // 按名称排序，目录在前
    files.sort_by(|a, b| match (a.is_dir, b.is_dir) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a.name.cmp(&b.name),
    });

    Ok(files)
}

/// 删除文件或目录
///
/// # 参数
/// - `file_path`: 文件或目录路径
/// - `recursive`: 是否递归删除目录
#[tauri::command]
pub fn delete_file(file_path: String, recursive: bool) -> Result<(), String> {
    let path = PathBuf::from(&file_path);

    if !path.exists() {
        return Err(format!("文件不存在: {}", file_path));
    }

    if path.is_dir() {
        if recursive {
            fs::remove_dir_all(&path)
                .map_err(|e| format!("删除目录失败: {}", e))?;
        } else {
            fs::remove_dir(&path)
                .map_err(|e| format!("删除目录失败（可能非空）: {}", e))?;
        }
    } else {
        fs::remove_file(&path)
            .map_err(|e| format!("删除文件失败: {}", e))?;
    }

    Ok(())
}

/// 创建目录
///
/// # 参数
/// - `dir_path`: 目录路径
/// - `recursive`: 是否递归创建父目录
#[tauri::command]
pub fn create_directory(dir_path: String, recursive: bool) -> Result<(), String> {
    let path = PathBuf::from(&dir_path);

    if recursive {
        fs::create_dir_all(&path)
            .map_err(|e| format!("创建目录失败: {}", e))?;
    } else {
        fs::create_dir(&path)
            .map_err(|e| format!("创建目录失败: {}", e))?;
    }

    Ok(())
}
```

---

### 步骤 5：实现进程管理命令

创建 `src-tauri/src/commands/process.rs`：

```rust
//! 进程管理命令
//! 管理 Sidecar 进程（Python 后端）的生命周期

use serde::{Deserialize, Serialize};
use tauri::State;
use crate::state::AppState;
use crate::state::process_manager::ProcessStatus;

/// Sidecar 状态响应
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SidecarStatusResponse {
    /// 是否正在运行
    pub is_running: bool,
    /// 状态描述
    pub status: String,
    /// 进程 ID（运行中时）
    pub pid: Option<u32>,
    /// 端口号
    pub port: u16,
    /// 启动时间
    pub started_at: Option<String>,
}

/// 启动 Sidecar（Python 后端）
///
/// # 参数
/// - `port`: 监听端口号，默认 8765
///
/// # 返回
/// 进程 PID
#[tauri::command]
pub fn start_sidecar(
    state: State<'_, AppState>,
    app_handle: tauri::AppHandle,
    port: Option<u16>,
) -> Result<u32, String> {
    let port = port.unwrap_or(8765);

    // 获取 sidecar 可执行文件路径
    let resource_path = app_handle
        .path()
        .resource_dir()
        .map_err(|e| format!("获取资源目录失败: {}", e))?;

    // 根据平台确定 sidecar 路径
    #[cfg(target_os = "windows")]
    let sidecar_path = resource_path.join("lingjing-python-backend.exe");

    #[cfg(not(target_os = "windows"))]
    let sidecar_path = resource_path.join("lingjing-python-backend");

    let sidecar_str = sidecar_path.to_string_lossy().to_string();

    let mut manager = state
        .process_manager
        .lock()
        .map_err(|e| format!("获取进程管理器锁失败: {}", e))?;

    manager.start_python_backend(&sidecar_str, port)
}

/// 停止 Sidecar（Python 后端）
#[tauri::command]
pub fn stop_sidecar(state: State<'_, AppState>) -> Result<(), String> {
    let mut manager = state
        .process_manager
        .lock()
        .map_err(|e| format!("获取进程管理器锁失败: {}", e))?;

    manager.stop_python_backend()
}

/// 检查 Sidecar 状态
///
/// # 返回
/// Sidecar 当前状态信息
#[tauri::command]
pub fn check_sidecar_status(state: State<'_, AppState>) -> Result<SidecarStatusResponse, String> {
    let manager = state
        .process_manager
        .lock()
        .map_err(|e| format!("获取进程管理器锁失败: {}", e))?;

    let status = manager.get_python_status();
    let info = manager.get_python_info();
    let port = manager.get_python_port();

    let (is_running, status_str) = match &status {
        ProcessStatus::Stopped => (false, "stopped".to_string()),
        ProcessStatus::Starting => (false, "starting".to_string()),
        ProcessStatus::Running => (true, "running".to_string()),
        ProcessStatus::Error(msg) => (false, format!("error: {}", msg)),
    };

    Ok(SidecarStatusResponse {
        is_running,
        status: status_str,
        pid: info.as_ref().map(|i| i.pid),
        port,
        started_at: info.as_ref().map(|i| i.started_at.clone()),
    })
}
```

---

### 步骤 6：实现应用信息命令

创建 `src-tauri/src/commands/app.rs`：

```rust
//! 应用信息命令
//! 提供应用版本、系统信息等查询功能

use serde::{Deserialize, Serialize};
use tauri::Manager;

/// 应用信息响应
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppInfo {
    /// 应用名称
    pub app_name: String,
    /// 应用版本
    pub version: String,
    /// Tauri 版本
    pub tauri_version: String,
    /// 操作系统
    pub os: String,
    /// 操作系统版本
    pub os_version: String,
    /// 架构
    pub arch: String,
    /// 设备主机名
    pub hostname: String,
}

/// 获取应用信息
///
/// 返回应用的版本、系统环境等信息
#[tauri::command]
pub fn get_app_info(app_handle: tauri::AppHandle) -> Result<AppInfo, String> {
    let package_info = app_handle
        .package_info()
        .map_err(|e| format!("获取包信息失败: {}", e))?;

    Ok(AppInfo {
        app_name: package_info.name.clone(),
        version: package_info.version.to_string(),
        tauri_version: env!("TAURI_VERSION").to_string(),
        os: std::env::consts::OS.to_string(),
        os_version: tauri_plugin_os::version()
            .map(|v| v.to_string())
            .unwrap_or_else(|_| "unknown".to_string()),
        arch: std::env::consts::ARCH.to_string(),
        hostname: hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "unknown".to_string()),
    })
}

/// 打开外部 URL
///
/// 使用系统默认浏览器打开指定 URL
///
/// # 参数
/// - `url`: 要打开的 URL
#[tauri::command]
pub async fn open_external_url(app_handle: tauri::AppHandle, url: String) -> Result<(), String> {
    tauri_plugin_opener::open_url(&app_handle, &url, None::<&str>)
        .map_err(|e| format!("打开 URL 失败: {}", e))
}
```

---

### 步骤 7：注册命令和插件

修改 `src-tauri/src/lib.rs`：

```rust
//! 灵境制造 V4 - Tauri 库入口
//! 注册所有 Tauri 命令和插件

pub mod commands;
pub mod state;

use state::AppState;

/// 初始化并注册所有 Tauri 命令
///
/// # 注册的命令
/// - 文件系统：get_app_data_dir, save_file, read_file, list_files, delete_file, create_directory
/// - 进程管理：start_sidecar, stop_sidecar, check_sidecar_status
/// - 应用信息：get_app_info, open_external_url
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // 注册 Tauri 插件
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_path::init())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_opener::init())
        // 注册全局状态
        .manage(AppState::new())
        // 注册 Tauri 命令
        .invoke_handler(tauri::generate_handler![
            // 文件系统命令
            commands::file::get_app_data_dir,
            commands::file::save_file,
            commands::file::read_file,
            commands::file::list_files,
            commands::file::delete_file,
            commands::file::create_directory,
            // 进程管理命令
            commands::process::start_sidecar,
            commands::process::stop_sidecar,
            commands::process::check_sidecar_status,
            // 应用信息命令
            commands::app::get_app_info,
            commands::app::open_external_url,
        ])
        .run(tauri::generate_context!())
        .expect("启动灵境制造应用失败");
}
```

修改 `src-tauri/src/main.rs`：

```rust
//! 灵境制造 V4 - Tauri 应用入口
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    lingjing_v4_lib::run()
}
```

---

### 步骤 8：创建前端 TypeScript 类型定义

创建 `src/types/tauri.ts`：

```typescript
/**
 * Tauri 后端类型定义
 * 与 Rust 后端命令对应的 TypeScript 类型
 */

// ==========================================
// 文件系统类型
// ==========================================

/** 文件信息 */
export interface FileInfo {
  /** 文件名 */
  name: string
  /** 文件完整路径 */
  path: string
  /** 是否为目录 */
  is_dir: boolean
  /** 文件大小（字节） */
  size: number
  /** 最后修改时间 */
  modified_at: string
  /** 文件扩展名 */
  extension: string | null
}

// ==========================================
// 进程管理类型
// ==========================================

/** Sidecar 进程状态 */
export type SidecarProcessStatus = 'stopped' | 'starting' | 'running' | 'error'

/** Sidecar 状态响应 */
export interface SidecarStatusResponse {
  /** 是否正在运行 */
  is_running: boolean
  /** 状态描述 */
  status: string
  /** 进程 ID */
  pid: number | null
  /** 端口号 */
  port: number
  /** 启动时间 */
  started_at: string | null
}

// ==========================================
// 应用信息类型
// ==========================================

/** 应用信息 */
export interface AppInfo {
  /** 应用名称 */
  app_name: string
  /** 应用版本 */
  version: string
  /** Tauri 版本 */
  tauri_version: string
  /** 操作系统 */
  os: string
  /** 操作系统版本 */
  os_version: string
  /** 系统架构 */
  arch: string
  /** 主机名 */
  hostname: string
}

// ==========================================
// Tauri 命令类型
// ==========================================

/**
 * Tauri 命令接口
 * 定义所有可从前端调用的 Rust 命令
 */
export interface TauriCommands {
  // --- 文件系统命令 ---
  /** 获取应用数据目录 */
  getAppDataDir: () => Promise<string>
  /** 保存文件 */
  saveFile: (filePath: string, content: string) => Promise<void>
  /** 读取文件 */
  readFile: (filePath: string) => Promise<string>
  /** 列出目录文件 */
  listFiles: (dirPath: string, extension?: string) => Promise<FileInfo[]>
  /** 删除文件 */
  deleteFile: (filePath: string, recursive?: boolean) => Promise<void>
  /** 创建目录 */
  createDirectory: (dirPath: string, recursive?: boolean) => Promise<void>

  // --- 进程管理命令 ---
  /** 启动 Sidecar */
  startSidecar: (port?: number) => Promise<number>
  /** 停止 Sidecar */
  stopSidecar: () => Promise<void>
  /** 检查 Sidecar 状态 */
  checkSidecarStatus: () => Promise<SidecarStatusResponse>

  // --- 应用信息命令 ---
  /** 获取应用信息 */
  getAppInfo: () => Promise<AppInfo>
  /** 打开外部 URL */
  openExternalUrl: (url: string) => Promise<void>
}
```

---

### 步骤 9：创建前端 Tauri 服务封装

创建 `src/services/tauri.ts`：

```typescript
/**
 * Tauri 服务封装
 * 提供类型安全的 Tauri 命令调用接口
 *
 * 使用方式：
 *   import { tauriService } from '@/services/tauri'
 *   const info = await tauriService.getAppInfo()
 */

import { invoke } from '@tauri-apps/api/core'
import type {
  FileInfo,
  SidecarStatusResponse,
  AppInfo,
  TauriCommands,
} from '@/types/tauri'

/**
 * Tauri 服务
 * 封装所有 Tauri Rust 命令的调用
 */
class TauriService implements TauriCommands {
  // ==========================================
  // 文件系统命令
  // ==========================================

  /**
   * 获取应用数据目录
   * @returns 应用数据目录的绝对路径
   */
  async getAppDataDir(): Promise<string> {
    return invoke<string>('get_app_data_dir')
  }

  /**
   * 保存文件
   * @param filePath - 文件完整路径
   * @param content - 文件内容
   */
  async saveFile(filePath: string, content: string): Promise<void> {
    return invoke<void>('save_file', {
      filePath,
      content,
    })
  }

  /**
   * 读取文件内容
   * @param filePath - 文件完整路径
   * @returns 文件的文本内容
   */
  async readFile(filePath: string): Promise<string> {
    return invoke<string>('read_file', { filePath })
  }

  /**
   * 列出目录下的文件
   * @param dirPath - 目录路径
   * @param extension - 可选的文件扩展名过滤
   * @returns 文件信息列表
   */
  async listFiles(dirPath: string, extension?: string): Promise<FileInfo[]> {
    return invoke<FileInfo[]>('list_files', {
      dirPath,
      extension: extension ?? null,
    })
  }

  /**
   * 删除文件或目录
   * @param filePath - 文件或目录路径
   * @param recursive - 是否递归删除目录，默认 true
   */
  async deleteFile(filePath: string, recursive = true): Promise<void> {
    return invoke<void>('delete_file', { filePath, recursive })
  }

  /**
   * 创建目录
   * @param dirPath - 目录路径
   * @param recursive - 是否递归创建父目录，默认 true
   */
  async createDirectory(dirPath: string, recursive = true): Promise<void> {
    return invoke<void>('create_directory', { dirPath, recursive })
  }

  // ==========================================
  // 进程管理命令
  // ==========================================

  /**
   * 启动 Python Sidecar 后端
   * @param port - 监听端口号，默认 8765
   * @returns 进程 PID
   */
  async startSidecar(port?: number): Promise<number> {
    return invoke<number>('start_sidecar', { port: port ?? null })
  }

  /**
   * 停止 Python Sidecar 后端
   */
  async stopSidecar(): Promise<void> {
    return invoke<void>('stop_sidecar')
  }

  /**
   * 检查 Sidecar 状态
   * @returns Sidecar 状态信息
   */
  async checkSidecarStatus(): Promise<SidecarStatusResponse> {
    return invoke<SidecarStatusResponse>('check_sidecar_status')
  }

  // ==========================================
  // 应用信息命令
  // ==========================================

  /**
   * 获取应用信息
   * @returns 应用版本和系统信息
   */
  async getAppInfo(): Promise<AppInfo> {
    return invoke<AppInfo>('get_app_info')
  }

  /**
   * 使用系统默认浏览器打开外部 URL
   * @param url - 要打开的 URL
   */
  async openExternalUrl(url: string): Promise<void> {
    return invoke<void>('open_external_url', { url })
  }
}

/** Tauri 服务单例 */
export const tauriService = new TauriService()

export default tauriService
```

---

### 步骤 10：安装 Tauri API 前端依赖

```bash
pnpm add @tauri-apps/api @tauri-apps/plugin-shell @tauri-apps/plugin-fs @tauri-apps/plugin-dialog @tauri-apps/plugin-opener
```

---

### 步骤 11：创建 Tauri 服务测试

创建 `tests/services/tauri.test.ts`：

```typescript
/**
 * Tauri 服务类型测试
 * 注意：这些测试仅验证类型定义，不实际调用 Tauri 命令
 */
import { describe, it, expect } from 'vitest'
import type {
  FileInfo,
  SidecarStatusResponse,
  AppInfo,
  TauriCommands,
} from '@/types/tauri'

describe('Tauri 类型定义', () => {
  it('FileInfo 类型应包含必要字段', () => {
    const fileInfo: FileInfo = {
      name: 'test.stl',
      path: '/path/to/test.stl',
      is_dir: false,
      size: 1024,
      modified_at: '2024-01-01 00:00:00',
      extension: 'stl',
    }
    expect(fileInfo.name).toBe('test.stl')
    expect(fileInfo.is_dir).toBe(false)
    expect(fileInfo.extension).toBe('stl')
  })

  it('SidecarStatusResponse 类型应包含必要字段', () => {
    const status: SidecarStatusResponse = {
      is_running: true,
      status: 'running',
      pid: 12345,
      port: 8765,
      started_at: '2024-01-01 00:00:00',
    }
    expect(status.is_running).toBe(true)
    expect(status.port).toBe(8765)
  })

  it('AppInfo 类型应包含必要字段', () => {
    const info: AppInfo = {
      app_name: '灵境制造',
      version: '4.0.0',
      tauri_version: '2.0.0',
      os: 'windows',
      os_version: '10.0',
      arch: 'x86_64',
      hostname: 'test-pc',
    }
    expect(info.app_name).toBe('灵境制造')
    expect(info.version).toBe('4.0.0')
  })
})
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

1. **Rust 编译验证**：在 `src-tauri/` 目录下执行 `cargo build`，确认编译通过
2. **应用启动验证**：执行 `pnpm tauri dev`，确认：
   - 桌面窗口正常启动
   - 控制台无 Rust panic 或错误
3. **TypeScript 编译验证**：执行 `pnpm build`，确认无类型错误
4. **类型完整性验证**：确认 `src/types/tauri.ts` 中的类型与 Rust 命令参数/返回值完全匹配
5. **服务封装验证**：确认 `src/services/tauri.ts` 可以正常导入且无编译错误

如果以上验证全部通过，Phase 1 完成。

---PROMPT END---

---

## Phase 2: Python AI 后端（Sidecar）

### 目标

搭建完整的 Python FastAPI 后端项目，包括统一响应格式、异常处理、Pydantic 数据模型、LLM 客户端抽象层（支持 Ollama 本地模型和云端 API）、健康检查接口，以及 PyInstaller 打包脚本。

### 验证标准

- [ ] `python -m app.main` 可正常启动 FastAPI 服务
- [ ] 访问 `http://localhost:8765/health` 返回健康状态
- [ ] 访问 `http://localhost:8765/api/ai/status` 返回 AI 状态
- [ ] 访问 `http://localhost:8765/docs` 可查看 Swagger 文档
- [ ] 全局异常处理正常工作（访问不存在的路由返回标准错误格式）
- [ ] `pip install -r requirements.txt` 可正常安装所有依赖
- [ ] `python build.py --help` 打包脚本可正常执行

---

---PROMPT START---

## 任务：搭建 Python AI 后端 Sidecar（Phase 2）

你是一个资深 Python 后端工程师。请在灵境制造 V4 项目中创建完整的 Python FastAPI 后端。该后端将作为 Tauri 应用的 Sidecar 运行。

### 重要约定
- 所有注释使用中文（docstring 和行内注释）
- Python 版本：3.11+
- 使用 dataclass 和 Pydantic v2 进行数据建模
- 使用 async/await 异步编程
- 遵循 RESTful API 设计规范
- 所有 API 响应使用统一格式

### 项目信息
- Python 后端目录：`lingjing-v4/python/`
- 应用代码目录：`lingjing-v4/python/app/`
- 默认端口：8765
- 产品名：灵境制造

---

### 步骤 1：创建 Python 项目目录结构

在 `lingjing-v4/python/` 下创建以下结构：

```
python/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── core/                # 核心模块
│   │   ├── __init__.py
│   │   ├── response.py      # 统一响应格式
│   │   └── exceptions.py    # 自定义异常
│   ├── models/              # 数据模型
│   │   ├── __init__.py
│   │   └── schemas.py       # Pydantic 模型
│   ├── ai/                  # AI 模块
│   │   ├── __init__.py
│   │   ├── llm_client.py    # LLM 客户端抽象
│   │   └── agents.py        # AI Agent（占位）
│   ├── cad/                 # CAD 模块
│   │   ├── __init__.py
│   │   ├── generator.py     # CAD 生成器（占位）
│   │   └── cadquery_gen.py  # CadQuery 生成（占位）
│   ├── rag/                 # RAG 知识库（占位）
│   │   └── __init__.py
│   └── services/            # 业务服务（占位）
│       └── __init__.py
├── requirements.txt
├── pyproject.toml
└── build.py                 # PyInstaller 打包脚本
```

---

### 步骤 2：创建 requirements.txt

创建 `python/requirements.txt`：

```
# Web 框架
fastapi==0.115.0
uvicorn[standard]==0.30.0

# 数据验证
pydantic==2.9.0
pydantic-settings==2.5.0

# 异步任务队列
celery[redis]==5.4.0
redis==5.1.0

# 向量数据库
chromadb==0.5.0

# 文本向量化
sentence-transformers==3.1.0

# 3D 模型处理
trimesh==4.5.0

# CAD 引擎
cadquery==2.5.0

# AI/LLM
ollama==0.3.0
httpx==0.27.0

# 文件处理
filetype==1.2.0
Pillow==10.4.0

# 数值计算
numpy==2.1.0

# 开发工具
python-multipart==0.0.9
```

---

### 步骤 3：创建 pyproject.toml

创建 `python/pyproject.toml`：

```toml
[project]
name = "lingjing-ai-backend"
version = "4.0.0"
description = "灵境制造 AI 后端 - FastAPI Sidecar"
requires-python = ">=3.11"
authors = [
    { name = "LingJing Team" }
]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

---

### 步骤 4：创建配置管理

创建 `python/app/__init__.py`：

```python
"""
灵境制造 AI 后端
FastAPI Sidecar 应用
"""
```

创建 `python/app/config.py`：

```python
"""
应用配置管理
支持环境变量覆盖，使用 dataclass 管理配置项
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServerConfig:
    """服务器配置"""
    # 服务主机
    host: str = "127.0.0.1"
    # 服务端口
    port: int = 8765
    # 是否开启调试模式
    debug: bool = False
    # 是否开启访问日志
    access_log: bool = True
    # CORS 允许的源
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:1420", "tauri://localhost"])


@dataclass
class AIConfig:
    """AI 模型配置"""
    # AI 模式：local（本地 Ollama）、cloud（云端 API）、rule（规则引擎）
    ai_mode: str = "local"
    # Ollama 服务地址
    ollama_base_url: str = "http://localhost:11434"
    # Ollama 默认模型
    ollama_model: str = "qwen2.5:7b"
    # 云端 API 类型：openai、deepseek
    cloud_api_type: str = "deepseek"
    # 云端 API Key（从环境变量读取）
    cloud_api_key: str = field(default_factory=lambda: os.getenv("LJ_CLOUD_API_KEY", ""))
    # 云端 API Base URL
    cloud_api_base_url: str = "https://api.deepseek.com/v1"
    # 请求超时时间（秒）
    request_timeout: int = 120
    # 最大重试次数
    max_retries: int = 3


@dataclass
class StorageConfig:
    """存储配置"""
    # 数据根目录
    data_dir: str = field(default_factory=lambda: os.getenv("LJ_DATA_DIR", ""))
    # 模型文件目录
    models_dir: str = ""
    # 上传文件目录
    uploads_dir: str = ""
    # 日志目录
    logs_dir: str = ""

    def __post_init__(self):
        """初始化后设置子目录"""
        if not self.data_dir:
            # 默认使用应用数据目录
            app_data = os.getenv("APPDATA", "")
            if app_data:
                self.data_dir = os.path.join(app_data, "lingjing", "data")
            else:
                self.data_dir = os.path.join(os.path.expanduser("~"), ".lingjing", "data")

        self.models_dir = os.path.join(self.data_dir, "models")
        self.uploads_dir = os.path.join(self.data_dir, "uploads")
        self.logs_dir = os.path.join(self.data_dir, "logs")


@dataclass
class RedisConfig:
    """Redis 配置"""
    # Redis 连接 URL
    url: str = "redis://localhost:6379/0"
    # 是否启用 Redis
    enabled: bool = False


@dataclass
class AppConfig:
    """应用总配置
    汇聚所有子配置，支持从环境变量覆盖
    """
    # 应用名称
    app_name: str = "灵境制造"
    # 应用版本
    app_version: str = "4.0.0"
    # 是否离线模式
    offline_mode: bool = False

    # 子配置
    server: ServerConfig = field(default_factory=ServerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量创建配置"""
        config = cls()

        # 服务器配置覆盖
        if host := os.getenv("LJ_HOST"):
            config.server.host = host
        if port := os.getenv("LJ_PORT"):
            config.server.port = int(port)
        if debug := os.getenv("LJ_DEBUG"):
            config.server.debug = debug.lower() in ("true", "1", "yes")

        # AI 配置覆盖
        if ai_mode := os.getenv("LJ_AI_MODE"):
            config.ai.ai_mode = ai_mode
        if ollama_url := os.getenv("LJ_OLLAMA_URL"):
            config.ai.ollama_base_url = ollama_url
        if ollama_model := os.getenv("LJ_OLLAMA_MODEL"):
            config.ai.ollama_model = ollama_model
        if cloud_api_key := os.getenv("LJ_CLOUD_API_KEY"):
            config.ai.cloud_api_key = cloud_api_key
        if cloud_api_type := os.getenv("LJ_CLOUD_API_TYPE"):
            config.ai.cloud_api_type = cloud_api_type
        if cloud_api_base := os.getenv("LJ_CLOUD_API_BASE"):
            config.ai.cloud_api_base_url = cloud_api_base

        # 离线模式
        if offline := os.getenv("LJ_OFFLINE_MODE"):
            config.offline_mode = offline.lower() in ("true", "1", "yes")

        # Redis 配置覆盖
        if redis_url := os.getenv("LJ_REDIS_URL"):
            config.redis.url = redis_url
            config.redis.enabled = True

        return config


# 全局配置实例
_settings: Optional[AppConfig] = None


def get_settings() -> AppConfig:
    """获取全局配置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = AppConfig.from_env()
    return _settings


def reload_settings() -> AppConfig:
    """重新加载配置"""
    global _settings
    _settings = AppConfig.from_env()
    return _settings
```

---

### 步骤 5：创建统一响应格式

创建 `python/app/core/__init__.py`：

```python
"""
核心模块
"""
```

创建 `python/app/core/response.py`：

```python
"""
统一响应格式
所有 API 接口返回统一的 JSON 响应结构
"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorCode:
    """错误码定义
    格式：模块(2位) + 错误类型(3位)
    """
    # 通用错误 00xxx
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    VALIDATION_ERROR = 2
    NOT_FOUND = 3
    PERMISSION_DENIED = 4
    RATE_LIMITED = 5

    # AI 模块错误 01xxx
    AI_MODEL_UNAVAILABLE = 1001
    AI_MODEL_TIMEOUT = 1002
    AI_MODEL_ERROR = 1003
    AI_INVALID_REQUEST = 1004
    AI_CONTEXT_TOO_LONG = 1005

    # CAD 模块错误 02xxx
    CAD_GENERATION_FAILED = 2001
    CAD_INVALID_INPUT = 2002
    CAD_FILE_ERROR = 2003
    CAD_UNSUPPORTED_FORMAT = 2004

    # 文件模块错误 03xxx
    FILE_NOT_FOUND = 3001
    FILE_READ_ERROR = 3002
    FILE_WRITE_ERROR = 3003
    FILE_INVALID_TYPE = 3004
    FILE_TOO_LARGE = 3005

    # 任务模块错误 04xxx
    TASK_NOT_FOUND = 4001
    TASK_TIMEOUT = 4002
    TASK_CANCELLED = 4003

    # LLM 模块错误 05xxx
    LLM_CONNECTION_ERROR = 5001
    LLM_RESPONSE_PARSE_ERROR = 5002
    LLM_RATE_LIMITED = 5003


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式

    示例：
        成功响应：{"code": 0, "message": "success", "data": { ... }}
        错误响应：{"code": 1001, "message": "AI 模型不可用", "data": null}
    """
    # 状态码，0 表示成功，非 0 表示错误
    code: int = Field(default=ErrorCode.SUCCESS, description="状态码")
    # 提示信息
    message: str = Field(default="success", description="提示信息")
    # 响应数据
    data: Optional[T] = Field(default=None, description="响应数据")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "code": 0,
                    "message": "success",
                    "data": {"key": "value"},
                }
            ]
        }


def success(data: Any = None, message: str = "success") -> dict:
    """创建成功响应

    Args:
        data: 响应数据
        message: 成功提示信息

    Returns:
        标准响应字典
    """
    return {
        "code": ErrorCode.SUCCESS,
        "message": message,
        "data": data,
    }


def error(
    code: int = ErrorCode.UNKNOWN_ERROR,
    message: str = "未知错误",
    data: Any = None,
) -> dict:
    """创建错误响应

    Args:
        code: 错误码
        message: 错误提示信息
        data: 附加错误数据

    Returns:
        标准响应字典
    """
    return {
        "code": code,
        "message": message,
        "data": data,
    }


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    # 状态码
    code: int = Field(default=ErrorCode.SUCCESS)
    # 提示信息
    message: str = Field(default="success")
    # 数据列表
    data: list[T] = Field(default_factory=list)
    # 总记录数
    total: int = Field(default=0, description="总记录数")
    # 当前页码
    page: int = Field(default=1, description="当前页码")
    # 每页数量
    page_size: int = Field(default=20, description="每页数量")
    # 总页数
    total_pages: int = Field(default=0, description="总页数")
```

---

### 步骤 6：创建自定义异常

创建 `python/app/core/exceptions.py`：

```python
"""
自定义异常定义
所有业务异常的基类和具体实现
"""

from typing import Any, Optional


class AppException(Exception):
    """应用基础异常

    所有业务异常都应继承此类，包含错误码和详细信息

    Attributes:
        code: 错误码
        message: 错误提示信息
        detail: 详细错误信息（可选）
    """

    def __init__(
        self,
        code: int,
        message: str,
        detail: Optional[str] = None,
        data: Any = None,
    ):
        self.code = code
        self.message = message
        self.detail = detail
        self.data = data
        super().__init__(message)

    def to_dict(self) -> dict:
        """转换为响应字典"""
        result = {
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }
        if self.detail:
            result["detail"] = self.detail
        return result


# ==========================================
# AI 模块异常
# ==========================================

class AIModelUnavailableError(AppException):
    """AI 模型不可用异常"""

    def __init__(self, model_name: str = "", reason: str = ""):
        message = f"AI 模型不可用: {model_name}" if model_name else "AI 模型不可用"
        if reason:
            message += f" ({reason})"
        super().__init__(
            code=1001,
            message=message,
            detail=f"model={model_name}, reason={reason}",
        )


class AIModelTimeoutError(AppException):
    """AI 模型请求超时异常"""

    def __init__(self, model_name: str = "", timeout: int = 0):
        super().__init__(
            code=1002,
            message=f"AI 模型请求超时: {model_name} (超时时间: {timeout}秒)",
        )


class AIModelResponseError(AppException):
    """AI 模型响应解析异常"""

    def __init__(self, model_name: str = "", reason: str = ""):
        super().__init__(
            code=1003,
            message=f"AI 模型响应错误: {reason}",
            detail=f"model={model_name}",
        )


class AIInvalidRequestError(AppException):
    """AI 请求参数无效异常"""

    def __init__(self, reason: str = ""):
        super().__init__(
            code=1004,
            message=f"AI 请求参数无效: {reason}",
        )


# ==========================================
# CAD 模块异常
# ==========================================

class CADGenerationError(AppException):
    """CAD 模型生成失败异常"""

    def __init__(self, reason: str = ""):
        super().__init__(
            code=2001,
            message=f"CAD 模型生成失败: {reason}",
        )


class CADInvalidInputError(AppException):
    """CAD 输入参数无效异常"""

    def __init__(self, reason: str = ""):
        super().__init__(
            code=2002,
            message=f"CAD 输入参数无效: {reason}",
        )


# ==========================================
# 文件模块异常
# ==========================================

class FileNotFoundException(AppException):
    """文件未找到异常"""

    def __init__(self, file_path: str = ""):
        super().__init__(
            code=3001,
            message=f"文件未找到: {file_path}",
            detail=f"path={file_path}",
        )


class FileReadError(AppException):
    """文件读取异常"""

    def __init__(self, file_path: str = "", reason: str = ""):
        super().__init__(
            code=3002,
            message=f"文件读取失败: {file_path} ({reason})",
        )


class FileWriteError(AppException):
    """文件写入异常"""

    def __init__(self, file_path: str = "", reason: str = ""):
        super().__init__(
            code=3003,
            message=f"文件写入失败: {file_path} ({reason})",
        )


class FileInvalidTypeError(AppException):
    """文件类型无效异常"""

    def __init__(self, file_type: str = "", expected: str = ""):
        message = f"不支持的文件类型: {file_type}"
        if expected:
            message += f"（期望: {expected}）"
        super().__init__(
            code=3004,
            message=message,
        )


class FileTooLargeError(AppException):
    """文件过大异常"""

    def __init__(self, size: int = 0, max_size: int = 0):
        super().__init__(
            code=3005,
            message=f"文件过大: {size} 字节（最大允许: {max_size} 字节）",
        )


# ==========================================
# 任务模块异常
# ==========================================

class TaskNotFoundException(AppException):
    """任务未找到异常"""

    def __init__(self, task_id: str = ""):
        super().__init__(
            code=4001,
            message=f"任务未找到: {task_id}",
        )


class TaskTimeoutError(AppException):
    """任务超时异常"""

    def __init__(self, task_id: str = "", timeout: int = 0):
        super().__init__(
            code=4002,
            message=f"任务超时: {task_id} (超时时间: {timeout}秒)",
        )


# ==========================================
# LLM 模块异常
# ==========================================

class LLMConnectionError(AppException):
    """LLM 连接异常"""

    def __init__(self, provider: str = "", reason: str = ""):
        super().__init__(
            code=5001,
            message=f"LLM 连接失败: {provider} ({reason})",
        )


class LLMResponseParseError(AppException):
    """LLM 响应解析异常"""

    def __init__(self, reason: str = ""):
        super().__init__(
            code=5002,
            message=f"LLM 响应解析失败: {reason}",
        )
```

---

### 步骤 7：创建 Pydantic 数据模型

创建 `python/app/models/__init__.py`：

```python
"""
数据模型模块
"""
```

创建 `python/app/models/schemas.py`：

```python
"""
Pydantic 数据模型
定义所有 API 请求和响应的数据结构
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ==========================================
# 枚举类型
# ==========================================

class AIMode(str, Enum):
    """AI 模式枚举"""
    LOCAL = "local"       # 本地 Ollama
    CLOUD = "cloud"       # 云端 API
    RULE = "rule"         # 规则引擎


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"       # 等待中
    RUNNING = "running"       # 运行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 已失败
    CANCELLED = "cancelled"   # 已取消


class ModelFormat(str, Enum):
    """3D 模型格式枚举"""
    STL = "stl"
    OBJ = "obj"
    GLB = "glb"
    GLTF = "gltf"
    STEP = "step"
    IGES = "iges"


class CADLanguage(str, Enum):
    """CAD 脚本语言枚举"""
    CADQUERY = "cadquery"
    OPENSCAD = "openscad"
    THREEJS = "threejs"


# ==========================================
# AI 相关模型
# ==========================================

class AISettings(BaseModel):
    """AI 设置"""
    mode: AIMode = Field(default=AIMode.LOCAL, description="AI 模式")
    ollama_model: str = Field(default="qwen2.5:7b", description="Ollama 模型名称")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama 服务地址")
    cloud_api_type: str = Field(default="deepseek", description="云端 API 类型")
    cloud_api_key: str = Field(default="", description="云端 API Key")
    cloud_api_base_url: str = Field(default="https://api.deepseek.com/v1", description="云端 API 地址")
    request_timeout: int = Field(default=120, ge=10, le=600, description="请求超时时间")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")


class AIStatusResponse(BaseModel):
    """AI 状态响应"""
    mode: str = Field(description="当前 AI 模式")
    ollama_available: bool = Field(description="Ollama 是否可用")
    ollama_version: Optional[str] = Field(default=None, description="Ollama 版本")
    installed_models: list[str] = Field(default_factory=list, description="已安装的 Ollama 模型")
    cloud_configured: bool = Field(description="云端 API 是否已配置")
    cloud_api_type: Optional[str] = Field(default=None, description="云端 API 类型")


class LLMMessage(BaseModel):
    """LLM 对话消息"""
    role: str = Field(description="消息角色")
    content: str = Field(description="消息内容")


class LLMRequest(BaseModel):
    """LLM 请求"""
    messages: list[LLMMessage] = Field(description="对话消息列表")
    model: Optional[str] = Field(default=None, description="模型名称")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(default=2048, ge=1, le=32768, description="最大生成 token 数")


class LLMResponse(BaseModel):
    """LLM 响应"""
    content: str = Field(description="生成的文本内容")
    model: str = Field(description="使用的模型")
    tokens_used: Optional[int] = Field(default=None, description="消耗的 token 数")
    elapsed_ms: Optional[int] = Field(default=None, description="响应耗时（毫秒）")


# ==========================================
# 三视图生成 3D 模型相关模型
# ==========================================

class ThreeViewTaskRequest(BaseModel):
    """三视图生成 3D 模型请求"""
    description: str = Field(default="", description="模型描述")
    use_ai: bool = Field(default=True, description="是否使用 AI 优化")
    output_format: ModelFormat = Field(default=ModelFormat.STL, description="输出模型格式")


class ThreeViewTaskResponse(BaseModel):
    """三视图生成任务响应"""
    task_id: str = Field(description="任务 ID")
    status: TaskStatus = Field(description="任务状态")
    created_at: datetime = Field(description="创建时间")
    model_path: Optional[str] = Field(default=None, description="模型文件路径")


# ==========================================
# 工艺规划相关模型
# ==========================================

class ProcessRouteRequest(BaseModel):
    """工艺路线生成请求"""
    part_description: str = Field(description="零件描述")
    material: str = Field(default="45#钢", description="材料")
    batch_size: int = Field(default=1, ge=1, description="批量")
    generate_nc: bool = Field(default=False, description="是否同时生成 NC 代码")


class ProcessStep(BaseModel):
    """工序步骤"""
    step_number: int = Field(description="工序号")
    name: str = Field(description="工序名称")
    description: str = Field(description="工序内容描述")
    equipment: Optional[str] = Field(default=None, description="使用设备")
    duration: Optional[float] = Field(default=None, description="预估工时（分钟）")


class ProcessRouteResponse(BaseModel):
    """工艺路线响应"""
    route_id: str = Field(description="工艺路线 ID")
    part_description: str = Field(description="零件描述")
    steps: list[ProcessStep] = Field(default_factory=list, description="工序步骤")
    total_duration: Optional[float] = Field(default=None, description="总工时（分钟）")


# ==========================================
# CadQuery 相关模型
# ==========================================

class CadQueryRequest(BaseModel):
    """CadQuery 生成请求"""
    description: str = Field(description="零件自然语言描述")
    output_format: ModelFormat = Field(default=ModelFormat.STL, description="输出格式")
    use_ai: bool = Field(default=True, description="是否使用 AI 解析描述")


class CadQueryResponse(BaseModel):
    """CadQuery 生成响应"""
    task_id: str = Field(description="任务 ID")
    script: Optional[str] = Field(default=None, description="生成的 CadQuery 脚本")
    model_path: Optional[str] = Field(default=None, description="模型文件路径")
    status: TaskStatus = Field(description="任务状态")


# ==========================================
# 通用模型
# ==========================================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(default="healthy", description="服务状态")
    version: str = Field(description="应用版本")
    uptime: float = Field(description="运行时间（秒）")
    ai_status: Optional[AIStatusResponse] = Field(default=None, description="AI 状态")


class FileInfoResponse(BaseModel):
    """文件信息响应"""
    name: str = Field(description="文件名")
    path: str = Field(description="文件路径")
    size: int = Field(description="文件大小")
    content_type: Optional[str] = Field(default=None, description="文件类型")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
```

---

### 步骤 8：创建 LLM 客户端抽象层

创建 `python/app/ai/__init__.py`：

```python
"""
AI 模块
"""
```

创建 `python/app/ai/llm_client.py`：

```python
"""
LLM 客户端抽象层
支持多种 LLM 后端：本地 Ollama、云端 API、规则引擎
通过工厂函数获取对应的客户端实例
"""

import abc
import asyncio
import time
import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.core.exceptions import (
    AIModelUnavailableError,
    AIModelTimeoutError,
    AIModelResponseError,
    LLMConnectionError,
    LLMResponseParseError,
)
from app.models.schemas import (
    AIMode,
    LLMRequest,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class BaseLLMClient(abc.ABC):
    """LLM 客户端抽象基类

    所有 LLM 客户端实现都必须继承此类并实现 chat 方法
    """

    def __init__(self, name: str):
        """初始化客户端

        Args:
            name: 客户端名称（用于日志）
        """
        self.name = name
        self._timeout = get_settings().ai.request_timeout
        self._max_retries = get_settings().ai.max_retries

    @abc.abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """发送对话请求

        Args:
            request: LLM 请求对象

        Returns:
            LLM 响应对象

        Raises:
            AIModelUnavailableError: 模型不可用
            AIModelTimeoutError: 请求超时
            AIModelResponseError: 响应解析失败
        """
        ...

    @abc.abstractmethod
    async def is_available(self) -> bool:
        """检查客户端是否可用

        Returns:
            True 表示可用
        """
        ...

    @abc.abstractmethod
    def get_model_name(self) -> str:
        """获取当前使用的模型名称

        Returns:
            模型名称字符串
        """
        ...

    async def chat_with_retry(self, request: LLMRequest) -> LLMResponse:
        """带重试机制的对话请求

        Args:
            request: LLM 请求对象

        Returns:
            LLM 响应对象
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(f"[{self.name}] 第 {attempt}/{self._max_retries} 次请求")
                return await self.chat(request)
            except (AIModelUnavailableError, AIModelTimeoutError, LLMConnectionError) as e:
                last_error = e
                logger.warning(f"[{self.name}] 第 {attempt} 次请求失败: {e.message}")
                if attempt < self._max_retries:
                    # 指数退避等待
                    wait_time = 2 ** attempt
                    logger.info(f"[{self.name}] 等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)

        # 所有重试都失败
        raise last_error or AIModelUnavailableError(reason="所有重试均失败")


class OllamaClient(BaseLLMClient):
    """Ollama 本地 LLM 客户端

    通过 HTTP API 与本地 Ollama 服务通信
    """

    def __init__(self):
        super().__init__("Ollama")
        settings = get_settings()
        self._base_url = settings.ai.ollama_base_url.rstrip("/")
        self._model = settings.ai.ollama_model

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """发送对话请求到 Ollama"""
        model = request.model or self._model
        start_time = time.time()

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                provider="Ollama",
                reason=f"无法连接到 {self._base_url}",
            ) from e
        except httpx.TimeoutException as e:
            raise AIModelTimeoutError(model_name=model, timeout=self._timeout) from e
        except httpx.HTTPStatusError as e:
            raise AIModelResponseError(
                model_name=model,
                reason=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            ) from e

        # 解析响应
        try:
            content = data.get("message", {}).get("content", "")
            elapsed = int((time.time() - start_time) * 1000)

            if not content:
                raise AIModelResponseError(model_name=model, reason="响应内容为空")

            return LLMResponse(
                content=content,
                model=model,
                tokens_used=data.get("eval_count"),
                elapsed_ms=elapsed,
            )
        except (KeyError, TypeError) as e:
            raise LLMResponseParseError(reason=f"解析 Ollama 响应失败: {e}")

    async def is_available(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def get_model_name(self) -> str:
        return self._model

    async def list_models(self) -> list[str]:
        """获取已安装的模型列表

        Returns:
            模型名称列表
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.warning(f"获取 Ollama 模型列表失败: {e}")
            return []

    async def get_version(self) -> Optional[str]:
        """获取 Ollama 版本

        Returns:
            版本字符串或 None
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/api/version")
                response.raise_for_status()
                data = response.json()
                return data.get("version")
        except Exception:
            return None


class CloudLLMClient(BaseLLMClient):
    """云端 LLM 客户端

    支持 OpenAI 兼容的 API 接口（OpenAI、DeepSeek 等）
    """

    def __init__(self):
        super().__init__("CloudLLM")
        settings = get_settings()
        self._api_key = settings.ai.cloud_api_key
        self._base_url = settings.ai.cloud_api_base_url.rstrip("/")
        self._api_type = settings.ai.cloud_api_type
        self._model = self._get_default_model()

    def _get_default_model(self) -> str:
        """根据 API 类型获取默认模型"""
        model_map = {
            "openai": "gpt-4o-mini",
            "deepseek": "deepseek-chat",
        }
        return model_map.get(self._api_type, "gpt-4o-mini")

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """发送对话请求到云端 API"""
        model = request.model or self._model
        start_time = time.time()

        if not self._api_key:
            raise AIModelUnavailableError(reason="云端 API Key 未配置")

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.ConnectError as e:
            raise LLMConnectionError(
                provider=self._api_type,
                reason=f"无法连接到 {self._base_url}",
            ) from e
        except httpx.TimeoutException as e:
            raise AIModelTimeoutError(model_name=model, timeout=self._timeout) from e
        except httpx.HTTPStatusError as e:
            raise AIModelResponseError(
                model_name=model,
                reason=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            ) from e

        # 解析响应
        try:
            choices = data.get("choices", [])
            if not choices:
                raise AIModelResponseError(model_name=model, reason="响应中没有 choices")

            content = choices[0].get("message", {}).get("content", "")
            elapsed = int((time.time() - start_time) * 1000)
            usage = data.get("usage", {})

            if not content:
                raise AIModelResponseError(model_name=model, reason="响应内容为空")

            return LLMResponse(
                content=content,
                model=model,
                tokens_used=usage.get("total_tokens"),
                elapsed_ms=elapsed,
            )
        except (KeyError, TypeError, IndexError) as e:
            raise LLMResponseParseError(reason=f"解析云端响应失败: {e}")

    async def is_available(self) -> bool:
        """检查云端 API 是否可用"""
        return bool(self._api_key)

    def get_model_name(self) -> str:
        return self._model


class RuleEngineClient(BaseLLMClient):
    """规则引擎客户端

    当 LLM 不可用时的降级方案，使用预定义规则生成响应
    """

    def __init__(self):
        super().__init__("RuleEngine")

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """规则引擎处理请求

        当前为占位实现，后续 Phase 中完善规则引擎逻辑
        """
        # 获取最后一条用户消息
        user_message = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_message = msg.content
                break

        # 简单的规则匹配响应
        response_text = (
            "[规则引擎] 当前 LLM 服务不可用，正在使用规则引擎处理您的请求。\n\n"
            f"收到消息: {user_message[:100]}...\n\n"
            "提示: 请在设置中配置本地 Ollama 或云端 API 以获得更好的 AI 体验。"
        )

        return LLMResponse(
            content=response_text,
            model="rule-engine-v1",
            tokens_used=0,
            elapsed_ms=0,
        )

    async def is_available(self) -> bool:
        """规则引擎始终可用"""
        return True

    def get_model_name(self) -> str:
        return "rule-engine-v1"


# ==========================================
# 工厂函数
# ==========================================

# 全局客户端缓存
_client_cache: dict[str, BaseLLMClient] = {}


def get_llm_client(mode: Optional[str] = None) -> BaseLLMClient:
    """获取 LLM 客户端实例（工厂函数）

    根据指定的 AI 模式返回对应的客户端实例。
    使用缓存避免重复创建。

    Args:
        mode: AI 模式，默认从配置读取

    Returns:
        LLM 客户端实例
    """
    settings = get_settings()
    ai_mode = mode or settings.ai.ai_mode

    # 检查缓存
    if ai_mode in _client_cache:
        return _client_cache[ai_mode]

    # 创建客户端
    if ai_mode == AIMode.LOCAL.value:
        client = OllamaClient()
    elif ai_mode == AIMode.CLOUD.value:
        client = CloudLLMClient()
    elif ai_mode == AIMode.RULE.value:
        client = RuleEngineClient()
    else:
        logger.warning(f"未知的 AI 模式: {ai_mode}，降级为规则引擎")
        client = RuleEngineClient()

    # 缓存客户端
    _client_cache[ai_mode] = client
    return client


def clear_client_cache() -> None:
    """清除客户端缓存（配置变更时调用）"""
    global _client_cache
    _client_cache = {}
```

---

### 步骤 9：创建占位路由模块

创建 `python/app/cad/__init__.py`：

```python
"""
CAD 模块
"""
```

创建 `python/app/cad/generator.py`：

```python
"""
CAD 模型生成器（占位模块）
后续 Phase 实现具体的 3D 模型生成逻辑
"""

import uuid
from datetime import datetime

from app.models.schemas import ThreeViewTaskRequest, ThreeViewTaskResponse
from app.core.response import success


async def generate_from_three_views(request: ThreeViewTaskRequest) -> dict:
    """从三视图生成 3D 模型（占位实现）

    Args:
        request: 三视图生成请求

    Returns:
        任务创建响应
    """
    # TODO: Phase 4 实现完整的三视图生成逻辑
    task = ThreeViewTaskResponse(
        task_id=str(uuid.uuid4()),
        status="pending",
        created_at=datetime.now(),
    )

    return success(data=task.model_dump())
```

创建 `python/app/cad/cadquery_gen.py`：

```python
"""
CadQuery 参数化生成（占位模块）
后续 Phase 实现自然语言到 CadQuery 脚本的转换
"""

import uuid

from app.models.schemas import CadQueryRequest, CadQueryResponse
from app.core.response import success


async def generate_cadquery(request: CadQueryRequest) -> dict:
    """从自然语言描述生成 CadQuery 脚本（占位实现）

    Args:
        request: CadQuery 生成请求

    Returns:
        生成任务响应
    """
    # TODO: Phase 4 实现完整的 CadQuery 生成逻辑
    task = CadQueryResponse(
        task_id=str(uuid.uuid4()),
        status="pending",
    )

    return success(data=task.model_dump())
```

创建 `python/app/ai/agents.py`：

```python
"""
AI Agent 模块（占位模块）
后续 Phase 5 实现六 Agent 协同工作流：
- UnderstandingAgent: 理解智能体
- PlanningAgent: 规划智能体
- ParameterAgent: 参数智能体
- NCAgent: NC 代码生成智能体
- VerificationAgent: 验证智能体
- RepairAgent: 修复智能体
"""

from app.core.response import success


async def run_agent_workflow(task_id: str, description: str) -> dict:
    """运行 AI Agent 工作流（占位实现）

    Args:
        task_id: 任务 ID
        description: 零件描述

    Returns:
        工作流执行结果
    """
    # TODO: Phase 5 实现完整的六 Agent 协同工作流
    return success(data={
        "task_id": task_id,
        "status": "pending",
        "message": "AI Agent 工作流尚未实现，将在 Phase 5 中完成",
    })
```

创建 `python/app/rag/__init__.py`：

```python
"""
RAG 知识库模块（占位）
后续 Phase 5 实现基于 ChromaDB 的工艺知识库
"""
```

创建 `python/app/services/__init__.py`：

```python
"""
业务服务模块（占位）
"""
```

---

### 步骤 10：创建 FastAPI 主应用

创建 `python/app/main.py`：

```python
"""
灵境制造 AI 后端 - FastAPI 应用入口
作为 Tauri 应用的 Sidecar 运行
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import APIRouter

from app.config import get_settings
from app.core.response import error, success, ErrorCode
from app.core.exceptions import AppException
from app.models.schemas import (
    AISettings,
    AIStatusResponse,
    HealthResponse,
    LLMRequest,
    LLMResponse,
    ProcessRouteRequest,
    ProcessRouteResponse,
)
from app.ai.llm_client import get_llm_client, OllamaClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 应用启动时间
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    处理启动和关闭时的资源初始化和清理
    """
    global _start_time
    _start_time = time.time()

    logger.info("=" * 60)
    logger.info("  灵境制造 AI 后端启动中...")
    logger.info(f"  版本: {get_settings().app_version}")
    logger.info(f"  端口: {get_settings().server.port}")
    logger.info(f"  AI 模式: {get_settings().ai.ai_mode}")
    logger.info("=" * 60)

    # 确保数据目录存在
    storage = get_settings().storage
    for directory in [storage.data_dir, storage.models_dir, storage.uploads_dir, storage.logs_dir]:
        os.makedirs(directory, exist_ok=True)

    logger.info("数据目录初始化完成")

    yield

    logger.info("灵境制造 AI 后端已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="灵境制造 AI 后端",
    description="面向制造行业的 AI 驱动 3D 模型生成与工艺管理 API",
    version=get_settings().app_version,
    lifespan=lifespan,
)

# CORS 中间件配置
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 全局异常处理
# ==========================================

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """业务异常处理"""
    logger.warning(f"业务异常: {exc.message} (code={exc.code})")
    return JSONResponse(
        status_code=200,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未捕获异常处理"""
    logger.error(f"未捕获异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=error(
            code=ErrorCode.UNKNOWN_ERROR,
            message=f"服务器内部错误: {str(exc)}",
        ),
    )


# ==========================================
# 健康检查路由
# ==========================================

@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查接口

    返回服务运行状态、版本信息和 AI 后端状态
    """
    import asyncio

    # 获取 AI 状态
    ai_status = None
    try:
        ai_status = await _get_ai_status()
    except Exception as e:
        logger.warning(f"获取 AI 状态失败: {e}")

    return HealthResponse(
        status="healthy",
        version=get_settings().app_version,
        uptime=time.time() - _start_time,
        ai_status=ai_status,
    )


# ==========================================
# API 路由
# ==========================================

api_router = APIRouter(prefix="/api")


# --- AI 相关接口 ---

@api_router.get("/ai/status", tags=["AI"])
async def get_ai_status():
    """获取 AI 后端状态

    检查 Ollama 和云端 API 的可用性，返回当前配置和已安装模型列表
    """
    return success(data=await _get_ai_status())


@api_router.post("/ai/chat", response_model=dict, tags=["AI"])
async def chat_with_llm(request: LLMRequest):
    """LLM 对话接口

    发送对话消息到 LLM，返回生成的文本内容。
    支持本地 Ollama 和云端 API 两种模式。
    """
    client = get_llm_client()

    # 检查客户端是否可用
    if not await client.is_available():
        from app.core.exceptions import AIModelUnavailableError
        raise AIModelUnavailableError(reason=f"{client.name} 不可用")

    # 发送请求（带重试）
    response = await client.chat_with_retry(request)

    return success(data=response.model_dump())


@api_router.put("/ai/settings", tags=["AI"])
async def update_ai_settings(new_settings: AISettings):
    """更新 AI 设置

    更新 AI 模式、模型选择等配置。
    注意：云端 API Key 不会返回给前端。
    """
    from app.config import reload_settings, _settings
    import os

    # 更新环境变量
    os.environ["LJ_AI_MODE"] = new_settings.mode.value
    os.environ["LJ_OLLAMA_MODEL"] = new_settings.ollama_model
    os.environ["LJ_OLLAMA_URL"] = new_settings.ollama_base_url
    if new_settings.cloud_api_key:
        os.environ["LJ_CLOUD_API_KEY"] = new_settings.cloud_api_key
    os.environ["LJ_CLOUD_API_TYPE"] = new_settings.cloud_api_type
    os.environ["LJ_CLOUD_API_BASE"] = new_settings.cloud_api_base_url

    # 重新加载配置
    reload_settings()

    # 清除 LLM 客户端缓存
    from app.ai.llm_client import clear_client_cache
    clear_client_cache()

    return success(message="AI 设置已更新")


# --- CAD 相关接口（占位） ---

@api_router.post("/cad/three-view-to-3d", tags=["CAD"])
async def create_three_view_task(request: ThreeViewTaskRequest):
    """创建三视图生成 3D 模型任务（占位）"""
    from app.cad.generator import generate_from_three_views
    return await generate_from_three_views(request)


@api_router.post("/cad/cadquery", tags=["CAD"])
async def create_cadquery_task(request: CadQueryRequest):
    """创建 CadQuery 生成任务（占位）"""
    from app.cad.cadquery_gen import generate_cadquery
    return await generate_cadquery(request)


# --- 工艺规划接口（占位） ---

@api_router.post("/process/route", tags=["工艺"])
async def generate_process_route(request: ProcessRouteRequest):
    """生成工艺路线（占位）"""
    import uuid
    # TODO: Phase 5 实现完整的工艺路线生成
    result = ProcessRouteResponse(
        route_id=str(uuid.uuid4()),
        part_description=request.part_description,
        steps=[],
    )
    return success(data=result.model_dump())


# 注册 API 路由
app.include_router(api_router)


# ==========================================
# 辅助函数
# ==========================================

async def _get_ai_status() -> AIStatusResponse:
    """获取 AI 状态信息

    Returns:
        AI 状态响应
    """
    cfg = get_settings().ai

    # 检查 Ollama
    ollama_available = False
    ollama_version = None
    installed_models = []

    try:
        ollama_client = OllamaClient()
        ollama_available = await ollama_client.is_available()
        if ollama_available:
            # 并行获取版本和模型列表
            import asyncio
            version_task = ollama_client.get_version()
            models_task = ollama_client.list_models()
            ollama_version, installed_models = await asyncio.gather(
                version_task, models_task
            )
    except Exception as e:
        logger.warning(f"检查 Ollama 状态失败: {e}")

    return AIStatusResponse(
        mode=cfg.ai_mode,
        ollama_available=ollama_available,
        ollama_version=ollama_version,
        installed_models=installed_models,
        cloud_configured=bool(cfg.cloud_api_key),
        cloud_api_type=cfg.cloud_api_type if cfg.cloud_api_key else None,
    )


# ==========================================
# 入口点
# ==========================================

def main():
    """应用入口"""
    cfg = get_settings().server

    uvicorn.run(
        "app.main:app",
        host=cfg.host,
        port=cfg.port,
        log_level="info" if cfg.access_log else "warning",
        access_log=cfg.access_log,
    )


if __name__ == "__main__":
    main()
```

---

### 步骤 11：创建 PyInstaller 打包脚本

创建 `python/build.py`：

```python
"""
灵境制造 AI 后端 - PyInstaller 打包脚本

用法：
    # 打包为单文件可执行程序
    python build.py

    # 打包为单目录
    python build.py --onedir

    # 指定输出名称
    python build.py --name lingjing-python-backend

    # 查看帮助
    python build.py --help
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="灵境制造 AI 后端打包工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python build.py                    # 打包为单文件
  python build.py --onedir           # 打包为单目录
  python build.py --name my-app      # 指定输出名称
        """,
    )

    parser.add_argument(
        "--name",
        default="lingjing-python-backend",
        help="输出可执行文件名称（默认: lingjing-python-backend）",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="打包为单目录模式（默认为单文件模式）",
    )
    parser.add_argument(
        "--noconfirm",
        action="store_true",
        help="覆盖输出目录时不确认",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="打包前清理构建缓存",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式（保留控制台窗口）",
    )

    return parser.parse_args()


def clean_build():
    """清理构建缓存"""
    dirs_to_clean = ["build", "dist"]
    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"清理目录: {d}")
            shutil.rmtree(d)


def build(args):
    """执行打包"""
    # 切换到脚本所在目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # 清理构建缓存
    if args.clean:
        clean_build()

    # 构建 PyInstaller 命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", args.name,
        "--clean",
    ]

    # 单文件或单目录模式
    if args.onedir:
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    # 调试模式
    if not args.debug:
        cmd.extend(["--noconsole", "--windowed"])

    # 隐藏导入（解决动态导入问题）
    hidden_imports = [
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "multipart",
    ]

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # 收集数据文件
    cmd.extend([
        "--collect-data", "pydantic",
        "--collect-data", "fastapi",
    ])

    # 添加图标（如果存在）
    icon_path = script_dir / "assets" / "icon.ico"
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    # 入口文件
    cmd.append("app/main.py")

    print("=" * 60)
    print("  灵境制造 AI 后端 - 打包工具")
    print("=" * 60)
    print(f"  模式: {'单目录' if args.onedir else '单文件'}")
    print(f"  名称: {args.name}")
    print(f"  调试: {'是' if args.debug else '否'}")
    print("=" * 60)
    print()

    # 执行打包
    print("开始打包...")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print(f"\n打包失败！返回码: {result.returncode}")
        sys.exit(1)

    # 输出结果路径
    if args.onedir:
        output_path = script_dir / "dist" / args.name
    else:
        # Windows 下添加 .exe 后缀
        if sys.platform == "win32":
            output_path = script_dir / "dist" / f"{args.name}.exe"
        else:
            output_path = script_dir / "dist" / args.name

    print()
    print("=" * 60)
    print("  打包成功！")
    print(f"  输出路径: {output_path}")
    print("=" * 60)

    return output_path


if __name__ == "__main__":
    args = parse_args()
    build(args)
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

1. **依赖安装验证**：在 `python/` 目录下执行 `pip install -r requirements.txt`，确认所有依赖安装成功
2. **应用启动验证**：在 `python/` 目录下执行 `python -m app.main`，确认：
   - 控制台输出"灵境制造 AI 后端启动中..."
   - 服务监听在 8765 端口
3. **健康检查验证**：访问 `http://localhost:8765/health`，确认：
   - 返回 JSON 格式的健康状态
   - 包含 `status: "healthy"` 字段
   - 包含 `version` 和 `uptime` 字段
4. **AI 状态验证**：访问 `http://localhost:8765/api/ai/status`，确认：
   - 返回 AI 模式和 Ollama 状态
   - 包含 `mode`、`ollama_available` 字段
5. **Swagger 文档验证**：访问 `http://localhost:8765/docs`，确认：
   - Swagger UI 正常显示
   - 可以看到所有注册的 API 接口
6. **异常处理验证**：访问 `http://localhost:8765/api/nonexistent`，确认：
   - 返回标准错误格式 `{"code": 3, "message": "Not Found", "data": null}`
7. **打包脚本验证**：执行 `python build.py --help`，确认帮助信息正常输出

如果以上验证全部通过，Phase 2 完成。

---PROMPT END---

## Phase 3: 本地 LLM 集成（Ollama）

### 目标

实现完整的 Ollama 本地 LLM 管理功能，包括模型管理（列表、下载、删除、详情）、GPU 信息查询、SSE 流式下载进度推送，以及前端设置页面的完整实现。

### 验证标准

- [ ] `python/app/ai/ollama_manager.py` 包含 OllamaManager 类，所有方法实现完整
- [ ] `python/app/ai/ollama_routes.py` 包含所有 API 路由，SSE 流式推送正常
- [ ] `main.py` 中注册了 ollama 路由
- [ ] `GET /api/ollama/status` 返回 Ollama 运行状态
- [ ] `GET /api/ollama/models` 返回已安装模型列表
- [ ] `GET /api/ollama/models/recommended` 返回推荐模型列表
- [ ] `POST /api/ollama/models/pull/{name}` 返回 SSE 流式进度
- [ ] `DELETE /api/ollama/models/{name}` 成功删除模型
- [ ] `GET /api/ollama/gpu-info` 返回 GPU 信息
- [ ] 前端 Settings.vue 包含 AI 模式切换、本地模型管理、云端 API 配置、通用设置
- [ ] 前端 TypeScript 编译无报错

---

---PROMPT START---

## 任务：实现本地 LLM 集成（Ollama）（Phase 3）

你是一个资深 Python 后端工程师和 Vue 3 前端工程师。请在已有的灵境制造 V4 项目（Phase 0-2 已完成）基础上，实现完整的 Ollama 本地 LLM 集成功能和前端设置页面。

### 重要约定
- 所有注释使用中文（docstring 和行内注释）
- Python 代码使用 async/await 异步编程
- Vue 代码使用 Composition API + `<script setup lang="ts">`
- 使用 Element Plus 组件库
- API 响应使用统一格式 `{"code": 0, "message": "success", "data": ...}`

### 项目信息
- 项目根目录：`lingjing-v4`
- Python 后端目录：`lingjing-v4/python/`
- 应用代码目录：`lingjing-v4/python/app/`
- 前端源码目录：`lingjing-v4/src/`
- FastAPI 默认端口：8765
- Ollama 默认地址：`http://localhost:11434`

### 已有代码说明
- `app/config.py`：配置管理，包含 `AIConfig`（ollama_base_url, ollama_model, cloud_api_key 等）
- `app/core/response.py`：统一响应格式，提供 `success()` 和 `error()` 函数
- `app/core/exceptions.py`：自定义异常（AIModelUnavailableError 等）
- `app/models/schemas.py`：Pydantic 数据模型（AISettings, AIStatusResponse, LLMRequest 等）
- `app/ai/llm_client.py`：LLM 客户端抽象层（BaseLLMClient, OllamaClient, CloudLLMClient, RuleEngineClient）
- `app/main.py`：FastAPI 入口，已注册 `api_router`（前缀 `/api`）

---

### 步骤 1：创建 Ollama 管理器

创建 `python/app/ai/ollama_manager.py`：

```python
"""
Ollama 模型管理器
提供 Ollama 服务的完整管理功能，包括模型列表、下载、删除、详情查询和 GPU 信息获取
"""

import logging
from typing import Optional, AsyncGenerator

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# 推荐模型列表
RECOMMENDED_MODELS = [
    {
        "name": "qwen2.5:7b",
        "size": "4.7 GB",
        "description": "通义千问 2.5 7B - 综合能力最强的中文开源模型，适合工艺理解和文本生成",
        "category": "通用",
        "recommended": True,
    },
    {
        "name": "qwen2.5:3b",
        "size": "2.0 GB",
        "description": "通义千问 2.5 3B - 轻量级中文模型，适合配置较低的设备，响应速度快",
        "category": "通用",
        "recommended": True,
    },
    {
        "name": "deepseek-r1:7b",
        "size": "4.7 GB",
        "description": "DeepSeek-R1 7B - 推理能力出色的开源模型，适合复杂工艺分析和参数优化",
        "category": "推理",
        "recommended": True,
    },
    {
        "name": "qwen2.5-coder:7b",
        "size": "4.7 GB",
        "description": "通义千问 2.5 Coder 7B - 代码生成专用模型，适合 G 代码生成和脚本编写",
        "category": "代码",
        "recommended": True,
    },
]


class OllamaManager:
    """Ollama 模型管理器

    封装 Ollama HTTP API，提供模型管理、状态查询和 GPU 信息获取功能。
    所有方法均为异步实现，支持 SSE 流式响应。
    """

    def __init__(self):
        """初始化管理器，从配置读取 Ollama 服务地址"""
        settings = get_settings()
        self._base_url = settings.ai.ollama_base_url.rstrip("/")
        self._timeout = 30  # 默认超时 30 秒

    def _get_client(self, timeout: Optional[int] = None) -> httpx.AsyncClient:
        """创建 HTTP 客户端

        Args:
            timeout: 超时时间（秒），默认使用实例配置

        Returns:
            httpx 异步客户端
        """
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout or self._timeout),
        )

    async def is_available(self) -> bool:
        """检查 Ollama 服务是否可用

        通过请求 /api/tags 接口判断 Ollama 是否正在运行。

        Returns:
            True 表示 Ollama 服务可用
        """
        try:
            async with self._get_client(timeout=5) as client:
                response = await client.get("/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama 不可用: {e}")
            return False

    async def get_version(self) -> Optional[str]:
        """获取 Ollama 版本号

        Returns:
            版本字符串，如 "0.5.4"；不可用时返回 None
        """
        try:
            async with self._get_client(timeout=5) as client:
                response = await client.get("/api/version")
                response.raise_for_status()
                data = response.json()
                return data.get("version")
        except Exception as e:
            logger.warning(f"获取 Ollama 版本失败: {e}")
            return None

    async def list_models(self) -> list[dict]:
        """获取已安装的模型列表

        Returns:
            模型信息字典列表，每个字典包含 name, size, modified_at, details 等字段
        """
        try:
            async with self._get_client(timeout=10) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                data = response.json()
                models = data.get("models", [])
                # 提取关键信息
                result = []
                for model in models:
                    result.append({
                        "name": model.get("name", ""),
                        "size": model.get("size", 0),
                        "modified_at": model.get("modified_at", ""),
                        "details": model.get("details", {}),
                        # 格式化文件大小
                        "size_display": self._format_size(model.get("size", 0)),
                        # 模型系列名称（去掉标签部分）
                        "model_family": model.get("details", {}).get("family", ""),
                        "quantization_level": model.get("details", {}).get("quantization_level", ""),
                    })
                return result
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []

    async def pull_model(self, model_name: str) -> AsyncGenerator[dict, None]:
        """拉取（下载）模型，SSE 流式返回进度

        通过 Ollama 的 /api/pull 接口下载模型，以 Server-Sent Events 方式
        逐条返回下载进度信息。

        Args:
            model_name: 模型名称，如 "qwen2.5:7b"

        Yields:
            进度信息字典，包含 status, digest, total, completed 等字段
        """
        payload = {
            "name": model_name,
            "stream": True,
        }

        try:
            async with self._get_client(timeout=600) as client:
                # 使用 stream 模式接收 SSE 响应
                async with client.stream("POST", "/api/pull", json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            import json
                            data = json.loads(line)

                            # 构建进度信息
                            status = data.get("status", "")

                            # 计算下载进度百分比
                            progress = None
                            total = data.get("total", 0)
                            completed = data.get("completed", 0)
                            if total and total > 0:
                                progress = round((completed / total) * 100, 1)

                            yield {
                                "status": status,
                                "digest": data.get("digest", ""),
                                "total": total,
                                "completed": completed,
                                "progress": progress,
                            }

                            # 下载完成
                            if status == "success":
                                logger.info(f"模型 {model_name} 下载完成")
                                break

                        except Exception as parse_error:
                            logger.warning(f"解析 SSE 行失败: {parse_error}")
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"下载模型失败: HTTP {e.response.status_code}")
            yield {
                "status": "error",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            logger.error(f"下载模型异常: {e}")
            yield {
                "status": "error",
                "error": str(e),
            }

    async def delete_model(self, model_name: str) -> bool:
        """删除已安装的模型

        Args:
            model_name: 模型名称

        Returns:
            True 表示删除成功
        """
        payload = {"name": model_name}

        try:
            async with self._get_client(timeout=30) as client:
                response = await client.delete("/api/delete", json=payload)
                response.raise_for_status()
                logger.info(f"模型 {model_name} 已删除")
                return True
        except httpx.HTTPStatusError as e:
            logger.error(f"删除模型失败: HTTP {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"删除模型异常: {e}")
            return False

    async def show_model_info(self, model_name: str) -> Optional[dict]:
        """获取模型详细信息

        Args:
            model_name: 模型名称

        Returns:
            模型详细信息字典，包含 license, modelfile, parameters, template 等
        """
        payload = {"name": model_name}

        try:
            async with self._get_client(timeout=10) as client:
                response = await client.post("/api/show", json=payload)
                response.raise_for_status()
                data = response.json()
                return {
                    "name": model_name,
                    "license": data.get("license", ""),
                    "modelfile": data.get("modelfile", ""),
                    "parameters": data.get("parameters", ""),
                    "template": data.get("template", ""),
                    "details": data.get("details", {}),
                    "model_info": data.get("model_info", {}),
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"获取模型信息失败: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"获取模型信息异常: {e}")
            return None

    async def get_gpu_info(self) -> dict:
        """获取 GPU 信息

        通过 Ollama 的 /api/ps 接口获取当前 GPU 使用情况。

        Returns:
            GPU 信息字典，包含 available, models 等字段
        """
        try:
            async with self._get_client(timeout=10) as client:
                response = await client.get("/api/ps")
                response.raise_for_status()
                data = response.json()
                return {
                    "available": True,
                    "models": data.get("models", []),
                }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # 旧版本 Ollama 不支持 /api/ps
                return {
                    "available": False,
                    "models": [],
                    "message": "当前 Ollama 版本不支持 GPU 信息查询，请升级到 0.5.0+",
                }
            logger.error(f"获取 GPU 信息失败: HTTP {e.response.status_code}")
            return {"available": False, "models": []}
        except Exception as e:
            logger.error(f"获取 GPU 信息异常: {e}")
            return {"available": False, "models": []}

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化文件大小

        Args:
            size_bytes: 字节数

        Returns:
            人类可读的大小字符串，如 "4.7 GB"
        """
        if size_bytes <= 0:
            return "未知"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.1f} {units[unit_index]}"


# 全局单例
_ollama_manager: Optional[OllamaManager] = None


def get_ollama_manager() -> OllamaManager:
    """获取 Ollama 管理器单例

    Returns:
        OllamaManager 实例
    """
    global _ollama_manager
    if _ollama_manager is None:
        _ollama_manager = OllamaManager()
    return _ollama_manager
```

---

### 步骤 2：创建 Ollama API 路由

创建 `python/app/ai/ollama_routes.py`：

```python
"""
Ollama API 路由
提供 Ollama 模型管理的 RESTful API 接口
"""

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

from app.ai.ollama_manager import (
    get_ollama_manager,
    RECOMMENDED_MODELS,
)
from app.core.response import success, error, ErrorCode

logger = logging.getLogger(__name__)

# 创建路由器
ollama_router = APIRouter(prefix="/ollama", tags=["Ollama"])


@ollama_router.get("/status")
async def get_ollama_status():
    """获取 Ollama 服务状态

    检查 Ollama 是否正在运行，返回版本号和可用性信息。
    """
    manager = get_ollama_manager()

    # 并行检查可用性和版本
    available = await manager.is_available()
    version = None

    if available:
        version = await manager.get_version()

    return success(data={
        "available": available,
        "version": version,
        "base_url": manager._base_url,
    })


@ollama_router.get("/models")
async def list_models():
    """获取已安装的模型列表

    返回本地 Ollama 中已安装的所有模型及其详细信息。
    """
    manager = get_ollama_manager()

    if not await manager.is_available():
        return error(
            code=ErrorCode.AI_MODEL_UNAVAILABLE,
            message="Ollama 服务不可用，请确认 Ollama 已启动",
        )

    models = await manager.list_models()
    return success(data={
        "models": models,
        "total": len(models),
    })


@ollama_router.get("/models/recommended")
async def get_recommended_models():
    """获取推荐模型列表

    返回预定义的推荐模型列表，包含模型大小、描述和分类信息。
    同时标注哪些模型已安装。
    """
    manager = get_ollama_manager()

    # 获取已安装模型名称集合
    installed_names = set()
    if await manager.is_available():
        installed_models = await manager.list_models()
        installed_names = {m["name"] for m in installed_models}

    # 标注安装状态
    result = []
    for model in RECOMMENDED_MODELS:
        model_info = {**model}
        model_info["installed"] = model_info["name"] in installed_names
        result.append(model_info)

    return success(data={
        "models": result,
        "total": len(result),
    })


@ollama_router.post("/models/pull/{model_name}")
async def pull_model(model_name: str):
    """拉取（下载）模型

    通过 SSE（Server-Sent Events）流式返回下载进度。
    前端应使用 EventSource 或 fetch + ReadableStream 接收。

    Args:
        model_name: 模型名称，如 "qwen2.5:7b"
    """
    manager = get_ollama_manager()

    if not await manager.is_available():
        return error(
            code=ErrorCode.AI_MODEL_UNAVAILABLE,
            message="Ollama 服务不可用，请确认 Ollama 已启动",
        )

    async def event_generator():
        """SSE 事件生成器"""
        try:
            async for progress in manager.pull_model(model_name):
                # 格式化为 SSE 数据
                yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"

                # 如果出错，终止流
                if progress.get("status") == "error":
                    break
        except Exception as e:
            logger.error(f"模型下载流异常: {e}")
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@ollama_router.delete("/models/{model_name}")
async def delete_model(model_name: str):
    """删除模型

    从本地 Ollama 中删除指定模型。

    Args:
        model_name: 模型名称
    """
    manager = get_ollama_manager()

    if not await manager.is_available():
        return error(
            code=ErrorCode.AI_MODEL_UNAVAILABLE,
            message="Ollama 服务不可用",
        )

    success_flag = await manager.delete_model(model_name)

    if success_flag:
        return success(message=f"模型 {model_name} 已删除")
    else:
        return error(
            code=ErrorCode.AI_MODEL_ERROR,
            message=f"删除模型 {model_name} 失败",
        )


@ollama_router.get("/models/{model_name}/info")
async def get_model_info(model_name: str):
    """获取模型详细信息

    Args:
        model_name: 模型名称
    """
    manager = get_ollama_manager()

    if not await manager.is_available():
        return error(
            code=ErrorCode.AI_MODEL_UNAVAILABLE,
            message="Ollama 服务不可用",
        )

    info = await manager.show_model_info(model_name)

    if info:
        return success(data=info)
    else:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"未找到模型 {model_name}",
        )


@ollama_router.get("/gpu-info")
async def get_gpu_info():
    """获取 GPU 信息

    返回当前 GPU 使用情况和正在运行的模型信息。
    需要 Ollama 0.5.0+ 版本支持。
    """
    manager = get_ollama_manager()

    if not await manager.is_available():
        return error(
            code=ErrorCode.AI_MODEL_UNAVAILABLE,
            message="Ollama 服务不可用",
        )

    gpu_info = await manager.get_gpu_info()
    return success(data=gpu_info)
```

---

### 步骤 3：在 main.py 中注册 Ollama 路由

修改 `python/app/main.py`，在 `app.include_router(api_router)` 之前，添加以下代码：

```python
# 注册 Ollama 路由
from app.ai.ollama_routes import ollama_router
app.include_router(ollama_router, prefix="/api")
```

同时，移除 main.py 中原有的占位 CAD 路由（`/api/cad/three-view-to-3d` 和 `/api/cad/cadquery`），以及占位的工艺规划路由（`/api/process/route`），因为它们将在 Phase 4 和 Phase 5 中被完整的路由模块替代。

---

### 步骤 4：创建前端 API 服务封装

创建 `src/services/ollama.ts`：

```typescript
/**
 * Ollama API 服务封装
 * 封装所有与 Ollama 模型管理相关的 API 调用
 */

import request from './request'

/** Ollama 状态信息 */
export interface OllamaStatus {
  available: boolean
  version: string | null
  base_url: string
}

/** 已安装模型信息 */
export interface OllamaModel {
  name: string
  size: number
  modified_at: string
  details: Record<string, unknown>
  size_display: string
  model_family: string
  quantization_level: string
}

/** 推荐模型信息 */
export interface RecommendedModel {
  name: string
  size: string
  description: string
  category: string
  recommended: boolean
  installed: boolean
}

/** 模型下载进度 */
export interface PullProgress {
  status: string
  digest: string
  total: number
  completed: number
  progress: number | null
  error?: string
}

/** GPU 信息 */
export interface GpuInfo {
  available: boolean
  models: Record<string, unknown>[]
  message?: string
}

/** AI 设置 */
export interface AISettingsForm {
  mode: 'local' | 'cloud' | 'rule'
  ollama_model: string
  ollama_base_url: string
  cloud_api_type: string
  cloud_api_key: string
  cloud_api_base_url: string
  cloud_model_name: string
}

/**
 * 获取 Ollama 服务状态
 */
export async function getOllamaStatus(): Promise<OllamaStatus> {
  const res = await request.get('/api/ollama/status')
  return res.data.data
}

/**
 * 获取已安装模型列表
 */
export async function listModels(): Promise<{ models: OllamaModel[]; total: number }> {
  const res = await request.get('/api/ollama/models')
  return res.data.data
}

/**
 * 获取推荐模型列表
 */
export async function getRecommendedModels(): Promise<{ models: RecommendedModel[]; total: number }> {
  const res = await request.get('/api/ollama/models/recommended')
  return res.data.data
}

/**
 * 拉取（下载）模型（SSE 流式）
 * @param modelName 模型名称
 * @param onProgress 进度回调
 * @returns Promise，下载完成时 resolve
 */
export async function pullModel(
  modelName: string,
  onProgress: (progress: PullProgress) => void
): Promise<void> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'

  const response = await fetch(`${baseUrl}/api/ollama/models/pull/${encodeURIComponent(modelName)}`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`下载模型失败: HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('无法获取响应流')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 解析 SSE 数据行
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data: PullProgress = JSON.parse(line.slice(6))
          onProgress(data)

          // 如果出错，抛出异常
          if (data.status === 'error') {
            throw new Error(data.error || '下载失败')
          }
        } catch (e) {
          if (e instanceof SyntaxError) continue
          throw e
        }
      }
    }
  }
}

/**
 * 删除模型
 * @param modelName 模型名称
 */
export async function deleteModel(modelName: string): Promise<void> {
  await request.delete(`/api/ollama/models/${encodeURIComponent(modelName)}`)
}

/**
 * 获取模型详细信息
 * @param modelName 模型名称
 */
export async function getModelInfo(modelName: string): Promise<Record<string, unknown>> {
  const res = await request.get(`/api/ollama/models/${encodeURIComponent(modelName)}/info`)
  return res.data.data
}

/**
 * 获取 GPU 信息
 */
export async function getGpuInfo(): Promise<GpuInfo> {
  const res = await request.get('/api/ollama/gpu-info')
  return res.data.data
}

/**
 * 获取 AI 状态
 */
export async function getAIStatus(): Promise<Record<string, unknown>> {
  const res = await request.get('/api/ai/status')
  return res.data.data
}

/**
 * 更新 AI 设置
 */
export async function updateAISettings(settings: AISettingsForm): Promise<void> {
  await request.put('/api/ai/settings', settings)
}

/**
 * 测试云端 API 连接
 */
export async function testCloudConnection(config: {
  api_type: string
  api_key: string
  api_base_url: string
  model_name: string
}): Promise<{ success: boolean; message: string }> {
  const res = await request.post('/api/ai/test-cloud', config)
  return res.data.data
}
```

创建 `src/services/request.ts`（如果尚未存在）：

```typescript
/**
 * Axios 请求封装
 * 统一处理请求拦截、响应拦截和错误处理
 */

import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const data = response.data
    // 业务错误码处理
    if (data.code !== undefined && data.code !== 0) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return response
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const messages: Record<number, string> = {
        400: '请求参数错误',
        401: '未授权',
        403: '禁止访问',
        404: '资源不存在',
        500: '服务器内部错误',
      }
      ElMessage.error(messages[status] || `请求失败 (${status})`)
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时')
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default request
```

---

### 步骤 5：创建前端设置页面

创建 `src/views/Settings.vue`：

```vue
<template>
  <div class="settings-page">
    <div class="settings-header">
      <h2>设置</h2>
      <p class="settings-desc">配置 AI 模型、云端服务和应用偏好</p>
    </div>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- AI 模式设置 -->
      <el-tab-pane label="AI 设置" name="ai">
        <div class="section">
          <h3>AI 模式</h3>
          <p class="section-desc">选择 AI 推理引擎，不同模式影响数据处理方式</p>

          <el-radio-group v-model="aiSettings.mode" @change="onModeChange" class="mode-group">
            <el-radio value="local" border>
              <div class="mode-item">
                <el-icon><Monitor /></el-icon>
                <div>
                  <strong>本地模式</strong>
                  <span>使用本地 Ollama，数据完全不出设备</span>
                </div>
              </div>
            </el-radio>
            <el-radio value="cloud" border>
              <div class="mode-item">
                <el-icon><Cloudy /></el-icon>
                <div>
                  <strong>云端模式</strong>
                  <span>使用云端 API，需配置 API Key</span>
                </div>
              </div>
            </el-radio>
            <el-radio value="rule" border>
              <div class="mode-item">
                <el-icon><Setting /></el-icon>
                <div>
                  <strong>离线模式</strong>
                  <span>使用规则引擎，无需 AI 模型</span>
                </div>
              </div>
            </el-radio>
          </el-radio-group>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="privacy-alert"
          >
            <template #title>
              <strong>隐私保护</strong>
            </template>
            <template #default>
              本地模式下，所有数据（包括零件描述、工艺参数、G 代码）均在本地处理，不会上传到任何服务器。
              切换到云端模式后，仅非敏感文本查询会发送至云端 API，CAD 文件和专有工艺参数永不上传。
            </template>
          </el-alert>
        </div>

        <!-- 本地模型管理 -->
        <div v-if="aiSettings.mode === 'local'" class="section">
          <h3>本地模型管理</h3>
          <p class="section-desc">管理 Ollama 本地模型，查看状态、下载推荐模型</p>

          <!-- Ollama 状态 -->
          <div class="ollama-status-card">
            <div class="status-row">
              <span class="status-label">Ollama 服务状态：</span>
              <el-tag :type="ollamaStatus.available ? 'success' : 'danger'" effect="dark">
                {{ ollamaStatus.available ? '运行中' : '未连接' }}
              </el-tag>
              <span v-if="ollamaStatus.version" class="version-text">
                版本 {{ ollamaStatus.version }}
              </span>
            </div>
            <div class="status-row">
              <span class="status-label">服务地址：</span>
              <el-input
                v-model="aiSettings.ollama_base_url"
                size="small"
                style="width: 300px"
                placeholder="http://localhost:11434"
              />
              <el-button size="small" @click="checkOllamaStatus" :loading="checkingStatus">
                刷新状态
              </el-button>
            </div>
          </div>

          <!-- 已安装模型列表 -->
          <div class="subsection">
            <div class="subsection-header">
              <h4>已安装模型</h4>
              <el-button size="small" @click="refreshModels" :loading="loadingModels">
                刷新列表
              </el-button>
            </div>

            <el-table
              v-loading="loadingModels"
              :data="installedModels"
              stripe
              empty-text="暂无已安装模型"
              style="width: 100%"
            >
              <el-table-column prop="name" label="模型名称" min-width="180" />
              <el-table-column prop="size_display" label="大小" width="120" />
              <el-table-column prop="model_family" label="模型系列" width="150" />
              <el-table-column prop="quantization_level" label="量化级别" width="120" />
              <el-table-column prop="modified_at" label="修改时间" width="180">
                <template #default="{ row }">
                  {{ formatDate(row.modified_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button
                    type="danger"
                    size="small"
                    text
                    @click="confirmDeleteModel(row.name)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 推荐模型 -->
          <div class="subsection">
            <div class="subsection-header">
              <h4>推荐模型</h4>
            </div>

            <div class="recommended-grid">
              <el-card
                v-for="model in recommendedModels"
                :key="model.name"
                class="model-card"
                shadow="hover"
              >
                <template #header>
                  <div class="card-header">
                    <span class="model-name">{{ model.name }}</span>
                    <el-tag
                      v-if="model.installed"
                      type="success"
                      size="small"
                    >
                      已安装
                    </el-tag>
                    <el-tag v-else type="info" size="small">{{ model.size }}</el-tag>
                  </div>
                </template>

                <p class="model-desc">{{ model.description }}</p>
                <div class="card-footer">
                  <el-tag size="small" effect="plain">{{ model.category }}</el-tag>
                  <el-button
                    v-if="!model.installed"
                    type="primary"
                    size="small"
                    :loading="pullingModel === model.name"
                    :disabled="!!pullingModel"
                    @click="startPullModel(model.name)"
                  >
                    {{ pullingModel === model.name ? '下载中...' : '下载' }}
                  </el-button>
                </div>

                <!-- 下载进度条 -->
                <div v-if="pullingModel === model.name && pullProgress" class="progress-wrapper">
                  <el-progress
                    :percentage="pullProgress.progress || 0"
                    :status="pullProgress.status === 'error' ? 'exception' : undefined"
                    :stroke-width="8"
                  />
                  <span class="progress-text">{{ pullProgress.status }}</span>
                </div>
              </el-card>
            </div>
          </div>
        </div>

        <!-- 云端 API 配置 -->
        <div v-if="aiSettings.mode === 'cloud'" class="section">
          <h3>云端 API 配置</h3>
          <p class="section-desc">配置云端 AI 服务提供商和 API 密钥</p>

          <el-form :model="aiSettings" label-width="120px" label-position="top">
            <el-form-item label="API 提供商">
              <el-select v-model="aiSettings.cloud_api_type" style="width: 100%">
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="OpenAI" value="openai" />
                <el-option label="自定义 (OpenAI 兼容)" value="custom" />
              </el-select>
            </el-form-item>

            <el-form-item label="API Key">
              <el-input
                v-model="aiSettings.cloud_api_key"
                type="password"
                show-password
                placeholder="请输入 API Key"
              />
            </el-form-item>

            <el-form-item label="API 地址">
              <el-input
                v-model="aiSettings.cloud_api_base_url"
                placeholder="https://api.deepseek.com/v1"
              />
            </el-form-item>

            <el-form-item label="模型名称">
              <el-input
                v-model="aiSettings.cloud_model_name"
                placeholder="deepseek-chat"
              />
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="saveCloudSettings"
                :loading="savingSettings"
              >
                保存配置
              </el-button>
              <el-button
                @click="testCloudConnection"
                :loading="testingConnection"
              >
                测试连接
              </el-button>
            </el-form-item>
          </el-form>

          <el-alert
            type="warning"
            :closable="false"
            show-icon
            class="privacy-alert"
          >
            <template #title>
              <strong>数据安全提醒</strong>
            </template>
            <template #default>
              云端模式下，仅非敏感文本查询会发送至云端 API。CAD 设计文件、专有工艺参数等敏感数据永不上传。
              API Key 仅存储在本地设备，不会发送到第三方服务器。
            </template>
          </el-alert>
        </div>

        <!-- 离线模式 -->
        <div v-if="aiSettings.mode === 'rule'" class="section">
          <h3>离线模式</h3>
          <el-alert
            type="info"
            :closable="false"
            show-icon
          >
            <template #title>
              离线模式已启用
            </template>
            <template #default>
              当前使用规则引擎处理请求，无需 AI 模型。功能受限，建议安装本地 Ollama 以获得完整体验。
            </template>
          </el-alert>
        </div>

        <!-- 保存按钮 -->
        <div class="save-bar">
          <el-button
            type="primary"
            size="large"
            @click="saveSettings"
            :loading="savingSettings"
          >
            保存 AI 设置
          </el-button>
        </div>
      </el-tab-pane>

      <!-- 通用设置 -->
      <el-tab-pane label="通用" name="general">
        <div class="section">
          <h3>语言设置</h3>
          <el-select v-model="language" style="width: 200px" @change="changeLanguage">
            <el-option label="简体中文" value="zh-CN" />
            <el-option label="English" value="en-US" />
          </el-select>
        </div>

        <div class="section">
          <h3>数据目录</h3>
          <p class="section-desc">应用数据存储位置</p>
          <div class="data-dir-row">
            <el-input :model-value="dataDir" readonly />
            <el-button @click="openDataDir">打开目录</el-button>
          </div>
        </div>

        <div class="section">
          <h3>关于</h3>
          <p>灵境制造 V4.0.0</p>
          <p class="text-muted">面向制造行业的 AI 驱动 3D 模型生成与工艺管理桌面应用</p>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 删除模型确认对话框 -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="确认删除模型"
      width="420px"
    >
      <p>确定要删除模型 <strong>{{ deletingModelName }}</strong> 吗？</p>
      <p class="text-muted">删除后需要重新下载才能使用。</p>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="doDeleteModel" :loading="deletingModel">
          确认删除
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor, Cloudy, Setting } from '@element-plus/icons-vue'
import {
  getOllamaStatus,
  listModels,
  getRecommendedModels,
  pullModel,
  deleteModel,
  getAIStatus,
  updateAISettings,
  testCloudConnection as testCloudApi,
  type OllamaStatus,
  type OllamaModel,
  type RecommendedModel,
  type PullProgress,
  type AISettingsForm,
} from '@/services/ollama'

// 当前激活的标签页
const activeTab = ref('ai')

// AI 设置表单
const aiSettings = reactive<AISettingsForm>({
  mode: 'local',
  ollama_model: 'qwen2.5:7b',
  ollama_base_url: 'http://localhost:11434',
  cloud_api_type: 'deepseek',
  cloud_api_key: '',
  cloud_api_base_url: 'https://api.deepseek.com/v1',
  cloud_model_name: 'deepseek-chat',
})

// Ollama 状态
const ollamaStatus = reactive<OllamaStatus>({
  available: false,
  version: null,
  base_url: 'http://localhost:11434',
})
const checkingStatus = ref(false)

// 已安装模型
const installedModels = ref<OllamaModel[]>([])
const loadingModels = ref(false)

// 推荐模型
const recommendedModels = ref<RecommendedModel[]>([])

// 模型下载
const pullingModel = ref<string | null>(null)
const pullProgress = ref<PullProgress | null>(null)

// 模型删除
const deleteDialogVisible = ref(false)
const deletingModelName = ref('')
const deletingModel = ref(false)

// 保存状态
const savingSettings = ref(false)
const testingConnection = ref(false)

// 通用设置
const language = ref('zh-CN')
const dataDir = ref('')

/** 检查 Ollama 状态 */
async function checkOllamaStatus() {
  checkingStatus.value = true
  try {
    const status = await getOllamaStatus()
    Object.assign(ollamaStatus, status)
    aiSettings.ollama_base_url = status.base_url
  } catch {
    ollamaStatus.available = false
    ollamaStatus.version = null
  } finally {
    checkingStatus.value = false
  }
}

/** 刷新已安装模型列表 */
async function refreshModels() {
  loadingModels.value = true
  try {
    const data = await listModels()
    installedModels.value = data.models
  } catch {
    ElMessage.error('获取模型列表失败')
  } finally {
    loadingModels.value = false
  }
}

/** 加载推荐模型列表 */
async function loadRecommendedModels() {
  try {
    const data = await getRecommendedModels()
    recommendedModels.value = data.models
  } catch {
    // 静默失败
  }
}

/** 开始下载模型 */
async function startPullModel(modelName: string) {
  pullingModel.value = modelName
  pullProgress.value = null

  try {
    await pullModel(modelName, (progress) => {
      pullProgress.value = progress
    })
    ElMessage.success(`模型 ${modelName} 下载完成`)
    await Promise.all([refreshModels(), loadRecommendedModels()])
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '下载失败'
    ElMessage.error(msg)
  } finally {
    pullingModel.value = null
    pullProgress.value = null
  }
}

/** 确认删除模型 */
function confirmDeleteModel(modelName: string) {
  deletingModelName.value = modelName
  deleteDialogVisible.value = true
}

/** 执行删除模型 */
async function doDeleteModel() {
  deletingModel.value = true
  try {
    await deleteModel(deletingModelName.value)
    ElMessage.success(`模型 ${deletingModelName.value} 已删除`)
    deleteDialogVisible.value = false
    await Promise.all([refreshModels(), loadRecommendedModels()])
  } catch {
    ElMessage.error('删除模型失败')
  } finally {
    deletingModel.value = false
  }
}

/** AI 模式切换 */
function onModeChange() {
  // 模式切换时不需要立即保存，用户点击保存按钮时统一保存
}

/** 保存 AI 设置 */
async function saveSettings() {
  savingSettings.value = true
  try {
    await updateAISettings(aiSettings)
    ElMessage.success('AI 设置已保存')
  } catch {
    ElMessage.error('保存设置失败')
  } finally {
    savingSettings.value = false
  }
}

/** 保存云端设置 */
async function saveCloudSettings() {
  await saveSettings()
}

/** 测试云端连接 */
async function testCloudConnection() {
  testingConnection.value = true
  try {
    const result = await testCloudApi({
      api_type: aiSettings.cloud_api_type,
      api_key: aiSettings.cloud_api_key,
      api_base_url: aiSettings.cloud_api_base_url,
      model_name: aiSettings.cloud_model_name,
    })
    if (result.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error(`连接测试失败: ${result.message}`)
    }
  } catch {
    ElMessage.error('连接测试失败')
  } finally {
    testingConnection.value = false
  }
}

/** 切换语言 */
function changeLanguage(lang: string) {
  language.value = lang
  ElMessage.success('语言设置已更新')
}

/** 打开数据目录 */
async function openDataDir() {
  ElMessage.info('功能开发中')
}

/** 格式化日期 */
function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

/** 加载 AI 状态 */
async function loadAIStatus() {
  try {
    const status = await getAIStatus()
    aiSettings.mode = (status.mode as AISettingsForm['mode']) || 'local'
    aiSettings.cloud_api_type = (status.cloud_api_type as string) || 'deepseek'
  } catch {
    // 静默失败，使用默认值
  }
}

/** 页面初始化 */
onMounted(async () => {
  await Promise.all([
    checkOllamaStatus(),
    refreshModels(),
    loadRecommendedModels(),
    loadAIStatus(),
  ])
})
</script>

<style scoped>
.settings-page {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
}
.settings-header {
  margin-bottom: 24px;
}
.settings-header h2 {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 8px 0;
}
.settings-desc {
  color: var(--el-text-color-secondary);
  margin: 0;
}
.section {
  margin-bottom: 32px;
}
.section h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px 0;
}
.section-desc {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  margin: 0 0 16px 0;
}
.mode-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}
.mode-group .el-radio {
  width: 100%;
  height: auto;
  margin: 0;
  padding: 16px;
}
.mode-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.mode-item .el-icon {
  font-size: 24px;
  color: var(--el-color-primary);
}
.mode-item div {
  display: flex;
  flex-direction: column;
}
.mode-item strong {
  font-size: 14px;
}
.mode-item span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
.privacy-alert {
  margin-top: 16px;
}
.ollama-status-card {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.status-row:last-child {
  margin-bottom: 0;
}
.status-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}
.version-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.subsection {
  margin-bottom: 24px;
}
.subsection-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.subsection-header h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}
.recommended-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.model-card {
  transition: transform 0.2s;
}
.model-card:hover {
  transform: translateY(-2px);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.model-name {
  font-weight: 600;
  font-size: 14px;
}
.model-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  margin: 0 0 12px 0;
}
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.progress-wrapper {
  margin-top: 12px;
}
.progress-text {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  text-align: center;
}
.save-bar {
  padding-top: 24px;
  border-top: 1px solid var(--el-border-color-lighter);
  text-align: right;
}
.data-dir-row {
  display: flex;
  gap: 12px;
}
.data-dir-row .el-input {
  flex: 1;
}
.text-muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
```

---

### 步骤 6：添加云端连接测试 API

在 `python/app/main.py` 的 `api_router` 下添加云端连接测试接口：

```python
@api_router.post("/ai/test-cloud", tags=["AI"])
async def test_cloud_connection(config: dict):
    """测试云端 API 连接

    使用用户提供的配置发送测试请求，验证 API Key 和网络连通性。
    """
    import httpx

    api_type = config.get("api_type", "deepseek")
    api_key = config.get("api_key", "")
    api_base_url = config.get("api_base_url", "").rstrip("/")
    model_name = config.get("model_name", "deepseek-chat")

    if not api_key:
        return success(data={"success": False, "message": "API Key 不能为空"})

    if not api_base_url:
        return success(data={"success": False, "message": "API 地址不能为空"})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Hello, this is a test message. Reply with 'OK'."}
        ],
        "max_tokens": 10,
        "temperature": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{api_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if choices:
                return success(data={
                    "success": True,
                    "message": f"连接成功！模型: {model_name}",
                })
            else:
                return success(data={
                    "success": False,
                    "message": "API 响应异常：无 choices 字段",
                })

    except httpx.ConnectError:
        return success(data={"success": False, "message": f"无法连接到 {api_base_url}"})
    except httpx.TimeoutException:
        return success(data={"success": False, "message": "连接超时（15秒）"})
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:200] if e.response.text else ""
        return success(data={
            "success": False,
            "message": f"HTTP {e.response.status_code}: {detail}",
        })
    except Exception as e:
        return success(data={"success": False, "message": f"连接失败: {str(e)}"})
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

1. **Ollama 管理器验证**：确认 `python/app/ai/ollama_manager.py` 包含 OllamaManager 类，所有方法（is_available, list_models, pull_model, delete_model, show_model_info, get_gpu_info）实现完整
2. **推荐模型验证**：确认 RECOMMENDED_MODELS 包含 4 个模型（qwen2.5:7b, qwen2.5:3b, deepseek-r1:7b, qwen2.5-coder:7b），每个模型有 name/size/description/category 字段
3. **路由注册验证**：启动后端服务，访问 `http://localhost:8765/docs`，确认以下接口存在：
   - `GET /api/ollama/status`
   - `GET /api/ollama/models`
   - `GET /api/ollama/models/recommended`
   - `POST /api/ollama/models/pull/{model_name}`
   - `DELETE /api/ollama/models/{model_name}`
   - `GET /api/ollama/gpu-info`
   - `POST /api/ai/test-cloud`
4. **Ollama 状态验证**：访问 `GET /api/ollama/status`，确认返回 available 和 version 字段
5. **前端编译验证**：`pnpm tauri dev` 启动后，访问设置页面，确认：
   - AI 模式切换（本地/云端/离线）正常
   - 本地模式下显示 Ollama 状态和模型列表
   - 云端模式下显示 API 配置表单
   - 隐私提示正确显示
6. **TypeScript 编译验证**：确认无 TypeScript 编译错误

如果以上验证全部通过，Phase 3 完成。

---PROMPT END---

---

## Phase 4: 3D/CAD 引擎

### 目标

实现完整的 3D/CAD 引擎功能，包括三视图生成 3D 模型（TRELLIS 集成）、CadQuery 参数化生成、Three.js 3D 查看器组件和三视图上传页面。

### 验证标准

- [ ] `python/app/cad/generator.py` 重写完成，包含三视图生成路由和后台任务
- [ ] `python/app/cad/cadquery_gen.py` 重写完成，包含 CadQuery 生成路由和后台任务
- [ ] `POST /api/cad/generate-from-views` 接收 3 个图片文件 + engine 参数
- [ ] `GET /api/cad/task/{task_id}` 返回任务状态
- [ ] `GET /api/cad/download/{task_id}` 下载生成的模型文件
- [ ] `POST /api/cad/cadquery/generate` 接收 CadQueryRequest
- [ ] 前端 ThreeViewer.vue 包含 Three.js 场景、模型加载、工具栏、响应式
- [ ] 前端 MultiViewTo3D.vue 包含三图上传、引擎选择、任务提交、进度显示
- [ ] 前端 TypeScript 编译无报错

---

---PROMPT START---

## 任务：实现 3D/CAD 引擎（Phase 4）

你是一个资深 Python 后端工程师和 Vue 3 前端工程师。请在已有的灵境制造 V4 项目（Phase 0-3 已完成）基础上，实现完整的 3D/CAD 引擎功能。

### 重要约定
- 所有注释使用中文（docstring 和行内注释）
- Python 代码使用 async/await 异步编程
- Vue 代码使用 Composition API + `<script setup lang="ts">`
- 使用 Element Plus 组件库
- API 响应使用统一格式 `{"code": 0, "message": "success", "data": ...}`
- TRELLIS 和 CadQuery 的实际集成使用 TODO 注释标记，当前使用占位逻辑

### 项目信息
- 项目根目录：`lingjing-v4`
- Python 后端目录：`lingjing-v4/python/`
- 应用代码目录：`lingjing-v4/python/app/`
- 前端源码目录：`lingjing-v4/src/`
- FastAPI 默认端口：8765
- 上传文件存储目录：由 config.py 中 StorageConfig.uploads_dir 配置

### 已有代码说明
- `app/config.py`：配置管理，StorageConfig 包含 uploads_dir 和 models_dir
- `app/core/response.py`：统一响应格式
- `app/core/exceptions.py`：自定义异常
- `app/models/schemas.py`：数据模型（TaskStatus, CadQueryRequest, ModelFormat 等）
- `app/main.py`：FastAPI 入口，已注册 api_router（前缀 `/api`）
- `app/cad/generator.py`：占位模块，需要重写
- `app/cad/cadquery_gen.py`：占位模块，需要重写

---

### 步骤 1：重写三视图生成器

重写 `python/app/cad/generator.py`：

```python
"""
三视图生成 3D 模型引擎
支持从三张视图图片（正视图、侧视图、俯视图）生成 3D 模型
集成 TRELLIS / Wonder3D 等开源 3D 重建引擎
"""

import asyncio
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.core.response import success, error, ErrorCode
from app.models.schemas import TaskStatus

logger = logging.getLogger(__name__)

# 创建路由器
generator_router = APIRouter(prefix="/cad", tags=["CAD-三视图"])

# 任务状态存储（生产环境应使用 Redis）
_tasks: dict[str, dict] = {}


def _get_task_dir(task_id: str) -> Path:
    """获取任务目录路径"""
    uploads_dir = Path(get_settings().storage.uploads_dir)
    task_dir = uploads_dir / "three_view_tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


@generator_router.post("/generate-from-views")
async def generate_from_views(
    front_view: UploadFile = File(..., description="正视图"),
    side_view: UploadFile = File(..., description="侧视图"),
    top_view: UploadFile = File(..., description="俯视图"),
    engine: str = Form(default="trellis", description="生成引擎: trellis 或 wonder3d"),
):
    """从三视图生成 3D 模型

    接收三张视图图片（正视图、侧视图、俯视图），启动后台任务进行 3D 模型重建。
    返回任务 ID，客户端可通过轮询查询任务状态。
    """
    if engine not in ("trellis", "wonder3d"):
        return error(
            code=ErrorCode.CAD_INVALID_INPUT,
            message=f"不支持的引擎: {engine}，可选: trellis, wonder3d",
        )

    task_id = str(uuid.uuid4())
    task_dir = _get_task_dir(task_id)

    try:
        views = {"front": front_view, "side": side_view, "top": top_view}
        saved_paths = {}

        for view_name, upload_file in views.items():
            if upload_file.content_type and not upload_file.content_type.startswith("image/"):
                return error(
                    code=ErrorCode.FILE_INVALID_TYPE,
                    message=f"{view_name}_view 文件类型无效: {upload_file.content_type}",
                )

            file_ext = Path(upload_file.filename or f"{view_name}.png").suffix or ".png"
            file_path = task_dir / f"{view_name}_view{file_ext}"
            content = await upload_file.read()

            if len(content) > 20 * 1024 * 1024:
                return error(
                    code=ErrorCode.FILE_TOO_LARGE,
                    message=f"{view_name}_view 文件过大（最大 20MB）",
                )

            with open(file_path, "wb") as f:
                f.write(content)
            saved_paths[view_name] = str(file_path)

        _tasks[task_id] = {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "progress": 0,
            "message": "任务已创建，等待处理",
            "result_path": None,
            "error": None,
            "engine": engine,
            "views": saved_paths,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }

        asyncio.create_task(_run_trellis(task_id, saved_paths, engine))

        return success(data={
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "message": "任务已创建",
        })

    except Exception as e:
        logger.error(f"创建三视图任务失败: {e}", exc_info=True)
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
        return error(code=ErrorCode.CAD_GENERATION_FAILED, message=f"创建任务失败: {str(e)}")


@generator_router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = _tasks.get(task_id)
    if not task:
        return error(code=ErrorCode.TASK_NOT_FOUND, message=f"任务不存在: {task_id}")

    return success(data={
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "error": task["error"],
        "created_at": task["created_at"],
        "completed_at": task["completed_at"],
    })


@generator_router.get("/download/{task_id}")
async def download_result(task_id: str):
    """下载生成的 3D 模型文件"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != TaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail=f"任务未完成，当前状态: {task['status']}")

    result_path = task.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="模型文件不存在")

    return FileResponse(
        path=result_path,
        filename=f"{task_id}.glb",
        media_type="model/gltf-binary",
    )


async def _run_trellis(task_id: str, view_paths: dict, engine: str):
    """后台任务：运行 TRELLIS / Wonder3D 3D 重建

    TODO: 集成实际的 TRELLIS 引擎
    当前为占位实现，模拟生成过程。

    TRELLIS 集成步骤（后续实现）：
    1. 安装 trellis pip 包：pip install trellis
    2. 加载 TRELLIS 预训练模型
    3. 预处理输入图片（统一尺寸、归一化）
    4. 调用 TRELLIS 推理接口生成 3D 模型
    5. 后处理（网格清理、格式转换）
    6. 保存为 .glb 格式
    """
    task = _tasks.get(task_id)
    if not task:
        return

    try:
        task["status"] = TaskStatus.RUNNING.value
        task["message"] = f"正在使用 {engine} 引擎生成 3D 模型..."
        task["progress"] = 10
        logger.info(f"[任务 {task_id}] 开始 {engine} 3D 重建")

        # 模拟预处理阶段
        await asyncio.sleep(1)
        task["progress"] = 20
        task["message"] = "正在预处理输入图片..."

        # 模拟特征提取阶段
        await asyncio.sleep(2)
        task["progress"] = 40
        task["message"] = "正在提取图像特征..."

        # 模拟 3D 重建阶段
        await asyncio.sleep(3)
        task["progress"] = 70
        task["message"] = "正在重建 3D 模型..."

        # 模拟后处理阶段
        await asyncio.sleep(2)
        task["progress"] = 90
        task["message"] = "正在后处理和格式转换..."

        # 生成占位输出文件
        task_dir = _get_task_dir(task_id)
        result_path = task_dir / "result.glb"

        # TODO: 替换为 TRELLIS 实际输出
        placeholder_content = _create_placeholder_glb()
        with open(result_path, "wb") as f:
            f.write(placeholder_content)

        task["status"] = TaskStatus.COMPLETED.value
        task["progress"] = 100
        task["message"] = "3D 模型生成完成"
        task["result_path"] = str(result_path)
        task["completed_at"] = datetime.now().isoformat()
        logger.info(f"[任务 {task_id}] 3D 模型生成完成: {result_path}")

    except Exception as e:
        logger.error(f"[任务 {task_id}] 3D 重建失败: {e}", exc_info=True)
        task["status"] = TaskStatus.FAILED.value
        task["error"] = str(e)
        task["message"] = f"生成失败: {str(e)}"
        task["completed_at"] = datetime.now().isoformat()


def _create_placeholder_glb() -> bytes:
    """创建占位 GLB 文件（最小有效 GLB 二进制格式）"""
    import struct
    import json

    gltf_json = json.dumps({
        "asset": {"version": "2.0", "generator": "灵境制造 V4"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "SCALAR", "max": [1.0], "min": [0.0]}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 12}],
        "buffers": [{"byteLength": 12}],
    }, separators=(",", ":")).encode("utf-8")

    binary_data = struct.pack("<3f", 0.0, 1.0, 0.0)

    json_padding = (4 - len(gltf_json) % 4) % 4
    json_chunk = gltf_json + b" " * json_padding

    bin_padding = (4 - len(binary_data) % 4) % 4
    bin_chunk = binary_data + b"\x00" * bin_padding

    glb_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    header = struct.pack("<4sII", b"glTF", 2, glb_length)
    json_header = struct.pack("<II", len(json_chunk), 0x4E4F534A)
    bin_header = struct.pack("<II", len(bin_chunk), 0x004E4942)

    return header + json_header + json_chunk + bin_header + bin_chunk
```

---

### 步骤 2：重写 CadQuery 参数化生成器

重写 `python/app/cad/cadquery_gen.py`：

```python
"""
CadQuery 参数化 3D 模型生成引擎
支持从自然语言描述生成 CadQuery 脚本，并执行生成 3D 模型
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.core.response import success, error, ErrorCode
from app.models.schemas import TaskStatus, CadQueryRequest

logger = logging.getLogger(__name__)

# 创建路由器
cadquery_router = APIRouter(prefix="/cad/cadquery", tags=["CAD-CadQuery"])

# 任务状态存储（生产环境应使用 Redis）
_cadquery_tasks: dict[str, dict] = {}


def _get_cadquery_task_dir(task_id: str) -> Path:
    """获取 CadQuery 任务目录路径"""
    uploads_dir = Path(get_settings().storage.uploads_dir)
    task_dir = uploads_dir / "cadquery_tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


@cadquery_router.post("/generate")
async def generate_cadquery(request: CadQueryRequest):
    """从自然语言描述生成 CadQuery 3D 模型

    接收零件的自然语言描述，使用 AI 解析为 CadQuery 脚本，
    然后执行脚本生成 3D 模型文件。
    """
    task_id = str(uuid.uuid4())

    _cadquery_tasks[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "progress": 0,
        "message": "任务已创建，等待处理",
        "result_path": None,
        "script": None,
        "error": None,
        "request": request.model_dump(),
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
    }

    asyncio.create_task(_run_cadquery(task_id, request))

    return success(data={
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "message": "任务已创建",
    })


@cadquery_router.get("/task/{task_id}")
async def get_cadquery_task_status(task_id: str):
    """查询 CadQuery 任务状态"""
    task = _cadquery_tasks.get(task_id)
    if not task:
        return error(code=ErrorCode.TASK_NOT_FOUND, message=f"任务不存在: {task_id}")

    return success(data={
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "script": task.get("script"),
        "error": task["error"],
        "created_at": task["created_at"],
        "completed_at": task["completed_at"],
    })


@cadquery_router.get("/download/{task_id}")
async def download_cadquery_result(task_id: str):
    """下载 CadQuery 生成的 3D 模型文件"""
    task = _cadquery_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != TaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail=f"任务未完成，当前状态: {task['status']}")

    result_path = task.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="模型文件不存在")

    return FileResponse(
        path=result_path,
        filename=f"{task_id}.stl",
        media_type="model/stl",
    )


async def _run_cadquery(task_id: str, request: CadQueryRequest):
    """后台任务：运行 CadQuery 生成

    TODO: 集成实际的 CadQuery 引擎
    当前为占位实现，模拟生成过程。

    CadQuery 集成步骤（后续实现）：
    1. 使用 AI（Ollama/云端）将自然语言描述解析为 CadQuery Python 脚本
    2. 在沙箱环境中执行 CadQuery 脚本
    3. 导出为 STL/OBJ/GLB 格式
    4. 验证生成的模型（流形检查、体积计算等）
    5. 保存结果文件
    """
    task = _cadquery_tasks.get(task_id)
    if not task:
        return

    try:
        task["status"] = TaskStatus.RUNNING.value
        task["progress"] = 10
        task["message"] = "正在解析零件描述..."
        logger.info(f"[CadQuery 任务 {task_id}] 开始处理: {request.description}")

        # 模拟 AI 解析阶段
        await asyncio.sleep(2)
        task["progress"] = 30
        task["message"] = "正在生成 CadQuery 脚本..."

        placeholder_script = f'''# 灵境制造 V4 - CadQuery 自动生成脚本
# 零件描述: {request.description}
# 生成时间: {datetime.now().isoformat()}

import cadquery as cq

# TODO: 由 AI 根据零件描述自动生成以下参数化建模代码
# 当前为占位脚本

result = (
    cq.Workplane("XY")
    .box(10, 10, 5)
    .edges("|Z").fillet(1.0)
    .faces(">Z").workplane().hole(3)
)

# export_stl(result, "{task_id}.stl")
'''
        task["script"] = placeholder_script
        task["progress"] = 50
        task["message"] = "正在执行 CadQuery 脚本..."

        # 模拟 CadQuery 执行阶段
        await asyncio.sleep(3)
        task["progress"] = 80
        task["message"] = "正在导出模型文件..."

        task_dir = _get_cadquery_task_dir(task_id)

        # 保存脚本
        script_path = task_dir / "script.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(placeholder_script)

        # TODO: 替换为 CadQuery 实际输出
        result_path = task_dir / "result.stl"
        placeholder_stl = _create_placeholder_stl()
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(placeholder_stl)

        task["status"] = TaskStatus.COMPLETED.value
        task["progress"] = 100
        task["message"] = "CadQuery 模型生成完成"
        task["result_path"] = str(result_path)
        task["completed_at"] = datetime.now().isoformat()
        logger.info(f"[CadQuery 任务 {task_id}] 生成完成: {result_path}")

    except Exception as e:
        logger.error(f"[CadQuery 任务 {task_id}] 生成失败: {e}", exc_info=True)
        task["status"] = TaskStatus.FAILED.value
        task["error"] = str(e)
        task["message"] = f"生成失败: {str(e)}"
        task["completed_at"] = datetime.now().isoformat()


def _create_placeholder_stl() -> str:
    """创建占位 STL 文件内容（ASCII 格式）"""
    return """solid lingjing_placeholder
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 1 0 0
      vertex 1 1 0
      vertex 0 1 0
    endloop
  endfacet
endsolid lingjing_placeholder
"""
```

---

### 步骤 3：在 main.py 中注册 CAD 路由

修改 `python/app/main.py`，移除原有的占位 CAD 路由，添加新的路由模块：

```python
# 注册 CAD 路由
from app.cad.generator import generator_router
from app.cad.cadquery_gen import cadquery_router
app.include_router(generator_router, prefix="/api")
app.include_router(cadquery_router, prefix="/api")
```

同时删除 main.py 中原有的以下占位路由（如果存在）：
- `@api_router.post("/cad/three-view-to-3d")`
- `@api_router.post("/cad/cadquery")`
- `@api_router.post("/process/route")`

---

### 步骤 4：创建前端 CAD API 服务封装

创建 `src/services/cad.ts`：

```typescript
/**
 * CAD API 服务封装
 * 封装三视图生成和 CadQuery 生成的 API 调用
 */

import request from './request'

/** 任务状态 */
export type TaskStatusType = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

/** 任务状态信息 */
export interface TaskInfo {
  task_id: string
  status: TaskStatusType
  progress: number
  message: string
  error: string | null
  created_at: string
  completed_at: string | null
}

/** CadQuery 任务状态（扩展） */
export interface CadQueryTaskInfo extends TaskInfo {
  script: string | null
}

/** 提交三视图生成任务 */
export async function submitThreeViewTask(
  files: { front: File; side: File; top: File },
  engine: string = 'trellis'
): Promise<{ task_id: string }> {
  const formData = new FormData()
  formData.append('front_view', files.front)
  formData.append('side_view', files.side)
  formData.append('top_view', files.top)
  formData.append('engine', engine)

  const res = await request.post('/api/cad/generate-from-views', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
  return res.data.data
}

/** 查询任务状态 */
export async function getTaskStatus(taskId: string): Promise<TaskInfo> {
  const res = await request.get(`/api/cad/task/${taskId}`)
  return res.data.data
}

/** 下载生成的模型文件 */
export async function downloadModel(taskId: string): Promise<Blob> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'
  const response = await fetch(`${baseUrl}/api/cad/download/${taskId}`)
  if (!response.ok) throw new Error(`下载失败: HTTP ${response.status}`)
  return response.blob()
}

/** 提交 CadQuery 生成任务 */
export async function submitCadQueryTask(params: {
  description: string
  output_format?: string
  use_ai?: boolean
}): Promise<{ task_id: string }> {
  const res = await request.post('/api/cad/cadquery/generate', params)
  return res.data.data
}

/** 查询 CadQuery 任务状态 */
export async function getCadQueryTaskStatus(taskId: string): Promise<CadQueryTaskInfo> {
  const res = await request.get(`/api/cad/cadquery/task/${taskId}`)
  return res.data.data
}

/** 下载 CadQuery 生成的模型文件 */
export async function downloadCadQueryModel(taskId: string): Promise<Blob> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'
  const response = await fetch(`${baseUrl}/api/cad/cadquery/download/${taskId}`)
  if (!response.ok) throw new Error(`下载失败: HTTP ${response.status}`)
  return response.blob()
}
```

---

### 步骤 5：创建 Three.js 3D 查看器组件

创建 `src/components/three/ThreeViewer.vue`：

```vue
<template>
  <div ref="containerRef" class="three-viewer">
    <!-- 工具栏 -->
    <div class="viewer-toolbar">
      <el-tooltip content="重置视角" placement="bottom">
        <el-button size="small" circle @click="resetCamera">
          <el-icon><RefreshRight /></el-icon>
        </el-button>
      </el-tooltip>
      <el-tooltip content="适应窗口" placement="bottom">
        <el-button size="small" circle @click="fitToView">
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </el-tooltip>
      <el-tooltip content="线框模式" placement="bottom">
        <el-button size="small" circle @click="toggleWireframe">
          <el-icon><Grid /></el-icon>
        </el-button>
      </el-tooltip>
      <el-tooltip content="截图" placement="bottom">
        <el-button size="small" circle @click="takeScreenshot">
          <el-icon><Camera /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <!-- 加载状态覆盖层 -->
    <div v-if="loading" class="viewer-overlay">
      <div class="overlay-content">
        <el-icon class="loading-icon is-loading"><Loading /></el-icon>
        <span>{{ loadingText }}</span>
      </div>
    </div>

    <!-- 错误状态覆盖层 -->
    <div v-if="errorMessage" class="viewer-overlay error">
      <div class="overlay-content">
        <el-icon class="error-icon"><WarningFilled /></el-icon>
        <span>{{ errorMessage }}</span>
        <el-button size="small" type="primary" @click="$emit('retry')">
          重试
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { RefreshRight, FullScreen, Grid, Camera, Loading, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'

const props = withDefaults(defineProps<{
  modelUrl?: string
  modelFormat?: 'gltf' | 'glb' | 'stl' | 'obj' | 'auto'
  backgroundColor?: string
  showGrid?: boolean
  autoFit?: boolean
  loadingText?: string
}>(), {
  modelUrl: '',
  modelFormat: 'auto',
  backgroundColor: '#f5f5f5',
  showGrid: true,
  autoFit: true,
  loadingText: '加载模型中...',
})

const emit = defineEmits<{
  (e: 'loaded'): void
  (e: 'error', message: string): void
  (e: 'retry'): void
}>()

const containerRef = ref<HTMLDivElement>()
const loading = ref(false)
const errorMessage = ref<string | null>(null)

let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let animationFrameId: number
let currentModel: THREE.Object3D | null = null
let wireframeMode = false
let resizeObserver: ResizeObserver | null = null

/** 初始化 Three.js 场景 */
function initScene() {
  if (!containerRef.value) return

  const container = containerRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(props.backgroundColor)

  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000)
  camera.position.set(5, 5, 5)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  container.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.enablePan = true
  controls.enableZoom = true
  controls.minDistance = 0.5
  controls.maxDistance = 500

  setupLights()
  if (props.showGrid) setupGrid()
  animate()
  setupResizeObserver()
}

/** 设置灯光 */
function setupLights() {
  scene.add(new THREE.AmbientLight(0xffffff, 0.6))

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8)
  dirLight.position.set(10, 20, 10)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.width = 2048
  dirLight.shadow.mapSize.height = 2048
  scene.add(dirLight)

  const fillLight = new THREE.DirectionalLight(0xffffff, 0.3)
  fillLight.position.set(-10, 10, -10)
  scene.add(fillLight)

  scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 0.4))
}

/** 设置网格地面 */
function setupGrid() {
  const grid = new THREE.GridHelper(20, 20, 0x888888, 0xcccccc)
  grid.material.opacity = 0.3
  grid.material.transparent = true
  scene.add(grid)
}

/** 渲染循环 */
function animate() {
  animationFrameId = requestAnimationFrame(animate)
  controls.update()
  renderer.render(scene, camera)
}

/** 设置 ResizeObserver 响应式 */
function setupResizeObserver() {
  if (!containerRef.value) return
  resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect
      if (width === 0 || height === 0) continue
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }
  })
  resizeObserver.observe(containerRef.value)
}

/** 加载模型 */
async function loadModel(url: string, format?: string) {
  if (!url) return
  loading.value = true
  errorMessage.value = null

  if (currentModel) {
    scene.remove(currentModel)
    disposeObject(currentModel)
    currentModel = null
  }

  const detectedFormat = format || props.modelFormat
  const fileFormat = detectedFormat === 'auto' ? detectFormat(url) : detectedFormat

  try {
    let object: THREE.Object3D
    switch (fileFormat) {
      case 'gltf': case 'glb': object = await loadGLTF(url); break
      case 'stl': object = await loadSTL(url); break
      case 'obj': object = await loadOBJ(url); break
      default: throw new Error(`不支持的模型格式: ${fileFormat}`)
    }

    centerAndScaleModel(object)
    scene.add(object)
    currentModel = object

    if (props.autoFit) fitToView()
    loading.value = false
    emit('loaded')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载模型失败'
    errorMessage.value = msg
    loading.value = false
    emit('error', msg)
  }
}

function loadGLTF(url: string): Promise<THREE.Object3D> {
  return new Promise((resolve, reject) => {
    new GLTFLoader().load(url, (gltf) => resolve(gltf.scene), undefined,
      (err) => reject(new Error(`GLTF 加载失败`)))
  })
}

function loadSTL(url: string): Promise<THREE.Object3D> {
  return new Promise((resolve, reject) => {
    new STLLoader().load(url, (geometry) => {
      geometry.computeVertexNormals()
      const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
        color: 0x6090c0, metalness: 0.3, roughness: 0.6,
      }))
      mesh.castShadow = true
      mesh.receiveShadow = true
      resolve(mesh)
    }, undefined, () => reject(new Error('STL 加载失败')))
  })
}

function loadOBJ(url: string): Promise<THREE.Object3D> {
  return new Promise((resolve, reject) => {
    new OBJLoader().load(url, (object) => {
      object.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          if (!child.material || (child.material as THREE.Material).type === 'MeshBasicMaterial') {
            child.material = new THREE.MeshStandardMaterial({ color: 0x808080, metalness: 0.2, roughness: 0.7 })
          }
          child.castShadow = true
          child.receiveShadow = true
        }
      })
      resolve(object)
    }, undefined, () => reject(new Error('OBJ 加载失败')))
  })
}

/** 居中和缩放模型 */
function centerAndScaleModel(object: THREE.Object3D) {
  const box = new THREE.Box3().setFromObject(object)
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  object.position.sub(center)
  const maxDim = Math.max(size.x, size.y, size.z)
  if (maxDim > 0) object.scale.multiplyScalar(5 / maxDim)
}

/** 适应视角到模型 */
function fitToView() {
  if (!currentModel) return
  const box = new THREE.Box3().setFromObject(currentModel)
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z)
  const fov = camera.fov * (Math.PI / 180)
  const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.5
  camera.position.set(center.x + dist * 0.7, center.y + dist * 0.5, center.z + dist * 0.7)
  controls.target.copy(center)
  controls.update()
}

/** 重置相机视角 */
function resetCamera() {
  camera.position.set(5, 5, 5)
  controls.target.set(0, 0, 0)
  controls.update()
}

/** 切换线框模式 */
function toggleWireframe() {
  wireframeMode = !wireframeMode
  if (!currentModel) return
  currentModel.traverse((child) => {
    if (child instanceof THREE.Mesh && child.material) {
      const mats = Array.isArray(child.material) ? child.material : [child.material]
      for (const mat of mats) {
        if (mat instanceof THREE.MeshStandardMaterial || mat instanceof THREE.MeshPhongMaterial) {
          mat.wireframe = wireframeMode
        }
      }
    }
  })
}

/** 截图 */
function takeScreenshot() {
  if (!renderer) return
  renderer.render(scene, camera)
  const dataUrl = renderer.domElement.toDataURL('image/png')
  const link = document.createElement('a')
  link.download = `灵境制造_截图_${Date.now()}.png`
  link.href = dataUrl
  link.click()
  ElMessage.success('截图已保存')
}

/** 递归释放 3D 对象资源 */
function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      if (child.geometry) child.geometry.dispose()
      if (child.material) {
        const mats = Array.isArray(child.material) ? child.material : [child.material]
        mats.forEach((m) => m.dispose())
      }
    }
  })
}

/** 根据文件扩展名检测模型格式 */
function detectFormat(url: string): string {
  const lower = url.toLowerCase()
  if (lower.endsWith('.glb')) return 'glb'
  if (lower.endsWith('.gltf')) return 'gltf'
  if (lower.endsWith('.stl')) return 'stl'
  if (lower.endsWith('.obj')) return 'obj'
  return 'glb'
}

/** 清理资源 */
function cleanup() {
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  if (currentModel) disposeObject(currentModel)
  if (controls) controls.dispose()
  if (renderer) {
    renderer.dispose()
    if (renderer.domElement?.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement)
  }
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
}

watch(() => props.modelUrl, (newUrl) => {
  if (newUrl) nextTick(() => loadModel(newUrl))
})

watch(() => props.backgroundColor, (newColor) => {
  if (scene) scene.background = new THREE.Color(newColor)
})

onMounted(() => {
  initScene()
  if (props.modelUrl) loadModel(props.modelUrl)
})

onBeforeUnmount(() => cleanup())

defineExpose({ loadModel, fitToView, resetCamera, toggleWireframe, takeScreenshot })
</script>

<style scoped>
.three-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #f5f5f5;
  border-radius: 8px;
  overflow: hidden;
}
.viewer-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  display: flex;
  gap: 4px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
  padding: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
.viewer-toolbar .el-button {
  width: 32px;
  height: 32px;
}
.viewer-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  z-index: 5;
}
.viewer-overlay.error {
  background: rgba(255, 255, 255, 0.95);
}
.overlay-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--el-text-color-secondary);
}
.loading-icon {
  font-size: 32px;
  color: var(--el-color-primary);
}
.error-icon {
  font-size: 32px;
  color: var(--el-color-danger);
}
</style>
```

---

### 步骤 6：创建三视图生成页面

创建 `src/views/MultiViewTo3D.vue`：

```vue
<template>
  <div class="multiview-page">
    <div class="page-header">
      <h2>三视图生成 3D 模型</h2>
      <p class="page-desc">上传正视图、侧视图、俯视图，AI 自动生成 3D 模型</p>
    </div>

    <!-- 上传区域 -->
    <div v-if="!taskId && taskStatus !== 'running'" class="upload-section">
      <div class="upload-grid">
        <div
          v-for="viewType in viewTypes"
          :key="viewType.key"
          class="upload-card"
          :class="{ 'has-file': files[viewType.key] }"
          @dragover.prevent="onDragOver"
          @dragleave="onDragLeave"
          @drop.prevent="(e) => onDrop(e, viewType.key)"
          @click="triggerUpload(viewType.key)"
        >
          <input
            :ref="(el: any) => { inputRefs[viewType.key] = el }"
            type="file"
            accept="image/*"
            style="display: none"
            @change="(e: Event) => onFileChange(e, viewType.key)"
          />
          <template v-if="files[viewType.key]">
            <img :src="previews[viewType.key]!" class="preview-image" :alt="viewType.label" />
            <div class="preview-overlay">
              <el-button type="danger" size="small" circle @click.stop="removeFile(viewType.key)">
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
            <span class="view-label">{{ viewType.label }}</span>
          </template>
          <template v-else>
            <el-icon class="upload-icon"><Plus /></el-icon>
            <span class="upload-text">{{ viewType.label }}</span>
            <span class="upload-hint">点击或拖拽上传</span>
          </template>
        </div>
      </div>

      <div class="engine-select">
        <span class="engine-label">生成引擎：</span>
        <el-radio-group v-model="selectedEngine">
          <el-radio-button value="trellis">TRELLIS</el-radio-button>
          <el-radio-button value="wonder3d">Wonder3D</el-radio-button>
        </el-radio-group>
      </div>

      <div class="submit-bar">
        <el-button type="primary" size="large" :disabled="!canSubmit" :loading="submitting" @click="submitTask">
          {{ submitting ? '提交中...' : '开始生成 3D 模型' }}
        </el-button>
      </div>
    </div>

    <!-- 任务进度 -->
    <div v-if="taskId" class="task-section">
      <div class="task-status-card">
        <div class="task-header">
          <h3>生成进度</h3>
          <el-button v-if="taskStatus === 'completed' || taskStatus === 'failed'" text @click="resetTask">
            重新开始
          </el-button>
        </div>
        <el-progress :percentage="taskProgress" :status="progressStatus" :stroke-width="12" style="margin-bottom: 16px" />
        <p class="task-message">{{ taskMessage }}</p>
        <div v-if="taskStatus === 'failed'" class="error-actions">
          <el-button type="primary" @click="retryTask">重试</el-button>
        </div>
      </div>

      <div v-if="taskStatus === 'completed'" class="viewer-section">
        <ThreeViewer v-if="modelBlobUrl" :model-url="modelBlobUrl" model-format="glb" style="height: 500px" />
        <div class="download-bar">
          <el-button type="primary" @click="downloadResult">
            <el-icon><Download /></el-icon>
            下载模型 (.glb)
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Close, Download } from '@element-plus/icons-vue'
import ThreeViewer from '@/components/three/ThreeViewer.vue'
import { submitThreeViewTask, getTaskStatus, downloadModel, type TaskInfo } from '@/services/cad'

type ViewType = 'front' | 'side' | 'top'

const viewTypes = [
  { key: 'front' as ViewType, label: '正视图' },
  { key: 'side' as ViewType, label: '侧视图' },
  { key: 'top' as ViewType, label: '俯视图' },
]

const inputRefs = reactive<Record<string, HTMLInputElement | null>>({})
const files = reactive<Record<ViewType, File | null>>({ front: null, side: null, top: null })
const previews = reactive<Record<ViewType, string | null>>({ front: null, side: null, top: null })
const selectedEngine = ref('trellis')
const submitting = ref(false)
const taskId = ref<string | null>(null)
const taskStatus = ref<string>('pending')
const taskProgress = ref(0)
const taskMessage = ref('')
const modelBlobUrl = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const canSubmit = computed(() => files.front && files.side && files.top && !submitting.value)
const progressStatus = computed(() => {
  if (taskStatus.value === 'completed') return 'success' as const
  if (taskStatus.value === 'failed') return 'exception' as const
  return undefined
})

function triggerUpload(key: ViewType) { inputRefs[key]?.click() }

function onFileChange(event: Event, key: ViewType) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) setFile(key, file)
}

function onDragOver(event: DragEvent) { (event.currentTarget as HTMLElement).classList.add('drag-over') }
function onDragLeave(event: DragEvent) { (event.currentTarget as HTMLElement).classList.remove('drag-over') }

function onDrop(event: DragEvent, key: ViewType) {
  (event.currentTarget as HTMLElement).classList.remove('drag-over')
  const file = event.dataTransfer?.files[0]
  if (file && file.type.startsWith('image/')) setFile(key, file)
  else ElMessage.warning('请上传图片文件')
}

function setFile(key: ViewType, file: File) {
  if (previews[key]) URL.revokeObjectURL(previews[key]!)
  files[key] = file
  previews[key] = URL.createObjectURL(file)
}

function removeFile(key: ViewType) {
  if (previews[key]) URL.revokeObjectURL(previews[key]!)
  files[key] = null
  previews[key] = null
}

async function submitTask() {
  if (!files.front || !files.side || !files.top) return
  submitting.value = true
  try {
    const result = await submitThreeViewTask({ front: files.front, side: files.side, top: files.top }, selectedEngine.value)
    taskId.value = result.task_id
    taskStatus.value = 'pending'
    taskProgress.value = 0
    taskMessage.value = '任务已提交，等待处理...'
    startPolling()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '提交失败')
  } finally {
    submitting.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    try {
      const task: TaskInfo = await getTaskStatus(taskId.value)
      taskStatus.value = task.status
      taskProgress.value = task.progress
      taskMessage.value = task.message
      if (task.status === 'completed') {
        stopPolling()
        await loadModelBlob(taskId.value)
        ElMessage.success('3D 模型生成完成！')
      } else if (task.status === 'failed') {
        stopPolling()
        ElMessage.error(`生成失败: ${task.error || '未知错误'}`)
      }
    } catch { /* 继续轮询 */ }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function loadModelBlob(tid: string) {
  try {
    const blob = await downloadModel(tid)
    if (modelBlobUrl.value) URL.revokeObjectURL(modelBlobUrl.value)
    modelBlobUrl.value = URL.createObjectURL(blob)
  } catch { ElMessage.error('下载模型文件失败') }
}

async function downloadResult() {
  if (!taskId.value) return
  try {
    const blob = await downloadModel(taskId.value)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.download = `灵境制造_3D模型_${taskId.value}.glb`
    link.href = url
    link.click()
    URL.revokeObjectURL(url)
  } catch { ElMessage.error('下载失败') }
}

async function retryTask() {
  if (!files.front || !files.side || !files.top) return
  resetTask()
  await submitTask()
}

function resetTask() {
  stopPolling()
  taskId.value = null
  taskStatus.value = 'pending'
  taskProgress.value = 0
  taskMessage.value = ''
  if (modelBlobUrl.value) { URL.revokeObjectURL(modelBlobUrl.value); modelBlobUrl.value = null }
}

onBeforeUnmount(() => {
  stopPolling()
  ;(['front', 'side', 'top'] as ViewType[]).forEach((k) => { if (previews[k]) URL.revokeObjectURL(previews[k]!) })
  if (modelBlobUrl.value) URL.revokeObjectURL(modelBlobUrl.value)
})
</script>

<style scoped>
.multiview-page { padding: 24px; max-width: 1100px; margin: 0 auto; }
.page-header { margin-bottom: 32px; }
.page-header h2 { font-size: 24px; font-weight: 600; margin: 0 0 8px 0; }
.page-desc { color: var(--el-text-color-secondary); margin: 0; }
.upload-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.upload-card {
  position: relative; aspect-ratio: 4 / 3; border: 2px dashed var(--el-border-color);
  border-radius: 12px; display: flex; flex-direction: column; align-items: center;
  justify-content: center; cursor: pointer; transition: all 0.3s; overflow: hidden;
  background: var(--el-fill-color-lighter);
}
.upload-card:hover { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.upload-card.drag-over { border-color: var(--el-color-primary); background: var(--el-color-primary-light-8); }
.upload-card.has-file { border-style: solid; border-color: var(--el-color-success); }
.upload-icon { font-size: 36px; color: var(--el-text-color-placeholder); margin-bottom: 8px; }
.upload-text { font-size: 16px; font-weight: 500; color: var(--el-text-color-regular); }
.upload-hint { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 4px; }
.preview-image { width: 100%; height: 100%; object-fit: contain; }
.preview-overlay { position: absolute; top: 8px; right: 8px; opacity: 0; transition: opacity 0.2s; }
.upload-card:hover .preview-overlay { opacity: 1; }
.view-label {
  position: absolute; bottom: 8px; left: 8px; background: rgba(0,0,0,0.6);
  color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;
}
.engine-select { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
.engine-label { font-size: 14px; color: var(--el-text-color-regular); }
.submit-bar { text-align: center; }
.task-section { margin-top: 24px; }
.task-status-card {
  background: var(--el-bg-color); border-radius: 12px; padding: 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin-bottom: 24px;
}
.task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.task-header h3 { font-size: 18px; font-weight: 600; margin: 0; }
.task-message { color: var(--el-text-color-secondary); font-size: 14px; margin: 0; }
.error-actions { margin-top: 16px; text-align: center; }
.viewer-section { margin-top: 24px; }
.download-bar { text-align: center; margin-top: 16px; }
</style>
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

1. **三视图生成器验证**：确认 `python/app/cad/generator.py` 包含 `POST /api/cad/generate-from-views`、`GET /api/cad/task/{task_id}`、`GET /api/cad/download/{task_id}` 路由，后台任务函数 `_run_trellis` 包含 TRELLIS 集成的 TODO 注释
2. **CadQuery 生成器验证**：确认 `python/app/cad/cadquery_gen.py` 包含 `POST /api/cad/cadquery/generate`、`GET /api/cad/cadquery/task/{task_id}`、`GET /api/cad/cadquery/download/{task_id}` 路由，后台任务函数 `_run_cadquery` 包含 CadQuery 集成的 TODO 注释
3. **路由注册验证**：启动后端服务，访问 `http://localhost:8765/docs`，确认所有 CAD 路由已注册
4. **三视图任务验证**：使用 curl 或 Swagger UI 提交三视图任务，确认返回 task_id、轮询状态变化、任务完成、可下载 .glb 文件
5. **前端 ThreeViewer 验证**：确认 ThreeViewer.vue 包含 Three.js 场景初始化、GLTFLoader/STLLoader/OBJLoader、工具栏、加载/错误覆盖层、ResizeObserver、onBeforeUnmount 清理
6. **前端 MultiViewTo3D 验证**：确认包含三图上传、引擎选择、任务提交、进度显示、ThreeViewer + 下载、错误 + 重试
7. **TypeScript 编译验证**：确认无 TypeScript 编译错误

如果以上验证全部通过，Phase 4 完成。

---PROMPT END---

---

## Phase 5: PhyCo-Agent 架构（论文成果集成）

> ⚠️ **重要变更**：本 Phase 已基于论文《知识图谱与数学规划耦合的工艺生成方法研究》进行重大重构。
> 原有的"六 Agent 直接生成"架构被替换为论文的 PhyCo-Agent 架构：
> - LLM 仅做"语义桥梁"（翻译自然语言→结构化约束），不参与任何优化计算
> - SCIP 数学规划求解器做多目标优化（加工时间/切削力/表面质量/刀具寿命）
> - 在线验证层（Kienzle/Taylor 解析公式）确保物理约束满足
> - 结构化知识库替代文本 RAG，提供精确的参数边界

**原 Phase 5 内容已归档，完整的新 Phase 5 实现请参见：[Phase 5 重构文档](./灵境制造V4_Phase5重构与Phase9.md)**

## Phase 6: 用户界面（全部页面完善）

### 目标

完善所有前端页面，实现完整的用户界面体验。包括主布局、首页/模型库、工作台、关于页、全局样式和启动流程。

### 验证标准

- [ ] `src/components/layout/AppLayout.vue` 包含左侧导航栏（可折叠）、顶部标题栏、底部状态栏
- [ ] `src/views/Home.vue` 包含欢迎区域、最近项目列表、快速操作入口、空状态提示
- [ ] `src/views/Workspace.vue` 包含文件树、3D 查看器、属性面板、工具栏、G 代码编辑器
- [ ] `src/views/About.vue` 包含应用信息、核心功能列表、隐私声明、技术栈信息
- [ ] `src/assets/styles/global.css` 包含 CSS 变量定义、全局字体、滚动条美化、过渡动画
- [ ] `src/App.vue` 包含启动检查逻辑（Python 后端 + Ollama 状态检测）
- [ ] `src/router/index.ts` 路由配置完整，所有页面可正常导航
- [ ] 前端 TypeScript 编译无报错

---

---PROMPT START---

## 任务：完善所有前端页面（Phase 6）

你是一个资深 Vue 3 前端工程师和 UI 设计师。请在已有的灵境制造 V4 项目（Phase 0-5 已完成）基础上，完善所有前端页面，实现完整的用户界面体验。

### 重要约定
- 所有注释使用中文（docstring 和行内注释）
- Vue 代码使用 Composition API + `<script setup lang="ts">`
- 使用 Element Plus 组件库
- 深色主题为主，制造行业风格，深蓝灰色调
- 响应式布局，支持不同窗口尺寸

### 项目信息
- 项目根目录：`lingjing-v4`
- 前端源码目录：`lingjing-v4/src/`
- Python 后端地址：`http://localhost:8765`
- Ollama 地址：`http://localhost:11434`

### 已有代码说明
- `src/main.ts`：应用入口，已注册 Element Plus、Pinia、Router
- `src/App.vue`：根组件（当前为简单版本，需要改造）
- `src/router/index.ts`：路由配置（可能需要更新）
- `src/views/Home.vue`：首页（占位版本）
- `src/views/Workspace.vue`：工作台（占位版本）
- `src/views/MultiViewTo3D.vue`：三视图生成页面（Phase 4 已实现）
- `src/views/ProcessPlan.vue`：工艺规划页面（Phase 5 已实现）
- `src/views/Settings.vue`：设置页面（Phase 3 已实现）
- `src/views/About.vue`：关于页（占位版本）
- `src/components/three/ThreeViewer.vue`：3D 查看器组件（Phase 4 已实现）
- `src/services/request.ts`：Axios 请求封装
- `src/services/ollama.ts`：Ollama API 服务
- `src/services/cad.ts`：CAD API 服务
- `src/services/process.ts`：工艺规划 API 服务

---

### 步骤 1：创建全局样式

创建 `src/assets/styles/global.css`：

```css
/**
 * 灵境制造 V4 - 全局样式
 * 深色主题，制造行业风格，深蓝灰色调
 */

/* ==========================================
   CSS 变量定义
   ========================================== */
:root {
  /* 主色调 - 深蓝灰 */
  --lj-primary: #409EFF;
  --lj-primary-light: #66B1FF;
  --lj-primary-dark: #3A8EE6;

  /* 背景色系 */
  --lj-bg-dark: #0F1923;
  --lj-bg-main: #141E2B;
  --lj-bg-card: #1A2736;
  --lj-bg-hover: #1E3044;
  --lj-bg-active: #253A50;

  /* 文字色系 */
  --lj-text-primary: #E8ECF1;
  --lj-text-regular: #B0BEC5;
  --lj-text-secondary: #78909C;
  --lj-text-placeholder: #546E7A;

  /* 边框色系 */
  --lj-border-light: #1E3044;
  --lj-border-regular: #2C3E50;
  --lj-border-dark: #37474F;

  /* 状态色 */
  --lj-success: #67C23A;
  --lj-warning: #E6A23C;
  --lj-danger: #F56C6C;
  --lj-info: #909399;

  /* 侧边栏 */
  --lj-sidebar-width: 220px;
  --lj-sidebar-collapsed-width: 64px;
  --lj-sidebar-bg: #0D1520;

  /* 顶部栏 */
  --lj-header-height: 48px;
  --lj-header-bg: #0D1520;

  /* 底部状态栏 */
  --lj-statusbar-height: 28px;
  --lj-statusbar-bg: #0A1018;

  /* 圆角 */
  --lj-radius-sm: 4px;
  --lj-radius-md: 8px;
  --lj-radius-lg: 12px;

  /* 阴影 */
  --lj-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
  --lj-shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
  --lj-shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);

  /* 过渡 */
  --lj-transition-fast: 0.15s ease;
  --lj-transition-normal: 0.25s ease;
  --lj-transition-slow: 0.35s ease;

  /* 字体 */
  --lj-font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial,
    sans-serif;
  --lj-font-mono: 'Consolas', 'Monaco', 'Courier New', monospace;
}

/* ==========================================
   全局重置
   ========================================== */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body, #app {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

body {
  font-family: var(--lj-font-family);
  font-size: 14px;
  color: var(--lj-text-primary);
  background-color: var(--lj-bg-dark);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ==========================================
   Element Plus 深色主题覆盖
   ========================================== */
:root {
  --el-color-primary: #409EFF;
  --el-color-primary-light-3: #79BBFF;
  --el-color-primary-light-5: #A0CFFF;
  --el-color-primary-light-7: #C6E2FF;
  --el-color-primary-light-9: #ECF5FF;
  --el-color-primary-dark-2: #337ECC;

  --el-bg-color: var(--lj-bg-main);
  --el-bg-color-page: var(--lj-bg-dark);
  --el-bg-color-overlay: var(--lj-bg-card);

  --el-text-color-primary: var(--lj-text-primary);
  --el-text-color-regular: var(--lj-text-regular);
  --el-text-color-secondary: var(--lj-text-secondary);
  --el-text-color-placeholder: var(--lj-text-placeholder);

  --el-border-color: var(--lj-border-regular);
  --el-border-color-light: var(--lj-border-light);
  --el-border-color-lighter: var(--lj-border-light);
  --el-border-color-dark: var(--lj-border-dark);

  --el-fill-color: var(--lj-bg-hover);
  --el-fill-color-light: var(--lj-bg-hover);
  --el-fill-color-lighter: var(--lj-bg-card);
  --el-fill-color-extra-light: var(--lj-bg-card);
  --el-fill-color-blank: var(--lj-bg-main);

  --el-mask-color: rgba(0, 0, 0, 0.7);
}

/* ==========================================
   滚动条美化
   ========================================== */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--lj-border-regular);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--lj-text-placeholder);
}

/* Firefox 滚动条 */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--lj-border-regular) transparent;
}

/* ==========================================
   全局过渡动画
   ========================================== */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--lj-transition-normal);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform var(--lj-transition-normal), opacity var(--lj-transition-normal);
}

.slide-left-enter-from {
  transform: translateX(-20px);
  opacity: 0;
}

.slide-left-leave-to {
  transform: translateX(20px);
  opacity: 0;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform var(--lj-transition-normal), opacity var(--lj-transition-normal);
}

.slide-right-enter-from {
  transform: translateX(20px);
  opacity: 0;
}

.slide-right-leave-to {
  transform: translateX(-20px);
  opacity: 0;
}

/* ==========================================
   通用工具类
   ========================================== */
.text-center { text-align: center; }
.text-right { text-align: right; }
.text-muted { color: var(--lj-text-secondary); }
.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* ==========================================
   链接样式
   ========================================== */
a {
  color: var(--lj-primary-light);
  text-decoration: none;
  transition: color var(--lj-transition-fast);
}

a:hover {
  color: var(--lj-primary);
}

/* ==========================================
   选中文字样式
   ========================================== */
::selection {
  background: var(--lj-primary);
  color: #fff;
}
```

---

### 步骤 2：创建主布局组件

创建 `src/components/layout/AppLayout.vue`：

```vue
<template>
  <div class="app-layout">
    <!-- 左侧导航栏 -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <!-- Logo 区域 -->
      <div class="sidebar-logo" @click="$router.push('/')">
        <div class="logo-icon">
          <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="2" y="2" width="28" height="28" rx="6" fill="#409EFF" fill-opacity="0.15" stroke="#409EFF" stroke-width="1.5"/>
            <path d="M8 22L16 10L24 22" stroke="#409EFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M12 18H20" stroke="#409EFF" stroke-width="2" stroke-linecap="round"/>
            <circle cx="16" cy="14" r="2" fill="#409EFF"/>
          </svg>
        </div>
        <transition name="fade">
          <span v-if="!sidebarCollapsed" class="logo-text">灵境制造</span>
        </transition>
      </div>

      <!-- 导航菜单 -->
      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <el-icon :size="20">
            <component :is="item.icon" />
          </el-icon>
          <transition name="fade">
            <span v-if="!sidebarCollapsed" class="nav-label">{{ item.label }}</span>
          </transition>
        </router-link>
      </nav>

      <!-- 折叠按钮 -->
      <div class="sidebar-footer">
        <div class="collapse-btn" @click="toggleSidebar">
          <el-icon :size="18">
            <DArrowLeft v-if="!sidebarCollapsed" />
            <DArrowRight v-else />
          </el-icon>
          <transition name="fade">
            <span v-if="!sidebarCollapsed" class="nav-label">收起菜单</span>
          </transition>
        </div>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <div class="main-area">
      <!-- 顶部标题栏 -->
      <header class="app-header">
        <div class="header-left">
          <h2 class="page-title">{{ currentPageTitle }}</h2>
        </div>
        <div class="header-right">
          <!-- AI 状态指示灯 -->
          <div class="ai-status" :class="aiStatusClass">
            <span class="status-dot"></span>
            <span class="status-text">{{ aiStatusText }}</span>
          </div>
          <span class="version-badge">v4.0.0</span>
        </div>
      </header>

      <!-- 主内容区域 -->
      <main class="app-content">
        <router-view v-slot="{ Component }">
          <transition name="slide-right" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

      <!-- 底部状态栏 -->
      <footer class="app-statusbar">
        <div class="statusbar-left">
          <span class="status-item" :class="backendStatusClass">
            <span class="status-dot-sm"></span>
            Python 后端: {{ backendStatusText }}
          </span>
          <span class="status-item" :class="ollamaStatusClass">
            <span class="status-dot-sm"></span>
            Ollama: {{ ollamaStatusText }}
          </span>
        </div>
        <div class="statusbar-right">
          <span class="status-item">AI 模式: {{ currentAIMode }}</span>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled,
  View,
  SetUp,
  Setting,
  InfoFilled,
  DArrowLeft,
  DArrowRight,
} from '@element-plus/icons-vue'

const route = useRoute()

// 侧边栏折叠状态
const sidebarCollapsed = ref(false)

// 后端状态
const backendOnline = ref(false)
const ollamaOnline = ref(false)
const aiMode = ref('本地')

// 导航项配置
const navItems = [
  { path: '/', label: '首页', icon: HomeFilled },
  { path: '/multiview', label: '三视图生成', icon: View },
  { path: '/process-plan', label: '工艺规划', icon: SetUp },
  { path: '/settings', label: '设置', icon: Setting },
  { path: '/about', label: '关于', icon: InfoFilled },
]

/** 切换侧边栏折叠 */
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

/** 判断导航项是否激活 */
function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

/** 当前页面标题 */
const currentPageTitle = computed(() => {
  const item = navItems.find((nav) => isActive(nav.path))
  return item?.label || '灵境制造'
})

/** AI 状态样式 */
const aiStatusClass = computed(() => {
  if (backendOnline.value && ollamaOnline.value) return 'status-online'
  if (backendOnline.value) return 'status-partial'
  return 'status-offline'
})

/** AI 状态文字 */
const aiStatusText = computed(() => {
  if (backendOnline.value && ollamaOnline.value) return 'AI 就绪'
  if (backendOnline.value) return 'Ollama 未连接'
  return '后端未连接'
})

/** 后端状态样式 */
const backendStatusClass = computed(() => backendOnline.value ? 'status-online' : 'status-offline')
const backendStatusText = computed(() => backendOnline.value ? '运行中' : '未连接')

/** Ollama 状态样式 */
const ollamaStatusClass = computed(() => ollamaOnline.value ? 'status-online' : 'status-offline')
const ollamaStatusText = computed(() => ollamaOnline.value ? '运行中' : '未连接')

/** 当前 AI 模式 */
const currentAIMode = computed(() => aiMode.value)

/** 检查 Python 后端状态 */
async function checkBackendStatus() {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'
    const res = await fetch(`${baseUrl}/api/health`, { signal: AbortSignal.timeout(5000) })
    backendOnline.value = res.ok
  } catch {
    backendOnline.value = false
  }
}

/** 检查 Ollama 状态 */
async function checkOllamaStatus() {
  try {
    const res = await fetch('http://localhost:11434/api/tags', { signal: AbortSignal.timeout(5000) })
    ollamaOnline.value = res.ok
  } catch {
    ollamaOnline.value = false
  }
}

/** 获取 AI 模式 */
async function fetchAIMode() {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'
    const res = await fetch(`${baseUrl}/api/ai/status`, { signal: AbortSignal.timeout(5000) })
    if (res.ok) {
      const data = await res.json()
      const mode = data?.data?.mode
      if (mode === 'cloud') aiMode.value = '云端'
      else if (mode === 'rule') aiMode.value = '离线'
      else aiMode.value = '本地'
    }
  } catch {
    aiMode.value = '未知'
  }
}

/** 综合检查所有服务状态 */
async function checkAllStatus() {
  await Promise.all([checkBackendStatus(), checkOllamaStatus(), fetchAIMode()])
}

let statusTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  checkAllStatus()
  // 每 30 秒检查一次状态
  statusTimer = setInterval(checkAllStatus, 30000)
})

onBeforeUnmount(() => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
})
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

/* 侧边栏 */
.sidebar {
  width: var(--lj-sidebar-width);
  height: 100%;
  background: var(--lj-sidebar-bg);
  border-right: 1px solid var(--lj-border-light);
  display: flex;
  flex-direction: column;
  transition: width var(--lj-transition-normal);
  flex-shrink: 0;
  overflow: hidden;
}

.sidebar.collapsed {
  width: var(--lj-sidebar-collapsed-width);
}

.sidebar-logo {
  height: var(--lj-header-height);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 10px;
  cursor: pointer;
  border-bottom: 1px solid var(--lj-border-light);
  flex-shrink: 0;
}

.logo-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.logo-icon svg {
  width: 100%;
  height: 100%;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--lj-text-primary);
  white-space: nowrap;
  letter-spacing: 1px;
}

/* 导航菜单 */
.sidebar-nav {
  flex: 1;
  padding: 8px;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--lj-radius-md);
  color: var(--lj-text-secondary);
  text-decoration: none;
  transition: all var(--lj-transition-fast);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
}

.nav-item:hover {
  background: var(--lj-bg-hover);
  color: var(--lj-text-primary);
}

.nav-item.active {
  background: var(--lj-primary);
  color: #fff;
}

.nav-label {
  font-size: 14px;
  white-space: nowrap;
}

/* 侧边栏底部 */
.sidebar-footer {
  padding: 8px;
  border-top: 1px solid var(--lj-border-light);
  flex-shrink: 0;
}

.collapse-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: var(--lj-radius-md);
  color: var(--lj-text-placeholder);
  cursor: pointer;
  transition: all var(--lj-transition-fast);
  overflow: hidden;
}

.collapse-btn:hover {
  background: var(--lj-bg-hover);
  color: var(--lj-text-secondary);
}

/* 主区域 */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* 顶部标题栏 */
.app-header {
  height: var(--lj-header-height);
  background: var(--lj-header-bg);
  border-bottom: 1px solid var(--lj-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--lj-text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* AI 状态指示灯 */
.ai-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  background: var(--lj-bg-card);
}

.ai-status .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ai-status.status-online .status-dot {
  background: var(--lj-success);
  box-shadow: 0 0 6px var(--lj-success);
}

.ai-status.status-partial .status-dot {
  background: var(--lj-warning);
  box-shadow: 0 0 6px var(--lj-warning);
}

.ai-status.status-offline .status-dot {
  background: var(--lj-danger);
  box-shadow: 0 0 6px var(--lj-danger);
}

.status-text {
  color: var(--lj-text-secondary);
  white-space: nowrap;
}

.version-badge {
  font-size: 11px;
  color: var(--lj-text-placeholder);
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--lj-bg-card);
}

/* 主内容区域 */
.app-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--lj-bg-main);
}

/* 底部状态栏 */
.app-statusbar {
  height: var(--lj-statusbar-height);
  background: var(--lj-statusbar-bg);
  border-top: 1px solid var(--lj-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  font-size: 11px;
  flex-shrink: 0;
}

.statusbar-left,
.statusbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--lj-text-placeholder);
}

.status-dot-sm {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-item.status-online .status-dot-sm {
  background: var(--lj-success);
}

.status-item.status-offline .status-dot-sm {
  background: var(--lj-danger);
}
</style>
```

---

### 步骤 3：创建首页/模型库页面

创建 `src/views/Home.vue`：

```vue
<template>
  <div class="home-page">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">欢迎使用灵境制造</h1>
        <p class="welcome-desc">
          AI 驱动的 3D 模型生成与工艺管理平台，数据不出本地设备
        </p>
        <div class="quick-actions">
          <el-button type="primary" size="large" @click="$router.push('/multiview')">
            <el-icon><View /></el-icon>
            三视图生成 3D 模型
          </el-button>
          <el-button size="large" @click="$router.push('/process-plan')">
            <el-icon><SetUp /></el-icon>
            智能工艺规划
          </el-button>
          <el-button size="large" @click="$router.push('/settings')">
            <el-icon><Setting /></el-icon>
            配置 AI 模型
          </el-button>
        </div>
      </div>
    </div>

    <!-- 最近项目 -->
    <div class="recent-section">
      <div class="section-header">
        <h2 class="section-title">最近项目</h2>
        <el-button text size="small" @click="loadProjects">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <!-- 项目列表 -->
      <div v-if="recentProjects.length > 0" class="project-grid">
        <div
          v-for="project in recentProjects"
          :key="project.id"
          class="project-card"
          @click="openProject(project)"
        >
          <div class="card-thumbnail">
            <div class="thumbnail-placeholder">
              <el-icon :size="32"><Box /></el-icon>
            </div>
            <div class="card-type-badge">{{ project.type }}</div>
          </div>
          <div class="card-info">
            <h3 class="card-name">{{ project.name }}</h3>
            <p class="card-desc">{{ project.description }}</p>
            <div class="card-meta">
              <span class="card-date">{{ project.date }}</span>
              <el-tag size="small" :type="project.status === 'completed' ? 'success' : 'warning'">
                {{ project.status === 'completed' ? '已完成' : '进行中' }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <el-empty description="暂无项目">
          <el-button type="primary" @click="$router.push('/multiview')">
            创建第一个项目
          </el-button>
        </el-empty>
      </div>
    </div>

    <!-- 功能特性 -->
    <div class="features-section">
      <h2 class="section-title">核心功能</h2>
      <div class="features-grid">
        <div class="feature-card" @click="$router.push('/multiview')">
          <div class="feature-icon" style="background: rgba(64, 158, 255, 0.15); color: #409EFF;">
            <el-icon :size="28"><View /></el-icon>
          </div>
          <h3>三视图生成 3D</h3>
          <p>上传正视图、侧视图、俯视图，AI 自动生成 3D 模型</p>
        </div>
        <div class="feature-card" @click="$router.push('/process-plan')">
          <div class="feature-icon" style="background: rgba(103, 194, 58, 0.15); color: #67C23A;">
            <el-icon :size="28"><SetUp /></el-icon>
          </div>
          <h3>智能工艺规划</h3>
          <p>AI 自动分析零件特征，生成完整工艺路线和 G 代码</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon" style="background: rgba(230, 162, 60, 0.15); color: #E6A23C;">
            <el-icon :size="28"><Cpu /></el-icon>
          </div>
          <h3>本地 AI 推理</h3>
          <p>集成 Ollama 本地 LLM，数据不出设备，隐私安全</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon" style="background: rgba(245, 108, 108, 0.15); color: #F56C6C;">
            <el-icon :size="28"><Lock /></el-icon>
          </div>
          <h3>数据安全</h3>
          <p>所有数据本地存储，无遥测，无数据上传，完全离线可用</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { View, SetUp, Setting, Refresh, Box, Cpu, Lock } from '@element-plus/icons-vue'

const router = useRouter()

/** 项目数据类型 */
interface Project {
  id: string
  name: string
  description: string
  type: string
  status: 'completed' | 'in_progress'
  date: string
}

/** 最近项目列表 */
const recentProjects = ref<Project[]>([])

/** 加载最近项目 */
async function loadProjects() {
  // TODO: 从后端 API 加载项目列表
  // 当前使用示例数据
  recentProjects.value = [
    {
      id: '1',
      name: '阶梯轴工艺规划',
      description: '45#钢阶梯轴，总长200mm，含螺纹和键槽',
      type: '工艺规划',
      status: 'completed',
      date: '2025-01-15',
    },
    {
      id: '2',
      name: '法兰盘三视图重建',
      description: '铸铁法兰盘，外径150mm，6个螺栓孔',
      type: '3D 重建',
      status: 'completed',
      date: '2025-01-14',
    },
    {
      id: '3',
      name: '支架零件加工',
      description: '铝合金支架，含多个加工面和螺纹孔',
      type: '工艺规划',
      status: 'in_progress',
      date: '2025-01-13',
    },
  ]
}

/** 打开项目 */
function openProject(project: Project) {
  if (project.type === '3D 重建') {
    router.push('/multiview')
  } else {
    router.push('/process-plan')
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.home-page {
  padding: 0;
  overflow-y: auto;
  height: 100%;
}

/* 欢迎区域 */
.welcome-section {
  background: linear-gradient(135deg, #0D1520 0%, #1A2736 50%, #0F1923 100%);
  padding: 48px 40px;
  border-bottom: 1px solid var(--lj-border-light);
}

.welcome-content {
  max-width: 800px;
}

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--lj-text-primary);
  margin: 0 0 12px 0;
}

.welcome-desc {
  font-size: 16px;
  color: var(--lj-text-secondary);
  margin: 0 0 28px 0;
}

.quick-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* 最近项目 */
.recent-section {
  padding: 24px 32px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--lj-text-primary);
  margin: 0;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.project-card {
  background: var(--lj-bg-card);
  border-radius: var(--lj-radius-lg);
  border: 1px solid var(--lj-border-light);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--lj-transition-normal);
}

.project-card:hover {
  border-color: var(--lj-primary);
  transform: translateY(-2px);
  box-shadow: var(--lj-shadow-md);
}

.card-thumbnail {
  height: 140px;
  background: var(--lj-bg-hover);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumbnail-placeholder {
  color: var(--lj-text-placeholder);
}

.card-type-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.5);
  color: var(--lj-text-regular);
}

.card-info {
  padding: 12px 16px;
}

.card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--lj-text-primary);
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-desc {
  font-size: 12px;
  color: var(--lj-text-secondary);
  margin: 0 0 8px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-date {
  font-size: 11px;
  color: var(--lj-text-placeholder);
}

/* 空状态 */
.empty-state {
  padding: 40px 0;
}

/* 功能特性 */
.features-section {
  padding: 24px 32px 40px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.feature-card {
  background: var(--lj-bg-card);
  border-radius: var(--lj-radius-lg);
  border: 1px solid var(--lj-border-light);
  padding: 20px;
  cursor: pointer;
  transition: all var(--lj-transition-normal);
}

.feature-card:hover {
  border-color: var(--lj-border-regular);
  transform: translateY(-2px);
  box-shadow: var(--lj-shadow-sm);
}

.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--lj-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.feature-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--lj-text-primary);
  margin: 0 0 6px 0;
}

.feature-card p {
  font-size: 12px;
  color: var(--lj-text-secondary);
  line-height: 1.5;
  margin: 0;
}
</style>
```

---

### 步骤 4：创建工作台页面

创建 `src/views/Workspace.vue`：

```vue
<template>
  <div class="workspace-page">
    <!-- 顶部工具栏 -->
    <div class="workspace-toolbar">
      <div class="toolbar-left">
        <el-button size="small" @click="openFile">
          <el-icon><FolderOpened /></el-icon>
          打开文件
        </el-button>
        <el-divider direction="vertical" />
        <el-button size="small" @click="resetView">
          <el-icon><RefreshRight /></el-icon>
          重置视图
        </el-button>
        <el-button size="small" @click="toggleWireframe">
          <el-icon><Grid /></el-icon>
          线框
        </el-button>
        <el-divider direction="vertical" />
        <el-select v-model="viewPreset" size="small" style="width: 120px" @change="applyViewPreset">
          <el-option label="等轴测" value="iso" />
          <el-option label="正视图" value="front" />
          <el-option label="侧视图" value="side" />
          <el-option label="俯视图" value="top" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button size="small" @click="takeScreenshot">
          <el-icon><Camera /></el-icon>
          截图
        </el-button>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="workspace-content">
      <!-- 左侧面板：文件树 -->
      <div class="panel-left" :class="{ collapsed: leftPanelCollapsed }">
        <div class="panel-header">
          <span class="panel-title">项目文件</span>
          <el-icon class="panel-collapse-btn" @click="leftPanelCollapsed = !leftPanelCollapsed">
            <DArrowLeft v-if="!leftPanelCollapsed" />
            <DArrowRight v-else />
          </el-icon>
        </div>
        <div v-if="!leftPanelCollapsed" class="panel-body">
          <el-tree
            :data="fileTree"
            :props="{ label: 'name', children: 'children' }"
            node-key="id"
            default-expand-all
            highlight-current
            @node-click="onFileClick"
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <el-icon :size="14">
                  <Folder v-if="data.type === 'folder'" />
                  <Document v-else-if="data.name.endsWith('.stl')" />
                  <Picture v-else-if="data.name.endsWith('.png') || data.name.endsWith('.jpg')" />
                  <Document v-else />
                </el-icon>
                <span>{{ node.label }}</span>
              </span>
            </template>
          </el-tree>
        </div>
      </div>

      <!-- 中间区域：3D 查看器 -->
      <div class="viewer-area">
        <ThreeViewer
          ref="viewerRef"
          :model-url="currentModelUrl"
          model-format="auto"
          background-color="#141E2B"
          :show-grid="true"
          style="width: 100%; height: 100%"
        />
      </div>

      <!-- 右侧面板：属性信息 -->
      <div class="panel-right" :class="{ collapsed: rightPanelCollapsed }">
        <div class="panel-header">
          <span class="panel-title">属性</span>
          <el-icon class="panel-collapse-btn" @click="rightPanelCollapsed = !rightPanelCollapsed">
            <DArrowRight v-if="!rightPanelCollapsed" />
            <DArrowLeft v-else />
          </el-icon>
        </div>
        <div v-if="!rightPanelCollapsed" class="panel-body">
          <div class="property-group">
            <h4 class="group-title">模型信息</h4>
            <div class="property-item">
              <span class="prop-label">文件名</span>
              <span class="prop-value">{{ currentFileName || '未加载' }}</span>
            </div>
            <div class="property-item">
              <span class="prop-label">格式</span>
              <span class="prop-value">{{ currentFileFormat || '-' }}</span>
            </div>
            <div class="property-item">
              <span class="prop-label">大小</span>
              <span class="prop-value">{{ currentFileSize || '-' }}</span>
            </div>
          </div>

          <div class="property-group">
            <h4 class="group-title">工艺信息</h4>
            <div class="property-item">
              <span class="prop-label">材料</span>
              <span class="prop-value">45#钢</span>
            </div>
            <div class="property-item">
              <span class="prop-label">精度</span>
              <span class="prop-value">IT7</span>
            </div>
            <div class="property-item">
              <span class="prop-label">工序数</span>
              <span class="prop-value">5</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部面板：G 代码编辑器 -->
    <div class="gcode-panel" :class="{ collapsed: gcodePanelCollapsed }">
      <div class="panel-header">
        <span class="panel-title">G 代码编辑器</span>
        <div class="panel-actions">
          <el-button text size="small" @click="copyGcode">
            <el-icon><DocumentCopy /></el-icon>
            复制
          </el-button>
          <el-icon class="panel-collapse-btn" @click="gcodePanelCollapsed = !gcodePanelCollapsed">
            <ArrowUp v-if="!gcodePanelCollapsed" />
            <ArrowDown v-else />
          </el-icon>
        </div>
      </div>
      <div v-if="!gcodePanelCollapsed" class="panel-body">
        <textarea
          v-model="gcodeContent"
          class="gcode-editor"
          spellcheck="false"
          placeholder="在此编辑或粘贴 G 代码..."
        ></textarea>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  FolderOpened, RefreshRight, Grid, Camera,
  Folder, Document, Picture, DocumentCopy,
  DArrowLeft, DArrowRight, ArrowUp, ArrowDown,
} from '@element-plus/icons-vue'
import ThreeViewer from '@/components/three/ThreeViewer.vue'

const viewerRef = ref<InstanceType<typeof ThreeViewer>>()

// 面板折叠状态
const leftPanelCollapsed = ref(false)
const rightPanelCollapsed = ref(false)
const gcodePanelCollapsed = ref(true)

// 视图预设
const viewPreset = ref('iso')

// 当前模型
const currentModelUrl = ref('')
const currentFileName = ref('')
const currentFileFormat = ref('')
const currentFileSize = ref('')

// G 代码内容
const gcodeContent = ref('')

/** 文件树数据 */
const fileTree = ref([
  {
    id: '1',
    name: '阶梯轴项目',
    type: 'folder',
    children: [
      {
        id: '2',
        name: '模型',
        type: 'folder',
        children: [
          { id: '3', name: 'shaft.glb', type: 'file' },
          { id: '4', name: 'shaft.stl', type: 'file' },
        ],
      },
      {
        id: '5',
        name: '图纸',
        type: 'folder',
        children: [
          { id: '6', name: 'front_view.png', type: 'file' },
          { id: '7', name: 'side_view.png', type: 'file' },
          { id: '8', name: 'top_view.png', type: 'file' },
        ],
      },
      { id: '9', name: 'program.nc', type: 'file' },
    ],
  },
])

/** 打开文件 */
function openFile() {
  ElMessage.info('文件打开功能开发中')
}

/** 重置视图 */
function resetView() {
  viewerRef.value?.resetCamera()
}

/** 切换线框模式 */
function toggleWireframe() {
  viewerRef.value?.toggleWireframe()
}

/** 截图 */
function takeScreenshot() {
  viewerRef.value?.takeScreenshot()
}

/** 应用视图预设 */
function applyViewPreset(preset: string) {
  resetView()
}

/** 文件树节点点击 */
function onFileClick(data: { name: string; type: string }) {
  if (data.type === 'file') {
    currentFileName.value = data.name
    const ext = data.name.split('.').pop()?.toLowerCase()
    currentFileFormat.value = ext?.toUpperCase() || ''
    currentFileSize.value = '2.4 MB'
    ElMessage.info(`已选择: ${data.name}`)
  }
}

/** 复制 G 代码 */
async function copyGcode() {
  if (!gcodeContent.value) {
    ElMessage.warning('没有可复制的 G 代码')
    return
  }
  try {
    await navigator.clipboard.writeText(gcodeContent.value)
    ElMessage.success('G 代码已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

onMounted(() => {
  gcodeContent.value = `O0001 (阶梯轴加工程序)
N10 G54 G90 G21 G17 (坐标系/绝对/公制/XY平面)
N20 G00 X100.0 Z50.0 (快速定位到安全位置)
N30 T0101 M06 (换1号刀：外圆车刀)
N40 M03 S800 (主轴正转 800rpm)
N50 M08 (冷却液开)
N60 G00 X65.0 Z2.0 (接近工件)
N70 G01 X60.0 Z0 F0.2 (车端面)
N80 G01 X30.0 Z-40.0 F0.15 (车外圆)
N90 G01 X20.0 Z-60.0 (车阶梯)
N100 G00 X100.0 Z50.0 (退刀)
N110 T0202 M06 (换2号刀：螺纹刀)
N120 G00 X25.0 Z5.0 (接近螺纹起点)
N130 G76 P020060 Q100 R0.1 (螺纹循环)
N140 G76 X17.4 Z-35.0 P1300 Q400 F2.0
N150 G00 X100.0 Z50.0 (退刀)
N160 M09 (冷却液关)
N170 M05 (主轴停)
N180 M30 (程序结束)`
})
</script>

<style scoped>
.workspace-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* 工具栏 */
.workspace-toolbar {
  height: 40px;
  background: var(--lj-bg-card);
  border-bottom: 1px solid var(--lj-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  flex-shrink: 0;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 主内容区域 */
.workspace-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* 侧面板通用样式 */
.panel-left,
.panel-right {
  width: 220px;
  background: var(--lj-bg-card);
  border-right: 1px solid var(--lj-border-light);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--lj-transition-normal);
  overflow: hidden;
}

.panel-right {
  border-right: none;
  border-left: 1px solid var(--lj-border-light);
}

.panel-left.collapsed,
.panel-right.collapsed {
  width: 32px;
}

.panel-header {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px;
  border-bottom: 1px solid var(--lj-border-light);
  flex-shrink: 0;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--lj-text-secondary);
  white-space: nowrap;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.panel-collapse-btn {
  cursor: pointer;
  color: var(--lj-text-placeholder);
  transition: color var(--lj-transition-fast);
  flex-shrink: 0;
}

.panel-collapse-btn:hover {
  color: var(--lj-text-primary);
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

/* 文件树 */
.tree-node {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--lj-text-regular);
}

/* 3D 查看器区域 */
.viewer-area {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

/* 属性面板 */
.property-group {
  margin-bottom: 16px;
}

.group-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--lj-text-secondary);
  margin: 0 0 8px 0;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--lj-border-light);
}

.property-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}

.prop-label {
  color: var(--lj-text-placeholder);
}

.prop-value {
  color: var(--lj-text-regular);
  text-align: right;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* G 代码面板 */
.gcode-panel {
  height: 200px;
  background: var(--lj-bg-card);
  border-top: 1px solid var(--lj-border-light);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: height var(--lj-transition-normal);
  overflow: hidden;
}

.gcode-panel.collapsed {
  height: 32px;
}

.gcode-editor {
  width: 100%;
  flex: 1;
  background: #1A1A2E;
  color: #D4D4D4;
  border: none;
  outline: none;
  padding: 12px;
  font-family: var(--lj-font-mono);
  font-size: 13px;
  line-height: 1.6;
  resize: none;
  tab-size: 4;
}
</style>
```

---

### 步骤 5：创建关于页面

创建 `src/views/About.vue`：

```vue
<template>
  <div class="about-page">
    <!-- 应用信息 -->
    <div class="about-hero">
      <div class="app-logo">
        <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" width="64" height="64">
          <rect x="4" y="4" width="56" height="56" rx="12" fill="#409EFF" fill-opacity="0.15" stroke="#409EFF" stroke-width="2"/>
          <path d="M16 44L32 16L48 44" stroke="#409EFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M24 36H40" stroke="#409EFF" stroke-width="3" stroke-linecap="round"/>
          <circle cx="32" cy="26" r="4" fill="#409EFF"/>
        </svg>
      </div>
      <h1 class="app-name">灵境制造</h1>
      <p class="app-slogan">AI 驱动的 3D 模型生成与工艺管理平台</p>
      <div class="app-version">
        <el-tag size="large" effect="dark">v4.0.0</el-tag>
        <span class="build-info">构建版本 2025.01.15 | Tauri 2 + Vue 3 + TypeScript</span>
      </div>
    </div>

    <!-- 核心功能 -->
    <div class="about-section">
      <h2 class="section-title">核心功能</h2>
      <div class="feature-list">
        <div class="feature-item">
          <el-icon :size="20" color="#409EFF"><View /></el-icon>
          <div>
            <h4>三视图生成 3D 模型</h4>
            <p>上传正视图、侧视图、俯视图，AI 自动生成 3D 模型（TRELLIS / Wonder3D 引擎）</p>
          </div>
        </div>
        <div class="feature-item">
          <el-icon :size="20" color="#67C23A"><SetUp /></el-icon>
          <div>
            <h4>智能工艺规划</h4>
            <p>六 Agent 协同工作流：语义理解、工艺路线规划、参数提取、G 代码生成、验证、自动修复</p>
          </div>
        </div>
        <div class="feature-item">
          <el-icon :size="20" color="#E6A23C"><Cpu /></el-icon>
          <div>
            <h4>本地 AI 推理</h4>
            <p>集成 Ollama 本地 LLM，支持 Qwen2.5、DeepSeek-R1 等模型，完全离线运行</p>
          </div>
        </div>
        <div class="feature-item">
          <el-icon :size="20" color="#F56C6C"><Lock /></el-icon>
          <div>
            <h4>数据安全</h4>
            <p>所有数据本地存储，无遥测，无数据上传，完全离线可用</p>
          </div>
        </div>
        <div class="feature-item">
          <el-icon :size="20" color="#909399"><Box /></el-icon>
          <div>
            <h4>3D 模型查看</h4>
            <p>基于 Three.js 的 3D 查看器，支持 GLTF/GLB、STL、OBJ 格式</p>
          </div>
        </div>
        <div class="feature-item">
          <el-icon :size="20" color="#409EFF"><DataAnalysis /></el-icon>
          <div>
            <h4>RAG 知识库</h4>
            <p>基于 ChromaDB 的制造工艺知识检索，支持自定义知识库扩展</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 隐私声明 -->
    <div class="about-section">
      <h2 class="section-title">隐私声明</h2>
      <div class="privacy-card">
        <el-alert type="success" :closable="false" show-icon>
          <template #title>
            <strong>数据不出本地设备</strong>
          </template>
          <template #default>
            <ul class="privacy-list">
              <li>所有用户数据（项目文件、工艺参数、G 代码）均存储在本地设备</li>
              <li>默认使用本地 Ollama 进行 AI 推理，无需联网</li>
              <li>不收集任何用户行为数据，无遥测</li>
              <li>不向任何第三方服务器发送数据</li>
              <li>云端 API 模式为可选功能，需用户主动配置并确认</li>
            </ul>
          </template>
        </el-alert>
      </div>
    </div>

    <!-- 技术栈 -->
    <div class="about-section">
      <h2 class="section-title">技术栈</h2>
      <div class="tech-grid">
        <div class="tech-item">
          <span class="tech-label">桌面框架</span>
          <span class="tech-value">Tauri 2</span>
        </div>
        <div class="tech-item">
          <span class="tech-label">前端框架</span>
          <span class="tech-value">Vue 3 + TypeScript</span>
        </div>
        <div class="tech-item">
          <span class="tech-label">UI 组件库</span>
          <span class="tech-value">Element Plus</span>
        </div>
        <div class="tech-item">
          <span class="tech-label">3D 渲染</span>
          <span class="tech-value">Three.js</span>
        </div>
        <div class="tech-item">
          <span class="tech-label">后端语言</span>
          <span class="tech-value">Rust + Python</span>
        </div>
        <div class="tech-item">
          <span class="tech-label">AI 框架</span>
          <span class="tech-value">FastAPI + Ollama</span>
        </div>
        <div class="tech-item">
          <span class="tech-label">向量数据库</span>
          <span class="tech-value">ChromaDB</span>
        </div>
        <div class="tech-item">
          <span class="tech-label">构建工具</span>
          <span class="tech-value">Vite 6</span>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="about-actions">
      <el-button type="primary" @click="checkUpdate" :loading="checkingUpdate">
        <el-icon><Refresh /></el-icon>
        检查更新
      </el-button>
      <el-button @click="openDataDir">
        <el-icon><FolderOpened /></el-icon>
        打开数据目录
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  View, SetUp, Cpu, Lock, Box, DataAnalysis,
  Refresh, FolderOpened,
} from '@element-plus/icons-vue'

const checkingUpdate = ref(false)

/** 检查更新 */
async function checkUpdate() {
  checkingUpdate.value = true
  try {
    // TODO: 接入 Tauri Updater
    await new Promise((resolve) => setTimeout(resolve, 1500))
    ElMessage.success('当前已是最新版本')
  } catch {
    ElMessage.error('检查更新失败')
  } finally {
    checkingUpdate.value = false
  }
}

/** 打开数据目录 */
async function openDataDir() {
  try {
    const { open } = await import('@tauri-apps/plugin-shell')
    await open(`file://${import.meta.env.VITE_DATA_DIR || '%APPDATA%/lingjing'}`)
  } catch {
    ElMessage.info('数据目录: %APPDATA%/lingjing')
  }
}
</script>

<style scoped>
.about-page {
  padding: 32px;
  max-width: 800px;
  margin: 0 auto;
  overflow-y: auto;
  height: 100%;
}

/* 应用信息 */
.about-hero {
  text-align: center;
  padding: 32px 0;
  border-bottom: 1px solid var(--lj-border-light);
  margin-bottom: 32px;
}

.app-logo {
  margin-bottom: 16px;
}

.app-name {
  font-size: 28px;
  font-weight: 700;
  color: var(--lj-text-primary);
  margin: 0 0 8px 0;
}

.app-slogan {
  font-size: 16px;
  color: var(--lj-text-secondary);
  margin: 0 0 16px 0;
}

.app-version {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.build-info {
  font-size: 12px;
  color: var(--lj-text-placeholder);
}

/* 区块 */
.about-section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--lj-text-primary);
  margin: 0 0 16px 0;
}

/* 功能列表 */
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-item {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: var(--lj-bg-card);
  border-radius: var(--lj-radius-md);
  border: 1px solid var(--lj-border-light);
}

.feature-item > div {
  flex: 1;
}

.feature-item h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--lj-text-primary);
  margin: 0 0 4px 0;
}

.feature-item p {
  font-size: 12px;
  color: var(--lj-text-secondary);
  line-height: 1.5;
  margin: 0;
}

/* 隐私声明 */
.privacy-card {
  background: var(--lj-bg-card);
  border-radius: var(--lj-radius-md);
  padding: 16px;
  border: 1px solid var(--lj-border-light);
}

.privacy-list {
  margin: 8px 0 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--lj-text-regular);
  line-height: 1.8;
}

/* 技术栈 */
.tech-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.tech-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--lj-bg-card);
  border-radius: var(--lj-radius-sm);
  border: 1px solid var(--lj-border-light);
}

.tech-label {
  font-size: 13px;
  color: var(--lj-text-secondary);
}

.tech-value {
  font-size: 13px;
  color: var(--lj-text-primary);
  font-weight: 500;
}

/* 操作按钮 */
.about-actions {
  display: flex;
  gap: 12px;
  padding-top: 24px;
  border-top: 1px solid var(--lj-border-light);
}
</style>
```

---

### 步骤 6：配置路由

创建或更新 `src/router/index.ts`：

```typescript
/**
 * 路由配置
 * 灵境制造 V4 - 所有页面路由定义
 */

import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      children: [
        {
          path: '',
          name: 'Home',
          component: () => import('@/views/Home.vue'),
          meta: { title: '首页' },
        },
        {
          path: 'workspace',
          name: 'Workspace',
          component: () => import('@/views/Workspace.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'multiview',
          name: 'MultiViewTo3D',
          component: () => import('@/views/MultiViewTo3D.vue'),
          meta: { title: '三视图生成' },
        },
        {
          path: 'process-plan',
          name: 'ProcessPlan',
          component: () => import('@/views/ProcessPlan.vue'),
          meta: { title: '工艺规划' },
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('@/views/Settings.vue'),
          meta: { title: '设置' },
        },
        {
          path: 'about',
          name: 'About',
          component: () => import('@/views/About.vue'),
          meta: { title: '关于' },
        },
      ],
    },
  ],
})

// 路由守卫 - 更新页面标题
router.beforeEach((to) => {
  const title = (to.meta.title as string) || '灵境制造'
  document.title = `${title} - 灵境制造 V4`
})

export default router
```

---

### 步骤 7：改造 App.vue（启动流程）

创建或更新 `src/App.vue`：

```vue
<template>
  <!-- 启动加载画面 -->
  <div v-if="!appReady" class="splash-screen">
    <div class="splash-content">
      <div class="splash-logo">
        <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" width="80" height="80">
          <rect x="4" y="4" width="56" height="56" rx="12" fill="#409EFF" fill-opacity="0.15" stroke="#409EFF" stroke-width="2"/>
          <path d="M16 44L32 16L48 44" stroke="#409EFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M24 36H40" stroke="#409EFF" stroke-width="3" stroke-linecap="round"/>
          <circle cx="32" cy="26" r="4" fill="#409EFF"/>
        </svg>
      </div>
      <h1 class="splash-title">灵境制造</h1>
      <p class="splash-version">v4.0.0</p>

      <!-- 加载状态 -->
      <div class="splash-status">
        <el-icon v-if="loading" class="is-loading" :size="20"><Loading /></el-icon>
        <el-icon v-else-if="loadError" :size="20" color="#F56C6C"><WarningFilled /></el-icon>
        <span :class="{ error: !!loadError }">{{ statusMessage }}</span>
      </div>

      <!-- 加载进度 -->
      <div v-if="loading" class="splash-progress">
        <el-progress :percentage="loadProgress" :stroke-width="4" :show-text="false" />
      </div>

      <!-- 错误时的重试按钮 -->
      <el-button
        v-if="loadError"
        type="primary"
        @click="retryInit"
        style="margin-top: 16px"
      >
        重新连接
      </el-button>
    </div>
  </div>

  <!-- 主应用 -->
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Loading, WarningFilled } from '@element-plus/icons-vue'

/** 应用是否就绪 */
const appReady = ref(false)
/** 是否正在加载 */
const loading = ref(true)
/** 加载错误 */
const loadError = ref(false)
/** 状态消息 */
const statusMessage = ref('正在初始化...')
/** 加载进度 */
const loadProgress = ref(0)

/** 检查 Python 后端 */
async function checkBackend(): Promise<boolean> {
  statusMessage.value = '正在连接 Python 后端...'
  loadProgress.value = 20

  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'
    const res = await fetch(`${baseUrl}/api/health`, { signal: AbortSignal.timeout(8000) })
    loadProgress.value = 40
    return res.ok
  } catch {
    return false
  }
}

/** 检查 Ollama */
async function checkOllama(): Promise<boolean> {
  statusMessage.value = '正在检查 Ollama...'
  loadProgress.value = 60

  try {
    const res = await fetch('http://localhost:11434/api/tags', { signal: AbortSignal.timeout(5000) })
    loadProgress.value = 80
    return res.ok
  } catch {
    return false
  }
}

/** 初始化应用 */
async function initApp() {
  loading.value = true
  loadError.value = false
  loadProgress.value = 0

  // 检查后端（允许后端未就绪，但给出提示）
  const backendOk = await checkBackend()
  const ollamaOk = await checkOllama()

  loadProgress.value = 90
  statusMessage.value = '正在加载应用...'

  if (!backendOk && !ollamaOk) {
    statusMessage.value = '后端服务未就绪，部分功能不可用'
    loadError.value = true
    loading.value = false
    setTimeout(() => { appReady.value = true }, 5000)
    return
  }

  if (!backendOk) {
    statusMessage.value = 'Python 后端未连接，AI 功能不可用'
  } else if (!ollamaOk) {
    statusMessage.value = 'Ollama 未连接，本地 AI 不可用'
  } else {
    statusMessage.value = '所有服务就绪'
  }

  loadProgress.value = 100
  await new Promise((resolve) => setTimeout(resolve, 500))
  appReady.value = true
  loading.value = false
}

/** 重试初始化 */
async function retryInit() {
  await initApp()
}

onMounted(() => {
  initApp()
})
</script>

<style scoped>
.splash-screen {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lj-bg-dark);
}

.splash-content {
  text-align: center;
  max-width: 400px;
}

.splash-logo {
  margin-bottom: 20px;
}

.splash-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--lj-text-primary);
  margin: 0 0 4px 0;
}

.splash-version {
  font-size: 14px;
  color: var(--lj-text-placeholder);
  margin: 0 0 24px 0;
}

.splash-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: var(--lj-text-secondary);
  margin-bottom: 16px;
}

.splash-status .error {
  color: var(--lj-danger);
}

.splash-progress {
  width: 240px;
  margin: 0 auto;
}
</style>
```

---

### 步骤 8：更新 main.ts 入口文件

创建或更新 `src/main.ts`：

```typescript
/**
 * 灵境制造 V4 - 应用入口
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import router from './router'

// 全局样式
import './assets/styles/global.css'

const app = createApp(App)

// 注册插件
app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// 挂载应用
app.mount('#app')
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

1. **全局样式验证**：确认 `src/assets/styles/global.css` 包含 CSS 变量定义（主色调、背景色、文字色、边框色、状态色、侧边栏、顶部栏、状态栏尺寸）、Element Plus 深色主题覆盖、滚动条美化、过渡动画（fade/slide）、通用工具类
2. **AppLayout 验证**：确认 `src/components/layout/AppLayout.vue` 包含左侧导航栏（可折叠，图标+文字，5 个导航项）、顶部标题栏（页面标题 + AI 状态指示灯 + 版本号）、底部状态栏（Python 后端状态 + Ollama 状态 + AI 模式）、状态自动检测（30 秒间隔）
3. **Home 验证**：确认 `src/views/Home.vue` 包含欢迎区域、快速操作按钮、最近项目卡片网格、空状态提示、核心功能展示
4. **Workspace 验证**：确认 `src/views/Workspace.vue` 包含文件树、3D 查看器、属性面板、工具栏、G 代码编辑器、面板折叠功能
5. **About 验证**：确认 `src/views/About.vue` 包含应用 Logo/名称/版本、核心功能列表（6 项）、隐私声明（5 条）、技术栈信息（8 项）、检查更新按钮
6. **路由验证**：确认 `src/router/index.ts` 包含 6 个路由（首页、工作台、三视图、工艺规划、设置、关于），全部使用 AppLayout 作为父布局
7. **App.vue 验证**：确认包含启动画面（Logo + 加载状态 + 进度条）、Python 后端检查、Ollama 检查、错误重试机制
8. **TypeScript 编译验证**：`pnpm tauri dev` 启动后，确认所有页面可正常导航，无 TypeScript 编译错误

如果以上验证全部通过，Phase 6 完成。

---PROMPT END---

---

## Phase 7: 数据持久化与设置系统

### 目标

实现完整的数据持久化，包括项目数据、用户设置、AI 配置。建立前端 Pinia Store 与 Rust 文件存储的双向同步机制。

### 验证标准

- [ ] `src/stores/appStore.ts` 包含应用全局状态（语言、主题、侧边栏折叠、后端状态）
- [ ] `src/stores/projectStore.ts` 包含项目管理（项目列表、当前项目、CRUD 操作）
- [ ] `src/stores/settingsStore.ts` 包含用户设置（AI 模式、本地模型、云端 API 配置）
- [ ] 所有 Store 使用 pinia-plugin-persistedstate 持久化到 localStorage
- [ ] `src-tauri/src/lib.rs` 包含 Rust 端数据持久化命令（load_settings, save_settings, load_projects, save_project, delete_project）
- [ ] `src/services/project.ts` 包含项目 CRUD API 封装
- [ ] `src/services/settings.ts` 包含设置读写 API 封装
- [ ] `src/services/backend.ts` 包含后端状态检测和自动重连
- [ ] 设置同步机制：前端 Store 与 Rust 文件存储双向同步
- [ ] 前端 TypeScript 编译无报错

---

---PROMPT START---

## 任务：实现数据持久化与设置系统（Phase 7）

你是一个资深 Rust 后端工程师和 Vue 3 前端工程师。请在已有的灵境制造 V4 项目（Phase 0-6 已完成）基础上，实现完整的数据持久化系统。

### 重要约定
- 所有注释使用中文（docstring 和行内注释）
- Rust 代码使用 serde 进行 JSON 序列化
- Vue 代码使用 Composition API + `<script setup lang="ts">`
- 使用 pinia-plugin-persistedstate 进行 Store 持久化
- 数据存储路径：`%APPDATA%/lingjing/`

### 项目信息
- 项目根目录：`lingjing-v4`
- 前端源码目录：`lingjing-v4/src/`
- Rust 后端目录：`lingjing-v4/src-tauri/`
- Python 后端地址：`http://localhost:8765`

### 已有代码说明
- `src-tauri/src/lib.rs`：Rust 命令入口（已有基础命令）
- `src-tauri/Cargo.toml`：Rust 依赖配置
- `src-tauri/tauri.conf.json`：Tauri 配置
- `src/stores/`：Pinia Store 目录（可能为空）
- `src/services/request.ts`：Axios 请求封装
- `src/services/ollama.ts`：Ollama API 服务

---

### 步骤 1：Rust 端数据持久化

更新 `src-tauri/Cargo.toml`，确保包含以下依赖（在 `[dependencies]` 中添加）：

```toml
serde = { version = "1", features = ["derive"] }
serde_json = "1"
dirs = "5"
```

更新 `src-tauri/src/lib.rs`，添加数据持久化相关命令：

```rust
/**
 * 灵境制造 V4 - Rust 后端命令
 * 包含文件系统操作、数据持久化等功能
 */

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

/// 应用设置结构体
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    /// AI 模式：local / cloud / rule
    pub ai_mode: String,
    /// Ollama 服务地址
    pub ollama_base_url: String,
    /// 当前使用的本地模型
    pub ollama_model: String,
    /// 云端 API 类型
    pub cloud_api_type: String,
    /// 云端 API Key（加密存储）
    pub cloud_api_key: String,
    /// 云端 API 地址
    pub cloud_api_base_url: String,
    /// 云端模型名称
    pub cloud_model_name: String,
    /// 界面语言
    pub language: String,
    /// 主题
    pub theme: String,
    /// 侧边栏是否折叠
    pub sidebar_collapsed: bool,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            ai_mode: "local".to_string(),
            ollama_base_url: "http://localhost:11434".to_string(),
            ollama_model: "qwen2.5:7b".to_string(),
            cloud_api_type: "deepseek".to_string(),
            cloud_api_key: String::new(),
            cloud_api_base_url: "https://api.deepseek.com/v1".to_string(),
            cloud_model_name: "deepseek-chat".to_string(),
            language: "zh-CN".to_string(),
            theme: "dark".to_string(),
            sidebar_collapsed: false,
        }
    }
}

/// 项目元数据结构体
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectMeta {
    /// 项目 ID
    pub id: String,
    /// 项目名称
    pub name: String,
    /// 项目描述
    pub description: String,
    /// 项目类型：three_view / process_plan / cadquery
    pub project_type: String,
    /// 项目状态：active / completed / archived
    pub status: String,
    /// 创建时间（ISO 8601）
    pub created_at: String,
    /// 最后修改时间（ISO 8601）
    pub updated_at: String,
    /// 项目文件路径
    pub project_dir: String,
    /// 缩略图路径（可选）
    pub thumbnail: Option<String>,
}

/// 获取应用数据目录
fn get_app_data_dir() -> Result<PathBuf, String> {
    let dir = dirs::data_dir()
        .ok_or("无法获取应用数据目录")?
        .join("lingjing");

    if !dir.exists() {
        fs::create_dir_all(&dir).map_err(|e| format!("创建数据目录失败: {}", e))?;
    }

    Ok(dir)
}

/// 获取设置文件路径
fn get_settings_path() -> Result<PathBuf, String> {
    Ok(get_app_data_dir()?.join("settings.json"))
}

/// 获取项目列表文件路径
fn get_projects_path() -> Result<PathBuf, String> {
    Ok(get_app_data_dir()?.join("projects.json"))
}

/// 加载设置
#[tauri::command]
pub fn load_settings() -> Result<AppSettings, String> {
    let path = get_settings_path()?;

    if !path.exists() {
        let default_settings = AppSettings::default();
        save_settings(default_settings.clone())?;
        return Ok(default_settings);
    }

    let content = fs::read_to_string(&path)
        .map_err(|e| format!("读取设置文件失败: {}", e))?;

    serde_json::from_str(&content)
        .map_err(|e| format!("解析设置文件失败: {}", e))
}

/// 保存设置
#[tauri::command]
pub fn save_settings(settings: AppSettings) -> Result<(), String> {
    let path = get_settings_path()?;
    let content = serde_json::to_string_pretty(&settings)
        .map_err(|e| format!("序列化设置失败: {}", e))?;

    fs::write(&path, content)
        .map_err(|e| format!("写入设置文件失败: {}", e))?;

    Ok(())
}

/// 加载项目列表
#[tauri::command]
pub fn load_projects() -> Result<Vec<ProjectMeta>, String> {
    let path = get_projects_path()?;

    if !path.exists() {
        return Ok(Vec::new());
    }

    let content = fs::read_to_string(&path)
        .map_err(|e| format!("读取项目列表失败: {}", e))?;

    serde_json::from_str(&content)
        .map_err(|e| format!("解析项目列表失败: {}", e))
}

/// 保存项目（新增或更新）
#[tauri::command]
pub fn save_project(project: ProjectMeta) -> Result<(), String> {
    let path = get_projects_path()?;
    let mut projects = load_projects().unwrap_or_default();

    if let Some(existing) = projects.iter_mut().find(|p| p.id == project.id) {
        *existing = project;
    } else {
        projects.push(project);
    }

    let content = serde_json::to_string_pretty(&projects)
        .map_err(|e| format!("序列化项目列表失败: {}", e))?;

    fs::write(&path, content)
        .map_err(|e| format!("写入项目列表失败: {}", e))?;

    Ok(())
}

/// 删除项目
#[tauri::command]
pub fn delete_project(project_id: String) -> Result<(), String> {
    let path = get_projects_path()?;
    let mut projects = load_projects().unwrap_or_default();
    projects.retain(|p| p.id != project_id);

    let content = serde_json::to_string_pretty(&projects)
        .map_err(|e| format!("序列化项目列表失败: {}", e))?;

    fs::write(&path, content)
        .map_err(|e| format!("写入项目列表失败: {}", e))?;

    Ok(())
}

/// 获取应用数据目录路径（供前端显示）
#[tauri::command]
pub fn get_data_dir() -> Result<String, String> {
    let dir = get_app_data_dir()?;
    Ok(dir.to_string_lossy().to_string())
}

/// 初始化 Tauri 插件注册
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            load_settings,
            save_settings,
            load_projects,
            save_project,
            delete_project,
            get_data_dir,
        ])
        .run(tauri::generate_context!())
        .expect("启动 Tauri 应用失败");
}
```

---

### 步骤 2：安装 pinia-plugin-persistedstate

在项目根目录执行：

```bash
pnpm add pinia-plugin-persistedstate
```

更新 `src/main.ts`，注册持久化插件：

```typescript
/**
 * 灵境制造 V4 - 应用入口
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import router from './router'

// 全局样式
import './assets/styles/global.css'

const app = createApp(App)

// 注册 Pinia（含持久化插件）
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)
app.use(pinia)

// 注册路由和 Element Plus
app.use(router)
app.use(ElementPlus)

// 挂载应用
app.mount('#app')
```

---

### 步骤 3：创建 Pinia Stores

创建 `src/stores/appStore.ts`：

```typescript
/**
 * 应用全局状态 Store
 * 管理语言、主题、侧边栏折叠、后端状态等全局状态
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore(
  'app',
  () => {
    const language = ref('zh-CN')
    const theme = ref('dark')
    const sidebarCollapsed = ref(false)
    const backendOnline = ref(false)
    const ollamaOnline = ref(false)
    const appVersion = ref('4.0.0')

    function toggleSidebar() {
      sidebarCollapsed.value = !sidebarCollapsed.value
    }

    function setBackendStatus(online: boolean) {
      backendOnline.value = online
    }

    function setOllamaStatus(online: boolean) {
      ollamaOnline.value = online
    }

    function setLanguage(lang: string) {
      language.value = lang
    }

    function setTheme(newTheme: string) {
      theme.value = newTheme
    }

    return {
      language,
      theme,
      sidebarCollapsed,
      backendOnline,
      ollamaOnline,
      appVersion,
      toggleSidebar,
      setBackendStatus,
      setOllamaStatus,
      setLanguage,
      setTheme,
    }
  },
  {
    persist: {
      key: 'lingjing-app',
      pick: ['language', 'theme', 'sidebarCollapsed'],
    },
  }
)
```

创建 `src/stores/settingsStore.ts`：

```typescript
/**
 * 用户设置 Store
 * 管理 AI 模式、本地模型、云端 API 配置等用户设置
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'

/** AI 模式类型 */
export type AIMode = 'local' | 'cloud' | 'rule'

export const useSettingsStore = defineStore(
  'settings',
  () => {
    const aiMode = ref<AIMode>('local')
    const ollamaBaseUrl = ref('http://localhost:11434')
    const ollamaModel = ref('qwen2.5:7b')
    const cloudApiType = ref('deepseek')
    const cloudApiKey = ref('')
    const cloudApiBaseUrl = ref('https://api.deepseek.com/v1')
    const cloudModelName = ref('deepseek-chat')
    const loaded = ref(false)

    /** 从 Rust 端加载设置 */
    async function loadFromRust() {
      try {
        const settings = await invoke<any>('load_settings')
        aiMode.value = settings.aiMode || 'local'
        ollamaBaseUrl.value = settings.ollamaBaseUrl || 'http://localhost:11434'
        ollamaModel.value = settings.ollamaModel || 'qwen2.5:7b'
        cloudApiType.value = settings.cloudApiType || 'deepseek'
        cloudApiKey.value = settings.cloudApiKey || ''
        cloudApiBaseUrl.value = settings.cloudApiBaseUrl || 'https://api.deepseek.com/v1'
        cloudModelName.value = settings.cloudModelName || 'deepseek-chat'
        loaded.value = true
        console.log('[SettingsStore] 从 Rust 加载设置成功')
      } catch (e) {
        console.warn('[SettingsStore] 从 Rust 加载设置失败:', e)
        loaded.value = true
      }
    }

    /** 保存设置到 Rust 端 */
    async function saveToRust() {
      try {
        await invoke('save_settings', {
          settings: {
            aiMode: aiMode.value,
            ollamaBaseUrl: ollamaBaseUrl.value,
            ollamaModel: ollamaModel.value,
            cloudApiType: cloudApiType.value,
            cloudApiKey: cloudApiKey.value,
            cloudApiBaseUrl: cloudApiBaseUrl.value,
            cloudModelName: cloudModelName.value,
            language: 'zh-CN',
            theme: 'dark',
            sidebarCollapsed: false,
          },
        })
        console.log('[SettingsStore] 设置已保存到 Rust')
      } catch (e) {
        console.error('[SettingsStore] 保存设置到 Rust 失败:', e)
      }
    }

    function setAIMode(mode: AIMode) {
      aiMode.value = mode
    }

    function setOllamaConfig(config: { baseUrl?: string; model?: string }) {
      if (config.baseUrl) ollamaBaseUrl.value = config.baseUrl
      if (config.model) ollamaModel.value = config.model
    }

    function setCloudConfig(config: {
      apiType?: string
      apiKey?: string
      baseUrl?: string
      modelName?: string
    }) {
      if (config.apiType) cloudApiType.value = config.apiType
      if (config.apiKey !== undefined) cloudApiKey.value = config.apiKey
      if (config.baseUrl) cloudApiBaseUrl.value = config.baseUrl
      if (config.modelName) cloudModelName.value = config.modelName
    }

    async function saveAll() {
      await saveToRust()
    }

    // 监听设置变更，自动同步到 Rust
    watch(
      [aiMode, ollamaBaseUrl, ollamaModel, cloudApiType, cloudApiBaseUrl, cloudModelName],
      () => {
        if (loaded.value) {
          saveToRust()
        }
      },
      { deep: true }
    )

    return {
      aiMode,
      ollamaBaseUrl,
      ollamaModel,
      cloudApiType,
      cloudApiKey,
      cloudApiBaseUrl,
      cloudModelName,
      loaded,
      loadFromRust,
      saveToRust,
      setAIMode,
      setOllamaConfig,
      setCloudConfig,
      saveAll,
    }
  },
  {
    persist: {
      key: 'lingjing-settings',
      pick: ['aiMode', 'ollamaBaseUrl', 'ollamaModel', 'cloudApiType', 'cloudApiKey', 'cloudApiBaseUrl', 'cloudModelName'],
    },
  }
)
```

创建 `src/stores/projectStore.ts`：

```typescript
/**
 * 项目管理 Store
 * 管理项目列表、当前项目、CRUD 操作
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

/** 项目类型 */
export type ProjectType = 'three_view' | 'process_plan' | 'cadquery'

/** 项目状态 */
export type ProjectStatus = 'active' | 'completed' | 'archived'

/** 项目元数据 */
export interface Project {
  id: string
  name: string
  description: string
  projectType: ProjectType
  status: ProjectStatus
  createdAt: string
  updatedAt: string
  projectDir: string
  thumbnail?: string
}

export const useProjectStore = defineStore(
  'project',
  () => {
    const projects = ref<Project[]>([])
    const currentProjectId = ref<string | null>(null)
    const loaded = ref(false)

    /** 从 Rust 端加载项目列表 */
    async function loadFromRust() {
      try {
        const data = await invoke<any[]>('load_projects')
        projects.value = data.map((p: any) => ({
          id: p.id,
          name: p.name,
          description: p.description,
          projectType: p.projectType,
          status: p.status,
          createdAt: p.createdAt,
          updatedAt: p.updatedAt,
          projectDir: p.projectDir,
          thumbnail: p.thumbnail,
        }))
        loaded.value = true
        console.log(`[ProjectStore] 加载了 ${projects.value.length} 个项目`)
      } catch (e) {
        console.warn('[ProjectStore] 从 Rust 加载项目失败:', e)
        loaded.value = true
      }
    }

    /** 保存项目到 Rust 端 */
    async function saveProjectToRust(project: Project) {
      try {
        await invoke('save_project', {
          project: {
            id: project.id,
            name: project.name,
            description: project.description,
            projectType: project.projectType,
            status: project.status,
            createdAt: project.createdAt,
            updatedAt: project.updatedAt,
            projectDir: project.projectDir,
            thumbnail: project.thumbnail || null,
          },
        })
      } catch (e) {
        console.error('[ProjectStore] 保存项目失败:', e)
        throw e
      }
    }

    /** 创建新项目 */
    async function createProject(params: {
      name: string
      description: string
      projectType: ProjectType
    }): Promise<Project> {
      const now = new Date().toISOString()
      const project: Project = {
        id: crypto.randomUUID(),
        name: params.name,
        description: params.description,
        projectType: params.projectType,
        status: 'active',
        createdAt: now,
        updatedAt: now,
        projectDir: '',
        thumbnail: undefined,
      }

      projects.value.unshift(project)
      await saveProjectToRust(project)
      return project
    }

    /** 更新项目 */
    async function updateProject(id: string, updates: Partial<Project>) {
      const index = projects.value.findIndex((p) => p.id === id)
      if (index === -1) return

      const project = {
        ...projects.value[index],
        ...updates,
        updatedAt: new Date().toISOString(),
      }
      projects.value[index] = project
      await saveProjectToRust(project)
    }

    /** 删除项目 */
    async function deleteProject(id: string) {
      try {
        await invoke('delete_project', { projectId: id })
        projects.value = projects.value.filter((p) => p.id !== id)
        if (currentProjectId.value === id) {
          currentProjectId.value = null
        }
      } catch (e) {
        console.error('[ProjectStore] 删除项目失败:', e)
        throw e
      }
    }

    function setCurrentProject(id: string | null) {
      currentProjectId.value = id
    }

    function getCurrentProject(): Project | undefined {
      if (!currentProjectId.value) return undefined
      return projects.value.find((p) => p.id === currentProjectId.value)
    }

    function getProjectsByType(type: ProjectType): Project[] {
      return projects.value.filter((p) => p.projectType === type)
    }

    function getRecentProjects(limit: number = 10): Project[] {
      return [...projects.value]
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        .slice(0, limit)
    }

    return {
      projects,
      currentProjectId,
      loaded,
      loadFromRust,
      createProject,
      updateProject,
      deleteProject,
      setCurrentProject,
      getCurrentProject,
      getProjectsByType,
      getRecentProjects,
    }
  },
  {
    persist: {
      key: 'lingjing-projects',
      pick: ['currentProjectId'],
    },
  }
)
```

---

### 步骤 4：创建前端服务层

创建 `src/services/backend.ts`：

```typescript
/**
 * 后端状态检测和自动重连服务
 */

import { ref } from 'vue'

/** 后端连接状态 */
export const backendStatus = ref<'connecting' | 'online' | 'offline'>('connecting')

/** Ollama 连接状态 */
export const ollamaStatus = ref<'connecting' | 'online' | 'offline'>('connecting')

/** 后端地址 */
const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'

/** Ollama 地址 */
const OLLAMA_URL = 'http://localhost:11434'

/** 检查后端健康状态 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`, {
      signal: AbortSignal.timeout(5000),
    })
    backendStatus.value = res.ok ? 'online' : 'offline'
    return res.ok
  } catch {
    backendStatus.value = 'offline'
    return false
  }
}

/** 检查 Ollama 状态 */
export async function checkOllamaHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${OLLAMA_URL}/api/tags`, {
      signal: AbortSignal.timeout(5000),
    })
    ollamaStatus.value = res.ok ? 'online' : 'offline'
    return res.ok
  } catch {
    ollamaStatus.value = 'offline'
    return false
  }
}

/** 自动重连管理器 */
export class AutoReconnector {
  private timer: ReturnType<typeof setInterval> | null = null
  private interval: number
  private onStatusChange?: (backend: boolean, ollama: boolean) => void

  constructor(interval: number = 15000, onStatusChange?: (backend: boolean, ollama: boolean) => void) {
    this.interval = interval
    this.onStatusChange = onStatusChange
  }

  /** 启动自动重连 */
  start() {
    this.stop()
    this.check()
    this.timer = setInterval(() => this.check(), this.interval)
  }

  /** 停止自动重连 */
  stop() {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
  }

  /** 执行检查 */
  private async check() {
    const [backend, ollama] = await Promise.all([
      checkBackendHealth(),
      checkOllamaHealth(),
    ])
    this.onStatusChange?.(backend, ollama)
  }
}
```

创建 `src/services/settings.ts`：

```typescript
/**
 * 设置读写 API 封装
 * 封装与 Rust 端和 Python 后端的设置交互
 */

import { invoke } from '@tauri-apps/api/core'
import request from './request'

/** 应用设置接口 */
export interface AppSettings {
  aiMode: 'local' | 'cloud' | 'rule'
  ollamaBaseUrl: string
  ollamaModel: string
  cloudApiType: string
  cloudApiKey: string
  cloudApiBaseUrl: string
  cloudModelName: string
  language: string
  theme: string
  sidebarCollapsed: boolean
}

/** 从 Rust 端加载设置 */
export async function loadSettingsFromRust(): Promise<AppSettings> {
  return invoke<AppSettings>('load_settings')
}

/** 保存设置到 Rust 端 */
export async function saveSettingsToRust(settings: AppSettings): Promise<void> {
  await invoke('save_settings', { settings })
}

/** 从 Python 后端加载 AI 状态 */
export async function loadAIStatusFromBackend(): Promise<Record<string, unknown>> {
  const res = await request.get('/api/ai/status')
  return res.data.data
}

/** 更新 Python 后端的 AI 设置 */
export async function updateBackendAISettings(settings: Partial<AppSettings>): Promise<void> {
  await request.put('/api/ai/settings', settings)
}

/** 获取应用数据目录路径 */
export async function getDataDir(): Promise<string> {
  return invoke<string>('get_data_dir')
}
```

创建 `src/services/project.ts`：

```typescript
/**
 * 项目 CRUD API 封装
 * 封装与 Rust 端的项目数据交互
 */

import { invoke } from '@tauri-apps/api/core'

/** 项目元数据接口 */
export interface ProjectMeta {
  id: string
  name: string
  description: string
  projectType: 'three_view' | 'process_plan' | 'cadquery'
  status: 'active' | 'completed' | 'archived'
  createdAt: string
  updatedAt: string
  projectDir: string
  thumbnail?: string
}

/** 从 Rust 端加载项目列表 */
export async function loadProjectsFromRust(): Promise<ProjectMeta[]> {
  return invoke<ProjectMeta[]>('load_projects')
}

/** 保存项目到 Rust 端 */
export async function saveProjectToRust(project: ProjectMeta): Promise<void> {
  await invoke('save_project', { project })
}

/** 从 Rust 端删除项目 */
export async function deleteProjectFromRust(projectId: string): Promise<void> {
  await invoke('delete_project', { projectId })
}
```

---

### 步骤 5：在 App.vue 中集成 Store 初始化

更新 `src/App.vue` 的 `<script setup>` 部分，在 `initApp` 函数中添加 Store 加载逻辑。在 `checkBackend` 之前，添加 Store 加载：

```typescript
// 在 App.vue 的 <script setup> 中添加以下导入和逻辑

import { useSettingsStore } from '@/stores/settingsStore'
import { useProjectStore } from '@/stores/projectStore'

// 在 initApp 函数中，在 checkBackend 之前调用
const settingsStore = useSettingsStore()
const projectStore = useProjectStore()

await settingsStore.loadFromRust()
await projectStore.loadFromRust()
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

1. **Rust 端验证**：确认 `src-tauri/src/lib.rs` 包含 load_settings, save_settings, load_projects, save_project, delete_project, get_data_dir 命令
2. **AppSettings 结构体验证**：确认包含 aiMode, ollamaBaseUrl, ollamaModel, cloudApiType, cloudApiKey, cloudApiBaseUrl, cloudModelName, language, theme, sidebarCollapsed 字段
3. **ProjectMeta 结构体验证**：确认包含 id, name, description, projectType, status, createdAt, updatedAt, projectDir, thumbnail 字段
4. **Store 验证**：确认 appStore、settingsStore、projectStore 存在且功能完整，使用 persistedstate 持久化
5. **服务层验证**：确认 backend.ts、settings.ts、project.ts 存在且功能完整
6. **同步机制验证**：确认 settingsStore 中 watch 监听设置变更并自动调用 saveToRust
7. **TypeScript 编译验证**：`pnpm tauri dev` 启动后无 TypeScript 编译错误

如果以上验证全部通过，Phase 7 完成。

---PROMPT END---

---

## Phase 8: 测试、打包与微软商店发布

### 目标

完成测试、打包配置、微软商店发布准备。包括前端测试、Python 后端测试、Tauri 打包配置、微软商店发布流程、自动更新配置和发布前检查清单。

### 验证标准

- [ ] `vitest.config.ts` 配置完整
- [ ] `tests/frontend/` 包含组件测试和 Store 测试示例
- [ ] `tests/python/` 包含 API 测试和 Agent 工作流测试示例
- [ ] `src-tauri/tauri.conf.json` 生产环境配置完整
- [ ] `scripts/build-sidecar.ps1` PyInstaller 打包脚本完整
- [ ] `scripts/build-msix.ps1` MSIX 打包脚本完整
- [ ] 自动更新配置（Tauri Updater）完整
- [ ] 发布前检查清单完整

---

---PROMPT START---

## 任务：测试、打包与微软商店发布（Phase 8）

你是一个资深 DevOps 工程师和 Tauri 桌面应用发布专家。请在已有的灵境制造 V4 项目（Phase 0-7 已完成）基础上，完成测试、打包配置和微软商店发布准备。

### 重要约定
- 所有注释使用中文
- 测试使用 Vitest（前端）和 pytest（Python）
- 打包使用 Tauri CLI + PyInstaller
- 微软商店发布使用 MSIX 格式

### 项目信息
- 项目根目录：`lingjing-v4`
- 前端源码目录：`lingjing-v4/src/`
- Rust 后端目录：`lingjing-v4/src-tauri/`
- Python 后端目录：`lingjing-v4/python/`
- 应用标识符：`com.lingjing.manufacturing`
- 应用名称：灵境制造

---

### 步骤 1：前端测试配置

安装 Vitest 依赖：

```bash
pnpm add -D vitest @vue/test-utils happy-dom @pinia/testing
```

创建 `vitest.config.ts`：

```typescript
/**
 * Vitest 测试配置
 */

import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'happy-dom',
    include: ['tests/frontend/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,vue}'],
      exclude: ['src/main.ts', 'src/**/*.d.ts'],
    },
    setupFiles: ['tests/frontend/setup.ts'],
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
})
```

创建 `tests/frontend/setup.ts`：

```typescript
/**
 * 测试环境初始化
 */

import { config } from '@vue/test-utils'

// 全局配置 Vue Test Utils
config.global.stubs = {
  // 存根 Tauri API（测试环境中不可用）
}

// Mock Tauri API
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}))

vi.mock('@tauri-apps/plugin-shell', () => ({
  open: vi.fn(),
}))
```

创建 `tests/frontend/stores/settingsStore.test.ts`：

```typescript
/**
 * settingsStore 单元测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSettingsStore } from '@/stores/settingsStore'

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}))

describe('settingsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('默认 AI 模式为 local', () => {
    const store = useSettingsStore()
    expect(store.aiMode).toBe('local')
  })

  it('默认 Ollama 地址', () => {
    const store = useSettingsStore()
    expect(store.ollamaBaseUrl).toBe('http://localhost:11434')
  })

  it('默认 Ollama 模型', () => {
    const store = useSettingsStore()
    expect(store.ollamaModel).toBe('qwen2.5:7b')
  })

  it('setAIMode 正确切换模式', () => {
    const store = useSettingsStore()
    store.setAIMode('cloud')
    expect(store.aiMode).toBe('cloud')
    store.setAIMode('rule')
    expect(store.aiMode).toBe('rule')
    store.setAIMode('local')
    expect(store.aiMode).toBe('local')
  })

  it('setOllamaConfig 正确更新配置', () => {
    const store = useSettingsStore()
    store.setOllamaConfig({
      baseUrl: 'http://192.168.1.100:11434',
      model: 'deepseek-r1:7b',
    })
    expect(store.ollamaBaseUrl).toBe('http://192.168.1.100:11434')
    expect(store.ollamaModel).toBe('deepseek-r1:7b')
  })

  it('setCloudConfig 正确更新配置', () => {
    const store = useSettingsStore()
    store.setCloudConfig({
      apiType: 'openai',
      apiKey: 'sk-test-123',
      baseUrl: 'https://api.openai.com/v1',
      modelName: 'gpt-4',
    })
    expect(store.cloudApiType).toBe('openai')
    expect(store.cloudApiKey).toBe('sk-test-123')
    expect(store.cloudApiBaseUrl).toBe('https://api.openai.com/v1')
    expect(store.cloudModelName).toBe('gpt-4')
  })
})
```

创建 `tests/frontend/stores/projectStore.test.ts`：

```typescript
/**
 * projectStore 单元测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProjectStore } from '@/stores/projectStore'

const mockInvoke = vi.fn()
vi.mock('@tauri-apps/api/core', () => ({
  invoke: (...args: unknown[]) => mockInvoke(...args),
}))

describe('projectStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockInvoke.mockResolvedValue([])
  })

  it('初始项目列表为空', () => {
    const store = useProjectStore()
    expect(store.projects).toEqual([])
    expect(store.currentProjectId).toBeNull()
  })

  it('createProject 创建新项目', async () => {
    const store = useProjectStore()
    mockInvoke.mockResolvedValue(undefined)

    const project = await store.createProject({
      name: '测试项目',
      description: '测试描述',
      projectType: 'three_view',
    })

    expect(project.name).toBe('测试项目')
    expect(project.description).toBe('测试描述')
    expect(project.projectType).toBe('three_view')
    expect(project.status).toBe('active')
    expect(project.id).toBeTruthy()
    expect(store.projects).toHaveLength(1)
  })

  it('deleteProject 删除项目', async () => {
    const store = useProjectStore()
    mockInvoke.mockResolvedValue(undefined)

    const project = await store.createProject({
      name: '待删除项目',
      description: '',
      projectType: 'process_plan',
    })

    await store.deleteProject(project.id)
    expect(store.projects).toHaveLength(0)
  })

  it('setCurrentProject 设置当前项目', async () => {
    const store = useProjectStore()
    mockInvoke.mockResolvedValue(undefined)

    const project = await store.createProject({
      name: '当前项目',
      description: '',
      projectType: 'cadquery',
    })

    store.setCurrentProject(project.id)
    expect(store.currentProjectId).toBe(project.id)

    const current = store.getCurrentProject()
    expect(current?.name).toBe('当前项目')
  })

  it('getRecentProjects 按更新时间排序', async () => {
    const store = useProjectStore()
    mockInvoke.mockResolvedValue(undefined)

    await store.createProject({ name: '项目A', description: '', projectType: 'three_view' })
    await new Promise((r) => setTimeout(r, 10))
    await store.createProject({ name: '项目B', description: '', projectType: 'process_plan' })

    const recent = store.getRecentProjects(2)
    expect(recent[0].name).toBe('项目B')
    expect(recent[1].name).toBe('项目A')
  })
})
```

在 `package.json` 中添加测试脚本：

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

---

### 步骤 2：Python 后端测试

创建 `tests/python/conftest.py`：

```python
"""
Python 测试配置
提供测试用的 FastAPI 客户端和 fixtures
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建测试客户端"""
    from app.main import app
    return TestClient(app)
```

创建 `tests/python/test_health.py`：

```python
"""
健康检查 API 测试
"""


def test_health_check(client):
    """测试健康检查接口"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "data" in data
```

创建 `tests/python/test_ai_status.py`：

```python
"""
AI 状态 API 测试
"""


def test_ai_status(client):
    """测试 AI 状态查询接口"""
    response = client.get("/api/ai/status")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    result = data["data"]
    assert "mode" in result
    assert "available" in result


def test_ai_settings_update(client):
    """测试 AI 设置更新接口"""
    response = client.put(
        "/api/ai/settings",
        json={
            "mode": "local",
            "ollama_model": "qwen2.5:7b",
            "ollama_base_url": "http://localhost:11434",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
```

创建 `tests/python/test_ollama.py`：

```python
"""
Ollama API 测试
"""


def test_ollama_status(client):
    """测试 Ollama 状态查询"""
    response = client.get("/api/ollama/status")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    result = data["data"]
    assert "available" in result
    assert "version" in result


def test_recommended_models(client):
    """测试推荐模型列表"""
    response = client.get("/api/ollama/models/recommended")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    models = data["data"]["models"]
    assert len(models) >= 4
    for model in models:
        assert "name" in model
        assert "size" in model
        assert "description" in model
        assert "category" in model
        assert "installed" in model
```

创建 `tests/python/test_workflow.py`：

```python
"""
AI 工作流 API 测试
"""

from unittest.mock import patch, AsyncMock


def test_workflow_requires_description(client):
    """测试工作流接口需要零件描述"""
    response = client.post(
        "/api/process-route/generate",
        json={
            "description": "",
            "material": "45钢",
        },
    )
    assert response.status_code == 422


@patch("app.ai.agents.get_llm_client")
def test_workflow_full(mock_get_client, client):
    """测试完整工作流（Mock LLM）"""
    mock_client = AsyncMock()
    mock_client.chat_with_retry = AsyncMock(
        return_value=AsyncMock(content='{"result": "test"}')
    )
    mock_get_client.return_value = mock_client

    response = client.post(
        "/api/process-route/generate",
        json={
            "description": "一根阶梯轴，总长200mm，最大直径60mm",
            "material": "45钢",
            "quantity": 1,
            "precision": "普通",
        },
    )
    assert response.status_code == 200
```

---

### 步骤 3：Tauri 打包配置

更新 `src-tauri/tauri.conf.json` 为生产环境配置：

```json
{
  "$schema": "https://raw.githubusercontent.com/nicegram/nicegram-ios-tauri/refs/heads/main/src-tauri/tauri.conf.json",
  "productName": "lingjing-manufacturing",
  "version": "4.0.0",
  "identifier": "com.lingjing.manufacturing",
  "build": {
    "beforeDevCommand": "pnpm dev",
    "devUrl": "http://localhost:1420",
    "beforeBuildCommand": "pnpm build",
    "frontendDist": "../dist"
  },
  "app": {
    "title": "灵境制造",
    "windows": [
      {
        "title": "灵境制造 V4",
        "width": 1280,
        "height": 800,
        "minWidth": 1024,
        "minHeight": 680,
        "resizable": true,
        "fullscreen": false,
        "decorations": true,
        "center": true
      }
    ],
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://localhost:8765 http://localhost:11434 https://*; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'"
    }
  },
  "bundle": {
    "active": true,
    "targets": ["nsis", "msi"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "resources": [],
    "copyright": "Copyright (c) 2025 LingJing Manufacturing",
    "category": "Productivity",
    "shortDescription": "AI 驱动的 3D 模型生成与工艺管理平台",
    "longDescription": "灵境制造是面向制造行业的 AI 驱动桌面应用，支持三视图生成 3D 模型、智能工艺规划、G 代码生成。数据不出本地设备，完全离线可用。",
    "windows": {
      "nsis": {
        "installMode": "currentUser",
        "displayLanguageSelector": false,
        "languages": ["SimpChinese", "English"]
      }
    }
  },
  "plugins": {
    "updater": {
      "endpoints": [
        "https://releases.lingjing.com/updates/{{target}}/{{arch}}/{{current_version}}"
      ],
      "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEEwQTIwQjNENEQ2NjE1QjQKUldRRk5XQk5FTlZGQlZKSTJOTVFSSUZCVkVZQkVFT1JWQkVGRlJTWkVVSUJFQkVGRkNFWQo="
    }
  }
}
```

---

### 步骤 4：PyInstaller 打包 Python Sidecar

创建 `scripts/build-sidecar.ps1`：

```powershell
# ============================================
# 灵境制造 V4 - Python Sidecar 打包脚本
# 使用 PyInstaller 将 Python FastAPI 后端打包为独立可执行文件
# ============================================

param(
    [string]$PythonPath = "python",
    [string]$OutputDir = "..\src-tauri\binaries",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  灵境制造 V4 - Python Sidecar 打包" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 1. 检查 Python 环境
Write-Host "`n[1/5] 检查 Python 环境..." -ForegroundColor Yellow
$pythonVersion = & $PythonPath --version 2>&1
Write-Host "  Python 版本: $pythonVersion"

# 2. 安装依赖
Write-Host "`n[2/5] 安装依赖..." -ForegroundColor Yellow
Push-Location python
& $PythonPath -m pip install --upgrade pip
& $PythonPath -m pip install -r requirements.txt
& $PythonPath -m pip install pyinstaller

# 3. 清理旧构建
if ($Clean -or (Test-Path "dist")) {
    Write-Host "`n[3/5] 清理旧构建..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist, build
}

# 4. 执行 PyInstaller 打包
Write-Host "`n[4/5] 执行 PyInstaller 打包..." -ForegroundColor Yellow
& $PythonPath -m PyInstaller `
    --name "lingjing-backend" `
    --onefile `
    --console `
    --noconfirm `
    --clean `
    --add-data "app:app" `
    --hidden-import "uvicorn.logging" `
    --hidden-import "uvicorn.loops" `
    --hidden-import "uvicorn.loops.auto" `
    --hidden-import "uvicorn.protocols" `
    --hidden-import "uvicorn.protocols.http" `
    --hidden-import "uvicorn.protocols.http.auto" `
    --hidden-import "uvicorn.protocols.websockets" `
    --hidden-import "uvicorn.protocols.websockets.auto" `
    --hidden-import "uvicorn.lifespan" `
    --hidden-import "uvicorn.lifespan.on" `
    --collect-all "app" `
    app/main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "  PyInstaller 打包失败!" -ForegroundColor Red
    Pop-Location
    exit 1
}

# 5. 复制到 Tauri binaries 目录
Write-Host "`n[5/5] 复制到 Tauri binaries 目录..." -ForegroundColor Yellow
$binaryName = "lingjing-backend.exe"
$sourcePath = "dist\$binaryName"
$targetDir = Resolve-Path -Path $OutputDir
$targetPath = Join-Path $targetDir $binaryName

if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

Copy-Item -Path $sourcePath -Destination $targetPath -Force
Write-Host "  已复制到: $targetPath"

Pop-Location

Write-Host "`n============================================" -ForegroundColor Green
Write-Host "  打包完成!" -ForegroundColor Green
Write-Host "  输出文件: $targetPath" -ForegroundColor Green
Write-Host "  文件大小: $([math]::Round((Get-Item $targetPath).Length / 1MB, 2)) MB" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
```

---

### 步骤 5：MSIX 打包脚本

创建 `scripts/build-msix.ps1`：

```powershell
# ============================================
# 灵境制造 V4 - MSIX 打包脚本
# 将 NSIS 安装包转换为微软商店可用的 MSIX 格式
# ============================================

param(
    [string]$Version = "4.0.0",
    [string]$OutputDir = ".\msix-output"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  灵境制造 V4 - MSIX 打包" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 1. 检查 MakeAppx 工具
Write-Host "`n[1/4] 检查打包工具..." -ForegroundColor Yellow
$makeAppx = Get-Command "MakeAppx.exe" -ErrorAction SilentlyContinue
if (-not $makeAppx) {
    Write-Host "  未找到 MakeAppx.exe，请安装 Windows SDK" -ForegroundColor Red
    Write-Host "  下载地址: https://developer.microsoft.com/windows/downloads/windows-sdk/" -ForegroundColor Yellow
    exit 1
}
Write-Host "  MakeAppx.exe: $($makeAppx.Source)"

# 2. 构建 Tauri 应用
Write-Host "`n[2/4] 构建 Tauri 应用..." -ForegroundColor Yellow
Push-Location ..
& pnpm tauri build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Tauri 构建失败!" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

# 3. 准备 MSIX 内容
Write-Host "`n[3/4] 准备 MSIX 内容..." -ForegroundColor Yellow
$msixDir = Join-Path $OutputDir "msix-content"
if (Test-Path $msixDir) {
    Remove-Item -Recurse -Force $msixDir
}
New-Item -ItemType Directory -Path $msixDir -Force | Out-Null

# 复制应用文件
$exePath = "..\src-tauri\target\release\lingjing-manufacturing.exe"
if (Test-Path $exePath) {
    Copy-Item $exePath $msixDir
}

# 复制依赖 DLL
$releaseDir = "..\src-tauri\target\release"
Get-ChildItem -Path $releaseDir -Filter "*.dll" | Copy-Item -Destination $msixDir

# 4. 创建 AppxManifest.xml
Write-Host "`n[4/4] 创建 MSIX 包..." -ForegroundColor Yellow

$manifestContent = @"
<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap rescap">
  <Identity
    Name="com.lingjing.manufacturing"
    Publisher="CN=你的发布者ID"
    Version="$Version.0" />
  <Properties>
    <DisplayName>灵境制造</DisplayName>
    <PublisherDisplayName>LingJing Manufacturing</PublisherDisplayName>
    <Description>AI 驱动的 3D 模型生成与工艺管理平台</Description>
    <Logo>icons\StoreLogo.png</Logo>
  </Properties>
  <Resources>
    <Resource Language="zh-CN" />
    <Resource Language="en-US" />
    <Resource uap:Scale="100" />
    <Resource uap:Scale="125" />
    <Resource uap:Scale="150" />
    <Resource uap:Scale="200" />
  </Resources>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.19041.0" />
  </Dependencies>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
  <Applications>
    <Application Id="LingJingApp" Executable="lingjing-manufacturing.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="灵境制造"
        Description="AI 驱动的 3D 模型生成与工艺管理平台"
        BackgroundColor="#0F1923"
        Square150x150Logo="icons\Square150x150Logo.png"
        Square44x44Logo="icons\Square44x44Logo.png"
        AppListEntry="default" />
    </Application>
  </Applications>
</Package>
"@

$manifestPath = Join-Path $msixDir "AppxManifest.xml"
Set-Content -Path $manifestPath -Value $manifestContent -Encoding UTF8

Write-Host "`n============================================" -ForegroundColor Yellow
Write-Host "  注意事项:" -ForegroundColor Yellow
Write-Host "  1. 请将 Publisher 替换为你的 Microsoft 开发者账户 ID" -ForegroundColor Yellow
Write-Host "  2. 请准备所有尺寸的应用图标" -ForegroundColor Yellow
Write-Host "  3. 建议使用 Microsoft Store 提交工具进行最终打包" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
```

---

### 步骤 6：自动更新配置

生成签名密钥对（仅执行一次）：

```bash
# 安装 Tauri signer 工具
cargo install tauri-plugin-updater

# 生成密钥对
# 注意：私钥请妥善保管，丢失后无法更新！
npx tauri signer generate -w ~/.tauri/lingjing.key
```

更新 `src-tauri/Cargo.toml`，添加 Updater 插件：

```toml
[dependencies]
tauri-plugin-updater = "2"
```

更新 `src-tauri/src/lib.rs`，注册 Updater 插件：

```rust
// 在 run() 函数中添加：
.plugin(tauri_plugin_updater::Builder::new().build())
```

更新 `src-tauri/capabilities/default.json`，添加 Updater 权限：

```json
{
  "identifier": "default",
  "description": "默认权限",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "shell:allow-open",
    "dialog:default",
    "fs:default",
    "updater:default"
  ]
}
```

创建静态更新服务器 JSON 文件 `docs/update-latest.json`（部署到静态服务器）：

```json
{
  "version": "4.0.0",
  "notes": "灵境制造 V4.0.0 - 首个正式版本\n\n新功能：\n- 三视图生成 3D 模型\n- 智能工艺规划\n- 本地 AI 推理\n- 数据本地存储",
  "pub_date": "2025-01-15T00:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "signature": "此处放置签名内容",
      "url": "https://releases.lingjing.com/lingjing-manufacturing_4.0.0_x64-setup.nsis.zip"
    }
  }
}
```

---

### 步骤 7：微软商店发布指南

创建 `docs/microsoft-store-guide.md`：

```markdown
# 微软商店发布指南

## 1. 注册 Microsoft 开发者账户

1. 访问 https://partner.microsoft.com/dashboard
2. 使用 Microsoft 账户登录
3. 选择"个人"或"公司"账户类型
4. 支付注册费用（个人约 $19/年，公司约 $99/年）
5. 完成身份验证

## 2. 创建应用

1. 在 Partner Center 中点击"创建新应用"
2. 选择"桌面应用"
3. 填写应用基本信息：
   - 产品名称：灵境制造
   - 产品类型：桌面应用
   - 分类：生产力工具

## 3. 准备提交材料

### 必需材料清单

- [ ] 应用图标（所有尺寸）
  - 44x44、50x50、150x150、310x150、310x310
- [ ] 应用截图（至少 1 张，最多 10 张）
  - 推荐：1280x720 或 1920x1080
- [ ] 隐私政策 URL
  - 建议使用 GitHub Pages 托管
- [ ] 应用支持联系方式
  - 邮箱：support@lingjing.com
- [ ] EULA（最终用户许可协议）URL（可选）

### 隐私政策要点

应用隐私政策必须包含以下内容：
1. 数据收集说明（明确声明不收集任何数据）
2. 数据使用说明
3. 数据存储位置（本地设备）
4. 第三方服务说明（Ollama 本地运行）
5. 联系方式

## 4. 打包和上传

### 方式一：使用 MSIX Packaging Tool（推荐）

1. 从 Microsoft Store 下载 MSIX Packaging Tool
2. 选择"桌面应用"
3. 指向安装后的应用可执行文件
4. 工具自动创建 MSIX 包
5. 上传到 Partner Center

### 方式二：手动创建 MSIX

1. 使用 `scripts/build-msix.ps1` 脚本
2. 替换 Publisher ID 为开发者账户 ID
3. 准备所有尺寸图标
4. 使用 MakeAppx.exe 打包
5. 使用 SignTool.exe 签名
6. 上传到 Partner Center

## 5. 提交审核

1. 在 Partner Center 中填写所有必填信息
2. 上传 MSIX 包
3. 设置定价（建议免费）
4. 选择分发市场（建议所有市场）
5. 提交审核

### 审核时间
- 首次提交：通常 3-7 个工作日
- 后续更新：通常 1-3 个工作日

## 6. 常见审核被拒原因和解决方案

### 被拒原因 1：应用闪退
- **原因**：WebView2 未正确打包
- **解决**：在 tauri.conf.json 中配置 WebView2 离线安装

### 被拒原因 2：缺少隐私政策
- **原因**：未提供隐私政策 URL 或内容不完整
- **解决**：准备完整的隐私政策页面

### 被拒原因 3：应用功能不完整
- **原因**：存在未实现的功能入口
- **解决**：移除未实现功能的入口或完成实现

### 被拒原因 4：安全扫描未通过
- **原因**：使用了不安全的 API 或库
- **解决**：更新依赖，移除不安全的代码

### 被拒原因 5：图标不符合规范
- **原因**：图标尺寸不正确或内容不清晰
- **解决**：按照规范准备所有尺寸的图标

## 7. WebView2 离线安装配置

创建 `src-tauri/tauri.microsoftstore.conf.json`（可选，用于微软商店版本）：

```json
{
  "bundle": {
    "targets": ["msi"],
    "windows": {
      "webviewInstallMode": {
        "type": "offlineInstaller",
        "silent": true
      },
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "timestampUrl": "http://timestamp.digicert.com",
      "wix": null
    }
  }
}
```
```

---

### 步骤 8：发布前检查清单

创建 `docs/release-checklist.md`：

```markdown
# 灵境制造 V4 - 发布前检查清单

## 功能完整性检查

- [ ] 三视图生成 3D 模型功能正常
- [ ] CadQuery 参数化生成功能正常
- [ ] 智能工艺规划功能正常
- [ ] G 代码生成和验证功能正常
- [ ] 3D 模型查看器（GLTF/GLB/STL/OBJ）正常
- [ ] Ollama 模型管理功能正常
- [ ] 设置页面所有功能正常
- [ ] 项目创建、编辑、删除功能正常
- [ ] 数据持久化正常（关闭重开后数据不丢失）
- [ ] 所有页面导航正常
- [ ] 空状态提示正确显示
- [ ] 错误处理和提示友好

## 安全性检查

- [ ] API Key 不在日志中明文打印
- [ ] 云端 API Key 仅存储在本地
- [ ] 无硬编码的密钥或密码
- [ ] CSP 策略正确配置
- [ ] Tauri 权限最小化配置
- [ ] Python 后端仅监听 localhost
- [ ] 无 SQL 注入风险
- [ ] 无 XSS 风险

## 性能检查

- [ ] 应用冷启动时间 < 5 秒
- [ ] 页面切换无明显卡顿
- [ ] 3D 模型加载流畅
- [ ] 内存占用合理（< 500MB 空闲状态）
- [ ] CPU 占用合理（空闲状态 < 5%）
- [ ] 大文件上传不阻塞 UI

## 隐私合规检查

- [ ] 无遥测代码
- [ ] 无数据上传（除用户主动配置的云端 API）
- [ ] 隐私声明完整准确
- [ ] 数据存储位置明确（%APPDATA%/lingjing）
- [ ] 卸载后数据可手动清理

## 微软商店要求检查

- [ ] 应用图标所有尺寸准备完毕
- [ ] 应用截图准备完毕（至少 3 张）
- [ ] 隐私政策 URL 可访问
- [ ] 应用支持联系方式有效
- [ ] MSIX 包签名正确
- [ ] WebView2 离线安装配置正确
- [ ] 应用安装和卸载正常
- [ ] 应用在干净 Windows 10/11 系统上可正常运行

## 打包检查

- [ ] Python sidecar 正确打包（PyInstaller）
- [ ] Rust 后端编译无错误
- [ ] 前端构建无错误
- [ ] NSIS 安装程序生成正常
- [ ] 安装后应用可正常启动
- [ ] 卸载后无残留（除用户数据）
- [ ] 自动更新功能正常

## 文档检查

- [ ] README.md 更新
- [ ] CHANGELOG.md 更新
- [ ] 用户使用文档完整
- [ ] 开发者文档完整
- [ ] 许可证文件包含
```

---

### 步骤 9：图标资源说明

在 `src-tauri/icons/` 目录下需要准备以下图标文件：

| 文件名 | 尺寸 | 用途 |
|--------|------|------|
| `32x32.png` | 32x32 px | 应用小图标 |
| `128x128.png` | 128x128 px | 应用图标 |
| `128x128@2x.png` | 256x256 px | 高 DPI 图标 |
| `icon.icns` | 多尺寸 | macOS 图标 |
| `icon.ico` | 多尺寸 | Windows 图标 |

生成图标脚本 `scripts/generate-icons.ps1`：

```powershell
# ============================================
# 灵境制造 V4 - 图标生成脚本
# 从 1024x1024 源图标生成所有尺寸
# ============================================

param(
    [Parameter(Mandatory=$true)]
    [string]$SourceIcon
)

$ErrorActionPreference = "Stop"
$iconsDir = "..\src-tauri\icons"

Write-Host "生成应用图标..." -ForegroundColor Cyan

if (-not (Test-Path $SourceIcon)) {
    Write-Host "源图标不存在: $SourceIcon" -ForegroundColor Red
    exit 1
}

# 检查 ImageMagick 是否安装
$magick = Get-Command "magick" -ErrorAction SilentlyContinue
if (-not $magick) {
    Write-Host "未找到 ImageMagick，请安装: https://imagemagick.org/" -ForegroundColor Red
    exit 1
}

$sizes = @(
    @{ Name = "32x32.png"; Size = "32x32" },
    @{ Name = "128x128.png"; Size = "128x128" },
    @{ Name = "128x128@2x.png"; Size = "256x256" },
    @{ Name = "Square44x44Logo.png"; Size = "44x44" },
    @{ Name = "Square150x150Logo.png"; Size = "150x150" },
    @{ Name = "StoreLogo.png"; Size = "50x50" },
    @{ Name = "Wide310x150Logo.png"; Size = "310x150" }
)

foreach ($item in $sizes) {
    magick convert $SourceIcon -resize $item.Size $iconsDir\$($item.Name)
    Write-Host "  生成: $($item.Name) ($($item.Size))" -ForegroundColor Green
}

# 生成 ICO 文件
magick convert $SourceIcon -define icon:auto-resize=256,128,64,48,32,16 $iconsDir\icon.ico
Write-Host "  生成: icon.ico" -ForegroundColor Green

Write-Host "`n图标生成完成!" -ForegroundColor Green
```

---

### 验证清单

完成以上所有步骤后，请执行以下验证：

1. **Vitest 配置验证**：确认 `vitest.config.ts` 包含 vue 插件、happy-dom 环境、coverage 配置、setupFiles
2. **前端测试验证**：确认 `tests/frontend/stores/` 包含 settingsStore.test.ts 和 projectStore.test.ts，`pnpm test` 可运行
3. **Python 测试验证**：确认 `tests/python/` 包含 test_health.py、test_ai_status.py、test_ollama.py、test_workflow.py，`pytest` 可运行
4. **Tauri 配置验证**：确认 `src-tauri/tauri.conf.json` 包含正确的 productName、identifier、version、bundle 配置、updater 配置
5. **PyInstaller 脚本验证**：确认 `scripts/build-sidecar.ps1` 包含完整的 5 步流程（检查环境、安装依赖、清理、打包、复制）
6. **MSIX 脚本验证**：确认 `scripts/build-msix.ps1` 包含 AppxManifest.xml 模板和注意事项
7. **自动更新验证**：确认 Cargo.toml 包含 tauri-plugin-updater 依赖，capabilities 包含 updater 权限
8. **微软商店指南验证**：确认 `docs/microsoft-store-guide.md` 包含 7 个章节（注册、创建、材料、打包、审核、被拒原因、WebView2）
9. **发布检查清单验证**：确认 `docs/release-checklist.md` 包含 6 大类检查项（功能、安全、性能、隐私、商店、打包、文档）

如果以上验证全部通过，Phase 8 完成。至此，灵境制造 V4 全部 Phase 开发完成。

---PROMPT END---

---

## Phase 9: 高级特性（论文完整实现预留）

> ⚠️ **V4.0 可跳过此 Phase**，后续迭代时实现。
> 本 Phase 为论文完整实现预留框架，包含知识图谱、HGNN、物理信息损失约束、离线 FEM 验证、数据飞轮等高级特性。

**完整实现请参见：[Phase 5 重构与 Phase 9 文档](./灵境制造V4_Phase5重构与Phase9.md)**

---

## 附录

### A. 常见问题排查

#### A.1 开发环境问题

**Q: `pnpm install` 报错 "ERESOLVE unable to resolve dependency tree"**
- 原因：Node.js 版本不兼容或依赖冲突
- 解决：确保使用 Node.js 18+，运行 `pnpm install --force` 或删除 `node_modules` 和 `lockfile` 后重试

**Q: Rust 编译报错 "linker 'link.exe' not found"**
- 原因：未安装 Visual Studio Build Tools
- 解决：安装 [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，勾选 "C++ 桌面开发" 工作负载

**Q: `cargo build` 报错 "error: could not compile `tauri`"**
- 原因：Rust 工具链版本过旧
- 解决：运行 `rustup update stable` 更新到最新稳定版

**Q: Python 虚拟环境激活失败**
- 原因：PowerShell 执行策略限制
- 解决：以管理员身份运行 `Set-ExecutionPolicy RemoteSigned`，然后重新激活虚拟环境

#### A.2 运行时问题

**Q: 启动后白屏或页面空白**
- 排查步骤：
  1. 打开开发者工具（F12）查看控制台错误
  2. 检查 Vite 开发服务器是否正常运行
  3. 检查 `tauri.conf.json` 中的 `devUrl` 配置是否正确

**Q: Python Sidecar 启动失败**
- 排查步骤：
  1. 检查 `python/` 目录下是否有正确的虚拟环境
  2. 手动运行 `python python/app/main.py` 查看错误信息
  3. 检查 `src-tauri/binaries/` 目录下是否有打包好的 Python 可执行文件
  4. 检查端口 8765 是否被占用

**Q: Ollama 连接失败**
- 排查步骤：
  1. 确认 Ollama 已安装并运行：`ollama list`
  2. 检查 Ollama API 地址（默认 `http://localhost:11434`）
  3. 在应用设置中测试 Ollama 连接
  4. 如果使用自定义端口，在设置中修改 Ollama 地址

**Q: 3D 模型无法显示**
- 排查步骤：
  1. 检查浏览器控制台是否有 WebGL 相关错误
  2. 确认显卡驱动已更新
  3. 检查 Three.js 版本兼容性
  4. 查看模型文件格式是否正确（STL/OBJ/GLTF）

#### A.3 打包问题

**Q: `tauri build` 报错 "No matching package named ..."**
- 原因：Cargo.toml 中依赖版本不存在或网络问题
- 解决：检查依赖版本，配置 Cargo 镜像源（如使用 rsproxy.cn）

**Q: 打包后应用体积过大**
- 优化方案：
  1. 使用 `cargo build --release` 的优化选项
  2. 在 `tauri.conf.json` 中启用 UPX 压缩
  3. 排除不必要的 Python 依赖
  4. 使用 `strip` 命令减小二进制体积

**Q: PyInstaller 打包后运行报错 "ModuleNotFoundError"**
- 原因：PyInstaller 未正确收集所有依赖
- 解决：在 `.spec` 文件中添加 `hiddenimports`，或使用 `--collect-all` 参数

**Q: 微软商店审核被拒**
- 常见原因和解决方案：
  1. 缺少隐私政策链接 → 在应用设置和商店提交中添加
  2. 应用闪退 → 确保所有异常都被捕获处理
  3. 功能不完整 → 确保所有按钮和功能都可用
  4. 图标不符合规范 → 使用 512x512 PNG 图标，确保无透明区域

---

### B. Trae Code 使用技巧

#### B.1 如何分步执行

1. **逐 Phase 执行**：严格按照 Phase 0 → Phase 8 的顺序执行，每个 Phase 完成并验证后再进入下一个
2. **大步骤拆分**：如果某个 Phase 的 Prompt 过长（如 Phase 0），可以按步骤拆分：
   - 先执行步骤 1-5（项目初始化和基础配置）
   - 验证通过后执行步骤 6-10（路由、状态管理、国际化）
   - 最后执行步骤 11-17（组件、页面、测试）
3. **增量执行**：如果需要修改某个步骤，只需将修改后的代码提供给 Trae Code，说明修改意图即可

#### B.2 如何处理失败

1. **读取错误信息**：仔细阅读 Trae Code 返回的错误信息，定位问题
2. **提供上下文**：将错误信息和相关代码一起粘贴给 Trae Code，请求修复
3. **回退策略**：如果修改导致更多问题，使用 Git 回退到上一个稳定状态
4. **分步验证**：不要一次性执行所有步骤，每完成一个关键步骤就验证一次
5. **检查依赖**：很多失败是因为前置步骤未正确完成，先确认依赖项

#### B.3 如何迭代修改

1. **精确描述**：明确告诉 Trae Code 要修改哪个文件的哪个部分，以及期望的行为
2. **提供参考**：如果需要修改的代码较长，先粘贴当前代码，再描述修改需求
3. **小步快跑**：每次只做一个小修改，验证通过后再做下一个
4. **保持一致性**：修改时注意与已有代码风格和架构保持一致
5. **利用验证清单**：每个 Phase 的验证清单是检查修改是否正确的重要参考

---

### C. 后续扩展方向

#### C.1 多租户 SaaS

- **目标**：将本地应用扩展为支持多用户、多组织的 SaaS 平台
- **技术方案**：
  - 后端迁移至云服务器（AWS/阿里云），使用 Kubernetes 部署
  - 数据库从 SQLite 迁移至 PostgreSQL
  - 添加用户认证系统（OAuth 2.0 / OIDC）
  - 实现组织级权限管理（RBAC）
  - 使用对象存储（S3/OSS）管理模型文件
- **优先级**：中（取决于市场需求）

#### C.2 移动端

- **目标**：开发 iOS/Android 移动端应用，支持模型查看和简单编辑
- **技术方案**：
  - 使用 Tauri 2 的移动端支持（目前处于 Beta）
  - 或使用 React Native / Flutter 独立开发
  - 3D 渲染使用 Model View (iOS) 和 Sceneform (Android)
  - 通过 REST API 与后端通信
- **优先级**：低（桌面端稳定后再考虑）

#### C.3 插件系统

- **目标**：支持第三方开发者开发插件，扩展应用功能
- **技术方案**：
  - 定义插件 API 接口规范
  - 使用 Web Worker 隔离插件运行环境
  - 实现插件市场（Plugin Marketplace）
  - 支持 Python 和 JavaScript 两种插件类型
  - 提供插件 SDK 和开发文档
- **优先级**：中高（可显著提升生态价值）

#### C.4 协作功能

- **目标**：支持多人实时协作编辑模型和工艺方案
- **技术方案**：
  - 使用 CRDT（Conflict-free Replicated Data Type）实现实时同步
  - 集成 WebSocket 实时通信
  - 添加评论和标注系统
  - 实现版本控制和变更历史
  - 支持离线编辑和自动同步
- **优先级**：中（企业客户有强需求）
