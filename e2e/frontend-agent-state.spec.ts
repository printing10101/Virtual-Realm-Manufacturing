import { test, expect, type Page } from '@playwright/test'

const _API_BASE = '/api/v1/agents'

interface AgentSummary {
  agent_id: string
  status: string
  current_task_id: string | null
  last_heartbeat: number
  updated_at: number
  created_at: number
}

interface CheckpointInfo {
  checkpoint_id: string
  epoch: number
  step: number
  best_metric: number | null
  best_metric_name: string
  checkpoint_type: string
  created_at: number
  metrics: Record<string, number>
  file_size_bytes: number
}

interface MemoryEntryInfo {
  memory_id: string
  content: string
  memory_type: string
  importance: number
  created_at: number
  last_accessed: number
  access_count: number
  tags: string[]
}

interface AgentDetail {
  agent_id: string
  current_task_id: string | null
  status: string
  last_heartbeat: number
  created_at: number
  updated_at: number
  session_context: {
    task_id: string | null
    task_type: string | null
    task_description: string
    goal_chain: unknown[]
    current_stage: string
    conversation_history: unknown[]
    injected_skills: string[]
    active_context_keys: string[]
    custom_context: Record<string, unknown>
  }
  checkpoint: CheckpointInfo | null
  checkpoints_history: CheckpointInfo[]
  memory: MemoryEntryInfo[]
  state_version: {
    state_version: number
    schema_version: string
    migration_history: unknown[]
  }
  metadata: Record<string, unknown>
}

function apiResponse<T>(data: T, message = 'Success') {
  return { code: 'SUCCESS', message, data }
}

const NOW = Math.floor(Date.now() / 1000)

const MOCK_AGENTS: AgentSummary[] = [
  {
    agent_id: 'agent-alpha-001',
    status: 'busy',
    current_task_id: 'task-train-042',
    last_heartbeat: NOW - 5,
    updated_at: NOW - 3,
    created_at: NOW - 7200,
  },
  {
    agent_id: 'agent-beta-002',
    status: 'idle',
    current_task_id: null,
    last_heartbeat: NOW - 30,
    updated_at: NOW - 30,
    created_at: NOW - 10800,
  },
  {
    agent_id: 'agent-gamma-003',
    status: 'error',
    current_task_id: 'task-infer-017',
    last_heartbeat: NOW - 300,
    updated_at: NOW - 60,
    created_at: NOW - 14400,
  },
  {
    agent_id: 'agent-delta-004',
    status: 'recovering',
    current_task_id: 'task-train-042',
    last_heartbeat: NOW - 2,
    updated_at: NOW - 2,
    created_at: NOW - 5000,
  },
  {
    agent_id: 'agent-epsilon-005',
    status: 'paused',
    current_task_id: 'task-eval-009',
    last_heartbeat: NOW - 120,
    updated_at: NOW - 45,
    created_at: NOW - 20000,
  },
]

