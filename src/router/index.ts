import { createRouter, createWebHistory } from 'vue-router'

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
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('../views/admin/UserManagement.vue'),
      meta: { requiresAuth: true, permission: 'user:manage' },
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
        next('/')
        return
      }
    } catch {
      next('/')
      return
    }
  }

  next()
})

export default router