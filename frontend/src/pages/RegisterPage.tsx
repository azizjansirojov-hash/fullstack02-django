import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import AppShell, { AuthNavSteps, SecureStatusChip } from '../components/layout/AppShell'
import { useAuth } from '../auth/AuthContext'
import { resolvePostLoginHref } from '../lib/readerOrigin'
import { EyeIcon, firstErrorMessage } from '../components/auth/authFormShared'
import '../assets/css/auth.css'

type AlertState = { type: 'success' | 'error'; message: string }

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.5 20 5.4v6.3c0 5.4-3.3 9-8 10.8-4.7-1.8-8-5.4-8-10.8V5.4L12 2.5Z" />
      <path d="m8.5 12 2.1 2.1 4.9-5" />
    </svg>
  )
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  )
}

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || ''

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [alert, setAlert] = useState<AlertState | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFieldErrors({})
    setAlert(null)
    setLoading(true)

    try {
      const { response, data } = await register({
        username,
        email,
        password,
        password_confirm: passwordConfirm,
        ...(next ? { next } : {}),
      })

      if (response.ok) {
        setAlert({
          type: 'success',
          message: data?.detail || 'Account created successfully.',
        })
        const redirectUrl = data?.redirect_url || next || '/library/'
        window.setTimeout(() => {
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
              : `Ro‘yxatdan o‘tish muvaffaqiyatsiz (HTTP ${response.status}).`,
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
          detail ||
            Object.values(nextFieldErrors)[0] ||
            Object.values(errors)[0] ||
            `Ro‘yxatdan o‘tish muvaffaqiyatsiz (HTTP ${response.status}).`
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
      title="Hisob yaratish"
      metaDescription="Libro.UZ hisobini yarating."
      wordmarkTo="/library"
      navCenter={<AuthNavSteps active="register" />}
      navStatus={<SecureStatusChip />}
      navAction={
        <>
          <Link className="nav__text-link" to="/library">
            Kutubxona
          </Link>
          <Link className="nav__action" to="/login">
            Kirish
          </Link>
        </>
      }
    >
      <section className="auth-layout auth-layout--register">
        <div className="hero" aria-labelledby="hero-title">
          <span className="pill">
            <span className="pill__dot" />
            Bugun Libro.UZ’ga qo‘shiling
          </span>
          <h1 id="hero-title" className="hero__title">
            <span>HISOB</span>
            <span className="hero__title--accent">YARATISH.</span>
          </h1>
          <p className="hero__lead">Bitta hisob. Imkoniyatlar olami.</p>
          <p className="hero__copy">
            Yaratish oson. Ishlatish qulay. Ro‘yxatdan o‘tgan zahoti himoyalangan.
          </p>
          <ul className="feature-list" aria-label="Hisob afzalliklari">
            <li>
              <span className="feature-icon">
                <ShieldIcon />
              </span>
              <span>
                <strong>Maxfiylik asosida</strong>Ma’lumotlaringiz himoyalangan.
              </span>
            </li>
            <li>
              <span className="feature-icon">
                <ClockIcon />
              </span>
              <span>
                <strong>Bir zumda tayyor</strong>Hisobni bitta oddiy qadamda yarating.
              </span>
            </li>
          </ul>
        </div>

        <div className="auth-column">
          <section className="auth-card auth-card--register" aria-labelledby="register-title">
            <div className="auth-card__header">
              <p className="section-label">Libro.UZ hisobi</p>
              <h2 id="register-title">Hisobingizni yarating</h2>
              <p className="auth-card__subtitle">Bir necha ma’lumot. Keyin hammasi tayyor.</p>
            </div>

            {alert && (
              <div className={`alert alert--${alert.type}`} role="status" aria-live="polite">
                {alert.message}
              </div>
            )}

            <form className="auth-form" onSubmit={handleSubmit} noValidate>
                <div className="field-row">
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
                    />
                    <p className="field__hint">Harflar, raqamlar va @/./+/-/_.</p>
                    <p className="field__error" hidden={!fieldErrors.username}>
                      {fieldErrors.username || ''}
                    </p>
                  </div>

                  <div className="field">
                    <label htmlFor="id_email">
                      Email <span className="optional">Ixtiyoriy</span>
                    </label>
                    <input
                      type="email"
                      id="id_email"
                      name="email"
                      autoComplete="email"
                      placeholder="name@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className={fieldErrors.email ? 'is-invalid' : undefined}
                    />
                    <p className="field__hint">Faqat hisobingiz uchun.</p>
                    <p className="field__error" hidden={!fieldErrors.email}>
                      {fieldErrors.email || ''}
                    </p>
                  </div>
                </div>

                <div className="field">
                  <label htmlFor="id_password">Parol</label>
                  <div className="input-with-action">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      id="id_password"
                      name="password"
                      autoComplete="new-password"
                      required
                      minLength={8}
                      placeholder="Parol yarating"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className={fieldErrors.password ? 'is-invalid' : undefined}
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
                  <p className="field__hint">
                    Kamida 8 belgi. Oddiy yoki shaxsiy parollardan saqlaning.
                  </p>
                  <p className="field__error" hidden={!fieldErrors.password}>
                    {fieldErrors.password || ''}
                  </p>
                </div>

                <div className="field">
                  <label htmlFor="id_password_confirm">Parolni tasdiqlang</label>
                  <div className="input-with-action">
                    <input
                      type={showConfirm ? 'text' : 'password'}
                      id="id_password_confirm"
                      name="password_confirm"
                      autoComplete="new-password"
                      required
                      minLength={8}
                      placeholder="Parolni tasdiqlang"
                      value={passwordConfirm}
                      onChange={(e) => setPasswordConfirm(e.target.value)}
                      className={fieldErrors.password_confirm ? 'is-invalid' : undefined}
                    />
                    <button
                      type="button"
                      className="toggle-password"
                      aria-label={showConfirm ? 'Parolni yashirish' : 'Parolni ko‘rsatish'}
                      onClick={() => setShowConfirm((v) => !v)}
                    >
                      <EyeIcon />
                      <span>{showConfirm ? 'Yashir' : 'Ko‘rsat'}</span>
                    </button>
                  </div>
                  <p className="field__error" hidden={!fieldErrors.password_confirm}>
                    {fieldErrors.password_confirm || ''}
                  </p>
                </div>

                <p className="terms-copy">
                  Davom etib,{' '}
                  <a href="/terms/" target="_blank" rel="noreferrer">
                    Foydalanish shartlari
                  </a>{' '}
                  va{' '}
                  <a href="/privacy/" target="_blank" rel="noreferrer">
                    Maxfiylik siyosati
                  </a>
                  ga rozilik bildirasiz. Huquqlar uchun:{' '}
                  <a href="/rights-report/" target="_blank" rel="noreferrer">
                    xabar berish
                  </a>
                  .
                </p>

                <button type="submit" className="primary-button" disabled={loading}>
                  <span className="button-label">
                    {loading ? 'Yaratilmoqda…' : 'Hisob yaratish'}
                  </span>
                  <span className="button-spinner" aria-hidden="true" hidden={!loading} />
                  <svg className="button-arrow" viewBox="0 0 20 20" aria-hidden="true">
                    <path d="m7.5 4.5 5 5.5-5 5.5" />
                  </svg>
                </button>
              </form>
          </section>
          <p className="privacy-note">
            Libro.UZ hisobingiz bormi? <Link to="/login">Kirish</Link>
          </p>
        </div>
      </section>
    </AppShell>
  )
}

