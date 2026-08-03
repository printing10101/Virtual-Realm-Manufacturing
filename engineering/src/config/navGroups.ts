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
  Share,
  Camera,
  Service,
  Cpu,
  Grid,
  Opportunity,
  Operation,
  Aim,
  Check,
  Clock,
  FolderOpened,
  Connection,
  Guide,
  Edit,
  Document,
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
      { path: '/workflow-panel', label: '工作流编排', icon: Share },
      { path: '/snapshot-panel', label: '实验快照', icon: Camera },
      { path: '/production-report', label: '生产报表', icon: Reading },
      { path: '/settings', label: '系统设置', icon: Setting },
    ],
  },
  {
    label: '智能模块',
    items: [
      { path: '/world-model', label: '世界模型', icon: Service },
      { path: '/rl-agent', label: '强化学习', icon: Cpu },
      { path: '/explainability', label: '可解释性', icon: Grid },
      { path: '/flywheel-dashboard', label: '数据飞轮', icon: Opportunity },
      { path: '/nl-modeling', label: '自然语言建模', icon: Guide },
    ],
  },
  {
    label: '数据与运营',
    items: [
      { path: '/cost-dashboard', label: '成本看板', icon: Operation },
      { path: '/goals', label: '目标对齐', icon: Aim },
      { path: '/approval-dashboard', label: '审批中心', icon: Check },
      { path: '/task-history', label: '任务历史', icon: Clock },
    ],
  },
  {
    label: '市场与工具',
    items: [
      { path: '/template-market', label: '模板市场', icon: FolderOpened },
      { path: '/plugin-market', label: '插件市场', icon: Connection },
      { path: '/rule-editor', label: '工艺规则', icon: Edit },
      { path: '/toolpath-editor', label: '刀具路径', icon: Operation },
      { path: '/plugin-manager', label: '插件管理', icon: FolderOpened },
      { path: '/plugin-logs', label: '插件日志', icon: Document },
    ],
  },
  {
    label: '系统与帮助',
    items: [
      { path: '/about', label: '关于', icon: Service },
    ],
  },
]
