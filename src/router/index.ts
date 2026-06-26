import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Home.vue'),
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: () => import('../views/Workspace.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/Settings.vue'),
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/About.vue'),
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
    },
    {
      path: '/toolpath-editor',
      name: 'toolpath-editor',
      component: () => import('../components/toolpath-editor/ToolpathEditor.vue'),
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
      meta: { title: '代理状态监控' },
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
      meta: { title: '分支管理' },
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
      meta: { title: '插件管理' },
    },
    {
      path: '/plugin-logs',
      name: 'plugin-logs',
      component: () => import('../views/PluginLogs.vue'),
      meta: { title: '插件日志' },
    },
    {
      path: '/task-board',
      name: 'task-board',
      component: () => import('../views/TaskBoard.vue'),
      meta: { title: '任务看板' },
    },
    {
      path: '/cost-dashboard',
      name: 'cost-dashboard',
      component: () => import('../views/CostDashboard.vue'),
      meta: { title: '成本仪表盘' },
    },
    {
      path: '/approval-dashboard',
      name: 'approval-dashboard',
      component: () => import('../views/ApprovalDashboard.vue'),
      meta: { title: '审批看板' },
    },
    {
      path: '/goals',
      name: 'goals',
      component: () => import('../views/Goals.vue'),
      meta: { title: '目标管理' },
    },
    {
      path: '/update-center',
      name: 'update-center',
      component: () => import('../views/UpdateCenter.vue'),
      meta: { title: '更新中心' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

// 路由守卫：权限检查
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // 检查是否需要特定权限（示例：管理员页面）
  const requiresAdmin = to.meta?.requiresAdmin === true
  
  if (requiresAdmin) {
    // 使用 auth store 检查实际权限
    if (!authStore.isAuthenticated || !authStore.isAdmin()) {
      ElMessage.warning('权限不足，无法访问该页面')
      next('/')
      return
    }
  }
  
  next()
})

export default router