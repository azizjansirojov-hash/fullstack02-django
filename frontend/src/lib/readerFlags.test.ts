import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.resetModules()
  vi.unstubAllEnvs()
})

describe('isReactReaderEnabled', () => {
  it('always returns true (React reader is the only implementation)', async () => {
    const { isReactReaderEnabled } = await import('./readerFlags')
    expect(isReactReaderEnabled()).toBe(true)
  })
})

describe('buildReadHref', () => {
  it('builds React PDF href with autoplay', async () => {
    const { buildReadHref } = await import('./readerOrigin')
    expect(buildReadHref('/library/foo/read/', 'page', true)).toBe(
      '/library/foo/read/?mode=pdf#autoplay=1',
    )
  })

  it('builds React flip href', async () => {
    const { buildReadHref, buildReactReadHref } = await import('./readerOrigin')
    expect(buildReactReadHref('/library/foo/read/', 'focus', false)).toBe(
      '/library/foo/read/?mode=flip',
    )
    expect(buildReadHref('/library/foo/read/', 'focus', false)).toBe(
      '/library/foo/read/?mode=flip',
    )
  })
})
