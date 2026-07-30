import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi } from './helpers/auth'

test.describe('logout', () => {
  test('logout clears session and protects reader route', async ({ page }) => {
    await loginViaUi(page)
    await page.goto('/library/')
    await page.getByRole('button', { name: 'Chiqish' }).click()

    await expect(page).toHaveURL(/\/login/)
    const me = await page.request.get('/api/me/')
    const meJson = await me.json()
    expect(meJson.authenticated).toBeFalsy()

    await page.goto(`/library/${E2E.pdSlug}/read?mode=flip`)
    await expect(page).toHaveURL(/\/login/)
  })
})
