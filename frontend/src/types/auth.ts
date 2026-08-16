/**
 * Auth API shapes — derived from backend/users/views.py
 * (MeAPIView, LoginAPIView, RegisterAPIView, logout/refresh/csrf/password-reset).
 */

export type AuthUser = {
  id: number
  username: string
  email: string
  is_staff: boolean
}

export type MeResponse =
  | { authenticated: false; user: null }
  | { authenticated: true; user: AuthUser }

export type LoginRequest = {
  username: string
  password: string
  remember_me?: boolean
  next?: string
}

export type RegisterRequest = {
  username: string
  email?: string
  password: string
  password_confirm: string
  next?: string
}

/** LoginAPIView / RegisterAPIView success JSON (cookies set separately). */
export type AuthSessionResponse = {
  detail: string
  redirect_url: string
  user: AuthUser
}

export type CsrfResponse = { detail: 'ok' | string }

export type LogoutResponse = { detail: string }

export type TokenRefreshResponse = { detail: string }

export type PasswordResetRequestBody = { email: string }

export type PasswordResetRequestResponse = { detail: string }

export type PasswordResetConfirmBody = {
  uid?: string
  uidb64?: string
  token: string
  password: string
  password_confirm: string
}

export type PasswordResetConfirmResponse = {
  detail: string
  redirect_url: string
}

/** Validation error payload returned by the password-reset confirmation endpoint. */
export type PasswordResetConfirmError = {
  detail?: string | string[]
  password?: string | string[]
  password_confirm?: string | string[]
}
