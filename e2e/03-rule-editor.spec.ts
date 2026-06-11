import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 3: 工艺规则编辑
 *
 * 覆盖以下能力：
 * - 列表加载现有规则
 * - 创建新规则（含字段校验）
 * - 编辑规则触发更新 API
 * - 删除规则
 * - 规则冲突检测（同名/优先级冲突）
 * - 规则分组管理
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

interface Rule {
  rule_id: string
  name: string
  description: string
  priority: number
  enabled: boolean
  group: string
  conditions: Array<{ field: string; op: string; value: string }>
  actions: Array<{ type: string; params: Record<string, unknown> }>
  created_at: number
  updated_at: number
}

const INITIAL_RULES: Rule[] = [
  {
    rule_id: 'rule-001',
    name: '孔特征-标准钻削',
    description: '当检测到孔径≥6mm时使用标准钻头',
    priority: 100,
    enabled: true,
    group: '钻削',
    conditions: [{ field: 'hole_diameter', op: 'gte', value: '6' }],
    actions: [{ type: 'set_tool', params: { tool_id: 'drill-m6' } }],
    created_at: NOW - 7200,
    updated_at: NOW - 3600,
  },
  {
    rule_id: 'rule-002',
    name: '粗加工-高速铣削',
    description: '粗加工阶段使用高速铣削策略',
    priority: 80,
    enabled: true,
    group: '铣削',
    conditions: [{ field: 'stage', op: 'eq', value: 'rough' }],
    actions: [{ type: 'set_strategy', params: { strategy: 'high_speed' } }],
    created_at: NOW - 3600,
    updated_at: NOW - 1800,
  },
]

let rulesDb: Rule[] = [...INITIAL_RULES]

