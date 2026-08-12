import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import AppShell, { AuthNavSteps, SecureStatusChip } from '../components/layout/AppShell'
import { useAuth } from '../auth/AuthContext'
import { resolvePostLoginHref } from '../lib/readerOrigin'
import { EyeIcon, firstErrorMessage } from '../components/auth/authFormShared'

type AlertState = { type: 'success' | 'error'; message: string }

function LockIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <rect x="4" y="8" width="12" height="9" rx="2" />
      <path d="M7 8V6a3 3 0 0 1 6 0v2" />
    </svg>
  )
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || ''

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [alert, setAlert] = useState<AlertState | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [successUser, setSuccessUser] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFieldErrors({})
    setAlert(null)
    setLoading(true)

    try {
      const { response, data } = await login({ username, password, next: next || undefined })

      if (response.ok) {
        setSuccessUser(data?.user?.username || username)
        setAlert({ type: 'success', message: data?.detail || 'Signed in successfully.' })
        const redirectUrl = data?.redirect_url || next || '/library/'
        window.setTimeout(() => {
          // Library intro plays on the dashboard; Django reader path hard-navigates when flagged.
          const djangoHref = resolvePostLoginHref(redirectUrl)
          if (djangoHref) {
            window.location.assign(djangoHref)
            return
          }
          const path = redirectUrl.startsWith('http')
            ? new URL(redirectUrl).pathname
            : redirectUrl
          navigate(path.replace(/\/$/, '') || '/library', { replace: true })
        }, 700)
        return
      }

      if (!data || typeof data !== 'object') {
        setAlert({
          type: 'error',
          message:
            response.status >= 500 || response.status === 0
              ? 'Backend javob bermadi. Django runserver (:8000) ishlayotganini tekshiring.'
              : `Kirish muvaffaqiyatsiz (HTTP ${response.status}).`,
        })
        return
      }

      const errors = data as Record<string, unknown>
      const nextFieldErrors: Record<string, string> = {}
      Object.entries(errors).forEach(([field, messages]) => {
        if (field === 'detail' || field === 'non_field_errors') return
        nextFieldErrors[field] = firstErrorMessage(messages)
      })
      setFieldErrors(nextFieldErrors)
      const detail = errors.detail || errors.non_field_errors
      setAlert({
        type: 'error',
        message: firstErrorMessage(
          detail || Object.values(nextFieldErrors)[0] || Object.values(errors)[0] ||
            `Kirish muvaffaqiyatsiz (HTTP ${response.status}).`
        ),
      })
    } catch (_err) {
      setAlert({
        type: 'error',
        message:
          'Backendga ulanib bo‘lmadi. Django :8000 da ishlayotganini tekshiring, keyin qayta urinib ko‘ring.',
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell
      title="Kirish"
      metaDescription="Hisobingizga xavfsiz va maxfiy kirish."
      wordmarkTo="/library"
      navCenter={<AuthNavSteps active="login" />}
      navStatus={<SecureStatusChip />}
      navAction={
        <>
          <Link className="nav__text-link" to="/library">
            Kutubxona
          </Link>
          <Link className="nav__action" to="/register">
            Hisob yaratish
          </Link>
        </>
      }
    >
      <section className="auth-layout">
        <div className="hero" aria-labelledby="hero-title">
          <span className="pill">
            <span className="pill__dot" />
            Welcome back to Libro.UZ
          </span>
          <h1 id="hero-title" className="hero__title">
            <span>SIGN</span>
            <span className="hero__title--accent">IN.</span>
          </h1>
          <p className="hero__lead">Pick up right where you left off.</p>
          <p className="hero__copy">
            Your account keeps everything important together, with privacy and security built into
            every layer.
          </p>
          <ul className="hero__stats" aria-hidden="true">
            <li>
              <strong>256-bit</strong>
              <span>Encryption</span>
            </li>
            <li>
              <strong>HttpOnly</strong>
              <span>JWT cookies</span>
            </li>
            <li>
              <strong>CSRF</strong>
              <span>Protected</span>
            </li>
          </ul>
        </div>

        <div className="auth-column">
          <section className="auth-card" aria-labelledby="login-title">
            <div className="auth-card__header">
              <p className="section-label">Libro.UZ hisobi</p>
              <h2 id="login-title">Kirish</h2>
              <p className="auth-card__subtitle">
                Davom etish uchun foydalanuvchi nomingizni kiriting.
              </p>
            </div>

            {alert && (
              <div className={`alert alert--${alert.type}`} role="status" aria-live="polite">
                {alert.message}
              </div>
            )}

            {successUser ? (
              <div className="success-panel">
                <strong>Welcome, {successUser}.</strong>
                <p>Opening your library…</p>
              </div>
            ) : (
              <form className="auth-form" onSubmit={handleSubmit} noValidate>
                <div className="field">
                  <label htmlFor="id_username">Foydalanuvchi nomi</label>
                  <input
                    type="text"
                    id="id_username"
                    name="username"
                    autoComplete="username"
                    required
                    maxLength={150}
                    placeholder="Foydalanuvchi nomi"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className={fieldErrors.username ? 'is-invalid' : undefined}
                    aria-invalid={fieldErrors.username ? 'true' : undefined}
                    aria-describedby="username-error"
                  />
                  <p id="username-error" className="field__error" hidden={!fieldErrors.username}>
                    {fieldErrors.username || ''}
                  </p>
                </div>

                <div className="field">
                  <label htmlFor="id_password">Parol</label>
                  <div className="input-with-action">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      id="id_password"
                      name="password"
                      autoComplete="current-password"
                      required
                      placeholder="Parol"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className={fieldErrors.password ? 'is-invalid' : undefined}
                      aria-invalid={fieldErrors.password ? 'true' : undefined}
                      aria-describedby="password-error"
                    />
                    <button
                      type="button"
                      className="toggle-password"
                      aria-label={showPassword ? 'Parolni yashirish' : 'Parolni ko‘rsatish'}
                      onClick={() => setShowPassword((v) => !v)}
                    >
                      <EyeIcon />
                      <span>{showPassword ? 'Yashir' : 'Ko‘rsat'}</span>
                    </button>
                  </div>
                  <p id="password-error" className="field__error" hidden={!fieldErrors.password}>
                    {fieldErrors.password || ''}
                  </p>
                </div>

                <button type="submit" className="primary-button" disabled={loading}>
                  <span className="button-label">
                    {loading ? 'Signing in…' : 'Davom etish'}
                  </span>
                  <span className="button-spinner" aria-hidden="true" hidden={!loading} />
                  <svg className="button-arrow" viewBox="0 0 20 20" aria-hidden="true">
                    <path d="m7.5 4.5 5 5.5-5 5.5" />
                  </svg>
                </button>
                <p className="privacy-note" style={{ marginTop: '0.75rem' }}>
                  <Link to="/password-reset">Parolni unutdingizmi?</Link>
                </p>
              </form>
            )}

            <div className="auth-card__divider">
              <span>Libro.UZ’da yangimisiz?</span>
            </div>
            <Link className="secondary-button" to="/register">
              Libro.UZ hisobini yaratish
            </Link>
          </section>
          <p className="privacy-note">
            <LockIcon />
            Kirishingiz xavfsiz JWT cookie’lar bilan himoyalangan.
          </p>
        </div>
      </section>
    </AppShell>
  )
}

