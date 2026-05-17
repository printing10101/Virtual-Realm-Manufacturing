import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Home.vue')
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: () => import('../views/Workspace.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/Settings.vue')
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/About.vue')
    },
    {
      path: '/task-history',
      name: 'task-history',
      component: () => import('../views/TaskHistory.vue')
    },
    {
      path: '/rule-editor',
      name: 'rule-editor',
      component: () => import('../views/RuleEditor.vue')
    },
    {
      path: '/toolpath-editor',
      name: 'toolpath-editor',
      component: () => import('../components/toolpath-editor/ToolpathEditor.vue')
    }
  ]
})

export default router
