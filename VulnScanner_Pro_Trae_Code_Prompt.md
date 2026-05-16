# VulnScanner Pro - Trae Code 完整开发提示词

## 🎯 角色定义

你是一个专业的Python安全工具开发专家，精通异步编程、GUI开发和AI集成。你将使用Python + Flet开发一个AI辅助漏洞扫描器。

## 📋 项目目标

- **开发周期**: 4周完成
- **核心功能**: 批量Web漏洞扫描 + AI自动验证 + 一键生成SRC报告
- **技术栈**: Python 3.10+ + asyncio + Flet + aiohttp + SQLite

## 🏗️ 项目结构要求

必须严格按照以下结构创建项目：

```
vulnscanner/
├── core/                      # 核心引擎
│   ├── __init__.py
│   ├── config.py              # 配置管理（含测试）
│   ├── http_engine.py         # 异步HTTP（含测试）
│   ├── crawler.py             # 智能爬虫（含测试）
│   └── scanner.py             # 扫描调度器（含测试）
│
├── detectors/                 # 漏洞检测器
│   ├── __init__.py
│   ├── base.py                # 检测器基类
│   ├── sqli.py                # SQL注入检测（含测试）
│   ├── xss.py                 # XSS检测（含测试）
│   └── info_leak.py           # 信息泄露检测（含测试）
│
├── ai/                        # AI模块
│   ├── __init__.py
│   ├── client.py              # Claude API封装（含测试）
│   ├── validator.py           # 漏洞验证（含测试）
│   └── prompts.py             # Prompt模板
│
├── reports/                   # 报告生成
│   ├── __init__.py
│   ├── generator.py           # 报告生成器（含测试）
│   └── templates/             # 平台模板
│       ├── vulbox.md
│       ├── butian.md
│       └── huoxian.md
│
├── database/                  # 数据层
│   ├── __init__.py
│   └── db.py                  # SQLite操作（含测试）
│
├── gui/                       # GUI界面
│   ├── __init__.py
│   ├── app.py                 # 应用入口
│   ├── router.py              # 页面路由
│   ├── components/            # 可复用组件
│   │   ├── sidebar.py
│   │   ├── target_input.py
│   │   ├── scan_progress.py
│   │   └── vuln_table.py
│   └── views/                 # 页面视图
│       ├── dashboard.py       # 仪表盘
│       ├── scan_view.py       # 扫描页面
│       ├── vuln_list.py       # 漏洞列表
│       ├── vuln_detail.py     # 漏洞详情
│       ├── report_view.py     # 报告页面
│       ├── history_view.py    # 历史任务
│       ├── stats_view.py      # 收益统计
│       └── settings_view.py   # 设置页面
│
├── tests/                     # 完整测试
│   ├── conftest.py            # pytest配置
│   ├── test_core/             # 核心测试
│   ├── test_detectors/        # 检测器测试
│   ├── test_ai/               # AI模块测试
│   ├── test_gui/              # GUI测试
│   └── integration/           # 集成测试
│
├── test_data/                 # 测试数据
│   ├── sample_targets.txt
│   └── mock_responses.json
│
├── config.json                # 配置文件
├── main.py                    # 命令行入口
├── main_gui.py                # GUI入口
├── requirements.txt
└── README.md
```

## 📦 依赖要求

创建requirements.txt：

```
flet>=0.20.0
aiohttp>=3.9.0
aiofiles>=23.0.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
anthropic>=0.18.0
```

## 🔧 配置文件规范

创建config.json：

```json
{
  "app": {
    "name": "VulnScanner Pro",
    "version": "1.0.0",
    "theme": "dark"
  },
  "scan": {
    "timeout": 10,
    "max_retries": 3,
    "concurrent_requests": 10,
    "crawl_depth": 3,
    "delay_min": 0.5,
    "delay_max": 2.0
  },
  "ai": {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "api_key": "",
    "confidence_threshold": 70,
    "max_tokens": 2000
  },
  "detectors": {
    "sqli": {
      "enabled": true,
      "payloads": [
        "'",
        "' OR '1'='1",
        "'; DROP TABLE users--",
        "' AND SLEEP(5)--",
        "' AND 1=1",
        "' AND 1=2"
      ],
      "error_keywords": [
        "SQL syntax",
        "mysql_fetch",
        "ORA-",
        "Microsoft OLE DB",
        "PostgreSQL"
      ]
    },
    "xss": {
      "enabled": true,
      "payloads": [
        "<script>alert(1)</script>",
        "\"><script>alert(1)</script>",
        "'><img src=x onerror=alert(1)>",
        "javascript:alert(1)"
      ]
    },
    "info_leak": {
      "enabled": true,
      "sensitive_files": [
        ".git/",
        ".env",
        "config.php",
        "web.config",
        "backup.zip",
        ".svn/",
        "admin/",
        "phpinfo.php"
      ]
    }
  },
  "reports": {
    "default_platform": "vulbox",
    "platforms": {
      "vulbox": "reports/templates/vulbox.md",
      "butian": "reports/templates/butian.md",
      "huoxian": "reports/templates/huoxian.md"
    }
  },
  "database": {
    "path": "data/vulnscanner.db"
  }
}
```

