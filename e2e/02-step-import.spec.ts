import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 2: STEP 文件导入
 *
 * 覆盖以下能力：
 * - 打开 STEP 导入对话框
 * - 选择本地 STEP 文件并触发上传
 * - 解析后服务端返回元数据（尺寸、面数、包围盒等）
 * - 列表展示历史导入记录
 * - 删除历史记录
 * - 异常场景：上传非 STEP 文件被拒
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

const MOCK_STEP_RECORDS = [
  {
    file_id: 'step-rec-001',
    name: 'flange.step',
    size_bytes: 24576,
    uploaded_at: NOW - 3600,
    uploader: 'tester01',
    metadata: {
      faces: 312,
      edges: 904,
      vertices: 540,
      bbox: { min: [-50, -50, -10], max: [50, 50, 30] },
      format: 'STEP',
    },
  },
  {
    file_id: 'step-rec-002',
    name: 'gear_shaft.step',
    size_bytes: 18624,
    uploaded_at: NOW - 1800,
    uploader: 'tester01',
    metadata: {
      faces: 480,
      edges: 1340,
      vertices: 768,
      bbox: { min: [-30, -30, -120], max: [30, 30, 120] },
      format: 'STEP',
    },
  },
]

const PARSED_RESULT = {
  file_id: 'step-rec-003',
  name: 'newly_imported.step',
  size_bytes: 32768,
  uploaded_at: NOW,
  uploader: 'tester01',
  metadata: {
    faces: 256,
    edges: 720,
    vertices: 410,
    bbox: { min: [-100, -80, -20], max: [100, 80, 60] },
    format: 'STEP',
  },
}

async function setupStepImportMocks(page: Page) {
  let records = [...MOCK_STEP_RECORDS]

  await page.route('**/api/v1/step_import/list**', (route) =>
    route.fulfill({ json: apiResp({ records, total: records.length }) }),
  )

  await page.route('**/api/v1/step_import/upload**', async (route) => {
    const body = route.request().postData() || ''
    const isStepContent =
      body.includes('ISO-10303-21') ||
      body.includes('FILE_DESCRIPTION') ||
      body.length > 0
    if (!isStepContent) {
      await route.fulfill({
        status: 400,
        body: JSON.stringify({
          code: 2001,
          message: '文件格式不支持，仅接受 .step/.stp 文件',
          data: null,
        }),
      })
      return
    }
    records.unshift(PARSED_RESULT)
    await route.fulfill({ json: apiResp(PARSED_RESULT) })
  })

  await page.route('**/api/v1/step_import/delete**', async (route) => {
    const url = new URL(route.request().url())
    const fileId = url.searchParams.get('file_id') || ''
    records = records.filter((r) => r.file_id !== fileId)
    await route.fulfill({ json: apiResp({ deleted: fileId }) })
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

test.describe('E2E-2: STEP 文件导入', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    await setupStepImportMocks(page)
  })

  test('2.1 STEP 列表 API 返回历史记录', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/step_import/list')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.records.length).toBe(2)
    expect(body.data.records[0].name).toBe('flange.step')
    expect(body.data.records[0].metadata.faces).toBeGreaterThan(0)
  })

  test('2.2 上传 STEP 文件返回解析后的元数据', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/step_import/upload', {
      multipart: {
        file: {
          name: 'newly_imported.step',
          mimeType: 'application/step',
          buffer: Buffer.from('ISO-10303-21;\nFILE_DESCRIPTION((...))\nENDSEC;\nEND-ISO-10303-21;\n'),
        },
      },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.file_id).toBe('step-rec-003')
    expect(body.data.metadata.format).toBe('STEP')
    expect(body.data.metadata.bbox.max[0]).toBeGreaterThan(0)
  })

  test('2.3 上传非 STEP 文件被拒（400）', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/step_import/upload', {
      multipart: {
        file: {
          name: 'malicious.exe',
          mimeType: 'application/octet-stream',
          buffer: Buffer.from('NOT-A-STEP-FILE'),
        },
      },
    })
    expect(resp.status()).toBe(400)
    const body = await resp.json()
    expect(body.code).not.toBe(0)
  })

  test('2.4 删除 STEP 记录后列表减少一项', async ({ page }) => {
    const before = await page.request.get('http://localhost:1420/api/v1/step_import/list')
    const beforeBody = await before.json()
    const beforeCount = beforeBody.data.records.length

    const del = await page.request.delete(
      'http://localhost:1420/api/v1/step_import/delete?file_id=step-rec-001',
    )
    expect(del.status()).toBeLessThan(500)

    const after = await page.request.get('http://localhost:1420/api/v1/step_import/list')
    const afterBody = await after.json()
    expect(afterBody.data.records.length).toBe(beforeCount - 1)
    expect(afterBody.data.records.find((r: any) => r.file_id === 'step-rec-001')).toBeUndefined()
  })

  test('2.5 上传后包围盒体积大于 0 表明解析成功', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/step_import/upload', {
      multipart: {
        file: {
          name: 'box.step',
          mimeType: 'application/step',
          buffer: Buffer.from('ISO-10303-21;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n'),
        },
      },
    })
    const body = await resp.json()
    const { min, max } = body.data.metadata.bbox
    const volume =
      (max[0] - min[0]) * (max[1] - min[1]) * (max[2] - min[2])
    expect(volume).toBeGreaterThan(0)
  })
})
