import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi, registerViaUi, resetProgressPage } from './helpers/auth'

async function csrfHeaders(page: import('@playwright/test').Page) {
  await page.request.get('/api/csrf/')
  const cookies = await page.context().cookies()
  const token = cookies.find((c) => c.name === 'csrftoken')?.value || ''
  return token ? { 'X-CSRFToken': token } : {}
}

test.describe('dashboard continue-card ratings', () => {
  test('continue card shows stars, comment form, and reordered actions', async ({ page }) => {
    const suffix = Date.now().toString(36)
    const username = `e2e_rate_${suffix}`
    const password = 'Libro-E2E-Battery-99!'
    await registerViaUi(page, {
      username,
      email: `${username}@example.com`,
      password,
    })

    const headers = await csrfHeaders(page)
    const progressRes = await page.request.put(`/api/library/${E2E.pdSlug}/progress/`, {
      headers,
      data: {
        mode: 'flip',
        page: 2,
        total_pages: 10,
        position: 0,
        status: 'reading',
      },
    })
    expect(progressRes.ok()).toBeTruthy()

    await page.goto('/library/')
    const card = page.getByTestId('continue-reading-card')
    await expect(card).toBeVisible({ timeout: 20_000 })
    await expect(card.getByRole('heading', { name: E2E.pdTitle })).toBeVisible()

    // Button order: Tinglash → Boshidan → Davom (by accessible name, not position index alone)
    await expect(card.getByRole('button', { name: /^Tinglash/ })).toBeVisible()
    await expect(card.getByRole('button', { name: /Boshidan boshlash/ })).toBeVisible()
    await expect(card.getByRole('button', { name: /O.qishni davom ettirish/ })).toBeVisible()

    const actionLabels = await card.locator('.continue-card__actions button').allTextContents()
    const normalized = actionLabels.map((t) => t.trim())
    expect(normalized[0]).toMatch(/^Tinglash/)
    expect(normalized[1]).toMatch(/Boshidan boshlash/)
    expect(normalized[2]).toMatch(/davom ettirish/i)

    // Visible comment form on the card surface
    await expect(card.getByRole('form', { name: 'Sharh yozish' })).toBeVisible()
    await expect(card.getByPlaceholder(/Fikringizni yozing/)).toBeVisible()

    const star5 = card.getByRole('radio', { name: '5 yulduz bilan baholash' })
    await expect(star5).toBeVisible()
    await star5.click()
    await expect(card.locator('.continue-card__rate-status--saved')).toBeVisible({
      timeout: 10_000,
    })

    const commentText = `E2E sharh ${suffix}`
    await card.getByPlaceholder(/Fikringizni yozing/).fill(commentText)
    await card.getByRole('button', { name: 'Yuborish' }).click()
    await expect(card.locator('.review-comment-form__status--saved')).toBeVisible({
      timeout: 10_000,
    })

    await expect
      .poll(async () => {
        const res = await page.request.get(`/api/library/${E2E.pdSlug}/reviews/`)
        const data = await res.json()
        const mine = (data.results || []).find(
          (r: { username: string; text?: string }) => r.username === username,
        )
        return mine?.text ?? null
      })
      .toBe(commentText)

    // Cross-user visibility: guest GET sees User A's text
    const guestCtx = await page.context().browser()!.newContext()
    const guestPage = await guestCtx.newPage()
    const guestRes = await guestPage.request.get(
      `${E2E.vite}/api/library/${E2E.pdSlug}/reviews/`,
    )
    expect(guestRes.ok()).toBeTruthy()
    const guestData = await guestRes.json()
    expect(guestData.results.some((r: { text: string }) => r.text === commentText)).toBeTruthy()
    await guestCtx.close()
  })

  test('carousel book click opens modal with reviews panel and comment form', async ({
    page,
  }) => {
    await loginViaUi(page)
    await resetProgressPage(page, E2E.pdSlug, 'flip')
    await page.goto('/library/')
    const newBooks = page.locator('.books-carousel')
    await expect(newBooks.getByRole('button', { name: E2E.pdTitle })).toBeVisible({
      timeout: 20_000,
    })
    await newBooks.getByRole('button', { name: E2E.pdTitle }).click()
    const modal = page.locator('.reader-launch-modal')
    await expect(modal).toBeVisible()
    await expect(modal.locator('.book-reviews-panel')).toBeVisible({ timeout: 10_000 })
    await expect(modal.getByRole('radio', { name: '5 yulduz bilan baholash' })).toBeVisible()
    await expect(modal.getByRole('form', { name: 'Sharh yozish' })).toBeVisible()
    await expect(modal.getByPlaceholder(/Fikringizni yozing/)).toBeVisible()
  })
})
