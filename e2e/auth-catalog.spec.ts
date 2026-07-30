import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi, registerViaUi } from './helpers/auth'

test.describe('auth → catalog → detail', () => {
  test('register, land in library, open public-domain book detail', async ({ page }) => {
    const suffix = Date.now().toString(36)
    const username = `e2e_reg_${suffix}`
    const email = `${username}@example.com`
    const password = 'E2e-Reg-Passw0rd!'

    await registerViaUi(page, { username, email, password })
    await page.goto('/library/')
    // The same title can appear in multiple dashboard regions (e.g. continue + carousel).
    // Scope expectations to the "Yangi kitoblar" carousel region.
    const newBooks = page.locator('.books-carousel')
    await expect(newBooks.getByRole('button', { name: E2E.pdTitle })).toBeVisible({ timeout: 20_000 })
    await page.goto(`/library/${E2E.pdSlug}/`)
    await expect(page).toHaveURL(new RegExp(`/library/${E2E.pdSlug}`))
    await expect(page.getByRole('heading', { name: E2E.pdTitle })).toBeVisible()
  })

  test('login as seeded owner and browse catalog', async ({ page }) => {
    await loginViaUi(page)
    await page.goto('/library/')
    const newBooks = page.locator('.books-carousel')
    await expect(newBooks.getByRole('button', { name: E2E.pdTitle })).toBeVisible({ timeout: 20_000 })
    await expect(newBooks.getByRole('button', { name: E2E.licensedTitle })).toBeVisible()
  })
})
