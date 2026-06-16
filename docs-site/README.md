# 灵境制造文档站

基于 VitePress 构建的专业文档站点，为灵境制造自适应工艺孪生平台提供完整的用户指南、开发者文档和 API 参考。

## 快速开始

### 安装依赖

```bash
cd docs-site
pnpm install
```

### 本地开发

```bash
pnpm dev
```

访问 http://localhost:5173 查看文档站点。

### 生产构建

```bash
pnpm build
```

构建产物将输出到 `dist/` 目录。

### 预览构建结果

```bash
pnpm preview
```

## 文档结构

```
docs-site/
├── docs/
│   ├── .vitepress/          # VitePress 配置
│   │   └── config.js        # 主题配置
│   ├── user-guide/          # 用户指南
│   ├── development/         # 开发者文档
│   ├── api/                 # API 参考
│   ├── ai/                  # AI 功能文档
│   ├── simulation/          # 仿真模块文档
│   ├── integrations/        # 系统集成文档
│   ├── wiki/                # 项目 Wiki
│   ├── changelog/           # 更新日志
│   └── index.md             # 首页
├── scripts/                 # 自动化脚本
│   └── generate-api-docs.js # API 文档生成
└── package.json
```

## 文档分类

### 用户指南
面向最终用户的操作文档，包括安装、配置、使用教程等。

### 开发者文档
面向开发人员的技
