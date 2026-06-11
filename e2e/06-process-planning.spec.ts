import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 6: 工艺规划（Process Planning）
 *
 * 覆盖：
 * - 启动规划任务
 * - 多阶段进度报告（孔识别 → 知识库 → 操作序列 → G-code → 验证）
 * - 完成时下载工艺报告
 * - 异常阶段失败时返回 error 信息
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

interface PlanStage {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  duration_ms?: number
  error?: string
}

interface PlanResult {
  plan_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  stages: PlanStage[]
  total_duration_ms: number
  gcode_url: string;
  report_url: string;
  metrics: {
    hole_count: number;
    feature_count: number;
    operations_count: number;
    gcode_lines: number;
  };
}

const SUCCESS_RESULT: PlanResult = {
  plan_id: 'plan-001',
  status: 'completed',
  stages: [
    { name: '输入校验', status: 'completed', duration_ms: 12 },
    { name: '孔特征识别', status: 'completed', duration_ms: 230 },
    { name: '知识库查询', status: 'completed', duration_ms: 145 },
    { name: '操作序列规划', status: 'completed', duration_ms: 380 },
    { name: 'G-code 生成', status: 'completed', duration_ms: 220 },
    { name: '结果验证', status: 'completed', duration_ms: 60 },
  ],
  total_duration_ms: 1047,
  gcode_url: '/api/v1/process_planning/plan-001/gcode',
  report_url: '/api/v1/process_planning/plan-001/report',
  metrics: {
    hole_count: 8,
    feature_count: 24,
    operations_count: 16,
    gcode_lines: 312,
  },
}

const FAILED_RESULT: PlanResult = {
  plan_id: 'plan-002',
  status: 'failed',
  stages: [
    { name: '输入校验', status: 'completed', duration_ms: 8 },
    { name: '孔特征识别', status: 'failed', duration_ms: 50, error: '几何体为空' },
  ],
  total_duration_ms: 58,
  gcode_url: '',
  report_url: '',
  metrics: { hole_count: 0, feature_count: 0, operations_count: 0, gcode_lines: 0 },
}

async function setupProcessPlanningMocks(page: Page) {
  await page.route('**/api/v1/process_planning/run**', async (route) => {
    const body = route.request().postDataJSON() || {}
    if (body.fail_at === '孔特征识别') {
      await route.fulfill({ json: apiResp(FAILED_RESULT) })
      return
    }
    await route.fulfill({ json: apiResp(SUCCESS_RESULT) })
  })

  await page.route('**/api/v1/process_planning/plan-001/gcode**', (route) => {
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/plain' },
      body: [
        '%',
        'O2001',
        'G0 Z50',
        'G1 X0 Y0 F500',
        'M30',
        '%',
      ].join('\n'),
    })
  })

  await page.route('**/api/v1/process_planning/plan-001/report**', (route) => {
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        plan_id: 'plan-001',
        summary: '工艺规划已完成',
        metrics: SUCCESS_RESULT.metrics,
        stages: SUCCESS_RESULT.stages,
      }),
    })
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

test.describe('E2E-6: 工艺规划', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    await setupProcessPlanningMocks(page)
  })

  test('6.1 启动规划任务，所有 6 个阶段 completed', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/process_planning/run', {
      data: { step_file_id: 'step-rec-001' },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.status).toBe('completed')
    expect(body.data.stages.length).toBe(6)
    for (const s of body.data.stages) {
      expect(s.status).toBe('completed')
    }
  })

  test('6.2 各阶段累加耗时 ≈ total_duration_ms', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/process_planning/run', {
      data: { step_file_id: 'step-rec-001' },
    })
    const body = await resp.json()
    const sum = body.data.stages.reduce(
      (acc: number, s: PlanStage) => acc + (s.duration_ms || 0),
      0,
    )
    expect(sum).toBe(body.data.total_duration_ms)
  })

  test('6.3 孔特征识别阶段失败时整体失败', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/process_planning/run', {
      data: { step_file_id: 'empty.step', fail_at: '孔特征识别' },
    })
    const body = await resp.json()
    expect(body.data.status).toBe('failed')
    const failedStage = body.data.stages.find((s: PlanStage) => s.status === 'failed')
    expect(failedStage?.name).toBe('孔特征识别')
    expect(failedStage?.error).toBeTruthy()
  })

  test('6.4 规划报告 metrics 字段完整', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/process_planning/run', {
      data: { step_file_id: 'step-rec-001' },
    })
    const body = await resp.json()
    const m = body.data.metrics
    expect(m.hole_count).toBeGreaterThan(0)
    expect(m.feature_count).toBeGreaterThan(0)
    expect(m.operations_count).toBeGreaterThan(0)
    expect(m.gcode_lines).toBeGreaterThan(0)
  })

  test('6.5 可下载 G-code 文件', async ({ page }) => {
    const resp = await page.request.get(
      'http://localhost:1420/api/v1/process_planning/plan-001/gcode',
    )
    const text = await resp.text()
    expect(text).toContain('O2001')
    expect(text).toContain('M30')
  })

  test('6.6 可下载 JSON 报告', async ({ page }) => {
    const resp = await page.request.get(
      'http://localhost:1420/api/v1/process_planning/plan-001/report',
    )
    const body = await resp.json()
    expect(body.plan_id).toBe('plan-001')
    expect(body.metrics.gcode_lines).toBe(312)
    expect(body.stages.length).toBe(6)
  })
})