async function setupRuleMocks(page: Page) {
  await page.route('**/api/v1/rules/list**', (route) => {
    route.fulfill({
      json: apiResp({ rules: rulesDb, total: rulesDb.length }),
    })
  })

  await page.route('**/api/v1/rules/create**', async (route) => {
    const body = route.request().postDataJSON() || {}
    if (!body.name || typeof body.name !== 'string') {
      await route.fulfill({
        status: 400,
        body: JSON.stringify({ code: 3001, message: 'name 字段必填', data: null }),
      })
      return
    }
    if (rulesDb.some((r) => r.name === body.name)) {
      await route.fulfill({
        status: 409,
        body: JSON.stringify({
          code: 3002,
          message: `规则名称 ${body.name} 已存在`,
          data: null,
        }),
      })
      return
    }
    const newRule: Rule = {
      rule_id: `rule-${Date.now()}`,
      name: body.name,
      description: body.description || '',
      priority: body.priority ?? 50,
      enabled: body.enabled ?? true,
      group: body.group || '默认',
      conditions: body.conditions || [],
      actions: body.actions || [],
      created_at: NOW,
      updated_at: NOW,
    }
    rulesDb = [newRule, ...rulesDb]
    await route.fulfill({ json: apiResp(newRule) })
  })

  await page.route('**/api/v1/rules/update**', async (route) => {
    const body = route.request().postDataJSON() || {}
    const idx = rulesDb.findIndex((r) => r.rule_id === body.rule_id)
    if (idx < 0) {
      await route.fulfill({
        status: 404,
        body: JSON.stringify({ code: 3003, message: '规则不存在', data: null }),
      })
      return
    }
    rulesDb[idx] = { ...rulesDb[idx], ...body, updated_at: NOW }
    await route.fulfill({ json: apiResp(rulesDb[idx]) })
  })

  await page.route('**/api/v1/rules/delete**', async (route) => {
    const body = route.request().postDataJSON() || {}
    rulesDb = rulesDb.filter((r) => r.rule_id !== body.rule_id)
    await route.fulfill({ json: apiResp({ deleted: body.rule_id }) })
  })

  await page.route('**/api/v1/rules/conflicts**', async (route) => {
    const conflicts: any[] = []
    const seen = new Map<string, Rule[]>()
    for (const r of rulesDb) {
      const k = `${r.group}::${r.priority}`
      const list = seen.get(k) || []
      list.push(r)
      seen.set(k, list)
    }
    for (const [k, list] of seen) {
      if (list.length > 1) {
        conflicts.push({
          conflict_type: 'same_group_priority',
          group_priority: k,
          rule_ids: list.map((r) => r.rule_id),
        })
      }
    }
    await route.fulfill({ json: apiResp({ conflicts }) })
  })

  await page.route('**/api/v1/rules/groups**', (route) => {
    const groups = Array.from(new Set(rulesDb.map((r) => r.group)))
    route.fulfill({ json: apiResp({ groups }) })
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

test.describe('E2E-3: 工艺规则编辑', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    // 每个用例重置内存数据
    rulesDb = [...INITIAL_RULES]
    await setupRuleMocks(page)
  })

  test('3.1 规则列表 API 返回初始规则', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/rules/list')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.rules.length).toBe(2)
    expect(body.data.rules.find((r: Rule) => r.name === '孔特征-标准钻削')).toBeTruthy()
  })

  test('3.2 创建合法规则后总数 +1', async ({ page }) => {
    const before = await (await page.request.get('http://localhost:1420/api/v1/rules/list')).json()
    const beforeCount = before.data.rules.length

    const created = await page.request.post('http://localhost:1420/api/v1/rules/create', {
      data: {
        name: '精加工-镜面铣削',
        description: '精加工阶段使用镜面铣削',
        priority: 90,
        enabled: true,
        group: '铣削',
        conditions: [{ field: 'stage', op: 'eq', value: 'finish' }],
        actions: [{ type: 'set_strategy', params: { strategy: 'mirror_milling' } }],
      },
    })
    const createdBody = await created.json()
    expect(createdBody.code).toBe(0)
    expect(createdBody.data.rule_id).toBeTruthy()

    const after = await (await page.request.get('http://localhost:1420/api/v1/rules/list')).json()
    expect(after.data.rules.length).toBe(beforeCount + 1)
  })

  test('3.3 缺少 name 字段被 400 拒绝', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/rules/create', {
      data: { description: '没有 name' },
    })
    expect(resp.status()).toBe(400)
    const body = await resp.json()
    expect(body.code).not.toBe(0)
  })

  test('3.4 重名规则被 409 拒绝', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/rules/create', {
      data: { name: '孔特征-标准钻削' },
    })
    expect(resp.status()).toBe(409)
    const body = await resp.json()
    expect(body.message).toContain('已存在')
  })

  test('3.5 更新规则 priority 字段', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/rules/update', {
      data: { rule_id: 'rule-001', priority: 200 },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.priority).toBe(200)
  })

  test('3.6 删除规则后列表减少', async ({ page }) => {
    const before = await (await page.request.get('http://localhost:1420/api/v1/rules/list')).json()
    const beforeCount = before.data.rules.length

    const del = await page.request.post('http://localhost:1420/api/v1/rules/delete', {
      data: { rule_id: 'rule-002' },
    })
    expect(del.status()).toBeLessThan(500)

    const after = await (await page.request.get('http://localhost:1420/api/v1/rules/list')).json()
    expect(after.data.rules.length).toBe(beforeCount - 1)
    expect(after.data.rules.find((r: Rule) => r.rule_id === 'rule-002')).toBeUndefined()
  })

  test('3.7 同组同优先级产生冲突', async ({ page }) => {
    // 构造冲突：让 rule-002 与新建的 rule-new 同组同优先级
    await page.request.post('http://localhost:1420/api/v1/rules/create', {
      data: {
        name: '粗加工-备用策略',
        priority: 80,
        group: '铣削',
        conditions: [{ field: 'stage', op: 'eq', value: 'rough' }],
        actions: [{ type: 'set_strategy', params: { strategy: 'backup' } }],
      },
    })
    const resp = await page.request.get('http://localhost:1420/api/v1/rules/conflicts')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.conflicts.length).toBeGreaterThan(0)
    expect(body.data.conflicts[0].conflict_type).toBe('same_group_priority')
  })

  test('3.8 规则分组 API 返回唯一分组', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/rules/groups')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.groups).toContain('钻削')
    expect(body.data.groups).toContain('铣削')
  })
})
