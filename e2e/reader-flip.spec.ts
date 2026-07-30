import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi, resetProgressPage, waitForProgressPage } from './helpers/auth'
import { openReactFlip, reactPageCounter } from './helpers/reader'

test.describe('flip reader + progress', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
    await resetProgressPage(page, E2E.pdSlug, 'flip')
  })

  test('React: page turn persists across reload', async ({ page }) => {
    await openReactFlip(page)
    const counter = reactPageCounter(page)
    await expect(counter).toContainText(/\/\s*\d+\s*sahifa/)

    await page.getByRole('button', { name: 'Next page' }).click({ force: true })
    await expect(counter).not.toHaveText(/^1\s*\/\s*\d+\s*sahifa$/, { timeout: 10_000 })

    await waitForProgressPage(page.request, E2E.pdSlug, 1)

    await page.reload()
    await expect(page.locator('.flip-reader-view')).toBeVisible({ timeout: 30_000 })
    await expect(reactPageCounter(page)).not.toHaveText(/^1\s*\/\s*\d+\s*sahifa$/)
  })
})
