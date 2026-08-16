import { defineConfig, devices } from '@playwright/test'

const VITE = process.env.E2E_VITE_ORIGIN || 'http://127.0.0.1:5173'
const DJANGO = process.env.E2E_DJANGO_ORIGIN || 'http://127.0.0.1:8000'

/**
 * Root Playwright config for Libro.UZ cross-stack E2E.
 * Expect migrate + seed_e2e before run (see npm run test:e2e).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: VITE,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'react',
      use: { baseURL: VITE },
      testMatch: /.*\.spec\.ts/,
    },
  ],
  webServer: [
    {
      // Free :8000 only — do not touch :5173 (Vite may already be reuseExistingServer).
      command:
        'cross-env LIBRO_DEV_PORTS=8000 node scripts/free-dev-ports.mjs && cross-env SKIP_VITE_AUTOSTART=1 E2E_RELAX_THROTTLE=1 DEBUG=True python backend/manage.py runserver 127.0.0.1:8000',
      url: `${DJANGO}/api/csrf/`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ...process.env,
        E2E_RELAX_THROTTLE: '1',
        DEBUG: 'True',
        SKIP_VITE_AUTOSTART: '1',
        // Dummy merchant keys for application-level checkout→webhook E2E (not live sandbox).
        PAYMENTS_ENABLED: process.env.PAYMENTS_ENABLED || '1',
        BOOK_PRICE_TIYIN: process.env.BOOK_PRICE_TIYIN || '50000',
        PAYME_MERCHANT_ID: process.env.PAYME_MERCHANT_ID || 'payme-m',
        PAYME_MERCHANT_KEY: process.env.PAYME_MERCHANT_KEY || 'payme-secret-key',
        PAYME_TEST_MODE: process.env.PAYME_TEST_MODE || '1',
        CLICK_MERCHANT_ID: process.env.CLICK_MERCHANT_ID || '11',
        CLICK_SERVICE_ID: process.env.CLICK_SERVICE_ID || '22',
        CLICK_SECRET_KEY: process.env.CLICK_SECRET_KEY || 'click-secret',
      },
    },
    {
      // Free :5173 only so an orphaned Vite from a prior aborted run cannot block E2E.
      command:
        'cross-env LIBRO_DEV_PORTS=5173 node scripts/free-dev-ports.mjs && npm run dev --prefix frontend',
      url: VITE,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ...process.env,
      },
    },
  ],
})
