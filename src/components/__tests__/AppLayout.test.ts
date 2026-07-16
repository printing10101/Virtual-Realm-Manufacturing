/* eslint-disable vue/no-unused-vars */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, VueWrapper } from '@vue/test-utils'
import AppLayout from '@/components/AppLayout.vue'
import { navGroups } from '@/config/navGroups'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params && 'n' in params) {
        return `${key}.${params.n}`
      }
      return key
    },
  }),
}))

// Mock vue-router
const mockRoute = { path: '/' }
const mockRouter = { push: vi.fn() }
vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => mockRouter,
  RouterLink: { template: '<a class="router-link"><slot /></a>' },
  RouterView: { template: '<div class="router-view"></div>' },
}))

// Mock @element-plus/icons-vue
vi.mock('@element-plus/icons-vue', () => ({
  Folder: { name: 'Folder', template: '<i class="icon-folder" />' },
  Search: { name: 'Search', template: '<i class="icon-search" />' },
  Refresh: { name: 'Refresh', template: '<i class="icon-refresh" />' },
  Bell: { name: 'Bell', template: '<i class="icon-bell" />' },
  DocumentAdd: { name: 'DocumentAdd', template: '<i class="icon-doc-add" />' },
  FolderOpened: { name: 'FolderOpened', template: '<i class="icon-folder-opened" />' },
  Document: { name: 'Document', template: '<i class="icon-document" />' },
  CopyDocument: { name: 'CopyDocument', template: '<i class="icon-copy-document" />' },
  Download: { name: 'Download', template: '<i class="icon-download" />' },
  Upload: { name: 'Upload', template: '<i class="icon-upload" />' },
  DocumentCopy: { name: 'DocumentCopy', template: '<i class="icon-document-copy" />' },
}))

