import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 9: 设置与系统配置
 *
 * 覆盖：
 * - 加载当前设置（通用/AI/工艺/UI 四类）
 * - 持久化主题切换
 * - 修改 AI 服务地址
 * - 修改工艺参数默认值
 * - 修改界面语言
 * - 重置全部设置
 * - 校验设置校验失败
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

const INITIAL_SETTINGS = {
  general: {
    language: 'zh-CN',
    timezone: 'Asia/Shanghai',
    auto_save: true,
    auto_save_interval_sec: 60,
  },
  ai: {
    provider: 'ollama',
    ollama_base_url: 'http://localhost:11434',
    default_model: 'qwen2.5:7b',
    temperature: 0.7,
    max_tokens: 2048,
  },
  process: {
    default_machine: 'Haas-VF2',
    default_material: 'Al-6061',
    safety_factor: 1.2,
    min_tool_diameter: 1.0,
  },
  ui: {
    theme: 'light',
    density: 'default',
    show_advanced_options: false,
  },
}

let settings: any = JSON.parse(JSON.stringify(INITIAL_SETTINGS))

async function setupSettingsMocks(page: Page) {
  await page.route('**/api/v1/settings/get**', (route) => {
    route.fulfill({ json: apiResp(settings) })
  })

  await page.route('**/api/v1/settings/update**', async (route) => {
    const body = route.request().postDataJSON() || {}
    if (body.section && body.values) {
      // 简单校验
      if (body.section === 'ai' && body.values.temperature !== undefined) {
        if (body.values.temperature < 0 || body.values.temperature > 2) {
          await route.fulfill({
            status: 400,
            body: JSON.stringify({ code: 6001, message: 'temperature 必须在 [0, 2]', data: null }),
          })
          return
        }
      }
      if (body.section === 'process' && body.values.safety_factor !== undefined) {
        if (body.values.safety_factor < 1.0 || body.values.safety_factor > 3.0) {
          await route.fulfill({
            status: 400,
            body: JSON.stringify({ code: 6002, message: 'safety_factor 必须在 [1.0, 3.0]', data: null }),
          })
          return
        }
      }
      settings = { ...settings, [body.section]: { ...settings[body.section], ...body.values } }
    }
    await route.fulfill({ json: apiResp(settings) })
  })

  await page.route('**/api/v1/settings/reset**', (route) => {
    settings = JSON.parse(JSON.stringify(INITIAL_SETTINGS))
    route.fulfill({ json: apiResp(settings) })
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

test.describe('E2E-9: 设置与系统配置', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    settings = JSON.parse(JSON.stringify(INITIAL_SETTINGS))
    await setupSettingsMocks(page)
  })

  test('9.1 加载初始设置（包含 4 个分组）', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/settings/get')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.general).toBeTruthy()
    expect(body.data.ai).toBeTruthy()
    expect(body.data.process).toBeTruthy()
    expect(body.data.ui).toBeTruthy()
    expect(body.data.ai.provider).toBe('ollama')
  })

  test('9.2 切换 UI 主题为 dark 后立即持久化', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/settings/update', {
      data: { section: 'ui', values: { theme: 'dark' } },
    })
    const body = await r.json()
    expect(body.code).toBe(0)
    expect(body.data.ui.theme).toBe('dark')

    const after = await (await page.request.get('http://localhost:1420/api/v1/settings/get')).json()
    expect(after.data.ui.theme).toBe('dark')
  })

  test('9.3 修改 AI 服务地址', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/settings/update', {
      data: { section: 'ai', values: { ollama_base_url: 'http://gpu-server:11434' } },
    })
    const body = await r.json()
    expect(body.code).toBe(0)
    expect(body.data.ai.ollama_base_url).toBe('http://gpu-server:11434')
  })

  test('9.4 temperature 越界（3.0）被 400 拒绝', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/settings/update', {
      data: { section: 'ai', values: { temperature: 3.0 } },
    })
    expect(r.status()).toBe(400)
  })

  test('9.5 safety_factor 越界（0.5）被 400 拒绝', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/settings/update', {
      data: { section: 'process', values: { safety_factor: 0.5 } },
    })
    expect(r.status()).toBe(400)
  })

  test('9.6 切换语言为 en-US', async ({ page }) => {
    const r = await page.request.post('http://localhost:1420/api/v1/settings/update', {
      data: { section: 'general', values: { language: 'en-US' } },
    })
    const body = await r.json()
    expect(body.code).toBe(0)
    expect(body.data.general.language).toBe('en-US')
  })

  test('9.7 修改后 reset 恢复初始值', async ({ page }) => {
    await page.request.post('http://localhost:1420/api/v1/settings/update', {
      data: { section: 'ui', values: { theme: 'dark' } },
    })
    const r = await page.request.post('http://localhost:1420/api/v1/settings/reset')
    const body = await r.json()
    expect(body.code).toBe(0)
    expect(body.data.ui.theme).toBe('light')
    expect(body.data.ai.temperature).toBeCloseTo(0.7, 5)
  })
})
