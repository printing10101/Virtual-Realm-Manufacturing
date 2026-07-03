/**
 * API 路径配置
 * 统一管理所有 API 基础路径，避免硬编码
 */

export const API_CONFIG = {
  /** 版本 1 基础路径 */
  V1: '/api/v1',

  /** 成本预算模块 */
  COST_BUDGET: '/api/v1/cost-budget',

  /** 设备监控模块 */
  EQUIPMENT: '/api/v1/equipment',

  /** 物料管理模块 */
  MATERIALS: '/api/v1/materials',

  /** 质量检验模块 */
  QUALITY: '/api/v1/quality',

  /** 生产报表模块 */
  PRODUCTION: '/api/v1/production',

  /** 工艺路线模块 */
  PROCESS_ROUTES: '/api/v1/process-routes',

  /** 代理管理模块 */
  AGENTS: '/api/v1/agents',

  /** 模板更新模块 */
  TEMPLATES_UPDATES: '/api/v1/templates/updates',

  /** 项目管理模块 */
  PROJECTS: '/api/v1/projects',

  /** 任务管理模块 */
  TASKS: '/api/v1/tasks',

  /** 模型管理模块 */
  MODELS: '/api/v1/models',

  /** 知识库模块 */
  KNOWLEDGE: '/api/v1/knowledge',

  /** 仿真模块 */
  SIMULATION: '/api/simulation',

  /** 系统配置 */
  SYSTEM: '/api/v1/system',

  /** 用户认证 */
  AUTH: '/api/v1/auth',

  /** LNN 模型服务 */
  LNN: '/api/v1/lnn',

  /** 插件管理 */
  PLUGINS: '/api/v1/plugins',

  /** 用户主权审计日志 */
  USER_SOVEREIGNTY: '/api/v1/user-sovereignty',

  /** 治理审批 */
  GOVERNANCE: '/api/v1/governance',

  /** 任务作业流 */
  JOBS: '/api/v1/jobs',

  /** 推理服务 */
  REASONING: '/api/v1/reasoning',

  /** 健康检查 */
  HEALTH: '/api/health',

  /** 指标监控 */
  METRICS: '/api/metrics',

  /** 工艺规则管理 */
  RULES: '/api/v1/rules',

  /** STEP 文件导入 */
  IMPORT: '/api/v1/import',

  /** 目标对齐管理 */
  GOAL_ALIGNMENT: '/api/v1/goal-alignment',

  /** DXF 文件导入 */
  DXF: '/api/dxf',

  /** NL-to-CAD 自然语言建模 */
  NL2CAD: '/api/v1/nl2cad',

  /** LLM Provider 网关（多后端 LLM 管理） */
  LLM_PROVIDERS: '/api/v1/llm-providers',

  /** 工艺理解与知识问答（基于 LLM 的工艺咨询/故障诊断/方案生成） */
  PROCESS_UNDERSTANDING: '/api/process-understanding',
} as const

/**
 * 构建完整的 API 路径
 * @param base - 基础路径（从 API_CONFIG 中选择）
 * @param path - 相对路径
 * @returns 完整的 API 路径
 */
export function buildApiPath(base: string, path: string): string {
  // 移除 path 开头的斜杠
  const cleanPath = path.startsWith('/') ? path.slice(1) : path
  return `${base}/${cleanPath}`
}
