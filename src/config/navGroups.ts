/**
 * 侧边栏导航分组配置。
 *
 * 抽取自 AppLayout.vue，统一管理导航项与图标，便于：
 * - 新增/修改路由时同步更新导航；
 * - 基于角色/权限过滤导航项；
 * - 与 router meta.title 保持一致。
 */
import type { Component } from 'vue'
import {
  DataLine,
  SetUp,
  Monitor,
  View,
  MagicStick,
  Folder,
  List,
  Tickets,
  Reading,
  Setting,
  ChatDotRound,
} from '@element-plus/icons-vue'

export interface NavItem {
  path: string
  label: string
  icon: Component
  /** 可选：所需权限标识，用于基于角色的导航过滤 */
  requiredPermission?: string
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export const navGroups: NavGroup[] = [
  {
    label: '核心功能',
    items: [
      { path: '/', label: '生产总览', icon: DataLine },
      { path: '/process-planning', label: '工艺规划', icon: SetUp },
      { path: '/equipment-monitor', label: '设备监控', icon: Monitor },
      { path: '/simulation', label: '仿真模拟', icon: View },
      { path: '/quality-inspection', label: '质量检测', icon: MagicStick },
      { path: '/process-understanding', label: '工艺理解', icon: ChatDotRound },
      { path: '/agent-dashboard', label: '智能体管理', icon: Tickets },
    ],
  },
  {
    label: '资源管理',
    items: [
      { path: '/material-management', label: '物料管理', icon: Folder },
      { path: '/task-board', label: '任务看板', icon: List },
      { path: '/production-report', label: '生产报表', icon: Reading },
      { path: '/settings', label: '系统设置', icon: Setting },
    ],
  },
]
