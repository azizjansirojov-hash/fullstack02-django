export type ApiResult<T> = {
  response: Response
  data: T | null
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1')}=([^;]*)`),
  )
  return match ? decodeURIComponent(match[1]!) : null
}

export function getCsrfToken(): string {
  return getCookie('csrftoken') || ''
}

async function rawFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  const method = (options.method || 'GET').toUpperCase()
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }

  if (options.body !== undefined && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    headers['X-CSRFToken'] = getCsrfToken()
  }

  const response = await fetch(path, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  let data: T | null = null
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    data = (await response.json()) as T
  }

  return { response, data }
}

/**
 * Fetch wrapper with credentials + CSRF.
 * On 401 (except auth endpoints), tries cookie refresh once then retries.
 * Throws if the Vite proxy / network cannot reach Django.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
  _retried = false,
): Promise<ApiResult<T>> {
  let result: ApiResult<T>
  try {
    result = await rawFetch<T>(path, options)
  } catch (err) {
    const error = new Error(
      'Backendga ulanib bo‘lmadi. Django runserver (127.0.0.1:8000) ishlamayapti.',
    )
    error.cause = err
    throw error
  }

  // Vite returns 500 HTML/text when the proxy target is down
  if (
    result.response.status === 500 &&
    result.data === null &&
    (path.startsWith('/api/') || path.startsWith('/media/'))
  ) {
    throw new Error(
      'Backendga ulanib bo‘lmadi. Django runserver (127.0.0.1:8000) ishlamayapti.',
    )
  }

  const isAuthPath =
    path.startsWith('/api/login') ||
    path.startsWith('/api/register') ||
    path.startsWith('/api/token/refresh') ||
    path.startsWith('/api/csrf') ||
    path.startsWith('/api/logout')

  if (result.response.status === 401 && !_retried && !isAuthPath) {
    const refresh = await rawFetch('/api/token/refresh/', { method: 'POST' })
    if (refresh.response.ok) {
      return apiFetch<T>(path, options, true)
    }
  }

  return result
}
