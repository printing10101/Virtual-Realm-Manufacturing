import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import(/* webpackChunkName: "layout" */ '@/layouts/AppLayout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import(/* webpackChunkName: "home" */ '@/views/Home.vue'),
        meta: { title: '首页' }
      },
      {
        path: 'workspace',
        name: 'Workspace',
        component: () => import(/* webpackChunkName: "workspace" */ '@/views/Workspace.vue'),
        meta: { title: '工作台' }
      },
      {
        path: 'multi-view-to-3d',
        name: 'MultiViewTo3D',
        component: () => import(/* webpackChunkName: "multiview-3d" */ '@/views/MultiViewTo3D.vue'),
        meta: { title: '三视图生成' }
      },
      {
        path: 'process-plan',
        name: 'ProcessPlan',
        component: () => import(/* webpackChunkName: "process-plan" */ '@/views/ProcessPlan.vue'),
        meta: { title: '工艺规划' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import(/* webpackChunkName: "settings" */ '@/views/Settings.vue'),
        meta: { title: '设置' }
      },
      {
        path: 'about',
        name: 'About',
        component: () => import(/* webpackChunkName: "about" */ '@/views/About.vue'),
        meta: { title: '关于' }
      },
      {
        path: 'validation',
        name: 'Validation',
        component: () => import(/* webpackChunkName: "validation" */ '@/views/ValidationView.vue'),
        meta: { title: '仿真验证' }
      },
      {
        path: 'experience',
        name: 'Experience',
        component: () => import(/* webpackChunkName: "experience" */ '@/views/ExperienceView.vue'),
        meta: { title: '经验回放' }
      },
      {
        path: 'models',
        name: 'Models',
        component: () => import(/* webpackChunkName: "models" */ '@/views/ModelView.vue'),
        meta: { title: '模型管理' }
      },
      {
        path: 'comparison',
        name: 'Comparison',
        component: () => import(/* webpackChunkName: "comparison" */ '@/views/ComparisonView.vue'),
        meta: { title: '方案对比' }
      },
      {
        path: 'documents',
        name: 'Documents',
        component: () => import(/* webpackChunkName: "documents" */ '@/views/DocumentView.vue'),
        meta: { title: '文档中心' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 预加载映射表
const preloadComponents: Record<string, () => Promise<any>> = {
  Home: () => import(/* webpackChunkName: "home" */ '@/views/Home.vue'),
  Workspace: () => import(/* webpackChunkName: "workspace" */ '@/views/Workspace.vue'),
  ProcessPlan: () => import(/* webpackChunkName: "process-plan" */ '@/views/ProcessPlan.vue'),
  Validation: () => import(/* webpackChunkName: "validation" */ '@/views/ValidationView.vue'),
  MultiViewTo3D: () => import(/* webpackChunkName: "multiview-3d" */ '@/views/MultiViewTo3D.vue'),
}

// 已预加载的组件缓存
const preloadedCache = new Map<string, Promise<any>>()

// 预加载指定路由组件
export function preloadRoute(routeName: string): void {
  if (preloadedCache.has(routeName)) return
  
  const loader = preloadComponents[routeName]
  if (loader) {
    preloadedCache.set(routeName, loader())
  }
}

// 批量预加载
export function preloadRoutes(routeNames: string[]): void {
  routeNames.forEach(name => preloadRoute(name))
}

// 智能预加载策略
export function smartPreload(): void {
  if (typeof window !== 'undefined' && document.readyState === 'complete') {
    setTimeout(() => {
      preloadRoutes(['Workspace', 'ProcessPlan', 'Validation'])
    }, 2000)
  }
}

export { router, routes }
export default router
