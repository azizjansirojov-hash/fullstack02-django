import { afterEach, describe, expect, it, vi } from 'vitest'

describe('readerOrigin helpers', () => {
  afterEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
  })

  it('defaults to localhost in development when unset', async () => {
    vi.stubEnv('PROD', false)
    vi.stubEnv('DEV', true)
    vi.stubEnv('VITE_DJANGO_ORIGIN', undefined)
    const { getDjangoReaderOrigin, isDjangoReaderPath, truncateWords } =
      await import('./readerOrigin.js')
    expect(getDjangoReaderOrigin()).toBe('http://127.0.0.1:8000')
    expect(isDjangoReaderPath('/library/foo/read/')).toBe(true)
    expect(isDjangoReaderPath('/library/foo/')).toBe(false)
    expect(truncateWords('one two three four', 3)).toBe('one two three …')
  })

  it('throws in production when VITE_DJANGO_ORIGIN is unset', async () => {
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_DJANGO_ORIGIN', undefined)
    await expect(import('./readerOrigin.js')).rejects.toThrow(/VITE_DJANGO_ORIGIN/)
  })

  it('allows empty VITE_DJANGO_ORIGIN in production (same-origin)', async () => {
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_DJANGO_ORIGIN', '')
    const { getDjangoReaderOrigin } = await import('./readerOrigin.js')
    expect(getDjangoReaderOrigin()).toBe('http://127.0.0.1:8000')
  })
})
