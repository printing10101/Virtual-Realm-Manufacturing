import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 7: 用户管理（管理员视角）
 *
 * 覆盖：
 * - 列表加载
 * - 创建用户
 * - 角色变更
 * - 禁用/启用
 * - 删除用户
 * - 权限不足时被拒（403）
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

interface User {
  user_id: string
  username: string
  role: 'admin' | 'engineer' | 'operator' | 'viewer'
  enabled: boolean;
  email: string;
  created_at: number;
  last_login: number | null;
}

const INITIAL_USERS: User[] = [
  {
    user_id: 'u-001',
    username: 'admin',
    role: 'admin',
    enabled: true,
    email: 'admin@lingjing.local',
    created_at: NOW - 86400 * 30,
    last_login: NOW - 600,
  },
  {
    user_id: 'u-002',
    username: 'engineer01',
    role: 'engineer',
    enabled: true,
    email: 'engineer01@lingjing.local',
    created_at: NOW - 86400 * 10,
    last_login: NOW - 1800,
  },
  {
    user_id: 'u-003',
    username: 'operator01',
    role: 'operator',
    enabled: false,
    email: 'operator01@lingjing.local',
    created_at: NOW - 86400 * 5,
    last_login: null,
  },
]

let usersDb: User[] = [...INITIAL_USERS]

async function setupUserMocks(page: Page, opts: { isAdmin: boolean } = { isAdmin: true }) {
  await page.route('**/api/v1/users/list**', async (route) => {
    if (!opts.isAdmin) {
      await route.fulfill({
        status: 403,
        body: JSON.stringify({ code: 5001, message: '权限不足', data: null }),
      })
      return
    }
    await route.fulfill({ json: apiResp({ users: usersDb, total: usersDb.length }) })
  })

  await page.route('**/api/v1/users/create**', async (route) => {
    if (!opts.isAdmin) {
      await route.fulfill({ status: 403, body: '{}' })
      return
    }
    const body = route.request().postDataJSON() || {}
    if (usersDb.some((u) => u.username === body.username)) {
      await route.fulfill({
        status: 409,
        body: JSON.stringify({ code: 5002, message: '用户名已存在', data: null }),
      })
      return
    }
    const u: User = {
      user_id: `u-${Date.now()}`,
      username: body.username,
      role: body.role || 'viewer',
      enabled: true,
      email: body.email || '',
      created_at: NOW,
      last_login: null,
    }
    usersDb = [u, ...usersDb]
    await route.fulfill({ json: apiResp(u) })
  })

  await page.route('**/api/v1/users/role**', async (route) => {
    if (!opts.isAdmin) {
      await route.fulfill({ status: 403, body: '{}' })
      return
    }
    const body = route.request().postDataJSON() || {}
    usersDb = usersDb.map((u) => (u.user_id === body.user_id ? { ...u, role: body.role } : u))
    await route.fulfill({ json: apiResp({ updated: true }) })
  })

  await page.route('**/api/v1/users/enable**', async (route) => {
    if (!opts.isAdmin) {
      await route.fulfill({ status: 403, body: '{}' })
      return
    }
    const body = route.request().postDataJSON() || {}
    usersDb = usersDb.map((u) =>
      u.user_id === body.user_id ? { ...u, enabled: !!body.enabled } : u,
    )
    await route.fulfill({ json: apiResp({ updated: true }) })
  })

  await page.route('**/api/v1/users/delete**', async (route) => {
    if (!opts.isAdmin) {
      await route.fulfill({ status: 403, body: '{}' })
      return
    }
    const body = route.request().postDataJSON() || {}
    usersDb = usersDb.filter((u) => u.user_id !== body.user_id)
    await route.fulfill({ json: apiResp({ deleted: body.user_id }) })
  })
}

async function setupCommon(page: Page) {
  await page.route('**/api/v1/version', (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ version: '1.12.1' }) }),
  )
  await page.route('**/api/health', (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ status: 'ok' }) }),
  )
  await page.route('**/api/health/ping', (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ ping: true }) }),
  )
  await page.route('**/health', (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ status: 'healthy' }) }),
  )
}

test.describe('E2E-7: 用户管理（管理员视角）', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    usersDb = [...INITIAL_USERS]
    await setupUserMocks(page, { isAdmin: true })
  })

  test('7.1 列表返回 3 个用户', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/users/list')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.users.length).toBe(3)
  })

  test('7.2 创建用户后总数 +1', async ({ page }) => {
    const before = await (await page.request.get('http://localhost:1420/api/v1/users/list')).json()
    const beforeCount = before.data.users.length

    const r = await page.request.post('http://localhost:1420/api/v1/users/create', {
      data: { username: 'newuser01', role: 'viewer', email: 'newuser01@lingjing.local' },
    })
    expect(r.status()).toBeLessThan(500)

    const after = await (await page.request.get('http://localhost:1420/api/v1/users/list')).json()
    expect(after.data.users.length).toBe(beforeCount + 1)
  })

  test('7.3 重复用户名被 409 拒绝', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/users/create', {
      data: { username: 'admin', role: 'viewer' },
    })
    expect(r.status()).toBe(409)
  })

  test('7.4 角色变更 engineer→operator 生效', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/users/role', {
      data: { user_id: 'u-002', role: 'operator' },
    })
    expect(r.status()).toBeLessThan(500)

    const list = await (await page.request.get('http://localhost:1420/api/v1/users/list')).json()
    const u = list.data.users.find((x: User) => x.user_id === 'u-002')
    expect(u.role).toBe('operator')
  })

  test('7.5 禁用用户 enabled=false', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/users/enable', {
      data: { user_id: 'u-002', enabled: false },
    })
    expect(r.status()).toBeLessThan(500)

    const list = await (await page.request.get('http://localhost:1420/api/v1/users/list')).json()
    const u = list.data.users.find((x: User) => x.user_id === 'u-002')
    expect(u.enabled).toBe(false)
  })

  test('7.6 删除用户后从列表移除', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/users/delete', {
      data: { user_id: 'u-003' },
    })
    expect(r.status()).toBeLessThan(500)

    const list = await (await page.request.get('http://localhost:1420/api/v1/users/list')).json()
    expect(list.data.users.find((x: User) => x.user_id === 'u-003')).toBeUndefined()
  })

  test('7.7 权限不足时（操作员）所有写操作 403', async ({ page }) => {
    await page.unroute('**/api/v1/users/**')
    await setupUserMocks(page, { isAdmin: false })

    const r1 = await page.request.get('http://localhost:1420/api/v1/users/list')
    expect(r1.status()).toBe(403)

    const r2 = await page.request.post('http://localhost:1420/api/v1/users/create', {
      data: { username: 'hacker', role: 'admin' },
    })
    expect(r2.status()).toBe(403)

    const r3 = await page.request.post('http://localhost:1420/api/v1/users/delete', {
      data: { user_id: 'u-001' },
    })
    expect(r3.status()).toBe(403)
  })
})
