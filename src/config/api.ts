/**
 * API 路径配置
 * 统一管理所有 API 基础路径，避免硬编码
 */

export const API_CONFIG = {
  /** 版本 1 基础路径 */
  V1: '/api/v1',
  
  /** 成本预算模块 */
  COST_BUDGET: '/api/v1/cost-budget',
  
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
  
  /** 工艺规划模块 */
  PROCESS_PLANNING: '/api/v1/process-planning',
  
  /** 仿真模块 */
  SIMULATION: '/api/v1/simulation',
  
  /** 系统配置 */
  SYSTEM: '/api/v1/system',
  
  /** 用户认证 */
  AUTH: '/api/v1/auth',
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
