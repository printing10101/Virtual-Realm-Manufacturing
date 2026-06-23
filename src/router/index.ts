import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/Login.vue'),
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Home.vue'),
      meta: { requiresAuth: true },
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
      meta: { requiresAuth: true, permission: 'system:config' },
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
      meta: { requiresAuth: true },
    },
    {
      path: '/rule-editor',
      name: 'rule-editor',
      component: () => import('../views/RuleEditor.vue'),
      meta: { requiresAuth: true, permission: 'rule:edit' },
    },
    {
      path: '/toolpath-editor',
      name: 'toolpath-editor',
      component: () => import('../components/toolpath-editor/ToolpathEditor.vue'),
      meta: { requiresAuth: true, permission: 'toolpath:edit' },
    },
    {
      path: '/process-planning',
      name: 'process-planning',
      component: () => import('../views/ProcessPlanning.vue'),
      meta: {
        requiresAuth: true,
        title: '工艺规划',
        permission: 'process:plan',
      },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('../views/admin/UserManagement.vue'),
      meta: { requiresAuth: true, permission: 'user:manage' },
    },
    {
      path: '/ux-demo',
      name: 'ux-demo',
      component: () => import('../views/UXDemo.vue'),
      meta: { requiresAuth: true, title: 'UX功能演示' },
    },
    {
      path: '/agent-dashboard',
      name: 'agent-dashboard',
      component: () => import('../views/AgentDashboard.vue'),
      meta: { requiresAuth: true, title: '代理状态监控', permission: 'agent:view' },
    },
    {
      path: '/agent-detail/:id',
      name: 'agent-detail',
      component: () => import('../views/AgentDetail.vue'),
      meta: { requiresAuth: true, title: '代理详情', permission: 'agent:view' },
    },
    {
      path: '/branch-manager',
      name: 'branch-manager',
      component: () => import('../views/BranchManager.vue'),
      meta: { requiresAuth: true, title: '分支管理', permission: 'template:manage' },
    },
    {
      path: '/template-detail/:id',
      name: 'template-detail',
      component: () => import('../views/TemplateDetail.vue'),
      meta: { requiresAuth: true, title: '模板详情', permission: 'template:view' },
    },
    {
      path: '/template-market',
      name: 'template-market',
      component: () => import('../views/TemplateMarket.vue'),
      meta: { requiresAuth: true, title: '模板市场', permission: 'template:view' },
    },
    {
      path: '/plugin-market',
      name: 'plugin-market',
      component: () => import('../views/PluginMarket.vue'),
      meta: { requiresAuth: true, title: '插件市场', permission: 'plugin:view' },
    },
    {
      path: '/plugin-manager',
      name: 'plugin-manager',
      component: () => import('../views/PluginManager.vue'),
      meta: { requiresAuth: true, title: '插件管理', permission: 'plugin:manage' },
    },
    {
      path: '/plugin-logs',
      name: 'plugin-logs',
      component: () => import('../views/PluginLogs.vue'),
      meta: { requiresAuth: true, title: '插件日志', permission: 'plugin:view' },
    },
    {
      path: '/task-board',
      name: 'task-board',
      component: () => import('../views/TaskBoard.vue'),
      meta: { requiresAuth: true, title: '任务看板', permission: 'task:view' },
    },
    {
      path: '/cost-dashboard',
      name: 'cost-dashboard',
      component: () => import('../views/CostDashboard.vue'),
      meta: { requiresAuth: true, title: '成本仪表盘', permission: 'cost:view' },
    },
    {
      path: '/approval-dashboard',
      name: 'approval-dashboard',
      component: () => import('../views/ApprovalDashboard.vue'),
      meta: { requiresAuth: true, title: '审批看板', permission: 'approval:view' },
    },
    {
      path: '/goals',
      name: 'goals',
      component: () => import('../views/Goals.vue'),
      meta: { requiresAuth: true, title: '目标管理', permission: 'goal:view' },
    },
    {
      path: '/update-center',
      name: 'update-center',
      component: () => import('../views/UpdateCenter.vue'),
      meta: { requiresAuth: true, title: '更新中心', permission: 'system:update' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  if (to.name === 'login') {
    next()
    return
  }

  if (!to.meta.requiresAuth) {
    next()
    return
  }

  let store: any = null
  try {
    const { useAuthStore } = await import('@/stores/auth')
    store = useAuthStore()
  } catch {
    next('/login')
    return
  }

  if (!store || !store.isAuthenticated) {
    next('/login')
    return
  }

  const requiredPermission = to.meta.permission as string | undefined
  if (requiredPermission) {
    try {
      const { usePermissionsStore } = await import('@/stores/permissions')
      const permStore = usePermissionsStore()

      if (!permStore.loaded) {
        await permStore.fetchPermissions()
      }

      if (!permStore.hasPermission(requiredPermission)) {
        ElMessage.warning('权限不足，无法访问该页面')
        next('/')
        return
      }
    } catch {
      ElMessage.warning('权限不足，无法访问该页面')
      next('/')
      return
    }
  }

  next()
})

export default router