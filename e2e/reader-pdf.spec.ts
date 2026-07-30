import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi, resetProgressPage, waitForProgressPage } from './helpers/auth'
import { openReactPdf } from './helpers/reader'

test.describe('PDF reader + progress', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
    await resetProgressPage(page, E2E.pdSlug, 'pdf')
  })

  test('React: PDF renders and Next persists page', async ({ page }) => {
    await openReactPdf(page)

    await expect
      .poll(async () => page.locator('canvas.pdf-reader__canvas').count(), { timeout: 45_000 })
      .toBeGreaterThan(0)

    const counter = page.locator('.reader-toolbar__page-label')
    await expect(counter).toContainText(/^\d+\s*betdan\s*1-bet/)

    const pageControls = counter.locator('xpath=ancestor::div[contains(@class,"reader-toolbar__group--pages")]')
    const next = pageControls.locator('.reader-toolbar__icon-btn[data-action="next"]')
    await expect(next).toBeEnabled({ timeout: 15_000 })
    await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes(`/api/library/${E2E.pdSlug}/progress/`) &&
          res.request().method() === 'PUT' &&
          res.ok(),
        { timeout: 15_000 },
      ).catch(() => null),
      next.click(),
    ])
    await expect(counter).toContainText(/^\d+\s*betdan\s*2-bet/)

    await waitForProgressPage(page.request, E2E.pdSlug, 1)

    await page.reload()
    await openReactPdf(page)
    await expect(page.locator('.reader-toolbar__page-label')).toContainText(
      /^\d+\s*betdan\s*2-bet/,
    )
  })
})
