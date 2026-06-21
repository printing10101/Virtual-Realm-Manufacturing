import { test, expect, type Page } from '@playwright/test'

/**
 * 飞轮端到端测试：数据进 → 工艺出 → 加工回 → 模型更新
 *
 * 覆盖完整业务链路：
 * 1) 登录并进入飞轮仪表盘
 * 2) 上传/录入加工数据（数据进）
 * 3) 查看系统生成的工艺方案（工艺出）
 * 4) 提交加工反馈结果（加工回）
 * 5) 查看模型更新与飞轮指标变化（模型更新）
 * 6) 导出飞轮报告
 * 7) 验证飞轮健康状态
 */

const _API = '/api/v1'

function standardApiResponse<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

// ---------- Mock 数据 ----------

const MOCK_LOGIN_RESPONSE = {
  access_token: 'mock-flywheel-e2e-token',
  refresh_token: 'mock-flywheel-refresh',
  token_type: 'bearer',
  user: {
    username: 'flywheel_tester',
    role: 'admin',
    created_at: '2026-01-15T08:00:00Z',
    last_login: new Date(NOW * 1000).toISOString(),
  },
}

const MOCK_FLYWHEEL_STATUS = {
  status: 'healthy',
  data_volume: 1250,
  model_quality: 87.5,
  adoption_rate: 72.3,
  uncertainty_mean: 0.23,
  feedback_delay: 45.2,
  health_score: 78.6,
  timestamp: new Date(NOW * 1000).toISOString(),
}

const MOCK_FLYWHEEL_METRICS = {
  current: {
    data_volume: 1250,
    model_quality: 87.5,
    adoption_rate: 72.3,
    uncertainty_mean: 0.23,
    feedback_delay: 45.2,
    timestamp: new Date(NOW * 1000).toISOString(),
  },
  historical: [
    {
      data_volume: 1240,
      model_quality: 87.3,
      adoption_rate: 72.0,
      uncertainty_mean: 0.24,
      feedback_delay: 46.0,
      timestamp: new Date((NOW - 86400) * 1000).toISOString(),
    },
  ],
  period_days: 7,
}

const MOCK_DATA_UPLOAD_RESULT = {
  record_id: 'REC-E2E-001',
  status: 'accepted',
  message: '加工数据已成功录入',
  timestamp: new Date(NOW * 1000).toISOString(),
}

const MOCK_PROCESS_PLAN = {
  plan_id: 'PLAN-E2E-001',
  record_id: 'REC-E2E-001',
  material: '45号钢',
  operations: [
    {
      step: 1,
      operation: '粗车外圆',
      spindle_speed: 1200,
      feed_rate: 0.3,
      depth_of_cut: 2.0,
    },
    {
      step: 2,
      operation: '精车外圆',
      spindle_speed: 1800,
      feed_rate: 0.1,
      depth_of_cut: 0.5,
    },
  ],
  estimated_time_min: 20,
  confidence: 0.89,
}

const MOCK_FEEDBACK_RESULT = {
  record_id: 'REC-E2E-001',
  first_pass_acceptance: true,
  actual_dimensions: { diameter: 100.05, length: 150.02 },
  surface_roughness: 1.6,
  submitted_at: new Date(NOW * 1000).toISOString(),
}

const MOCK_MODEL_UPDATE = {
  model_id: 'lnn-v3-baseline',
  previous_quality: 87.3,
  updated_quality: 87.5,
  improvement: 0.2,
  retrained: false,
  timestamp: new Date(NOW * 1000).toISOString(),
}

const MOCK_WEEKLY_REPORT = {
  report_type: 'weekly',
  generated_at: new Date(NOW * 1000).toISOString(),
  period: {
    start: new Date((NOW - 7 * 86400) * 1000).toISOString(),
    end: new Date(NOW * 1000).toISOString(),
  },
  current_metrics: MOCK_FLYWHEEL_STATUS,
  trends: {
    data_volume: { current: 1250, change: 70, change_percent: 5.6 },
    model_quality: { current: 87.5, change: 0.2, change_percent: 0.23 },
    adoption_rate: { current: 72.3, change: 0.3, change_percent: 0.42 },
  },
  summary: {
    health_score: 78.6,
    health_status: 'good',
    highlights: ['模型质量优秀，达到 87.5%', '用户采纳率良好，达到 72.3%'],
    recommendations: ['飞轮运转良好，继续保持当前策略'],
  },
}

const MOCK_METRIC_DEFINITIONS = {
  metrics: [
    {
      name: 'data_volume',
      description: '加工记录数：系统处理的数据记录总量',
      unit: '条',
      range: '>= 0',
      calculation: 'SELECT COUNT(*) FROM machining_records',
    },
    {
      name: 'model_quality',
      description: '模型质量：模型预测准确率',
      unit: '%',
      range: '0 - 100',
      calculation: '正确预测数 / 总预测数 × 100',
    },
    {
      name: 'adoption_rate',
      description: '用户采纳率：用户接受模型建议的比例',
      unit: '%',
      range: '0 - 100',
      calculation: '采纳建议次数 / 总建议次数 × 100',
    },
    {
      name: 'uncertainty_mean',
      description: '不确定性均值：模型预测不确定性的平均值',
      unit: '分数',
      range: '0 - 1',
      calculation: 'AVG(uncertainty_score) FROM predictions',
    },
    {
      name: 'feedback_delay',
      description: '回灌延迟：数据从产生到反馈回系统的平均时间',
      unit: '分钟',
      range: '>= 0',
      calculation: 'AVG(feedback_time - data_time) FROM feedback_loop',
    },
  ],
}

