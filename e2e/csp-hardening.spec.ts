import { expect, test, type Page } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi } from './helpers/auth'
import { openReactFlip, openReactListen, openReactPdf } from './helpers/reader'

type CspViolation = {
  blockedURI: string
  violatedDirective: string
  originalPolicy: string
}

async function installCspProbe(page: Page) {
  await page.addInitScript(() => {
    const w = window as Window & { __cspViolations?: CspViolation[] }
    w.__cspViolations = []
    document.addEventListener('securitypolicyviolation', (event) => {
      w.__cspViolations = w.__cspViolations || []
      w.__cspViolations.push({
        blockedURI: event.blockedURI,
        violatedDirective: event.violatedDirective,
        originalPolicy: event.originalPolicy,
      })
    })
  })
}

async function assertNoCspViolations(page: Page, label: string) {
  const violations = await page.evaluate(() => {
    const w = window as Window & { __cspViolations?: CspViolation[] }
    return w.__cspViolations || []
  })
  expect(violations, `${label} CSP violations: ${JSON.stringify(violations)}`).toEqual([])
}

test.describe('CSP hardening walkthrough', () => {
  test.beforeEach(async ({ page }) => {
    await installCspProbe(page)
  })

  test('guest routes and catalog have no CSP violations', async ({ page }) => {
    await page.goto('/login/')
    await expect(page.locator('#id_username')).toBeVisible()
    await assertNoCspViolations(page, 'login')

    await page.goto('/register/')
    await expect(page.locator('#id_email')).toBeVisible()
    await assertNoCspViolations(page, 'register')

    await loginViaUi(page)
    await page.goto('/library/')
    await expect(page.locator('.books-carousel')).toBeVisible({ timeout: 20_000 })
    await assertNoCspViolations(page, 'catalog')

    await page.goto(`/library/${E2E.pdSlug}/`)
    await expect(page.getByRole('heading', { name: E2E.pdTitle })).toBeVisible()
    await assertNoCspViolations(page, 'book-detail')
  })

  test('PDF.js worker renders under worker-src', async ({ page }) => {
    await loginViaUi(page)
    await openReactPdf(page)
    await expect
      .poll(async () => page.locator('canvas.pdf-reader__canvas').count(), { timeout: 45_000 })
      .toBeGreaterThan(0)
    await assertNoCspViolations(page, 'pdf-reader')
  })

  test('flip and listen modes have no CSP violations', async ({ page }) => {
    await loginViaUi(page)
    await openReactFlip(page)
    await assertNoCspViolations(page, 'flip-reader')
    await openReactListen(page)
    await assertNoCspViolations(page, 'listen-reader')
  })

  test('mocked checkout status page has no CSP violations', async ({ page }) => {
    await page.route('**/api/payments/transactions/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '00000000-0000-4000-8000-000000000001',
          status: 'paid',
          provider: 'payme',
          amount_tiyin: 100000,
          book_slug: 'example',
          paid_at: new Date().toISOString(),
        }),
      })
    })
    await loginViaUi(page)
    await page.goto('/payment/status/00000000-0000-4000-8000-000000000001')
    await expect(page).toHaveURL(/payment\/status/)
    await assertNoCspViolations(page, 'checkout-status')
  })

  test('Django admin login/list/change work under admin CSP', async ({ page }) => {
    await page.goto(`${E2E.django}/admin/login/`)
    await expect(page.locator('#id_username')).toBeVisible()
    await assertNoCspViolations(page, 'admin-login')

    await page.locator('#id_username').fill(E2E.staff.username)
    await page.locator('#id_password').fill(E2E.staff.password)
    await page.locator('input[type="submit"]').click()
    await expect(page).toHaveURL(/\/admin\/$/)
    await assertNoCspViolations(page, 'admin-index')

    await page.goto(`${E2E.django}/admin/library/book/`)
    await expect(page.locator('#result_list')).toBeVisible()
    await assertNoCspViolations(page, 'admin-changelist')

    const changeLink = page.locator('#result_list tbody th a, #result_list tbody a').first()
    await expect(changeLink).toBeVisible()
    await changeLink.click()
    await expect(page.locator('#content-main form')).toBeVisible()
    await assertNoCspViolations(page, 'admin-change')
  })
})