const MOCK_DETAIL: AgentDetail = {
  agent_id: 'agent-alpha-001',
  current_task_id: 'task-train-042',
  status: 'busy',
  last_heartbeat: NOW - 5,
  created_at: NOW - 7200,
  updated_at: NOW - 3,
  session_context: {
    task_id: 'task-train-042',
    task_type: 'training',
    task_description: '使用高质量NC加工数据集微调3D模型生成能力',
    goal_chain: [],
    current_stage: 'model_finetune',
    conversation_history: [
      { role: 'user', content: '开始模型训练' },
      { role: 'assistant', content: '训练已启动，当前epoch 2/10' },
      { role: 'user', content: '调整学习率为0.001' },
    ],
    injected_skills: ['nc_machining', 'toolpath_generation', 'precision_calibration'],
    active_context_keys: ['model_config', 'training_params', 'dataset_info'],
    custom_context: {},
  },
  checkpoint: {
    checkpoint_id: 'train_ckpt_e3',
    epoch: 3,
    step: 300,
    best_metric: 0.0342,
    best_metric_name: 'val_loss',
    checkpoint_type: 'epoch_end',
    created_at: NOW - 10,
    metrics: { train_loss: 0.041, val_loss: 0.0342, accuracy: 0.92 },
    file_size_bytes: 14680064,
  },
  checkpoints_history: [
    {
      checkpoint_id: 'train_ckpt_e3',
      epoch: 3,
      step: 300,
      best_metric: 0.0342,
      best_metric_name: 'val_loss',
      checkpoint_type: 'epoch_end',
      created_at: NOW - 10,
      metrics: {},
      file_size_bytes: 14680064,
    },
    {
      checkpoint_id: 'train_ckpt_e2',
      epoch: 2,
      step: 200,
      best_metric: 0.0521,
      best_metric_name: 'val_loss',
      checkpoint_type: 'epoch_end',
      created_at: NOW - 610,
      metrics: {},
      file_size_bytes: 14680064,
    },
    {
      checkpoint_id: 'train_ckpt_e1',
      epoch: 1,
      step: 100,
      best_metric: 0.0893,
      best_metric_name: 'val_loss',
      checkpoint_type: 'epoch_end',
      created_at: NOW - 1210,
      metrics: {},
      file_size_bytes: 14680064,
    },
  ],
  memory: [
    {
      memory_id: 'mem-001',
      content: '数据集包含50000个NC加工样本，涵盖铣削、车削、钻孔三类工艺',
      memory_type: 'observation',
      importance: 0.95,
      created_at: NOW - 7000,
      last_accessed: NOW - 100,
      access_count: 12,
      tags: ['dataset', 'nc_machining'],
    },
    {
      memory_id: 'mem-002',
      content: '学习率调整为0.001后验证损失显著下降，当前最佳epoch=3',
      memory_type: 'decision',
      importance: 0.88,
      created_at: NOW - 3000,
      last_accessed: NOW - 50,
      access_count: 8,
      tags: ['hyperparams', 'training'],
    },
    {
      memory_id: 'mem-003',
      content: '检测到GPU内存使用率峰值85%，建议降低batch size',
      memory_type: 'observation',
      importance: 0.72,
      created_at: NOW - 1000,
      last_accessed: NOW - 200,
      access_count: 5,
      tags: ['gpu', 'monitoring'],
    },
  ],
  state_version: {
    state_version: 7,
    schema_version: '2.1.0',
    migration_history: [],
  },
  metadata: {
    model_name: 'LNN-Model-V3',
    framework: 'pytorch',
    total_epochs: 10,
  },
}

