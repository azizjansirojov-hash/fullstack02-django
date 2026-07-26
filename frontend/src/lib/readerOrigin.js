/**
 * Django HTML reader origin until the React reader is migrated.
 * - Local Vite (dev): default http://127.0.0.1:8000 when unset
 * - Docker/same-origin build: set VITE_DJANGO_ORIGIN= (empty) → window.location.origin
 * - Production builds must set VITE_DJANGO_ORIGIN (empty string is OK); unset fails loudly
 */
function resolveDjangoReaderOrigin() {
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
        '(use empty string or "same" for same-origin, or an absolute Django origin).',
    )
  }
  return 'http://127.0.0.1:8000'
}

export function getDjangoReaderOrigin() {
  return resolveDjangoReaderOrigin()
}

/** @deprecated Prefer getDjangoReaderOrigin() — kept for any legacy imports. */
export const DJANGO_READER_ORIGIN = getDjangoReaderOrigin()

/**
 * True when path is the Django immersive reader (not a React route).
 * @param {string} pathOrUrl
 */
export function isDjangoReaderPath(pathOrUrl) {
  if (!pathOrUrl) return false
  try {
    const path = pathOrUrl.startsWith('http')
      ? new URL(pathOrUrl).pathname
      : String(pathOrUrl).split('?')[0].split('#')[0]
    return /^\/library\/[^/]+\/read\/?$/.test(path)
  } catch {
    return false
  }
}

/**
 * Full URL for a post-login redirect into the Django reader (or absolute URL).
 * @param {string} redirectUrl
 */
export function resolvePostLoginHref(redirectUrl) {
  if (!redirectUrl) return null
  if (redirectUrl.startsWith('http://') || redirectUrl.startsWith('https://')) {
    return redirectUrl
  }
  const path = redirectUrl.startsWith('/') ? redirectUrl : `/${redirectUrl}`
  if (isDjangoReaderPath(path)) {
    return `${getDjangoReaderOrigin()}${path}`
  }
  return null
}

/**
 * Build a full URL to the Django reader with mode / autoplay.
 * @param {string} readUrl relative path e.g. /library/slug/read/
 * @param {'focus'|'page'} mode
 * @param {boolean} autoplay
 */
export function buildDjangoReadHref(readUrl, mode = 'focus', autoplay = false) {
  const url = new URL(readUrl || '/', getDjangoReaderOrigin())
  if (mode === 'page') {
    url.searchParams.set('mode', 'pdf')
  } else {
    url.searchParams.set('mode', 'flip')
  }
  let href = `${url.origin}${url.pathname}${url.search}`
  if (autoplay) {
    href += '#autoplay=1'
  }
  return href
}

export function truncateWords(text, count = 18) {
  if (!text) return ''
  const words = String(text).trim().split(/\s+/)
  if (words.length <= count) return words.join(' ')
  return `${words.slice(0, count).join(' ')} …`
}
