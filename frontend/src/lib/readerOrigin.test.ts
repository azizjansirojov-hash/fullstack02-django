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

describe('resolvePostLoginHref', () => {
  it('returns relative path for same-origin reader absolute URL', async () => {
    const { resolvePostLoginHref } = await import('./readerOrigin')
    const href = `${window.location.origin}/library/some-book/read`
    expect(resolvePostLoginHref(href)).toBe('/library/some-book/read')
  })

  it('returns null for cross-origin absolute reader URL', async () => {
    const { resolvePostLoginHref } = await import('./readerOrigin')
    expect(resolvePostLoginHref('https://evil.com/library/some-book/read')).toBeNull()
  })

  it('returns null for same-origin non-reader absolute URL', async () => {
    const { resolvePostLoginHref } = await import('./readerOrigin')
    expect(resolvePostLoginHref(`${window.location.origin}/admin`)).toBeNull()
  })

  it('returns relative reader path unchanged', async () => {
    const { resolvePostLoginHref } = await import('./readerOrigin')
    expect(resolvePostLoginHref('/library/some-book/read')).toBe('/library/some-book/read')
  })

  it('returns null for relative non-reader path', async () => {
    const { resolvePostLoginHref } = await import('./readerOrigin')
    expect(resolvePostLoginHref('/settings')).toBeNull()
  })

  it('returns null for null, undefined, or empty string', async () => {
    const { resolvePostLoginHref } = await import('./readerOrigin')
    expect(resolvePostLoginHref(null)).toBeNull()
    expect(resolvePostLoginHref(undefined)).toBeNull()
    expect(resolvePostLoginHref('')).toBeNull()
  })
})
