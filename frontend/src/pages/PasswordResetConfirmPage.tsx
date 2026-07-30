import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell, { SecureStatusChip } from '../components/layout/AppShell'
import { confirmPasswordReset, ensureCsrf } from '../api/auth'
import '../assets/css/auth.css'

type AlertState = { type: 'success' | 'error'; message: string } | null

/**
 * Password-reset confirm — replaces Django password_reset_confirm.html.
 * Route: /password-reset/:uidb64/:token
 */
export default function PasswordResetConfirmPage() {
  const { uidb64 = '', token = '' } = useParams<{ uidb64: string; token: string }>()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [alert, setAlert] = useState<AlertState>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setAlert(null)
    try {
      await ensureCsrf()
      const { response, data } = await confirmPasswordReset({
        uid: uidb64,
        token,
        password,
        password_confirm: passwordConfirm,
      })
      if (response.ok) {
        const detail =
          data && 'detail' in data && typeof data.detail === 'string'
            ? data.detail
            : 'Parol yangilandi.'
        const redirectUrl =
          data && 'redirect_url' in data && typeof data.redirect_url === 'string'
            ? data.redirect_url
            : '/login'
        setAlert({
          type: 'success',
          message: detail,
        })
        window.setTimeout(() => {
          navigate(redirectUrl, { replace: true })
        }, 800)
        return
      }
      const raw =
        data &&
        ('detail' in data
          ? data.detail
          : 'password' in data
            ? data.password
            : 'password_confirm' in data
              ? data.password_confirm
              : null)
      const msg = Array.isArray(raw) ? raw[0] : raw
      setAlert({
        type: 'error',
        message: typeof msg === 'string' ? msg : 'Xatolik.',
      })
    } catch {
      setAlert({ type: 'error', message: 'Backendga ulanib bo‘lmadi.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell
      title="Yangi parol"
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
      <section className="auth-layout">
        <div className="auth-column" style={{ margin: '0 auto' }}>
          <section className="auth-card" aria-labelledby="reset-confirm-title">
            <div className="auth-card__header">
              <p className="section-label">Libro.UZ hisobi</p>
              <h2 id="reset-confirm-title">Yangi parol qo‘ying</h2>
              <p className="auth-card__subtitle">
                Kamida 8 belgi. Oddiy parollardan saqlaning.
              </p>
            </div>
            {alert ? (
              <div className={`alert alert--${alert.type}`} role="status">
                {alert.message}
              </div>
            ) : null}
            <form className="auth-form" onSubmit={handleSubmit} noValidate>
              <div className="field">
                <label htmlFor="id_password">Yangi parol</label>
                <input
                  type="password"
                  id="id_password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="id_password_confirm">Parolni tasdiqlang</label>
                <input
                  type="password"
                  id="id_password_confirm"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                />
              </div>
              <button type="submit" className="primary-button" disabled={loading}>
                <span className="button-label">
                  {loading ? 'Saqlanmoqda…' : 'Parolni saqlash'}
                </span>
              </button>
            </form>
          </section>
        </div>
      </section>
    </AppShell>
  )
}
