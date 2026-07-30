import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { registerViaUi } from './helpers/auth'
import { openReactFlip } from './helpers/reader'

test.describe('shelf status persistence', () => {
  test('planned → reading → finished persists', async ({ page }) => {
    // Fresh user: DELETE /status/ only removes `planned`, so owner pollution breaks this journey.
    const suffix = Date.now().toString(36)
    const username = `e2e_shelf_${suffix}`
    await registerViaUi(page, {
      username,
      email: `${username}@example.com`,
      // Avoid UserAttributeSimilarityValidator vs username containing "shelf".
      password: 'Libro-E2E-Battery-99!',
    })

    await page.goto(`/library/${E2E.pdSlug}/`)
    await expect(page.getByRole('heading', { name: E2E.pdTitle })).toBeVisible()

    await page.getByRole('button', { name: /Rejaga qo['‘]shish/ }).click()
    await expect(page.getByRole('button', { name: /Rejadan olib tashlash/ })).toBeVisible({
      timeout: 10_000,
    })

    let detail = await (await page.request.get(`/api/library/${E2E.pdSlug}/`)).json()
    expect(detail.reading_status).toBe('planned')

    await page.goto('/library/mening/')
    await page.getByRole('tab', { name: /Rejamdagi kitoblar/ }).click()
    await expect(page.getByText(E2E.pdTitle)).toBeVisible({ timeout: 15_000 })

    // Opening the reader + page activity promotes planned → reading via progress API
    await openReactFlip(page)
    await page.getByRole('button', { name: 'Next page' }).click({ force: true })
    await expect
      .poll(async () => {
        const d = await (await page.request.get(`/api/library/${E2E.pdSlug}/`)).json()
        return d.reading_status
      })
      .toBe('reading')

    await page.goto(`/library/${E2E.pdSlug}/`)
    await page.getByRole('button', { name: 'Tugatdim' }).click()
    await expect(
      page.getByRole('button', { name: /O['‘]qiyotganlarga qaytarish/ }),
    ).toBeVisible({
      timeout: 10_000,
    })

    detail = await (await page.request.get(`/api/library/${E2E.pdSlug}/`)).json()
    expect(detail.reading_status).toBe('finished')
  })
})
