import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

// mock http 客户端，避免真实网络请求
vi.mock('@/utils/http', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

import http from '@/utils/http'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('未登录时 token 为 null', () => {
      const store = useAuthStore()
      expect(store.token).toBeNull()
    })

    it('未登录时 user 为 null', () => {
      const store = useAuthStore()
      expect(store.user).toBeNull()
    })

    it('未登录时 isAuthenticated 为 false', () => {
      const store = useAuthStore()
      expect(store.isAuthenticated).toBe(false)
    })

    it('未登录时 userRole 降级为 viewer', () => {
      const store = useAuthStore()
      expect(store.userRole).toBe('viewer')
    })

    it('未登录时 permissions 为空数组', () => {
      const store = useAuthStore()
      expect(store.permissions).toEqual([])
    })

    it('sessionStorage 存在 token 时恢复 token', () => {
      sessionStorage.setItem('auth_token', 'persisted_token')
      const store = useAuthStore()
      expect(store.token).toBe('persisted_token')
    })

    it('sessionStorage 存在合法用户时恢复用户', () => {
      const userInfo = {
        id: 'u1',
        username: 'alice',
        role: 'admin',
        permissions: ['read'],
      }
      sessionStorage.setItem('auth_user', JSON.stringify(userInfo))
      const store = useAuthStore()
      expect(store.user).toMatchObject({ username: 'alice', role: 'admin' })
      expect(store.userRole).toBe('admin')
    })

    it('sessionStorage 用户数据损坏时降级为 null 并清理', () => {
      sessionStorage.setItem('auth_user', '{invalid json}')
      const store = useAuthStore()
      expect(store.user).toBeNull()
      expect(sessionStorage.getItem('auth_user')).toBeNull()
    })

    it('sessionStorage 用户 role 非法时降级为 viewer', () => {
      const userInfo = {
        id: 'u1',
        username: 'bob',
        role: 'superadmin',
        permissions: [],
      }
      sessionStorage.setItem('auth_user', JSON.stringify(userInfo))
      const store = useAuthStore()
      expect(store.userRole).toBe('viewer')
    })
  })

  describe('computed', () => {
    it('token 存在时 isAuthenticated 为 true', () => {
      const store = useAuthStore()
      store.$patch({ token: 'abc' })
      expect(store.isAuthenticated).toBe(true)
    })

    it('user 存在时 userRole 反映用户角色', () => {
      const store = useAuthStore()
      store.$patch({
        user: { id: '1', username: 'op', role: 'operator', permissions: [] },
      })
      expect(store.userRole).toBe('operator')
    })

    it('user 存在时 permissions 反映用户权限', () => {
      const store = useAuthStore()
      store.$patch({
        user: { id: '1', username: 'op', role: 'operator', permissions: ['read', 'write'] },
      })
      expect(store.permissions).toEqual(['read', 'write'])
    })
  })

  describe('isAdmin', () => {
    it('role 为 admin 时返回 true', () => {
      const store = useAuthStore()
      store.$patch({
        user: { id: '1', username: 'admin', role: 'admin', permissions: [] },
      })
      expect(store.isAdmin()).toBe(true)
    })

    it('role 非 admin 时返回 false', () => {
      const store = useAuthStore()
      store.$patch({
        user: { id: '1', username: 'op', role: 'operator', permissions: [] },
      })
      expect(store.isAdmin()).toBe(false)
    })
  })

  describe('hasPermission', () => {
    it('拥有指定权限时返回 true', () => {
      const store = useAuthStore()
      store.$patch({
        user: { id: '1', username: 'op', role: 'operator', permissions: ['read', 'write'] },
      })
      expect(store.hasPermission('write')).toBe(true)
    })

    it('未拥有指定权限时返回 false', () => {
      const store = useAuthStore()
      store.$patch({
        user: { id: '1', username: 'op', role: 'operator', permissions: ['read'] },
      })
      expect(store.hasPermission('delete')).toBe(false)
    })

    it('未登录时返回 false', () => {
      const store = useAuthStore()
      expect(store.hasPermission('read')).toBe(false)
    })
  })

  describe('login', () => {
    it('登录成功时保存 token 和用户信息', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: {
          code: 0,
          data: {
            access_token: 'token_123',
            user: {
              username: 'alice',
              role: 'admin',
              permissions: ['read', 'write'],
            },
          },
        },
      })
      const store = useAuthStore()
      const result = await store.login('alice', 'password')
      expect(result.success).toBe(true)
      expect(store.token).toBe('token_123')
      expect(store.user).toMatchObject({ username: 'alice', role: 'admin' })
      expect(sessionStorage.getItem('auth_token')).toBe('token_123')
      expect(JSON.parse(sessionStorage.getItem('auth_user')!)).toMatchObject({
        username: 'alice',
        role: 'admin',
      })
    })

    it('后端返回非 0 code 时登录失败', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: { code: 1, message: '密码错误' },
      })
      const store = useAuthStore()
      const result = await store.login('alice', 'wrong')
      expect(result.success).toBe(false)
      expect(result.error).toBe('密码错误')
    })

    it('后端未返回 message 时使用默认错误信息', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: { code: 1 },
      })
      const store = useAuthStore()
      const result = await store.login('alice', 'wrong')
      expect(result.success).toBe(false)
      expect(result.error).toBe('登录失败')
    })

    it('网络异常时返回错误信息', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockRejectedValue({
        response: { data: { message: '服务不可用' } },
      })
      const store = useAuthStore()
      const result = await store.login('alice', 'password')
      expect(result.success).toBe(false)
      expect(result.error).toBe('服务不可用')
    })

    it('网络异常无 response.message 时降级为 error.message', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('timeout'))
      const store = useAuthStore()
      const result = await store.login('alice', 'password')
      expect(result.success).toBe(false)
      expect(result.error).toBe('timeout')
    })

    it('未知异常时返回网络错误提示', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockRejectedValue('unknown')
      const store = useAuthStore()
      const result = await store.login('alice', 'password')
      expect(result.success).toBe(false)
      expect(result.error).toBe('网络错误，登录失败')
    })

    it('后端返回非法 role 时降级为 viewer', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: {
          code: 0,
          data: {
            access_token: 'tk',
            user: { username: 'bob', role: 'hacker', permissions: [] },
          },
        },
      })
      const store = useAuthStore()
      await store.login('bob', 'pwd')
      expect(store.userRole).toBe('viewer')
    })

    it('后端未返回 user 时使用 username 参数', async () => {
      ;(http.post as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: {
          code: 0,
          data: { access_token: 'tk', user: undefined },
        },
      })
      const store = useAuthStore()
      await store.login('charlie', 'pwd')
      expect(store.user?.username).toBe('charlie')
      expect(store.user?.id).toBe('')
    })
  })

  describe('logout', () => {
    it('登出时清空 token、user 和 sessionStorage', () => {
      const store = useAuthStore()
      store.$patch({
        token: 'old',
        user: { id: '1', username: 'x', role: 'admin', permissions: [] },
      })
      sessionStorage.setItem('auth_token', 'old')
      sessionStorage.setItem('auth_user', '{}')

      store.logout()
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(sessionStorage.getItem('auth_token')).toBeNull()
      expect(sessionStorage.getItem('auth_user')).toBeNull()
    })
  })

  describe('setToken', () => {
    it('设置 token 并持久化到 sessionStorage', () => {
      const store = useAuthStore()
      store.setToken('new_token')
      expect(store.token).toBe('new_token')
      expect(sessionStorage.getItem('auth_token')).toBe('new_token')
    })
  })

  describe('setUser', () => {
    it('设置 user 并持久化到 sessionStorage', () => {
      const store = useAuthStore()
      store.setUser({ id: '9', username: 'dan', role: 'admin', permissions: ['all'] })
      expect(store.user).toMatchObject({ username: 'dan', role: 'admin' })
      expect(JSON.parse(sessionStorage.getItem('auth_user')!)).toMatchObject({
        username: 'dan',
      })
    })
  })
})