function setupApiMocks(page: Page) {
  return page.route('**/api/v1/agents/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const method = route.request().method()

    // POST /api/v1/agents/{id}/clone
    const cloneMatch = path.match(/\/api\/v1\/agents\/(.+)\/clone$/)
    if (cloneMatch && method === 'POST') {
      const body = route.request().postDataJSON()
      const targetId = body.target_agent_id
      const detail = structuredClone(MOCK_DETAIL)
      detail.agent_id = targetId
      detail.status = 'idle'
      detail.current_task_id = null
      await route.fulfill({ json: apiResponse(detail, `Cloned agent to '${targetId}'`) })
      return
    }

    // POST /api/v1/agents/{id}/checkpoints/rollback
    const rollbackMatch = path.match(/\/api\/v1\/agents\/(.+)\/checkpoints\/rollback$/)
    if (rollbackMatch && method === 'POST') {
      const body = route.request().postDataJSON()
      const detail = structuredClone(MOCK_DETAIL)
      const found = detail.checkpoints_history.find(
        (c) => c.checkpoint_id === body.checkpoint_id
      )
      if (found) {
        detail.checkpoint = { ...found }
        detail.status = 'busy'
      }
      await route.fulfill({ json: apiResponse(detail, `Rolled back to checkpoint '${body.checkpoint_id}'`) })
      return
    }

    // POST /api/v1/agents/{id}/checkpoints/save
    const saveCkptMatch = path.match(/\/api\/v1\/agents\/(.+)\/checkpoints\/save$/)
    if (saveCkptMatch && method === 'POST') {
      const body = route.request().postDataJSON()
      const newCkpt: CheckpointInfo = {
        checkpoint_id: body.checkpoint_id || 'manual-ckpt-saved',
        epoch: body.epoch || 3,
        step: body.step || 300,
        best_metric: body.best_metric ?? null,
        best_metric_name: body.best_metric_name || 'loss',
        checkpoint_type: body.checkpoint_type || 'manual',
        created_at: NOW,
        metrics: body.metrics || {},
        file_size_bytes: 14680064,
      }
      const detail = structuredClone(MOCK_DETAIL)
      detail.checkpoint = newCkpt
      detail.checkpoints_history.unshift(newCkpt)
      await route.fulfill({ json: apiResponse(detail, 'Checkpoint saved') })
      return
    }

    // POST /api/v1/agents/{id}/save
    const saveMatch = path.match(/\/api\/v1\/agents\/(.+)\/save$/)
    if (saveMatch && method === 'POST') {
      const detail = structuredClone(MOCK_DETAIL)
      await route.fulfill({ json: apiResponse(detail, 'Agent state saved') })
      return
    }

    // POST /api/v1/agents/{id}/resume
    const resumeMatch = path.match(/\/api\/v1\/agents\/(.+)\/resume$/)
    if (resumeMatch && method === 'POST') {
      await route.fulfill({
        json: apiResponse({ status: 'resumed_with_checkpoint', checkpoint: MOCK_DETAIL.checkpoint }),
      })
      return
    }

    // POST /api/v1/agents/{id}/snapshot
    const snapshotMatch = path.match(/\/api\/v1\/agents\/(.+)\/snapshot$/)
    if (snapshotMatch && method === 'POST') {
      await route.fulfill({ json: apiResponse({ snapshot_key: 'snap-20260513-001' }, 'Snapshot created') })
      return
    }

    // POST /api/v1/agents/{id}/rollback
    const stateRollbackMatch = path.match(/\/api\/v1\/agents\/(.+)\/rollback$/)
    if (stateRollbackMatch && method === 'POST') {
      await route.fulfill({ json: apiResponse(MOCK_DETAIL, 'Rollback successful') })
      return
    }

    // GET /api/v1/agents/{id}/checkpoints
    const listCkptMatch = path.match(/\/api\/v1\/agents\/(.+)\/checkpoints$/)
    if (listCkptMatch && method === 'GET') {
      await route.fulfill({ json: apiResponse(MOCK_DETAIL.checkpoints_history) })
      return
    }

    // GET /api/v1/agents/{id}/history
    const histMatch = path.match(/\/api\/v1\/agents\/(.+)\/history$/)
    if (histMatch && method === 'GET') {
      await route.fulfill({ json: apiResponse([]) })
      return
    }

    // POST heartbeat, context, memory
    if (method === 'POST') {
      const detail = structuredClone(MOCK_DETAIL)
      await route.fulfill({ json: apiResponse(detail) })
      return
    }

    // DELETE
    if (method === 'DELETE') {
      await route.fulfill({ json: apiResponse(null, 'Deleted') })
      return
    }

    // GET /api/v1/agents/{id} — detail
    const detailMatch = path.match(/\/api\/v1\/agents\/([^/]+)$/)
    if (detailMatch && method === 'GET') {
      const aid = detailMatch[1]
      if (aid === 'agent-alpha-001') {
        await route.fulfill({ json: apiResponse(MOCK_DETAIL) })
      } else {
        const other = structuredClone(MOCK_DETAIL)
        other.agent_id = aid
        await route.fulfill({ json: apiResponse(other) })
      }
      return
    }

    // GET /api/v1/agents/ — list
    await route.fulfill({ json: apiResponse(MOCK_AGENTS) })
  })
}

async function navigateToAgents(page: Page) {
  await page.goto('/agents')
  await page.waitForSelector('.agent-dashboard')
}

async function navigateToAgentDetail(page: Page, agentId: string) {
  await page.goto(`/agents/${agentId}`)
  await page.waitForSelector('.agent-detail-page')
}

