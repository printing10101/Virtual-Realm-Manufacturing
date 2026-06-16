/**
 * 示例工程数据类型定义
 */

/** 示例工程分类 */
export type ExampleCategory = 
  | 'basic'        // 基础示例
  | 'modeling'     // 3D建模
  | 'toolpath'     // 工具路径
  | 'simulation'   // 仿真模拟
  | 'ai'           // AI功能
  | 'advanced'     // 高级应用

/** 示例工程难度级别 */
export type ExampleDifficulty = 'beginner' | 'intermediate' | 'advanced'

/** 示例工程数据结构 */
export interface ExampleProject {
  /** 唯一标识 */
  id: string
  /** 工程名称 */
  name: string
  /** 简短描述 */
  description: string
  /** 详细说明（支持 Markdown） */
  details: string
  /** 分类 */
  category: ExampleCategory
  /** 难度级别 */
  difficulty: ExampleDifficulty
  /** 标签 */
  tags: string[]
  /** 代码示例 */
  code: string
  /** 代码语言 */
  language: string
  /** 预览图片 URL */
  previewImage?: string
  /** 使用场景 */
  useCases: string[]
  /** 创建时间 */
  createdAt: string
  /** 更新时间 */
  updatedAt: string
  /** 下载次数（用于排序） */
  downloadCount: number
  /** 是否收藏 */
  isFavorite?: boolean
}

/** 示例工程过滤器 */
export interface ExampleFilter {
  /** 搜索关键词 */
  keyword?: string
  /** 分类过滤 */
  category?: ExampleCategory | 'all'
  /** 难度过滤 */
  difficulty?: ExampleDifficulty | 'all'
  /** 标签过滤 */
  tags?: string[]
  /** 排序方式 */
  sortBy?: 'name' | 'date' | 'downloads' | 'difficulty'
  /** 排序方向 */
  sortOrder?: 'asc' | 'desc'
}