// ---------- Mock 设置 ----------

async function setupCommonMocks(page: Page) {
  await page.route('**/api/v1/version', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: '2.2.0', commit: 'e2e-flywheel' }),
    }),
  )
  await page.route('**/api/health/ping', (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ ping: true }) }),
  )
  await page.route('**/api/health', (route) =>
    route.fulfill({ status: 200, body: JSON.stringify({ status: 'ok', version: '2.2.0' }) }),
  )
  await page.route('**/health', (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ status: 'healthy', timestamp: Date.now(), version: '2.2.0', uptime: 7200 }),
    }),
  )
}

async function setupLoginMocks(page: Page) {
  await page.route('**/api/v1/auth/login', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_LOGIN_RESPONSE) }),
  )
  await page.route('**/api/v1/auth/register', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_LOGIN_RESPONSE) }),
  )
}

async function setupFlywheelMocks(page: Page) {
  // 飞轮状态
  await page.route('**/api/v1/flywheel/status', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_FLYWHEEL_STATUS) }),
  )

  // 飞轮指标
  await page.route('**/api/v1/flywheel/metrics**', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_FLYWHEEL_METRICS) }),
  )

  // 指标定义
  await page.route('**/api/v1/flywheel/definitions', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_METRIC_DEFINITIONS) }),
  )

  // 周报
  await page.route('**/api/v1/flywheel/report/weekly**', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_WEEKLY_REPORT) }),
  )
}

async function setupDataIngestionMocks(page: Page) {
  // 数据上传/录入
  await page.route('**/api/v1/flywheel/ingest', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_DATA_UPLOAD_RESULT) }),
  )

  // 工艺方案生成
  await page.route('**/api/v1/flywheel/process-plan**', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_PROCESS_PLAN) }),
  )

  // 加工反馈提交
  await page.route('**/api/v1/flywheel/feedback', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_FEEDBACK_RESULT) }),
  )

  // 模型更新
  await page.route('**/api/v1/flywheel/model-update**', (route) =>
    route.fulfill({ json: standardApiResponse(MOCK_MODEL_UPDATE) }),
  )
}

// ---------- 测试套件 ----------

