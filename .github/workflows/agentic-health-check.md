---
name: "灵境制造 · 每日仓库健康巡检"
description: "每日自动巡检 Issue、PR、CI、文档，生成结构化巡检报告"
on:
  schedule:
    - cron: "0 0 * * 1-5"
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
  actions: read
---

# 灵境制造 · 每日仓库健康巡检

## 巡检任务

### 1. Issue 分类与审查
逐一检查最近 30 天内新建或更新的 Issue：
- 给出分类建议（bug / feature / enhancement / documentation / question）
- 标记超过 30 天未处理的 Issue
- 指出需要紧急处理的 Issue（多个评论、标签为 bug、有用户催促）
- 检查是否有重复 Issue

### 2. Pull Request 审查
逐一检查当前打开的 Pull Request：
- 等待合并时间（超过 7 天的标红）
- 是否有冲突需要解决
- CI 是否全部通过
- 是否缺少 Reviewer
- 合并后是否需要同步更新文档或 README

### 3. CI/CD 健康度
- 统计最近 7 天工作流执行情况：通过率、失败率
- 对失败的 Workflow 分析可能原因
- 是否有长期跳过的测试

### 4. 仓库活跃度
- 最近 7 天提交数量
- 活跃贡献者列表
- 分支状态（超过 30 天未合并的分支）
- Release 和 Tag 是否规范

### 5. 文档完整性
- README 与当前代码是否一致
- 是否有缺失的关键文档（API 文档、部署文档、贡献指南）
- 文档链接是否有效

## 输出格式

生成一份结构化 Markdown 报告，包含：
- 摘要（一句话概括仓库当前状态）
- 各模块详细分析（带具体数据）
- 行动建议（按优先级排序，每条建议包含责任人和预计耗时）
- 趋势对比（与上次巡检对比变化）