## 📋 开发阶段规划

### Phase 1: 核心引擎（Week 1）

#### Day 1-2: 基础框架

**core/config.py** 要求：
- 支持读取config.json
- 支持热重载配置
- 提供类型安全的配置访问
- 包含完整单元测试

**core/http_engine.py** 要求：
- 基于aiohttp的异步HTTP客户端
- 支持自动重试机制（最多3次）
- 支持User-Agent轮换
- 支持请求延迟（0.5-2秒随机）
- 支持并发请求控制
- 包含完整单元测试

**测试要求**：
- 配置读取测试（正常/异常/默认值）
- HTTP请求测试（正常/超时/重试）
- 并发请求测试（10并发无错误）
- 使用httpbin.org验证

#### Day 3-4: 爬虫 + SQL注入检测

**core/crawler.py** 要求：
- 异步网页爬取
- URL提取（链接、表单）
- URL去重机制
- 可配置爬取深度
- 包含完整单元测试

**detectors/sqli.py** 要求：
- 基于BaseDetector基类
- 支持报错型SQL注入检测
- 支持布尔盲注检测
- 支持时间盲注检测
- 可配置payload列表
- 包含完整单元测试

**测试要求**：
- 爬取测试（提取所有链接和表单）
- 去重测试（1000 URL去重正确）
- SQL注入检测测试（使用DVWA靶场）
- 准备5个真实案例 + 5个误报案例

#### Day 5-7: XSS检测 + 扫描调度器

**detectors/xss.py** 要求：
- 反射型XSS检测
- 存储型XSS检测（可选）
- 可配置payload列表
- 包含完整单元测试

**core/scanner.py** 要求：
- 任务调度器
- 结果收集器
- 进度回调机制
- 内存优化（<200MB）
- 包含完整单元测试

**测试要求**：
- XSS检测测试（使用DVWA靶场）
- 完整扫描流程测试
- 性能测试
- 集成测试：扫描3个目标，发现漏洞

**Phase 1 验收标准**：
- 命令行可运行：`python test_scanner.py --target http://testphp.vulnweb.com`
- 发现SQL注入或XSS漏洞
- pytest -v 全部通过

### Phase 2: GUI界面（Week 2）

#### Day 8-9: Flet框架 + 基础界面

**gui/app.py** 要求：
- Flet应用入口
- 深色主题
- 窗口尺寸1200x800
- 包含完整单元测试

**gui/router.py** 要求：
- 页面路由管理
- 页面切换动画
- 包含完整单元测试

**gui/components/sidebar.py** 要求：
- 侧边栏导航
- 图标+文字菜单项
- 当前页面高亮

**测试要求**：
- 应用启动测试
- 页面切换测试（<100ms）
- 响应式布局测试
- 性能测试（切换流畅无卡顿）

#### Day 10-12: 扫描页面 + 漏洞列表

**gui/views/scan_view.py** 要求：
- 目标输入（单URL/文件导入）
- 配置面板（深度/模块/并发）
- 进度显示（实时更新）
- 开始/停止按钮
- 包含完整单元测试

**gui/views/vuln_list.py** 要求：
- 漏洞表格展示
- 筛选功能（严重程度/类型）
- 排序功能
- 操作按钮（查看/验证/生成报告）
- 包含完整单元测试

**gui/components/target_input.py** 要求：
- URL输入框
- 文件导入按钮
- URL验证

**gui/components/scan_progress.py** 要求：
- 进度条
- 当前状态文字
- 已扫描/发现漏洞计数

**gui/components/vuln_table.py** 要求：
- 数据表格
- 分页功能
- 行选择

**测试要求**：
- 目标输入测试
- 配置选择测试
- 扫描流程测试（开始→进度→结果）
- 漏洞列表测试（显示/筛选/排序）

#### Day 13-14: 漏洞详情 + 历史任务

**gui/views/vuln_detail.py** 要求：
- 弹窗展示漏洞详情
- 请求/响应展示
- AI验证结果展示
- 生成报告按钮

**gui/views/history_view.py** 要求：
- 历史扫描任务列表
- 任务状态显示
- 重新扫描功能

**gui/views/dashboard.py** 要求：
- 统计卡片（今日扫描/发现漏洞/待验证）
- 快速操作按钮
- 最近活动列表

**测试要求**：
- 漏洞详情弹窗测试
- 历史记录保存/读取测试
- 端到端测试：输入→扫描→查看→保存
- 长时间运行测试（连续扫描1小时）

