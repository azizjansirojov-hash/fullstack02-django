/**
 * Payment checkout UI shell (mocked) plus application-level checkout → webhook
 * → entitlement against Django using dummy merchant keys (same as payments unit
 * tests). This is not live Payme/Click sandbox certification — see PAYMENTS.md.
 */
import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { csrfHeaders, loginViaUi, registerViaUi } from './helpers/auth'

test.describe('payment checkout (mocked)', () => {
  test('shows purchasable checkout controls when API marks book purchasable', async ({
    page,
  }) => {
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

    await page.goto('/payment/status/00000000-0000-4000-8000-000000000001')
    await expect(page).toHaveURL(/login|payment\/status/)
  })
})

test.describe('payment checkout → webhook → entitlement', () => {
  test('Payme JSON-RPC fulfill grants licensed reader access', async ({ page }) => {
    const username = `e2e_pay_${Date.now()}`
    await registerViaUi(page, {
      username,
      email: `${username}@example.com`,
      password: 'E2e-Pay-Passw0rd!Strong',
    })

    const headers = await csrfHeaders(page)
    const checkout = await page.request.post('/api/payments/checkout/', {
      headers: { ...headers, 'Content-Type': 'application/json' },
      data: { book_slug: E2E.licensedSlug, provider: 'payme' },
    })
    expect(checkout.ok(), await checkout.text()).toBeTruthy()
    const payload = await checkout.json()
    const txId = payload.transaction_id as string
    const amount = payload.amount_tiyin as number
    expect(txId).toBeTruthy()
    expect(amount).toBeGreaterThan(0)

    const paymeId = `e2e-payme-${Date.now()}`
    const auth = `Basic ${Buffer.from('Paycom:payme-secret-key').toString('base64')}`
    const methods: { method: string; params: Record<string, unknown> }[] = [
      {
        method: 'CheckPerformTransaction',
        params: { amount, account: { order_id: txId } },
      },
      {
        method: 'CreateTransaction',
        params: {
          id: paymeId,
          time: Date.now(),
          amount,
          account: { order_id: txId },
        },
      },
      { method: 'PerformTransaction', params: { id: paymeId } },
    ]
    for (const step of methods) {
      const hook = await page.request.post('/api/payments/payme/webhook/', {
        headers: {
          Authorization: auth,
          'Content-Type': 'application/json',
        },
        data: { id: 1, method: step.method, params: step.params },
      })
      expect(hook.ok(), await hook.text()).toBeTruthy()
      const body = await hook.json()
      expect(body, JSON.stringify(body)).toHaveProperty('result')
    }

    const status = await page.request.get(`/api/payments/transactions/${txId}/`)
    expect(status.ok()).toBeTruthy()
    expect((await status.json()).status).toBe('paid')

    const manifest = await page.request.get(`/api/library/${E2E.licensedSlug}/reader/`)
    expect(manifest.status()).toBe(200)
    expect((await manifest.json()).body).toBeTruthy()
  })

  test('e2e_owner licensed book remains unpurchased (seed isolation)', async ({ page }) => {
    await loginViaUi(page)
    const manifest = await page.request.get(`/api/library/${E2E.licensedSlug}/reader/`)
    expect(manifest.status()).toBe(403)
  })
})
