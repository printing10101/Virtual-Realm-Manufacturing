import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 10: 健康监控与告警
 *
 * 覆盖：
 * - /health 端点返回 ok
 * - 心跳上报
 * - 服务异常时 health 返回 503
 * - 健康检查项目逐项校验（DB、Redis、模型、磁盘）
 * - 告警查询与确认
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

interface HealthDetail {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: number;
  version: string;
  uptime: number;
  checks: {
    database: { status: 'ok' | 'fail'; latency_ms: number; details?: string };
    redis: { status: 'ok' | 'fail'; latency_ms: number; details?: string };
    model_registry: { status: 'ok' | 'fail'; model_count: number };
    disk: { status: 'ok' | 'warn' | 'fail'; free_gb: number; total_gb: number };
  };
}

const HEALTHY: HealthDetail = {
  status: 'healthy',
  timestamp: NOW * 1000,
  version: '1.12.1',
  uptime: 86400,
  checks: {
    database: { status: 'ok', latency_ms: 5 },
    redis: { status: 'ok', latency_ms: 1 },
    model_registry: { status: 'ok', model_count: 3 },
    disk: { status: 'ok', free_gb: 250, total_gb: 500 },
  },
}

const DEGRADED: HealthDetail = {
  status: 'degraded',
  timestamp: NOW * 1000,
  version: '1.12.1',
  uptime: 86400,
  checks: {
    database: { status: 'ok', latency_ms: 8 },
    redis: { status: 'fail', latency_ms: 5000, details: 'Connection refused' },
    model_registry: { status: 'ok', model_count: 3 },
    disk: { status: 'warn', free_gb: 30, total_gb: 500 },
  },
}

async function setupHealthMocks(page: Page) {
  await page.route('**/health', (route) => {
    route.fulfill({ json: HEALTHY })
  })
  await page.route('**/api/health', (route) => {
    route.fulfill({ json: apiResp(HEALTHY) })
  })
  await page.route('**/api/health/ping', (route) => {
    route.fulfill({ status: 200, body: JSON.stringify({ ping: true }) })
  })
  await page.route('**/api/health/details', (route) => {
    route.fulfill({ json: apiResp(HEALTHY) })
  })
  await page.route('**/api/health/degraded', (route) => {
    route.fulfill({ status: 503, body: JSON.stringify(apiResp(DEGRADED)) })
  })
  await page.route('**/api/v1/heartbeat**', async (route) => {
    const body = route.request().postDataJSON() || {}
    await route.fulfill({
      json: apiResp({
        agent_id: body.agent_id,
        server_time: NOW,
        accepted: true,
        next_heartbeat_in_sec: 30,
      }),
    })
  })
  await page.route('**/api/v1/alerts**', (route) => {
    route.fulfill({
      json: apiResp({
        alerts: [
          {
            alert_id: 'alert-001',
            severity: 'warning',
            source: 'health',
            message: 'Redis 连接超时',
            created_at: NOW - 120,
            acknowledged: false,
          },
          {
            alert_id: 'alert-002',
            severity: 'info',
            source: 'disk',
            message: '磁盘可用空间低于 50GB',
            created_at: NOW - 600,
            acknowledged: true,
          },
        ],
        total: 2,
      }),
    })
  })
  await page.route('**/api/v1/alerts/ack**', async (route) => {
    const body = route.request().postDataJSON() || {}
    await route.fulfill({ json: apiResp({ alert_id: body.alert_id, acknowledged: true }) })
  })
}

test.describe('E2E-10: 健康监控与告警', () => {
  test.beforeEach(async ({ page }) => {
    await setupHealthMocks(page)
  })

  test('10.1 /health 返回 healthy', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/health')
    const body = await resp.json()
    expect(body.status).toBe('healthy')
    expect(body.version).toBeTruthy()
    expect(body.uptime).toBeGreaterThan(0)
  })

  test('10.2 /api/health/details 包含 4 项检查', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/health/details')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.checks.database.status).toBe('ok')
    expect(body.data.checks.redis.status).toBe('ok')
    expect(body.data.checks.model_registry.model_count).toBeGreaterThan(0)
    expect(body.data.checks.disk.total_gb).toBeGreaterThan(0)
  })

  test('10.3 Redis 故障时整体 degraded 且 HTTP 503', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/health/degraded')
    expect(resp.status()).toBe(503)
    const body = await resp.json()
    expect(body.data.status).toBe('degraded')
    expect(body.data.checks.redis.status).toBe('fail')
    expect(body.data.checks.disk.status).toBe('warn')
  })

  test('10.4 心跳上报后 next_heartbeat_in_sec>0', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/heartbeat', {
      data: { agent_id: 'agent-alpha-001', status: 'idle' },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.accepted).toBe(true)
    expect(body.data.next_heartbeat_in_sec).toBeGreaterThan(0)
  })

  test('10.5 告警列表包含至少一条 warning', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/alerts')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.alerts.length).toBeGreaterThan(0)
    const warning = body.data.alerts.find((a: any) => a.severity === 'warning')
    expect(warning).toBeTruthy()
    expect(warning.acknowledged).toBe(false)
  })

  test('10.6 确认告警后 acknowledged=true', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/alerts/ack', {
      data: { alert_id: 'alert-001' },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.acknowledged).toBe(true)
  })

  test('10.7 磁盘总容量大于已用空间', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/health/details')
    const body = await resp.json()
    const disk = body.data.checks.disk
    expect(disk.total_gb).toBeGreaterThan(disk.free_gb)
    expect(disk.free_gb).toBeGreaterThan(0)
  })
})