**Phase 2 验收标准**：
- GUI可正常运行：`python main_gui.py`
- 通过GUI完成一次完整扫描
- 查看漏洞详情和历史记录

### Phase 3: AI集成（Week 3）

#### Day 15-17: AI客户端 + 漏洞验证

**ai/client.py** 要求：
- Claude API封装
- 流式响应支持
- 错误重试机制
- Token消耗统计
- 包含完整单元测试

**ai/validator.py** 要求：
- 漏洞验证逻辑
- 置信度评分（0-100）
- 批量验证支持
- 包含完整单元测试

**ai/prompts.py** 要求：
- 漏洞验证Prompt模板
- 报告生成Prompt模板
- 可配置模板

**测试要求**：
- API调用测试（使用Mock）
- 漏洞验证测试（10个案例：5真5假）
- 缓存测试（同一漏洞只调用一次）
- Token消耗统计

**验收标准**：
- 验证准确率 > 75%（真漏洞识别）
- 误报率 < 30%（假漏洞过滤）
- 平均Token消耗 < 1000/次

#### Day 18-19: 报告生成 + 模板

**reports/generator.py** 要求：
- Markdown报告生成
- 支持多平台模板
- 一键复制到剪贴板
- 包含完整单元测试

**reports/templates/*.md** 要求：
- vulbox.md: 漏洞盒子模板
- butian.md: 补天平台模板
- huoxian.md: 火线安全模板
- 包含所有必需字段

**gui/views/report_view.py** 要求：
- 报告预览
- 平台选择
- 复制到剪贴板按钮

**测试要求**：
- 各平台模板测试
- 报告内容完整性测试
- 复制功能测试
- 人工验证：报告可直接提交

#### Day 20-21: 数据库 + 收益统计

**database/db.py** 要求：
- SQLite数据库操作
- 任务表（扫描任务）
- 漏洞表（发现的漏洞）
- 收益表（漏洞奖金）
- 包含完整单元测试

**gui/views/stats_view.py** 要求：
- 收益统计图表
- 漏洞趋势图
- 平台分布图
- 月度/年度统计

**gui/views/settings_view.py** 要求：
- API密钥配置
- 扫描参数配置
- 主题切换
- 数据导出

**测试要求**：
- 数据库CRUD测试
- 状态流转测试（待验证→已提交→已确认）
- 统计计算测试
- 数据持久化测试

**Phase 3 验收标准**：
- AI验证漏洞，置信度 > 75%
- 生成报告并复制到剪贴板
- 查看收益统计图表

### Phase 4: 实战优化（Week 4）

#### Day 22-24: 实战测试 + Bug修复

任务：
1. 扫描5个公益SRC目标
2. 人工验证AI判断结果
3. 提交3个漏洞到平台
4. 记录问题和修复

#### Day 25-26: 优化完善 + 性能调优

优化任务：
1. 内存优化（大网站扫描 < 300MB）
2. 速度优化（并发调整）
3. 准确率优化（Prompt调优）
4. 用户体验优化

#### Day 27-28: 打包发布 + 文档

发布任务：
1. PyInstaller打包exe
2. 编写README和使用文档
3. 创建个人使用笔记

**Phase 4 验收标准**：
- 产生第一笔漏洞收入（任何金额）
- 可独立运行的exe文件
- 完整文档

## 🧪 测试策略

### 测试金字塔
- 单元测试（70%）
- 集成测试（20%）
- 端到端测试（10%）

### 测试要求
1. 每个模块必须有单元测试
2. 核心流程必须有集成测试
3. 每个Phase必须有验收测试
4. 实战前必须通过全部测试

### 测试命令
```bash
# 运行所有测试
pytest -v

# 运行特定模块
pytest -v tests/test_core/
pytest -v tests/test_detectors/
pytest -v tests/test_ai/

# 生成覆盖率报告
pytest --cov=vulnscanner --cov-report=html
```

## ⚠️ 开发原则

1. **测试驱动**: 先写测试，再写实现
2. **小步快跑**: 每个功能独立测试通过
3. **及时验证**: 每完成一个模块就运行测试
4. **文档同步**: 代码+测试+文档一起更新

## 🚀 立即开始

请按以下顺序开始开发：

1. 创建项目结构和配置文件
2. 实现core/config.py和core/http_engine.py
3. 编写对应的测试代码
4. 使用httpbin.org验证HTTP引擎
5. 继续Phase 1的其他模块

## ✅ 成功标准

| 时间 | 里程碑 | 验证方式 |
|------|--------|----------|
| Week 1 | 核心引擎完成 | 命令行扫描发现漏洞 |
| Week 2 | GUI可用 | 可视化操作完成扫描 |
| Week 3 | AI集成完成 | AI验证+报告生成 |
| Week 4 | 产生收入 | 提交漏洞获得奖金 |

**最终目标: 4周内拥有能赚钱的漏洞扫描工具！**
