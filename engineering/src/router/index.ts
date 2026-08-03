import { createRouter, createWebHashHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Home.vue'),
      meta: { public: true },
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: () => import('../views/Workspace.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/Settings.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/About.vue'),
      meta: { public: true },
    },
    {
      path: '/task-history',
      name: 'task-history',
      component: () => import('../views/TaskHistory.vue'),
    },
    {
      path: '/rule-editor',
      name: 'rule-editor',
      component: () => import('../views/RuleEditor.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/toolpath-editor',
      name: 'toolpath-editor',
      component: () => import('../components/toolpath-editor/ToolpathEditor.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/process-planning',
      name: 'process-planning',
      component: () => import('../views/ProcessPlanning.vue'),
      meta: { title: '工艺规划' },
    },
    {
      path: '/ux-demo',
      name: 'ux-demo',
      component: () => import('../views/UXDemo.vue'),
      meta: { title: 'UX功能演示' },
    },
    {
      path: '/agent-dashboard',
      name: 'agent-dashboard',
      component: () => import('../views/AgentDashboard.vue'),
      meta: { title: '代理状态监控', requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/agent-detail/:id',
      name: 'agent-detail',
      component: () => import('../views/AgentDetail.vue'),
      meta: { title: '代理详情' },
    },
    {
      path: '/branch-manager',
      name: 'branch-manager',
      component: () => import('../views/BranchManager.vue'),
      meta: { title: '分支管理', requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/template-detail/:id',
      name: 'template-detail',
      component: () => import('../views/TemplateDetail.vue'),
      meta: { title: '模板详情' },
    },
    {
      path: '/template-market',
      name: 'template-market',
      component: () => import('../views/TemplateMarket.vue'),
      meta: { title: '模板市场' },
    },
    {
      path: '/plugin-market',
      name: 'plugin-market',
      component: () => import('../views/PluginMarket.vue'),
      meta: { title: '插件市场' },
    },
    {
      path: '/plugin-manager',
      name: 'plugin-manager',
      component: () => import('../views/PluginManager.vue'),
      meta: { title: '插件管理', requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/plugin-logs',
      name: 'plugin-logs',
      component: () => import('../views/PluginLogs.vue'),
      meta: { title: '插件日志', requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/task-board',
      name: 'task-board',
      component: () => import('../views/TaskBoard.vue'),
      meta: { title: '任务看板' },
    },
    {
      path: '/workflow-panel',
      name: 'workflow-panel',
      component: () => import('../views/WorkflowPanel.vue'),
      meta: { title: '工作流编排' },
    },
    {
      path: '/snapshot-panel',
      name: 'snapshot-panel',
      component: () => import('../views/SnapshotPanel.vue'),
      meta: { title: '实验快照' },
    },
    {
      path: '/flywheel-dashboard',
      name: 'flywheel-dashboard',
      component: () => import('../components/FlywheelDashboard.vue'),
      meta: { title: '数据飞轮', requiresAuth: true },
    },
    {
      path: '/cost-dashboard',
      name: 'cost-dashboard',
      component: () => import('../views/CostDashboard.vue'),
      meta: { title: '成本仪表盘', requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/approval-dashboard',
      name: 'approval-dashboard',
      component: () => import('../views/ApprovalDashboard.vue'),
      meta: { title: '审批看板', requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/goals',
      name: 'goals',
      component: () => import('../views/Goals.vue'),
      meta: { title: '目标管理' },
    },
    {
      path: '/simulation',
      name: 'simulation',
      component: () => import('../views/Simulation.vue'),
      meta: { title: '仿真模拟' },
    },
    {
      path: '/equipment-monitor',
      name: 'equipment-monitor',
      component: () => import('../views/EquipmentMonitor.vue'),
      meta: { title: '设备监控' },
    },
    {
      path: '/quality-inspection',
      name: 'quality-inspection',
      component: () => import('../views/QualityInspection.vue'),
      meta: { title: '质量检测' },
    },
    {
      path: '/material-management',
      name: 'material-management',
      component: () => import('../views/MaterialManagement.vue'),
      meta: { title: '物料管理' },
    },
    {
      path: '/production-report',
      name: 'production-report',
      component: () => import('../views/ProductionReport.vue'),
      meta: { title: '生产报表' },
    },
    {
      path: '/update-center',
      name: 'update-center',
      component: () => import('../views/UpdateCenter.vue'),
      meta: { title: '更新中心' },
    },
    {
      path: '/nl-modeling',
      name: 'nl-modeling',
      component: () => import('../views/NLModeling.vue'),
      meta: { title: '自然语言建模' },
    },
    {
      path: '/process-understanding',
      name: 'process-understanding',
      component: () => import('../views/ProcessUnderstanding.vue'),
      meta: { title: '工艺理解' },
    },
    {
      path: '/world-model',
      name: 'world-model',
      component: () => import('../views/WorldModel.vue'),
      meta: { title: '世界模型', requiresAuth: true },
    },
    {
      path: '/rl-agent',
      name: 'rl-agent',
      component: () => import('../views/RLAgent.vue'),
      meta: { title: 'RL 决策', requiresAuth: true },
    },
    {
      path: '/explainability',
      name: 'explainability',
      component: () => import('../views/Explainability.vue'),
      meta: { title: '可解释性', requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

// 路由守卫：认证与权限检查（安全默认：非公开路由均要求登录）
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  // 公开路由直接放行（首页、关于页等）
  const isPublic = to.meta?.public === true
  if (isPublic) {
    next()
    return
  }

  // 所有非公开路由默认要求认证
  if (!authStore.isAuthenticated) {
    ElMessage.warning('请先登录后再访问该页面')
    next('/')
    return
  }

  // 管理员权限检查
  const requiresAdmin = to.meta?.requiresAdmin === true
  if (requiresAdmin && !authStore.isAdmin()) {
    ElMessage.warning('权限不足，无法访问该页面')
    next('/')
    return
  }

  next()
})

export default router