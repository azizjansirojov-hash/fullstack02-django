import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import AppShell, { SecureStatusChip } from '../components/layout/AppShell'
import { requestPasswordReset } from '../api/auth'
import '../assets/css/auth.css'

type AlertState = { type: 'success' | 'error'; message: string } | null

export default function PasswordResetPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [alert, setAlert] = useState<AlertState>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setAlert(null)
    try {
      const { data } = await requestPasswordReset({ email })
      setAlert({
        type: 'success',
        message: data?.detail || 'If an account exists for that email, a reset link has been sent.',
      })
    } catch (_err) {
      setAlert({ type: 'error', message: 'Backendga ulanib bo‘lmadi.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell
      title="Parolni tiklash"
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
          <section className="auth-card">
            <div className="auth-card__header">
              <p className="section-label">Libro.UZ hisobi</p>
              <h2>Parolni tiklash</h2>
              <p className="auth-card__subtitle">
                Email manzilingizni kiriting — tiklash havolasini yuboramiz.
              </p>
            </div>
            {alert && (
              <div className={`alert alert--${alert.type}`} role="status">
                {alert.message}
              </div>
            )}
            <form className="auth-form" onSubmit={handleSubmit} noValidate>
              <div className="field">
                <label htmlFor="id_email">Email</label>
                <input
                  type="email"
                  id="id_email"
                  required
                  autoComplete="email"
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <button type="submit" className="primary-button" disabled={loading}>
                <span className="button-label">
                  {loading ? 'Yuborilmoqda…' : 'Havola yuborish'}
                </span>
              </button>
            </form>
            <p className="privacy-note" style={{ marginTop: '1rem' }}>
              <Link to="/login">Kirishga qaytish</Link>
            </p>
          </section>
        </div>
      </section>
    </AppShell>
  )
}

