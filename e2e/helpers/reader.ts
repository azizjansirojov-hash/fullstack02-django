import { expect, type Page } from '@playwright/test'
import { E2E } from '../fixtures'

/** React immersive reader (Phase 4 — only reader implementation). */
export async function openReactFlip(page: Page, slug = E2E.pdSlug) {
  await page.goto(`/library/${slug}/read?mode=flip`)
  await expect(page.locator('.reader-shell')).toBeVisible()
  await expect(page.locator('.flip-reader-view')).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.page').first()).toBeVisible({ timeout: 30_000 })
}

export async function openReactPdf(page: Page, slug = E2E.pdSlug) {
  await page.goto(`/library/${slug}/read?mode=pdf`)
  await expect(page.locator('.pdf-reader-mode')).toBeVisible({ timeout: 30_000 })
}

export async function openReactListen(page: Page, slug = E2E.pdSlug) {
  await page.goto(`/library/${slug}/read?mode=flip#autoplay=1`)
  await expect(page.locator('.flip-reader-view')).toBeVisible({ timeout: 30_000 })
  const tinglash = page.getByRole('button', { name: 'Tinglash' })
  if (await tinglash.isVisible()) {
    // Autoplay may already open the bar; otherwise open it.
    const shell = page.locator('.flip-reader-view__audio-shell')
    if (await shell.getAttribute('hidden') !== null) {
      await tinglash.click()
    }
  }
  await expect(page.locator('.flip-reader-view__audio-shell')).not.toHaveAttribute('hidden', '')
}

export function reactPageCounter(page: Page) {
  return page.locator('.flip-book-mode__counter, .book-reader__counter').first()
}
