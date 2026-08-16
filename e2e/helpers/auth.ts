import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { E2E } from '../fixtures'

export async function csrfHeaders(page: Page): Promise<Record<string, string>> {
  await page.request.get('/api/csrf/')
  const cookies = await page.context().cookies()
  const token = cookies.find((c) => c.name === 'csrftoken')?.value || ''
  return token ? { 'X-CSRFToken': token } : {}
}

export async function loginViaUi(
  page: Page,
  username = E2E.owner.username,
  password = E2E.owner.password,
) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await page.goto('/login/')
    await page.locator('#id_username').fill(username)
    await page.locator('input[name="password"]').fill(password)
    await page.locator('button[type="submit"]').click()

    const throttled = page.getByText(/throttled|Expected available/i)
    try {
      await expect
        .poll(
          async () => {
            if (await throttled.isVisible().catch(() => false)) return 'throttled'
            const res = await page.request.get('/api/me/')
            const data = await res.json()
            return data?.authenticated ? 'ok' : 'pending'
          },
          { timeout: 20_000 },
        )
        .toBe('ok')
      return
    } catch {
      if (await throttled.isVisible().catch(() => false)) {
        await page.waitForTimeout(5_000 + attempt * 5_000)
        continue
      }
      throw new Error(`loginViaUi failed for ${username}`)
    }
  }
  throw new Error(`loginViaUi exhausted retries for ${username}`)
}

export async function registerViaUi(
  page: Page,
  opts: { username: string; email: string; password: string },
) {
  await page.goto('/register/')
  await page.locator('#id_username').fill(opts.username)
  await page.locator('#id_email').fill(opts.email)
  await page.locator('#id_password').fill(opts.password)
  await page.locator('#id_password_confirm').fill(opts.password)
  await page.locator('button[type="submit"]').click()
  await expect.poll(async () => {
    const res = await page.request.get('/api/me/')
    const data = await res.json()
    return Boolean(data?.authenticated && data?.user?.username === opts.username)
  }).toBe(true)
}

export async function fetchProgress(request: APIRequestContext, slug: string) {
  const res = await request.get(`/api/library/${encodeURIComponent(slug)}/progress/`)
  expect(res.ok()).toBeTruthy()
  return res.json()
}

export async function waitForProgressPage(
  request: APIRequestContext,
  slug: string,
  minPage: number,
) {
  await expect
    .poll(async () => {
      const data = await fetchProgress(request, slug)
      return data.exists ? Number(data.page) : -1
    })
    .toBeGreaterThanOrEqual(minPage)
}

/** Reset reader page bookmark so PDF/flip tests start from page 1 (0-indexed page=0). */
export async function resetProgressPage(
  page: Page,
  slug: string,
  mode: 'flip' | 'pdf' | 'listen' = 'flip',
) {
  const headers = await csrfHeaders(page)
  const res = await page.request.put(`/api/library/${encodeURIComponent(slug)}/progress/`, {
    headers,
    data: {
      mode,
      page: 0,
      position: 0,
      clear_audio: true,
      reopen: true,
      status: 'reading',
    },
  })
  expect(res.ok()).toBeTruthy()
}
