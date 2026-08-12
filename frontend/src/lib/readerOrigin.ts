/**
 * Reader launch URLs and post-login redirects.
 * - Local Vite (dev): same-origin relative paths
 * - Docker/same-origin build: VITE_DJANGO_ORIGIN empty → window.location.origin when needed
 */

/**
 * Origin used when an absolute backend URL is required (rare; prefer relative SPA paths).
 */
export function getAppOrigin(): string {
  const raw = import.meta.env.VITE_DJANGO_ORIGIN
  if (raw === '' || raw === 'same') {
    if (typeof window !== 'undefined' && window.location?.origin) {
      return window.location.origin
    }
    return 'http://127.0.0.1:8000'
  }
  if (raw) {
    return String(raw).replace(/\/$/, '')
  }
  if (import.meta.env.PROD) {
    throw new Error(
      'VITE_DJANGO_ORIGIN must be set for production builds ' +
        '(use empty string or "same" for same-origin, or an absolute origin).',
    )
  }
  return 'http://127.0.0.1:8000'
}

/** @deprecated Use getAppOrigin() — alias retained for existing tests during rename. */
export function getDjangoReaderOrigin(): string {
  return getAppOrigin()
}

/**
 * True when path is the immersive reader route.
 */
export function isReaderPath(pathOrUrl: string | null | undefined): boolean {
  if (!pathOrUrl) return false
  try {
    const path = pathOrUrl.startsWith('http')
      ? new URL(pathOrUrl).pathname
      : String(pathOrUrl).split('?')[0]!.split('#')[0]
    return /^\/library\/[^/]+\/read\/?$/.test(path ?? '')
  } catch {
    return false
  }
}

/** @deprecated Prefer isReaderPath */
export function isDjangoReaderPath(pathOrUrl: string | null | undefined): boolean {
  return isReaderPath(pathOrUrl)
}

/**
 * Same-origin reader href for post-login assign(); otherwise null for navigate().
 */
export function resolvePostLoginHref(redirectUrl: string | null | undefined): string | null {
  if (!redirectUrl) return null

  // Security (open-redirect fix): an absolute URL is only ever safe to hand
  // to window.location.assign() if it (a) resolves to THIS app's own origin
  // and (b) targets the reader route. Anything else — a different host, or
  // a same-host path that isn't the reader — must fall through to `null` so
  // the caller performs an in-app, same-origin navigate() instead of a real
  // browser navigation.
  if (redirectUrl.startsWith('http://') || redirectUrl.startsWith('https://')) {
    let parsed: URL
    try {
      parsed = new URL(redirectUrl)
    } catch {
      return null
    }
    const currentOrigin = typeof window !== 'undefined' ? window.location?.origin : undefined
    const isSameOrigin = Boolean(currentOrigin) && parsed.origin === currentOrigin
    if (isSameOrigin && isReaderPath(parsed.pathname)) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`
    }
    return null
  }

  const path = redirectUrl.startsWith('/') ? redirectUrl : `/${redirectUrl}`
  if (isReaderPath(path)) {
    return path
  }
  return null
}

export type ReaderLaunchMode = 'focus' | 'page'

/**
 * Same-origin React reader URL (relative path + query + hash).
 */
export function buildReactReadHref(
  readUrl: string | null | undefined,
  mode: ReaderLaunchMode = 'focus',
  autoplay = false,
): string {
  const origin =
    typeof window !== 'undefined' && window.location?.origin
      ? window.location.origin
      : 'http://127.0.0.1:5173'
  const url = new URL(readUrl || '/', origin)
  if (mode === 'page') {
    url.searchParams.set('mode', 'pdf')
  } else {
    url.searchParams.set('mode', 'flip')
  }
  let href = `${url.pathname}${url.search}`
  if (autoplay) {
    href += '#autoplay=1'
  }
  return href
}

/**
 * Launch href for the React reader.
 */
export function buildReadHref(
  readUrl: string | null | undefined,
  mode: ReaderLaunchMode = 'focus',
  autoplay = false,
): string {
  return buildReactReadHref(readUrl, mode, autoplay)
}

export function truncateWords(text: string | null | undefined, count = 18): string {
  if (!text) return ''
  const words = String(text).trim().split(/\s+/)
  if (words.length <= count) return words.join(' ')
  return `${words.slice(0, count).join(' ')} …`
}
