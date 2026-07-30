import type {
  AuthSessionResponse,
  CsrfResponse,
  LoginRequest,
  LogoutResponse,
  MeResponse,
  PasswordResetConfirmBody,
  PasswordResetConfirmError,
  PasswordResetConfirmResponse,
  PasswordResetRequestResponse,
  RegisterRequest,
  TokenRefreshResponse,
} from '../types/auth'
import { apiFetch } from './client'

export async function ensureCsrf() {
  return apiFetch<CsrfResponse>('/api/csrf/')
}

export async function fetchMe() {
  return apiFetch<MeResponse>('/api/me/')
}

export async function login({ username, password, next }: LoginRequest) {
  const body: LoginRequest = { username, password }
  if (next) body.next = next
  return apiFetch<AuthSessionResponse>('/api/login/', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function register(payload: RegisterRequest) {
  return apiFetch<AuthSessionResponse>('/api/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function requestPasswordReset({ email }: { email: string }) {
  return apiFetch<PasswordResetRequestResponse>('/api/password-reset/', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function confirmPasswordReset(payload: PasswordResetConfirmBody) {
  return apiFetch<PasswordResetConfirmResponse | PasswordResetConfirmError>('/api/password-reset/confirm/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function logout() {
  return apiFetch<LogoutResponse>('/api/logout/', { method: 'POST' })
}

export async function refreshToken() {
  return apiFetch<TokenRefreshResponse>('/api/token/refresh/', { method: 'POST' })
}