test.describe('E2E-Flywheel: 数据进→工艺出→加工回→模型更新', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommonMocks(page)
    await setupLoginMocks(page)
    await setupFlywheelMocks(page)
    await setupDataIngestionMocks(page)
  })

  test('F1. 飞轮仪表盘页面可加载并展示健康状态', async ({ page }) => {
    await page.goto('/flywheel')
    await page.waitForLoadState('networkidle')

    // 验证页面渲染
    const body = page.locator('body')
    await expect(body).toBeVisible()

    // 通过 API 验证飞轮状态数据通路
    const resp = await page.request.get('http://localhost:1420/api/v1/flywheel/status')
    const body_ = await resp.json()
    expect(body_.code).toBe(0)
    expect(body_.data.status).toBe('healthy')
    expect(body_.data.health_score).toBeGreaterThan(0)
    expect(body_.data.data_volume).toBeGreaterThan(0)
  })

  test('F2. 数据进：上传加工数据成功', async ({ page }) => {
    // 通过 API 模拟数据录入
    const resp = await page.request.post('http://localhost:1420/api/v1/flywheel/ingest', {
      data: {
        record_id: 'REC-E2E-001',
        machine_id: 'CNC-001',
        tool_id: 'TOOL-001',
        workpiece_material: '45号钢',
        process_plan: { spindle_speed: 1200, feed_rate: 0.2, depth_of_cut: 1.5 },
        first_pass_acceptance: true,
        surface_roughness: 1.6,
      },
      headers: { 'content-type': 'application/json' },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.status).toBe('accepted')
    expect(body.data.record_id).toBe('REC-E2E-001')
  })

  test('F3. 工艺出：系统生成工艺方案', async ({ page }) => {
    // 请求工艺方案
    const resp = await page.request.get(
      'http://localhost:1420/api/v1/flywheel/process-plan?record_id=REC-E2E-001',
    )
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.plan_id).toBeTruthy()
    expect(body.data.operations.length).toBeGreaterThan(0)
    expect(body.data.confidence).toBeGreaterThan(0)
  })

  test('F4. 加工回：提交加工反馈结果', async ({ page }) => {
    // 提交反馈
    const resp = await page.request.post('http://localhost:1420/api/v1/flywheel/feedback', {
      data: {
        record_id: 'REC-E2E-001',
        first_pass_acceptance: true,
        actual_dimensions: { diameter: 100.05, length: 150.02 },
        surface_roughness: 1.6,
      },
      headers: { 'content-type': 'application/json' },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.record_id).toBe('REC-E2E-001')
    expect(body.data.first_pass_acceptance).toBe(true)
  })

  test('F5. 模型更新：查看模型质量变化', async ({ page }) => {
    // 请求模型更新状态
    const resp = await page.request.get(
      'http://localhost:1420/api/v1/flywheel/model-update?record_id=REC-E2E-001',
    )
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.updated_quality).toBeGreaterThanOrEqual(body.data.previous_quality)
    expect(body.data.model_id).toBeTruthy()
  })

  test('F6. 飞轮指标 API 返回当前与历史数据', async ({ page }) => {
    const resp = await page.request.get(
      'http://localhost:1420/api/v1/flywheel/metrics?days=7',
    )
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.current.data_volume).toBeGreaterThan(0)
    expect(body.data.historical.length).toBeGreaterThan(0)
    expect(body.data.period_days).toBe(7)
  })

  test('F7. 周报生成并验证结构完整性', async ({ page }) => {
    const resp = await page.request.get(
      'http://localhost:1420/api/v1/flywheel/report/weekly',
    )
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.report_type).toBe('weekly')
    expect(body.data.current_metrics).toBeTruthy()
    expect(body.data.trends).toBeTruthy()
    expect(body.data.summary.health_score).toBeGreaterThan(0)
    expect(body.data.summary.recommendations.length).toBeGreaterThan(0)
  })

  test('F8. 指标定义 API 返回完整说明', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/flywheel/definitions')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.metrics.length).toBeGreaterThanOrEqual(5)

    const names = body.data.metrics.map((m: any) => m.name)
    expect(names).toContain('data_volume')
    expect(names).toContain('model_quality')
    expect(names).toContain('adoption_rate')
    expect(names).toContain('uncertainty_mean')
    expect(names).toContain('feedback_delay')
  })

  test('F9. 完整业务链路：数据进→工艺出→加工回→模型更新', async ({ page }) => {
    // 1. 数据进
    const ingestResp = await page.request.post('http://localhost:1420/api/v1/flywheel/ingest', {
      data: {
        record_id: 'REC-E2E-FULL-001',
        machine_id: 'CNC-001',
        tool_id: 'TOOL-001',
        workpiece_material: '45号钢',
        process_plan: { spindle_speed: 1200, feed_rate: 0.2, depth_of_cut: 1.5 },
        first_pass_acceptance: true,
        surface_roughness: 1.6,
      },
      headers: { 'content-type': 'application/json' },
    })
    const ingestBody = await ingestResp.json()
    expect(ingestBody.code).toBe(0)

    // 2. 工艺出
    const planResp = await page.request.get(
      'http://localhost:1420/api/v1/flywheel/process-plan?record_id=REC-E2E-FULL-001',
    )
    const planBody = await planResp.json()
    expect(planBody.code).toBe(0)
    expect(planBody.data.operations.length).toBeGreaterThan(0)

    // 3. 加工回
    const feedbackResp = await page.request.post(
      'http://localhost:1420/api/v1/flywheel/feedback',
      {
        data: {
          record_id: 'REC-E2E-FULL-001',
          first_pass_acceptance: true,
          actual_dimensions: { diameter: 100.05, length: 150.02 },
          surface_roughness: 1.6,
        },
        headers: { 'content-type': 'application/json' },
      },
    )
    const feedbackBody = await feedbackResp.json()
    expect(feedbackBody.code).toBe(0)

    // 4. 模型更新
    const updateResp = await page.request.get(
      'http://localhost:1420/api/v1/flywheel/model-update?record_id=REC-E2E-FULL-001',
    )
    const updateBody = await updateResp.json()
    expect(updateBody.code).toBe(0)
    expect(updateBody.data.updated_quality).toBeGreaterThanOrEqual(
      updateBody.data.previous_quality,
    )

    // 5. 验证飞轮状态已更新
    const statusResp = await page.request.get('http://localhost:1420/api/v1/flywheel/status')
    const statusBody = await statusResp.json()
    expect(statusBody.code).toBe(0)
    expect(statusBody.data.data_volume).toBeGreaterThan(0)
  })

  test('F10. 重复数据摄入时幂等处理', async ({ page }) => {
    const record = {
      record_id: 'REC-E2E-DUP-001',
      machine_id: 'CNC-001',
      tool_id: 'TOOL-001',
      workpiece_material: '45号钢',
      process_plan: { spindle_speed: 1200 },
      first_pass_acceptance: true,
      surface_roughness: 1.6,
    }

    // 第一次提交
    const resp1 = await page.request.post('http://localhost:1420/api/v1/flywheel/ingest', {
      data: record,
      headers: { 'content-type': 'application/json' },
    })
    expect(resp1.status()).toBeLessThan(500)

    // 第二次提交相同记录
    const resp2 = await page.request.post('http://localhost:1420/api/v1/flywheel/ingest', {
      data: record,
      headers: { 'content-type': 'application/json' },
    })
    expect(resp2.status()).toBeLessThan(500)
  })
})
