import { test, expect, type Page } from '@playwright/test'

/**
 * 端到端场景 5: 工具路径（Toolpath）编辑与生成
 *
 * 覆盖：
 * - 加载现有 toolpath
 * - 添加 G-code 段
 * - 修改进给速度
 * - 撤销 / 重做
 * - 导出 G-code
 * - 解析 G-code 字符串
 */

function apiResp<T>(data: T, code = 0, message = 'OK') {
  return { code, message, data }
}

const NOW = Math.floor(Date.now() / 1000)

interface ToolpathSegment {
  id: string
  type: 'rapid' | 'linear' | 'arc_cw' | 'arc_ccw'
  start: [number, number, number]
  end: [number, number, number]
  feed_rate: number
  spindle_speed: number
}

const INITIAL_TOOLPATH: ToolpathSegment[] = [
  {
    id: 'seg-001',
    type: 'rapid',
    start: [0, 0, 50],
    end: [0, 0, 5],
    feed_rate: 5000,
    spindle_speed: 0,
  },
  {
    id: 'seg-002',
    type: 'linear',
    start: [0, 0, 5],
    end: [50, 0, 5],
    feed_rate: 800,
    spindle_speed: 12000,
  },
  {
    id: 'seg-003',
    type: 'linear',
    start: [50, 0, 5],
    end: [50, 30, 5],
    feed_rate: 800,
    spindle_speed: 12000,
  },
]

let segments: ToolpathSegment[] = [...INITIAL_TOOLPATH]
const history: string[] = [] // operation names

function pushHistory(op: string) {
  history.push(op)
}

async function setupToolpathMocks(page: Page) {
  await page.route('**/api/v1/toolpath/load**', (route) => {
    route.fulfill({ json: apiResp({ toolpath_id: 'tp-001', segments }) })
  })

  await page.route('**/api/v1/toolpath/segments/add**', async (route) => {
    const body = route.request().postDataJSON() || {}
    const seg: ToolpathSegment = {
      id: `seg-${Date.now()}`,
      type: body.type || 'linear',
      start: body.start || [0, 0, 0],
      end: body.end || [0, 0, 0],
      feed_rate: body.feed_rate ?? 600,
      spindle_speed: body.spindle_speed ?? 10000,
    }
    segments = [...segments, seg]
    pushHistory(`add:${seg.id}`)
    await route.fulfill({ json: apiResp(seg) })
  })

  await page.route('**/api/v1/toolpath/segments/feed**', async (route) => {
    const body = route.request().postDataJSON() || {}
    segments = segments.map((s) =>
      s.id === body.segment_id ? { ...s, feed_rate: body.feed_rate } : s,
    )
    pushHistory(`feed:${body.segment_id}:${body.feed_rate}`)
    await route.fulfill({ json: apiResp({ updated: true }) })
  })

  await page.route('**/api/v1/toolpath/undo**', (route) => {
    const last = history.pop()
    // 简化的撤销：根据 op 还原
    if (last?.startsWith('add:')) {
      const id = last.slice(4)
      segments = segments.filter((s) => s.id !== id)
    } else if (last?.startsWith('feed:')) {
      const [, id, feed] = last.split(':')
      segments = segments.map((s) =>
        s.id === id ? { ...s, feed_rate: Number(feed) } : s,
      )
    }
    route.fulfill({ json: apiResp({ undone: last }) })
  })

  await page.route('**/api/v1/toolpath/redo**', (route) => {
    // 简化：仅占位
    route.fulfill({ json: apiResp({ redone: history[history.length - 1] || null }) })
  })

  await page.route('**/api/v1/toolpath/export**', (route) => {
    const lines = [
      '%',
      'O1001',
      ...segments.flatMap((s) => {
        if (s.type === 'rapid') {
          return [`G0 Z${s.end[2]}`]
        }
        return [`G1 X${s.end[0]} Y${s.end[1]} Z${s.end[2]} F${s.feed_rate}`]
      }),
      'M30',
      '%',
    ].join('\n')
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/plain' },
      body: lines,
    })
  })

  await page.route('**/api/v1/toolpath/parse**', async (route) => {
    const body = route.request().postDataJSON() || {}
    const code: string = body.gcode || ''
    const lines = code
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l.length > 0 && !l.startsWith('%') && !l.startsWith('('))
    const parsed = lines.length
    await route.fulfill({ json: apiResp({ parsed_lines: parsed, segments }) })
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

test.describe('E2E-5: 工具路径编辑与生成', () => {
  test.beforeEach(async ({ page }) => {
    await setupCommon(page)
    segments = [...INITIAL_TOOLPATH]
    history.length = 0
    await setupToolpathMocks(page)
  })

  test('5.1 加载 toolpath 返回 3 段', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/toolpath/load')
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.segments.length).toBe(3)
    expect(body.data.segments[0].type).toBe('rapid')
  })

  test('5.2 添加新段后总数 +1', async ({ page }) => {
    const before = await (await page.request.get('http://localhost:1420/api/v1/toolpath/load')).json()
    const beforeCount = before.data.segments.length

    await page.request.post('http://localhost:1420/api/v1/toolpath/segments/add', {
      data: {
        type: 'linear',
        start: [50, 30, 5],
        end: [0, 30, 5],
        feed_rate: 600,
        spindle_speed: 12000,
      },
    })

    const after = await (await page.request.get('http://localhost:1420/api/v1/toolpath/load')).json()
    expect(after.data.segments.length).toBe(beforeCount + 1)
  })

  test('5.3 修改段进给速度后立即生效', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/toolpath/segments/feed', {
      data: { segment_id: 'seg-002', feed_rate: 1500 },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)

    const after = await (await page.request.get('http://localhost:1420/api/v1/toolpath/load')).json()
    const seg = after.data.segments.find((s: ToolpathSegment) => s.id === 'seg-002')
    expect(seg.feed_rate).toBe(1500)
  })

  test('5.4 撤销 add 操作后段被移除', async ({ page }) => {
    await page.request.post('http://localhost:1420/api/v1/toolpath/segments/add', {
      data: { type: 'linear', start: [0, 0, 0], end: [10, 10, 0], feed_rate: 500 },
    })
    const before = await (await page.request.get('http://localhost:1420/api/v1/toolpath/load')).json()
    expect(before.data.segments.length).toBe(4)

    const undo = await page.request.post('http://localhost:1420/api/v1/toolpath/undo')
    const undoBody = await undo.json()
    expect(undoBody.code).toBe(0)

    const after = await (await page.request.get('http://localhost:1420/api/v1/toolpath/load')).json()
    expect(after.data.segments.length).toBe(3)
  })

  test('5.5 导出 G-code 文件包含 G0/G1/M30 指令', async ({ page }) => {
    const resp = await page.request.get('http://localhost:1420/api/v1/toolpath/export')
    const text = await resp.text()
    expect(text).toContain('G0')
    expect(text).toContain('G1')
    expect(text).toContain('M30')
  })

  test('5.6 解析 G-code 字符串返回行数', async ({ page }) => {
    const resp = await page.request.post('http://localhost:1420/api/v1/toolpath/parse', {
      data: {
        gcode: [
          '%',
          'O0001',
          'G0 Z5',
          'G1 X10 Y0 F500',
          'G1 X10 Y10 F500',
          'M30',
          '%',
        ].join('\n'),
      },
    })
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.parsed_lines).toBe(4)
  })
})