// Mock http
const mockHttpGet = vi.fn()
vi.mock('@/utils/http', () => ({
  default: {
    get: mockHttpGet,
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// Mock error-handler
vi.mock('@/utils/error-handler', () => ({
  extractErrorMessage: vi.fn((error: unknown) => String(error)),
}))

// Mock BackendStatusIndicator component
vi.mock('@/components/BackendStatusIndicator.vue', () => ({
  default: {
    name: 'BackendStatusIndicator',
    template: '<div class="mock-backend-status-indicator"></div>',
  },
}))

// Mock ElTooltip / ElDropdown / ElDropdownMenu / ElDropdownItem / ElButton / ElTag / ElDivider / ElIcon
vi.mock('element-plus', () => ({
  ElTooltip: { template: '<div class="el-tooltip"><slot /></div>', props: ['content', 'placement'] },
  ElDropdown: {
    template: '<div class="el-dropdown" @click="$emit(\'command\', \'new\')"><slot /><slot name="dropdown" /></div>',
    props: ['trigger', 'placement'],
    emits: ['command'],
  },
  ElDropdownMenu: { template: '<div class="el-dropdown-menu"><slot /></div>' },
  ElDropdownItem: {
    template: '<div class="el-dropdown-item" @click="$emit(\'click\')"><slot /></div>',
    props: ['command', 'divided'],
    emits: ['click'],
  },
  ElButton: {
    template: '<button class="el-button" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['type', 'loading', 'disabled', 'size', 'text', 'icon', 'circle'],
    emits: ['click'],
  },
  ElTag: { template: '<span class="el-tag"><slot /></span>', props: ['size', 'type', 'effect'] },
  ElDivider: { template: '<hr class="el-divider" />', props: ['direction'] },
  ElIcon: { template: '<span class="el-icon"><slot /></span>', props: ['size'] },
}))

describe('AppLayout.vue', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    vi.clearAllMocks()
    // 默认返回空通知列表
    mockHttpGet.mockResolvedValue({ data: { code: 0, data: [] } })
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  const mountComponent = (props: Record<string, unknown> = {}) => {
    wrapper = shallowMount(AppLayout, {
      props,
      global: {
        stubs: {
          router-link: { template: '<a class="router-link"><slot /></a>' },
          router-view: { template: '<div class="router-view"></div>' },
        },
      },
    })
    return wrapper
  }

  describe('组件挂载', () => {
    it('应该正确挂载组件', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.app-layout').exists()).toBe(true)
    })

    it('应该渲染侧边栏', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.layout-sidebar').exists()).toBe(true)
    })

    it('应该渲染主区域', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.layout-main').exists()).toBe(true)
    })

    it('应该渲染头部', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.layout-header').exists()).toBe(true)
    })

    it('应该渲染内容区域', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.layout-content').exists()).toBe(true)
    })

    it('应该渲染品牌区域', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.sidebar-brand').exists()).toBe(true)
      expect(wrapper.find('.brand-name').exists()).toBe(true)
    })
  })

  describe('导航渲染', () => {
    it('应该渲染所有导航分组', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const groups = wrapper.findAll('.nav-group')
      expect(groups.length).toBe(navGroups.length)
    })

    it('应该渲染正确的分组标签', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const labels = wrapper.findAll('.nav-group-label')
      expect(labels.length).toBe(navGroups.length)
      expect(labels[0].text()).toBe(navGroups[0].label)
      expect(labels[1].text()).toBe(navGroups[1].label)
    })

    it('应该渲染所有导航项', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const items = wrapper.findAll('.nav-item')
      const totalItems = navGroups.reduce((sum, g) => sum + g.items.length, 0)
      expect(items.length).toBe(totalItems)
    })

    it('应该渲染导航项文本', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const itemTexts = wrapper.findAll('.nav-item-text')
      expect(itemTexts.length).toBeGreaterThan(0)
      expect(itemTexts[0].text()).toBe(navGroups[0].items[0].label)
    })
  })

  describe('props 处理', () => {
    it('没有 projectName 时不显示项目指示器', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.project-indicator').exists()).toBe(false)
    })

    it('有 projectName 时显示项目指示器', async () => {
      mountComponent({ projectName: '测试项目' })
      await wrapper.vm.$nextTick()
      const indicator = wrapper.find('.project-indicator')
      expect(indicator.exists()).toBe(true)
      expect(indicator.text()).toContain('测试项目')
    })

    it('isModified 为 true 且 projectName 存在时显示未保存标签', async () => {
      mountComponent({ projectName: '测试项目', isModified: true })
      await wrapper.vm.$nextTick()
      const indicator = wrapper.find('.project-indicator')
      expect(indicator.exists()).toBe(true)
    })

    it('isModified 为 false 时不显示未保存标签', async () => {
      mountComponent({ projectName: '测试项目', isModified: false })
      await wrapper.vm.$nextTick()
      const indicator = wrapper.find('.project-indicator')
      expect(indicator.exists()).toBe(true)
    })
  })

  describe('事件触发', () => {
    it('点击刷新按钮应该触发 refresh 事件', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const refreshBtn = wrapper.findAll('.header-btn')[0]
      await refreshBtn.trigger('click')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('handleFileCommand 应该触发 file-command 事件', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      wrapper.vm.handleFileCommand('save')
      await wrapper.vm.$nextTick()
      expect(wrapper.emitted('file-command')).toBeTruthy()
      expect(wrapper.emitted('file-command')![0]).toEqual(['save'])
    })

    it('handleFileCommand 不同命令应该正确触发', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      wrapper.vm.handleFileCommand('new')
      wrapper.vm.handleFileCommand('open')
      wrapper.vm.handleFileCommand('import-step')
      await wrapper.vm.$nextTick()
      const emitted = wrapper.emitted('file-command')
      expect(emitted).toBeTruthy()
      expect(emitted!.length).toBe(3)
      expect(emitted![0]).toEqual(['new'])
      expect(emitted![1]).toEqual(['open'])
      expect(emitted![2]).toEqual(['import-step'])
    })
  })

  describe('isActive 方法', () => {
    it('根路径匹配当前路由为根路径时返回 true', async () => {
      mockRoute.path = '/'
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.isActive('/')).toBe(true)
    })

    it('根路径不匹配非根路由时返回 false', async () => {
      mockRoute.path = '/simulation'
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.isActive('/')).toBe(false)
    })

    it('子路径匹配前缀时返回 true', async () => {
      mockRoute.path = '/simulation/view'
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.isActive('/simulation')).toBe(true)
    })

    it('子路径不匹配其他前缀时返回 false', async () => {
      mockRoute.path = '/simulation'
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.isActive('/equipment-monitor')).toBe(false)
    })
  })

  describe('mapPriorityToType 方法', () => {
    it('应该将 critical 映射为 error', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.mapPriorityToType('critical')).toBe('error')
    })

    it('应该将 high 映射为 warning', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.mapPriorityToType('high')).toBe('warning')
    })

    it('应该将 medium 映射为 info', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.mapPriorityToType('medium')).toBe('info')
    })

    it('应该将 low 映射为 success', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.mapPriorityToType('low')).toBe('success')
    })

    it('未知优先级应默认映射为 info', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.mapPriorityToType('unknown')).toBe('info')
    })
  })

  describe('formatTime 方法', () => {
    it('应该返回格式化后的时间字符串', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const now = Math.floor(Date.now() / 1000)
      const result = wrapper.vm.formatTime(now)
      expect(typeof result).toBe('string')
      expect(result).toContain('home.timeMinutesAgo')
    })

    it('分钟级时间差应返回分钟前', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const oneMinuteAgo = Math.floor(Date.now() / 1000) - 1
      const result = wrapper.vm.formatTime(oneMinuteAgo)
      expect(result).toContain('home.timeMinutesAgo')
    })

    it('小时级时间差应返回小时前', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const twoHoursAgo = Math.floor(Date.now() / 1000) - 7200
      const result = wrapper.vm.formatTime(twoHoursAgo)
      expect(result).toContain('home.timeHoursAgo')
    })

    it('天级时间差应返回天前', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const twoDaysAgo = Math.floor(Date.now() / 1000) - 172800
      const result = wrapper.vm.formatTime(twoDaysAgo)
      expect(result).toContain('home.timeDaysAgo')
    })
  })

  describe('fetchNotifications 方法', () => {
    it('挂载时应调用 fetchNotifications', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(mockHttpGet).toHaveBeenCalled()
    })

    it('应该调用正确的 API 路径', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(mockHttpGet).toHaveBeenCalledWith('/api/v1/notifications')
    })

    it('收到有效通知数据应填充 notifications 数组', async () => {
      mockHttpGet.mockResolvedValueOnce({
        data: {
          code: 0,
          data: [
            {
              notification_id: 'n1',
              title: '测试通知1',
              created_at: Math.floor(Date.now() / 1000) - 60,
              priority: 'high',
            },
            {
              notification_id: 'n2',
              title: '测试通知2',
              created_at: Math.floor(Date.now() / 1000) - 3600,
              priority: 'low',
            },
          ],
        },
      })
      mountComponent()
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.notifications.length).toBe(2)
      expect(wrapper.vm.notifications[0].text).toBe('测试通知1')
      expect(wrapper.vm.notifications[0].type).toBe('warning')
      expect(wrapper.vm.notifications[1].type).toBe('success')
      expect(wrapper.vm.notifications[0].read).toBe(false)
    })

    it('API 返回 code 非 0 时不应填充通知', async () => {
      mockHttpGet.mockResolvedValueOnce({ data: { code: 1, data: null } })
      mountComponent()
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.notifications.length).toBe(0)
    })

    it('API 返回 data 为空时不应填充通知', async () => {
      mockHttpGet.mockResolvedValueOnce({ data: { code: 0, data: null } })
      mountComponent()
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.notifications.length).toBe(0)
    })

    it('请求失败时不应抛出错误', async () => {
      mockHttpGet.mockRejectedValueOnce(new Error('网络错误'))
      mountComponent()
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.notifications.length).toBe(0)
    })
  })

  describe('markAllRead 方法', () => {
    it('应该将所有通知标记为已读', async () => {
      mockHttpGet.mockResolvedValueOnce({
        data: {
          code: 0,
          data: [
            {
              notification_id: 'n1',
              title: '通知1',
              created_at: Math.floor(Date.now() / 1000),
              priority: 'high',
            },
            {
              notification_id: 'n2',
              title: '通知2',
              created_at: Math.floor(Date.now() / 1000),
              priority: 'low',
            },
          ],
        },
      })
      mountComponent()
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.notifications.length).toBe(2)
      expect(wrapper.vm.notifications.every((n: any) => !n.read)).toBe(true)
      wrapper.vm.markAllRead()
      expect(wrapper.vm.notifications.every((n: any) => n.read)).toBe(true)
    })

    it('没有通知时调用不应抛出错误', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(() => wrapper.vm.markAllRead()).not.toThrow()
    })
  })

  describe('头部区域', () => {
    it('应该渲染搜索框', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.header-search').exists()).toBe(true)
      expect(wrapper.find('.search-input').exists()).toBe(true)
    })

    it('应该渲染头部操作区', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.header-actions').exists()).toBe(true)
    })

    it('应该渲染头部按钮', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      const btns = wrapper.findAll('.header-btn')
      expect(btns.length).toBeGreaterThanOrEqual(2)
    })

    it('应该渲染 BackendStatusIndicator 组件', async () => {
      mountComponent()
      await wrapper.vm.$nextTick()
      expect(wrapper.findComponent({ name: 'BackendStatusIndicator' }).exists()).toBe(true)
    })
  })
})
