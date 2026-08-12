import { useEffect, type ReactNode } from 'react'
import { Link } from 'react-router'
import Constellation from './Constellation'
import Logo from './Logo'

export type AppShellProps = {
  title?: string
  metaDescription?: string
  wordmarkTo?: string
  navCenter?: ReactNode
  navStatus?: ReactNode
  navAction?: ReactNode
  footerNote?: string
  bodyClassName?: string
  children?: ReactNode
}

/**
 * Mirrors base.html chrome: constellation, header, main, footer.
 */
export default function AppShell({
  title = 'Hisob',
  metaDescription,
  wordmarkTo = '/library',
  navCenter,
  navStatus,
  navAction,
  footerNote = 'Shifrlangan HttpOnly autentifikatsiya bilan himoyalangan.',
  bodyClassName = '',
  children,
}: AppShellProps) {
  useEffect(() => {
    document.title = `${title} · Libro.UZ`
    if (!metaDescription) return undefined
    let meta = document.querySelector('meta[name="description"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.setAttribute('name', 'description')
      document.head.appendChild(meta)
    }
    meta.setAttribute('content', metaDescription)
    return undefined
  }, [title, metaDescription])

  return (
    <div className={bodyClassName || undefined}>
      <Constellation />
      <div className="backdrop-glow" aria-hidden="true" />

      <div className="app">
        <header className="site-header">
          <nav className="nav" aria-label="Asosiy navigatsiya">
            <Link className="wordmark" to={wordmarkTo} aria-label="Libro.UZ bosh sahifa">
              <Logo size="sm" />
            </Link>

            {navCenter}

            <div className="nav__links">
              {navStatus}
              {navAction}
            </div>
          </nav>
        </header>

        <main className="page">{children}</main>

        <footer className="site-footer">
          <p>© 2026 Libro.UZ. Barcha huquqlar himoyalangan.</p>
          <p className="site-footer__security">{footerNote}</p>
        </footer>
      </div>
    </div>
  )
}

/** Default auth-flow nav steps (login/register). */
export function AuthNavSteps({ active }: { active: 'login' | 'register' }) {
  return (
    <div className="nav__center" aria-hidden="true">
      <span className={`nav__step${active === 'login' ? ' is-active' : ''}`}>
        <em>01</em> Kirish
      </span>
      <span className={`nav__step${active === 'register' ? ' is-active' : ''}`}>
        <em>02</em> Hisob yaratish
      </span>
    </div>
  )
}

export function SecureStatusChip() {
  return (
    <span className="status-chip">
      <span className="status-chip__dot" />
      Xavfsiz kirish yoqilgan
    </span>
  )
}

