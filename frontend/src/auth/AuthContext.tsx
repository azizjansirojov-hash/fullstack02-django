import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { ApiResult } from '../api/client'
import {
  ensureCsrf,
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  refreshToken as apiRefreshToken,
  register as apiRegister,
} from '../api/auth'
import type {
  AuthSessionResponse,
  AuthUser,
  LoginRequest,
  RegisterRequest,
} from '../types/auth'

/**
 * Shared auth state. `user` is always `AuthUser | null` (never undefined / {}).
 * `isAuthenticated` is derived as `Boolean(user)` — same invariant as the JSX version.
 *
 * Bootstrap: `ready === false` until the initial CSRF + /api/me/ (+ optional refresh) finishes.
 * During that window, `user` usually stays `null`, but after a successful `refresh()` call
 * and before `setReady(true)`, React can paint once with `user` set and `ready` still false.
 * Route gates (RequireAuth / GuestOnly / HomeRedirect) wait on `ready`; they do not trust
 * `isAuthenticated` alone while loading.
 */
export type AuthContextValue = {
  user: AuthUser | null
  ready: boolean
  isAuthenticated: boolean
  login: (credentials: LoginRequest) => Promise<ApiResult<AuthSessionResponse>>
  register: (payload: RegisterRequest) => Promise<ApiResult<AuthSessionResponse>>
  logout: () => Promise<void>
  refresh: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function userFromPayload(payload: AuthUser | null | undefined): AuthUser | null {
  if (!payload) return null
  return {
    id: payload.id,
    username: payload.username,
    email: payload.email,
    is_staff: payload.is_staff ?? false,
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [ready, setReady] = useState(false)

  const refresh = useCallback(async () => {
    const { response, data } = await fetchMe()
    if (response.ok && data?.authenticated) {
      setUser(userFromPayload(data.user))
      return true
    }
    setUser(null)
    return false
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await ensureCsrf()
        if (cancelled) return

        let ok = await refresh()
        if (cancelled) return

        // Access may be expired while refresh cookie is still valid.
        if (!ok) {
          const { response } = await apiRefreshToken()
          if (cancelled) return
          if (response.ok) {
            ok = await refresh()
          }
        }
        if (!ok && !cancelled) {
          setUser(null)
        }
      } catch {
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setReady(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refresh])

  const login = useCallback(async ({ username, password, next }: LoginRequest) => {
    const result = await apiLogin({ username, password, next })
    if (result.response.ok && result.data?.user) {
      setUser(userFromPayload(result.data.user))
    }
    return result
  }, [])

  const register = useCallback(async (payload: RegisterRequest) => {
    const result = await apiRegister(payload)
    if (result.response.ok && result.data?.user) {
      setUser(userFromPayload(result.data.user))
    }
    return result
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      ready,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      refresh,
    }),
    [user, ready, login, register, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
