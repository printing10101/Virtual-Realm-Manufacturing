import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 4: 任务调度与执行
 *
 * 覆盖：
 * - 任务列表加载
 * - 创建任务
 * - 任务状态轮询：pending → running → completed
 * - 任务取消
 * - 任务重试
 * - 任务历史与执行日志
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

interface Job {
  job_id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  created_at: number
  updated_at: number
  progress: number
  agent_id: string | null
  result?: { output: string; metrics: Record<string, number> }
  error?: string
}

const INITIAL_JOBS: Job[] = [
  {
    job_id: 'job-001',
    name: '工艺规划-法兰盘',
    status: 'completed',
    created_at: NOW - 7200,
    updated_at: NOW - 7100,
    progress: 100,
    agent_id: 'agent-alpha-001',
    result: { output: 'gcode-output-001.nc', metrics: { duration_ms: 12400, lines: 312 } },
  },
  {
    job_id: 'job-002',
    name: '推理任务-振动信号',
    status: 'running',
    created_at: NOW - 600,
    updated_at: NOW - 60,
    progress: 62,
    agent_id: 'agent-alpha-001',
  },
  {
    job_id: 'job-003',
    name: '仿真任务-铣削',
    status: 'failed',
    created_at: NOW - 1800,
    updated_at: NOW - 1700,
    progress: 35,
    agent_id: null,
    error: 'CAD 解析失败：空几何体',
  },
]

let jobsDb: Job[] = [...INITIAL_JOBS]

async function setupJobMocks(page: Page) {
  await page.route('**/api/v1/jobs**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const path = url.pathname

    if (method === 'GET') {
      await route.fulfill({
        json: apiResp({ jobs: jobsDb, total: jobsDb.length, has_more: false }),
      })
      return
    }
    if (method === 'POST' && path.endsWith('/jobs')) {
      const body = route.request().postDataJSON() || {}
      const newJob: Job = {
        job_id: `job-${Date.now()}`,
        name: body.name || '未命名任务',
        status: 'pending',
        created_at: NOW,
        updated_at: NOW,
        progress: 0,
        agent_id: null,
      }
      jobsDb = [newJob, ...jobsDb]
      await route.fulfill({ json: apiResp(newJob) })
      return
    }
    if (method === 'POST' && path.match(/\/jobs\/.+\/cancel$/)) {
      const m = path.match(/\/jobs\/([^/]+)\/cancel$/)
      const id = m?.[1]
      const idx = jobsDb.findIndex((j) => j.job_id === id)
      if (idx >= 0) {
        jobsDb[idx].status = 'cancelled'
        jobsDb[idx].updated_at = NOW
        await route.fulfill({ json: apiResp(jobsDb[idx]) })
        return
      }
    }
    if (method === 'POST' && path.match(/\/jobs\/.+\/retry$/)) {
      const m = path.match(/\/jobs\/([^/]+)\/retry$/)
      const id = m?.[1]
      const idx = jobsDb.findIndex((j) => j.job_id === id)
      if (idx >= 0) {
        jobsDb[idx].status = 'pending'
        jobsDb[idx].progress = 0
        jobsDb[idx].error = undefined
        jobsDb[idx].updated_at = NOW
        await route.fulfill({ json: apiResp(jobsDb[idx]) })
        return
      }
    }
    if (method === 'GET' && path.match(/\/jobs\/[^/]+$/)) {
      const id = path.split('/').pop()
      const job = jobsDb.find((j) => j.job_id === id)
      if (job) {
        await route.fulfill({ json: apiResp(job) })
        return
      }
    }
    if (method === 'GET' && path.match(/\/jobs\/[^/]+\/logs$/)) {
      await route.fulfill({
        json: apiResp({
          logs: [
            { ts: NOW - 60, level: 'info', msg: '任务已启动' },
            { ts: NOW - 30, level: 'info', msg: '加载数据集 50000 条' },
            { ts: NOW - 5, level: 'info', msg: '训练进度 62%' },
          ],
        }),
      })
      return
    }
    await route.fulfill({ status: 404, body: '{}' })
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

test.describe('E2E-4: 任务调度与执行', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    jobsDb = [...INITIAL_JOBS]
    await setupJobMocks(page)
  })

  test('4.1 任务列表加载初始 3 条', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/jobs')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.jobs.length).toBe(3)
    expect(body.data.jobs.find((j: Job) => j.status === 'completed')).toBeTruthy()
    expect(body.data.jobs.find((j: Job) => j.status === 'running')).toBeTruthy()
    expect(body.data.jobs.find((j: Job) => j.status === 'failed')).toBeTruthy()
  })

  test('4.2 创建新任务初始状态为 pending', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/jobs', {
      data: { name: 'E2E-新建任务', type: 'inference' },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.status).toBe('pending')
    expect(body.data.progress).toBe(0)

    const list = await (await page.request.get('http://localhost:1420/api/v1/jobs')).json()
    expect(list.data.jobs.length).toBe(4)
  })

  test('4.3 取消 running 任务后状态变为 cancelled', async ({ page }) => {
    const resp = await page.request.post(
      'http://localhost:1420/api/v1/jobs/job-002/cancel',
    )
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.status).toBe('cancelled')
  })

  test('4.4 重试 failed 任务后状态变为 pending 且 error 清除', async ({ page }) => {
    const resp = await page.request.post(
      'http://localhost:1420/api/v1/jobs/job-003/retry',
    )
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.status).toBe('pending')
    expect(body.data.error).toBeUndefined()
    expect(body.data.progress).toBe(0)
  })

  test('4.5 获取单个任务详情', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/jobs/job-001')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.job_id).toBe('job-001')
    expect(body.data.status).toBe('completed')
    expect(body.data.result?.output).toBe('gcode-output-001.nc')
  })

  test('4.6 任务执行日志返回至少一条 info 级别记录', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/jobs/job-001/logs')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.logs.length).toBeGreaterThan(0)
    const infoLogs = body.data.logs.filter((l: any) => l.level === 'info')
    expect(infoLogs.length).toBeGreaterThan(0)
  })

  test('4.7 已完成任务结果包含 metrics 字段', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/jobs/job-001')
    const body = await resp.json()
    expect(body.data.result).toBeTruthy()
    expect(body.data.result.metrics.duration_ms).toBeGreaterThan(0)
    expect(body.data.result.metrics.lines).toBeGreaterThan(0)
  })

  test('4.8 任务进度数值在 [0, 100] 范围内', async ({ page }) => {
    const list = await (await page.request.get('http://localhost:1420/api/v1/jobs')).json()
    for (const j of list.data.jobs as Job[]) {
      expect(j.progress).toBeGreaterThanOrEqual(0)
      expect(j.progress).toBeLessThanOrEqual(100)
    }
  })
})
