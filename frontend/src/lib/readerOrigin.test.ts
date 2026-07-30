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
    const { getAppOrigin, isReaderPath, truncateWords } = await import('./readerOrigin')
    expect(getAppOrigin()).toBe('http://127.0.0.1:8000')
    expect(isReaderPath('/library/foo/read/')).toBe(true)
    expect(isReaderPath('/library/foo/')).toBe(false)
    expect(truncateWords('one two three four', 3)).toBe('one two three …')
  })

  it('throws in production when VITE_DJANGO_ORIGIN is unset and origin is requested', async () => {
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_DJANGO_ORIGIN', undefined)
    const { getAppOrigin } = await import('./readerOrigin')
    expect(() => getAppOrigin()).toThrow(/VITE_DJANGO_ORIGIN/)
  })

  it('allows empty VITE_DJANGO_ORIGIN in production (same-origin)', async () => {
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_DJANGO_ORIGIN', '')
    const { getAppOrigin } = await import('./readerOrigin')
    expect(getAppOrigin()).toBe(window.location.origin)
  })
})
