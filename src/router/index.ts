import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '首页' }
      },
      {
        path: 'workspace',
        name: 'Workspace',
        component: () => import('@/views/Workspace.vue'),
        meta: { title: '工作台' }
      },
      {
        path: 'multi-view-to-3d',
        name: 'MultiViewTo3D',
        component: () => import('@/views/MultiViewTo3D.vue'),
        meta: { title: '三视图生成' }
      },
      {
        path: 'process-plan',
        name: 'ProcessPlan',
        component: () => import('@/views/ProcessPlan.vue'),
        meta: { title: '工艺规划' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '设置' }
      },
      {
        path: 'about',
        name: 'About',
        component: () => import('@/views/About.vue'),
        meta: { title: '关于' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
