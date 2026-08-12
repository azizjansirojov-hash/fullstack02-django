import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { fetchProgress, loginViaUi, resetProgressPage } from './helpers/auth'
import { openReactFlip, openReactListen } from './helpers/reader'

test.describe('listen / audio overlay + progress', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
    await resetProgressPage(page, E2E.pdSlug, 'flip')
  })

  test('React: audio overlay plays and currentTime advances (real playback)', async ({ page }) => {
    await openReactListen(page)

    const audio = page.locator('audio.flip-reader-view__audio, .flip-reader-view audio')
    await expect(audio).toHaveCount(1)

    // Wait until gated media metadata is available (playable fixture MP3).
    await expect
      .poll(async () => {
        return page.evaluate(() => {
          const el = document.querySelector('audio') as HTMLAudioElement | null
          return el && Number.isFinite(el.duration) && el.duration > 0 ? el.duration : 0
        })
      }, { timeout: 20_000 })
      .toBeGreaterThan(0)

    const progressed = await page.evaluate(async () => {
      const el = document.querySelector('audio') as HTMLAudioElement | null
      if (!el) throw new Error('no audio')
      el.muted = true
      el.currentTime = 0
      try {
        await el.play()
      } catch (err) {
        return { ok: false, reason: String(err), currentTime: el.currentTime, error: el.error?.code }
      }
      const start = el.currentTime
      await new Promise((r) => setTimeout(r, 800))
      return {
        ok: !el.paused && el.currentTime > start,
        paused: el.paused,
        start,
        currentTime: el.currentTime,
        duration: el.duration,
        error: el.error?.code ?? null,
      }
    })

    expect(progressed.ok, JSON.stringify(progressed)).toBeTruthy()
    expect(Number(progressed.currentTime)).toBeGreaterThan(Number(progressed.start))

    await page.evaluate(() => {
      const el = document.querySelector('audio') as HTMLAudioElement | null
      el?.pause()
    })

    await expect
      .poll(async () => {
        const data = await fetchProgress(page.request, E2E.pdSlug)
        return data.exists && data.mode === 'listen' ? Number(data.position) : -1
      }, { timeout: 20_000 })
      .toBeGreaterThan(0)
  })

  test('React: audio overlay plays and saves listen progress on pause', async ({ page }) => {
    await openReactListen(page)

    const audio = page.locator('audio.flip-reader-view__audio, .flip-reader-view audio')
    await expect(audio).toHaveCount(1)

    await page.evaluate(async () => {
      const el = document.querySelector('audio') as HTMLAudioElement | null
      if (!el) throw new Error('no audio')
      el.muted = true
      try {
        await el.play()
      } catch {
        /* autoplay policies — still seek + pause to force save */
      }
      el.currentTime = Math.min(1.5, el.duration || 1.5)
      el.dispatchEvent(new Event('timeupdate'))
      el.pause()
    })

    await expect
      .poll(async () => {
        const data = await fetchProgress(page.request, E2E.pdSlug)
        return data.exists && data.mode === 'listen' ? Number(data.position) : -1
      }, { timeout: 20_000 })
      .toBeGreaterThan(0)

    // Full reload of the reader URL — progress bookmark must survive.
    await page.reload()
    await expect
      .poll(async () => {
        const data = await fetchProgress(page.request, E2E.pdSlug)
        return data.exists ? Number(data.position) : -1
      }, { timeout: 20_000 })
      .toBeGreaterThan(0)

    const afterReload = await fetchProgress(page.request, E2E.pdSlug)
    expect(Number(afterReload.position)).toBeGreaterThan(0)
  })

  test('React: toolbar Tinglash starts playback without modal autoplay hash', async ({ page }) => {
    // Count play() calls so we still assert the toolbar path starts playback.
    await page.addInitScript(() => {
      ;(window as unknown as { __libroPlayCalls?: number }).__libroPlayCalls = 0
      const proto = HTMLMediaElement.prototype
      const originalPlay = proto.play
      proto.play = function playPatched(...args: unknown[]) {
        const w = window as unknown as { __libroPlayCalls?: number }
        w.__libroPlayCalls = (w.__libroPlayCalls || 0) + 1
        return originalPlay.apply(this, args as [])
      }
    })

    await openReactFlip(page)

    const shell = page.locator('.flip-reader-view__audio-shell')
    await expect(shell).toHaveAttribute('hidden', '')

    const callsBefore = await page.evaluate(
      () => (window as unknown as { __libroPlayCalls?: number }).__libroPlayCalls || 0,
    )

    await page.getByRole('button', { name: 'Tinglash' }).click()

    await expect(shell).not.toHaveAttribute('hidden', '')
    await expect
      .poll(async () => {
        return page.evaluate(
          () => (window as unknown as { __libroPlayCalls?: number }).__libroPlayCalls || 0,
        )
      }, { timeout: 10_000 })
      .toBeGreaterThan(callsBefore)
  })
})