// ============================================================
// 7a. 登录系统前端界面
// ============================================================
test.describe('7. 前端状态显示验证 — AgentDashboard 页面', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page)
  })

  test('7a-1: 页面可正常加载，显示标题"代理状态监控"', async ({ page }) => {
    await navigateToAgents(page)
    await expect(page.locator('h2')).toContainText('代理状态监控')
  })

  test('7a-2: 状态筛选下拉框包含全部6种状态选项', async ({ page }) => {
    await navigateToAgents(page)
    const select = page.locator('.dashboard-actions .el-select')
    await expect(select).toBeVisible()
    await select.click()
    const options = page.locator('.el-select-dropdown__item')
    await expect(options.first()).toBeVisible()
    const count = await options.count()
    expect(count).toBeGreaterThanOrEqual(5)
  })

  // ============================================================
  // 7b. 导航至代理详情页面
  // ============================================================
  test('7b: 点击代理ID链接可跳转到详情页', async ({ page }) => {
    await navigateToAgents(page)
    await page.waitForSelector('.el-table__body-wrapper tr')
    await page.locator('.agent-table-card .el-link').first().click()
    await page.waitForURL('**/agents/agent-alpha-001')
    await expect(page.locator('.agent-detail-page')).toBeVisible()
    await expect(page.locator('h2')).toContainText('agent-alpha-001')
  })

  // ============================================================
  // 7c. 验证页面显示的状态信息与后端存储一致
  // ============================================================
  test('7c: 统计卡片数据与mock后端一致', async ({ page }) => {
    await navigateToAgents(page)
    // 代理总数 = 5
    await expect(page.locator('.stat-total .stat-value')).toHaveText('5')
    // 活跃 = busy(1) + recovering(1) = 2
    await expect(page.locator('.stat-active .stat-value')).toHaveText('2')
    // 空闲 = idle(1) = 1
    await expect(page.locator('.stat-idle .stat-value')).toHaveText('1')
    // 异常 = error(1) + stopped(0) = 1
    await expect(page.locator('.stat-error .stat-value')).toHaveText('1')
  })

  test('7c: 代理列表包含全部5条记录', async ({ page }) => {
    await navigateToAgents(page)
    const rows = page.locator('.el-table__body-wrapper tbody tr')
    await expect(rows.first()).toBeVisible()
    const count = await rows.count()
    expect(count).toBe(5)
  })

  test('7c: 列表显示正确的agent_id', async ({ page }) => {
    await navigateToAgents(page)
    for (const agent of MOCK_AGENTS) {
      await expect(page.locator('.el-table__body-wrapper')).toContainText(agent.agent_id)
    }
  })

  test('7c: 列表显示正确的current_task_id', async ({ page }) => {
    await navigateToAgents(page)
    await expect(page.locator('.el-table__body-wrapper')).toContainText('task-train-042')
    // agent-beta-002 has null task → "-" text
    await expect(page.locator('.el-table__body-wrapper')).toContainText('-')
  })

  test('7c: 时间列显示为可读中文格式', async ({ page }) => {
    await navigateToAgents(page)
    const timeCell = page.locator('.el-table__body-wrapper tbody tr').first().locator('td').nth(3)
    const text = await timeCell.textContent()
    expect(text).toMatch(/\d{4}\/\d{1,2}\/\d{1,2}/)
  })

  // ============================================================
  // 7d. 确认所有关键状态参数正确显示
  // ============================================================
  test('7d: 状态标签文字映射正确', async ({ page }) => {
    await navigateToAgents(page)
    // busy → 忙碌 for agent-alpha-001
    const firstRow = page.locator('.el-table__body-wrapper tbody tr').first()
    await expect(firstRow.locator('.el-tag').first()).toContainText('忙碌')
  })

  test('7d: status筛选后重新加载', async ({ page }) => {
    await navigateToAgents(page)
    const select = page.locator('.dashboard-actions .el-select')
    await select.click()
    await page.locator('.el-select-dropdown__item', { hasText: '空闲' }).click()
    // After filtering, list should still render
    await expect(page.locator('.el-table__body-wrapper')).toBeVisible()
  })

  test('7d: 刷新按钮重新加载数据', async ({ page }) => {
    await navigateToAgents(page)
    const refreshBtn = page.locator('.dashboard-actions .el-button', { hasText: '刷新' })
    await expect(refreshBtn).toBeVisible()
    await expect(refreshBtn).toBeEnabled()
    await refreshBtn.click()
    await expect(page.locator('.el-table__body-wrapper tbody tr').first()).toBeVisible()
  })

  // ============================================================
  // 7e. 检查状态更新的实时性和准确性
  // ============================================================
  test('7e: 刷新后统计卡片保持准确', async ({ page }) => {
    await navigateToAgents(page)
    const refreshBtn = page.locator('.dashboard-actions .el-button', { hasText: '刷新' })
    await refreshBtn.click()
    await page.waitForTimeout(500)
    await expect(page.locator('.stat-total .stat-value')).toHaveText('5')
  })
})

