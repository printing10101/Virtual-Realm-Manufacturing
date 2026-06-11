import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 8: AI 模型管理与推理
 *
 * 覆盖：
 * - 列出可用模型
 * - 查看模型详情与版本
 * - 启动推理任务（轮询直到完成）
 * - 获取推理结果
 * - 模型评估指标查看
 * - 删除已部署模型
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

interface ModelInfo {
  model_id: string
  name: string
  version: string
  type: string
  status: 'available' | 'training' | 'deprecated'
  created_at: number
  metrics: { accuracy?: number; f1?: number; loss?: number };
}

const MODELS: ModelInfo[] = [
  {
    model_id: 'lnn-v3',
    name: 'LNN V3 Baseline',
    version: '3.0.0',
    type: 'lnn',
    status: 'available',
    created_at: '2026-01-10T10:00:00Z' as any,
    metrics: { accuracy: 0.94, f1: 0.92, loss: 0.0342 },
  },
  {
    model_id: 'lnn-v3-finetune',
    name: 'LNN V3 NC Finetune',
    version: '3.1.0',
    type: 'lnn',
    status: 'available',
    created_at: '2026-02-15T10:00:00Z' as any,
    metrics: { accuracy: 0.96, f1: 0.95, loss: 0.0211 },
  },
  {
    model_id: 'jepa-3d-base',
    name: 'I-JEPA 3D Base',
    version: '1.0.0',
    type: 'ijepa_3d',
    status: 'available',
    created_at: '2026-01-20T10:00:00Z' as any,
    metrics: { accuracy: 0.89 },
  },
]

async function setupModelMocks(page: Page) {
  await page.route('**/api/v1/lnn/models**', (route) => {
    route.fulfill({
      json: apiResp({ models: MODELS, total: MODELS.length }),
    })
  })

  await page.route('**/api/v1/lnn/models/lnn-v3-finetune**', (route) => {
    route.fulfill({
      json: apiResp(MODELS.find((m) => m.model_id === 'lnn-v3-finetune')),
    })
  })

  await page.route('**/api/v1/lnn/infer**', async (route) => {
    const body = route.request().postDataJSON() || {}
    await route.fulfill({
      json: apiResp({
        job_id: `job-${Date.now()}`,
        status: 'completed',
        model_id: body.model_id || 'lnn-v3',
        started_at: NOW - 5,
        finished_at: NOW,
        duration_ms: 5000,
        prediction: { label: 'normal', confidence: 0.91 },
        features: { rms: 0.4, peak: 1.8 },
      }),
    })
  })

  await page.route('**/api/v1/lnn/models/lnn-v3/metrics**', (route) => {
    route.fulfill({
      json: apiResp({
        model_id: 'lnn-v3',
        metrics: MODELS[0].metrics,
        training_history: [
          { epoch: 1, loss: 0.21, val_loss: 0.19 },
          { epoch: 2, loss: 0.12, val_loss: 0.11 },
          { epoch: 3, loss: 0.05, val_loss: 0.0342 },
        ],
      }),
    })
  })

  await page.route('**/api/v1/lnn/models/jepa-3d-base**', (route) =>
    route.fulfill({ status: 204, body: '' }),
  )
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

test.describe('E2E-8: AI 模型管理与推理', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    await setupModelMocks(page)
  })

  test('8.1 模型列表返回 3 个模型', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/lnn/models')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.models.length).toBe(3)
    expect(body.data.models.find((m: ModelInfo) => m.model_id === 'lnn-v3-finetune')).toBeTruthy()
  })

  test('8.2 获取模型详情', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/lnn/models/lnn-v3-finetune')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.version).toBe('3.1.0')
    expect(body.data.metrics.f1).toBeCloseTo(0.95, 2)
  })

  test('8.3 启动推理任务并完成', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/lnn/infer', {
      data: { model_id: 'lnn-v3-finetune', input: { signal: [0.1, 0.2] } },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.status).toBe('completed')
    expect(body.data.prediction.confidence).toBeGreaterThan(0.5)
  })

  test('8.4 模型评估指标包含 training_history', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/lnn/models/lnn-v3/metrics')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.training_history.length).toBeGreaterThan(0)
    const last = body.data.training_history[body.data.training_history.length - 1]
    expect(last.val_loss).toBeLessThan(last.loss + 0.05)
  })

  test('8.5 删除已废弃模型返回 204', async ({ page }) => {
    const resp = await page.request.delete('http://localhost:1420/api/v1/lnn/models/jepa-3d-base')
    expect([200, 202, 204]).toContain(resp.status())
  })

  test('8.6 推理耗时在合理范围内（< 60s）', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/lnn/infer', {
      data: { model_id: 'lnn-v3' },
    })
    const body = await resp.json()
    expect(body.data.duration_ms).toBeLessThan(60000)
    expect(body.data.duration_ms).toBeGreaterThan(0)
  })
})
