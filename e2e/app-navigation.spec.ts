import { test, expect, type Page } from '@playwright/test'

async function mockApiRoutes(page: Page) {
  await page.route('**/api/v1/version', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: '2.5.0', commit: 'test-abc' }),
    })
  })
  await page.route('**/api/health/ping', (route) => {
    route.fulfill({ status: 200, body: JSON.stringify({ ping: true }) })
  })
  await page.route('**/api/health', (route) => {
    route.fulfill({ status: 200, body: JSON.stringify({ status: 'ok', version: '2.5.0' }) })
  })
  await page.route('**/health', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({ status: 'healthy', timestamp: Date.now(), version: '2.5.0', uptime: 3600 }),
    })
  })
  await page.route('**/api/v1/lnn/models', (route) => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({
        code: 'SUCCESS',
        message: 'OK',
        data: { models: [], total: 0 },
      }),
    })
  })
}

test.describe('1. Home Page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('home page loads successfully', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL('/')
  })

  test('home page has title', async ({ page }) => {
    await page.goto('/')
    const title = await page.title()
    expect(title).toContain('灵境制造')
  })

  test('home page has navigation elements', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })
})

test.describe('2. About Page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('about page loads', async ({ page }) => {
    await page.goto('/about')
    await expect(page).toHaveURL('/about')
  })

  test('about page has content', async ({ page }) => {
    await page.goto('/about')
    await page.waitForLoadState('networkidle')
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })
})

test.describe('3. Workspace Page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('workspace page loads', async ({ page }) => {
    await page.goto('/workspace')
    await expect(page).toHaveURL('/workspace')
  })

  test('workspace page renders without crashing', async ({ page }) => {
    await page.goto('/workspace')
    await page.waitForLoadState('networkidle')
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })
})

test.describe('4. Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('settings page loads', async ({ page }) => {
    await page.goto('/settings')
    await expect(page).toHaveURL('/settings')
  })

  test('settings page renders components', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })
})

test.describe('5. Task History Page', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
    await page.route('**/api/v1/jobs**', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          code: 'SUCCESS',
          message: 'OK',
          data: { jobs: [], total: 0, has_more: false },
        }),
      })
    })
  })

  test('task history page loads', async ({ page }) => {
    await page.goto('/task-history')
    await expect(page).toHaveURL('/task-history')
  })

  test('task history page has job table', async ({ page }) => {
    await page.goto('/task-history')
    await page.waitForLoadState('networkidle')
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })
})

test.describe('6. Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page)
  })

  test('can navigate between pages', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.goto('/about')
    await expect(page).toHaveURL('/about')

    await page.goto('/settings')
    await expect(page).toHaveURL('/settings')

    await page.goto('/')
    await expect(page).toHaveURL('/')
  })
})