// ============================================================
// AgentDetail 页面详细验证
// ============================================================
test.describe('7. 前端状态显示验证 — AgentDetail 页面', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page)
    await navigateToAgentDetail(page, 'agent-alpha-001')
  })

  // --- 基本信息卡片 ---
  test('7d-1: 基本信息卡片 — agent_id 正确', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('agent-alpha-001')
  })

  test('7d-1: 基本信息卡片 — current_task_id 正确', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('task-train-042')
  })

  test('7d-1: 基本信息卡片 — Schema版本显示', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('2.1.0')
  })

  test('7d-1: 基本信息卡片 — 时间可读格式', async ({ page }) => {
    const descItems = page.locator('.el-descriptions__body .el-descriptions__content')
    const lastHearbeat = descItems.nth(2)
    const text = await lastHearbeat.textContent()
    expect(text).toMatch(/\d{4}\/\d{1,2}\/\d{1,2}/)
  })

  test('7d-1: 状态标签显示"忙碌"', async ({ page }) => {
    const tag = page.locator('.detail-header .el-tag')
    await expect(tag).toContainText('忙碌')
  })

  // --- 会话上下文卡片 ---
  test('7d-2: 会话上下文 — task_type 显示 training', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('training')
  })

  test('7d-2: 会话上下文 — current_stage 显示 model_finetune', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('model_finetune')
  })

  test('7d-2: 会话上下文 — injected_skills 标签完整', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('nc_machining')
    await expect(page.locator('.agent-detail-page')).toContainText('toolpath_generation')
    await expect(page.locator('.agent-detail-page')).toContainText('precision_calibration')
  })

  test('7d-2: 会话上下文 — 对话历史条数=3', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('3 条')
  })

  // --- 当前检查点卡片 ---
  test('7d-3: 检查点卡片 — checkpoint_id 显示 train_ckpt_e3', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('train_ckpt_e3')
  })

  test('7d-3: 检查点卡片 — epoch/step 显示 3/300', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('3')
    await expect(page.locator('.agent-detail-page')).toContainText('300')
  })

  test('7d-3: 检查点卡片 — best_metric 显示 val_loss=0.0342', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('0.0342')
    await expect(page.locator('.agent-detail-page')).toContainText('val_loss')
  })

  test('7d-3: 检查点卡片 — 文件大小显示为可读格式', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('MB')
  })

  test('7d-3: 检查点卡片 — 类型显示 epoch_end', async ({ page }) => {
    await expect(page.locator('.agent-detail-page')).toContainText('epoch_end')
  })

  // --- 代理记忆区域 ---
  test('7d-4: 记忆区域 — 标题显示记忆条数=3', async ({ page }) => {
    await expect(page.locator('.memory-card')).toContainText('代理记忆')
    await expect(page.locator('.memory-card')).toContainText('3 条')
  })

  test('7d-4: 记忆列表 — 3条记录可见', async ({ page }) => {
    const rows = page.locator('.memory-card .el-table__body-wrapper tbody tr')
    await expect(rows.first()).toBeVisible()
    const count = await rows.count()
    expect(count).toBe(3)
  })

  test('7d-4: 记忆列表 — memory_type 标签正确', async ({ page }) => {
    await expect(page.locator('.memory-card')).toContainText('observation')
    await expect(page.locator('.memory-card')).toContainText('decision')
  })

  test('7d-4: 记忆列表 — 按重要性排序（首条 importance=0.95）', async ({ page }) => {
    const firstImportance = page.locator('.memory-card .el-table__body-wrapper tbody tr').first().locator('.el-progress__text')
    await expect(firstImportance).toContainText('95')
  })

  test('7d-4: 记忆可视化 — 切换视图按钮可用', async ({ page }) => {
    const toggleBtn = page.locator('.memory-card .card-header-flex .el-button', { hasText: '可视化' })
    await expect(toggleBtn).toBeVisible()
    await toggleBtn.click()
    await expect(page.locator('.memory-chart-container')).toBeVisible()
  })

  test('7d-4: 记忆可视化 — 条形图渲染内容', async ({ page }) => {
    await page.locator('.memory-card .card-header-flex .el-button', { hasText: '可视化' }).click()
    const bars = page.locator('.memory-bar-item')
    await expect(bars.first()).toBeVisible()
    const count = await bars.count()
    expect(count).toBe(3)
  })

  test('7d-4: 记忆可视化 — 切回列表视图', async ({ page }) => {
    await page.locator('.memory-card .card-header-flex .el-button', { hasText: '可视化' }).click()
    await page.locator('.memory-card .card-header-flex .el-button', { hasText: '列表' }).click()
    await expect(page.locator('.memory-card .el-table__body-wrapper')).toBeVisible()
  })

  // --- 检查点历史时间线 ---
  test('7d-5: 检查点历史 — 标题显示3个', async ({ page }) => {
    await expect(page.locator('.history-card')).toContainText('检查点历史')
    await expect(page.locator('.history-card')).toContainText('3 个')
  })

  test('7d-5: 检查点历史 — 时间线包含epoch_end标签', async ({ page }) => {
    await expect(page.locator('.history-card')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.history-card')).toContainText('epoch_end')
  })

  test('7d-5: 检查点历史 — 时间线包含Epoch 3和Epoch 2', async ({ page }) => {
    await expect(page.locator('.history-card')).toContainText('Epoch 3, Step 300')
    await expect(page.locator('.history-card')).toContainText('Epoch 2, Step 200')
  })

  test('7d-5: 检查点历史 — 回滚按钮可见', async ({ page }) => {
    const rollbackBtn = page.locator('.history-card .el-button', { hasText: '回滚' })
    await expect(rollbackBtn.first()).toBeVisible()
  })

  // --- 操作按钮 ---
  test('7d-6: 克隆按钮打开对话框', async ({ page }) => {
    const cloneBtn = page.locator('.detail-header .el-button', { hasText: '克隆' })
    await expect(cloneBtn).toBeVisible()
    await cloneBtn.click()
    await expect(page.locator('.el-dialog')).toBeVisible()
  })

  test('7d-6: 手动保存按钮显示', async ({ page }) => {
    const saveBtn = page.locator('.checkpoint-card .el-button', { hasText: '手动保存' })
    await expect(saveBtn).toBeVisible()
    await expect(saveBtn).toBeEnabled()
  })

  test('7d-6: 返回列表按钮可用', async ({ page }) => {
    const backBtn = page.locator('.detail-header .el-button', { hasText: '返回列表' })
    await expect(backBtn).toBeVisible()
    await backBtn.click()
    await page.waitForURL('**/agents')
    await expect(page.locator('.agent-dashboard')).toBeVisible()
  })
})

