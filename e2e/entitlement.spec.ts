import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi } from './helpers/auth'

test.describe('entitlement gating', () => {
  test('licensed book without purchase is blocked in UI and API', async ({ page }) => {
    await loginViaUi(page)

    await page.goto(`/library/${E2E.licensedSlug}/`)
    await expect(page.getByRole('heading', { name: E2E.licensedTitle })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sotib olish kerak' })).toBeVisible()
    await expect(page.getByText(/pullik|Purchase|xarid/i).first()).toBeVisible()

    const manifest = await page.request.get(`/api/library/${E2E.licensedSlug}/reader/`)
    expect(manifest.status()).toBe(403)

    // React reader route should redirect away from immersive shell
    await page.goto(`/library/${E2E.licensedSlug}/read?mode=flip`)
    await expect(page).not.toHaveURL(new RegExp(`/read`))
    await expect(page.locator('.flip-reader-view')).toHaveCount(0)
  })
})