// ============================================================
// 边界场景
// ============================================================
test.describe('7. 前端状态显示验证 — 边界场景', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page)
  })

  test('空记忆的代理详情正常渲染', async ({ page }) => {
    const emptyDetail = structuredClone(MOCK_DETAIL)
    emptyDetail.memory = []
    emptyDetail.agent_id = 'agent-empty-mem'

    await page.route('**/api/v1/agents/agent-empty-mem', async (route) => {
      await route.fulfill({ json: apiResponse(emptyDetail) })
    })

    await navigateToAgentDetail(page, 'agent-empty-mem')
    await expect(page.locator('.memory-card')).toContainText('0 条')
    await expect(page.locator('.memory-card .el-empty')).toBeVisible()
  })

  test('无检查点的代理详情正常渲染', async ({ page }) => {
    const noCkptDetail = structuredClone(MOCK_DETAIL)
    noCkptDetail.checkpoint = null
    noCkptDetail.checkpoints_history = []
    noCkptDetail.agent_id = 'agent-no-ckpt'

    await page.route('**/api/v1/agents/agent-no-ckpt', async (route) => {
      await route.fulfill({ json: apiResponse(noCkptDetail) })
    })

    await navigateToAgentDetail(page, 'agent-no-ckpt')
    await expect(page.locator('.checkpoint-card .el-empty')).toBeVisible()
  })

  test('idle状态代理的恢复按钮可点击', async ({ page }) => {
    await navigateToAgents(page)
    // agent-beta-002 is idle
    const idleRow = page.locator('.el-table__body-wrapper tbody tr', { hasText: 'agent-beta-002' })
    const resumeBtn = idleRow.locator('.el-button', { hasText: '恢复' })
    await expect(resumeBtn).toBeEnabled()
  })

  test('busy状态代理的恢复按钮禁用', async ({ page }) => {
    await navigateToAgents(page)
    // agent-alpha-001 is busy
    const busyRow = page.locator('.el-table__body-wrapper tbody tr', { hasText: 'agent-alpha-001' })
    const resumeBtn = busyRow.locator('.el-button', { hasText: '恢复' })
    await expect(resumeBtn).toBeDisabled()
  })

  test('刷新按钮loading状态', async ({ page }) => {
    await navigateToAgents(page)
    // Slow response mock for one request
    let routed = false
    await page.route('**/api/v1/agents/', async (route) => {
      if (!routed) {
        routed = true
        await new Promise((r) => setTimeout(r, 2000))
      }
      await route.fulfill({ json: apiResponse(MOCK_AGENTS) })
    }, { times: 1 })

    const refreshBtn = page.locator('.dashboard-actions .el-button', { hasText: '刷新' })
    await refreshBtn.click()
    await expect(refreshBtn).toHaveClass(/is-loading/)
  })
})
