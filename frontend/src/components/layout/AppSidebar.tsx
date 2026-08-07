import { useEffect, useRef, useState, type FormEvent, type ReactElement } from 'react'
import { Link, NavLink, useNavigate } from 'react-router'
import Logo from './Logo'
import SidebarNotifications from './SidebarNotifications'
import {
  CartIcon,
  ChevronIcon,
  GearIcon,
  GlobeIcon,
  GridIcon,
  HomeIcon,
  LibraryIcon,
  MoonIcon,
} from './sidebarIcons'
import { useAuth } from '../../auth/AuthContext'
import {
  THEME_KEY,
  THEME_KEY_LEGACY,
  storageGet,
  storageSet,
} from '../../lib/storageKeys'
import { localeLabel, readLocale, writeLocale, type AppLocale, SUPPORTED_LOCALES } from '../../lib/locale'

type ThemeMode = 'light' | 'dark'

const NAV: Array<{
  to: string
  end?: boolean
  label: string
  icon: () => ReactElement
}> = [
  { to: '/library', end: true, label: 'Asosiy sahifa', icon: HomeIcon },
  { to: '/library/toplamlar', label: "To'plamlar", icon: GridIcon },
  { to: '/library/dokon', label: "Kutubxona do'koni", icon: CartIcon },
  { to: '/library/mening', label: 'Mening kutubxonam', icon: LibraryIcon },
]

function readTheme(): ThemeMode {
  try {
    const saved = storageGet(localStorage, THEME_KEY, THEME_KEY_LEGACY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* ignore */
  }
  return 'dark'
}

function applyTheme(theme: ThemeMode) {
  document.documentElement.dataset.theme = theme
  storageSet(localStorage, THEME_KEY, theme, THEME_KEY_LEGACY)
}

export type AppSidebarProps = {
  collapsed: boolean
  onToggleCollapse: () => void
  mobileOpen: boolean
  onCloseMobile?: () => void
}

/**
 * Persistent left sidebar — Mutolaa structure, Libro.UZ branding.
 */
export default function AppSidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}: AppSidebarProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [searchDraft, setSearchDraft] = useState('')
  const [notifOpen, setNotifOpen] = useState(false)
  const [langOpen, setLangOpen] = useState(false)
  const [locale, setLocale] = useState<AppLocale>(readLocale)
  const [theme, setTheme] = useState<ThemeMode>(readTheme)
  const lowerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    writeLocale(locale)
  }, [locale])

  useEffect(() => {
    function onDocClick(event: globalThis.MouseEvent) {
      const target = event.target
      if (!(target instanceof Node) || !lowerRef.current?.contains(target)) {
        setNotifOpen(false)
        setLangOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const q = searchDraft.trim()
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    const qs = params.toString()
    navigate(qs ? `/library/dokon?${qs}` : '/library/dokon')
    onCloseMobile?.()
  }

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  function toggleNotif() {
    setNotifOpen((isOpen) => !isOpen)
    setLangOpen(false)
  }

  function toggleLang() {
    setLangOpen((v) => !v)
    setNotifOpen(false)
  }

  function toggleTheme() {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  const initials = (user?.username || '?').slice(0, 2).toUpperCase()
  const isDark = theme === 'dark'

  return (
    <aside
      className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}${mobileOpen ? ' is-open' : ''}`}
      aria-label="Asosiy navigatsiya"
    >
      <div className="sidebar__top">
        <Link className="sidebar__logo" to="/library" onClick={onCloseMobile} aria-label="Libro.UZ bosh sahifa">
          <Logo size="sm" />
        </Link>
        <button
          type="button"
          className="sidebar__collapse"
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Yon panelni ochish' : 'Yon panelni yig‘ish'}
          aria-expanded={!collapsed}
        >
          <ChevronIcon expand={collapsed} />
        </button>
      </div>

      <form className="sidebar__search" onSubmit={handleSearch} role="search">
        <span className="sidebar__search-icon-label" aria-hidden>
          ⌕
        </span>
        <input
          type="search"
          value={searchDraft}
          onChange={(e) => setSearchDraft(e.target.value)}
          placeholder="Kitob yoki muallifni izlang..."
          aria-label="Kitob yoki muallifni izlang"
        />
      </form>

      <nav className="sidebar__nav">
        {NAV.map(({ to, end, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={Boolean(end)}
            className={({ isActive }) => `sidebar__link${isActive ? ' is-active' : ''}`}
            onClick={onCloseMobile}
            title={label}
          >
            <Icon />
            <span className="sidebar__link-label">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar__lower" ref={lowerRef}>
        <SidebarNotifications
          user={user}
          open={notifOpen}
          onToggle={toggleNotif}
          onCloseMobile={onCloseMobile}
        />

        <div className="sidebar__control">
          <button
            type="button"
            className={`sidebar__row${langOpen ? ' is-open' : ''}`}
            onClick={toggleLang}
            title="Til"
            aria-expanded={langOpen}
          >
            <GlobeIcon />
            <span className="sidebar__row-label">Til</span>
            <span className="sidebar__row-meta">{localeLabel(locale)}</span>
          </button>
          {langOpen ? (
            <div className="sidebar__popover" role="listbox" aria-label="Til">
              {SUPPORTED_LOCALES.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  className={`sidebar__popover-option${locale === item.code ? ' is-selected' : ''}`}
                  role="option"
                  aria-selected={locale === item.code}
                  onClick={() => {
                    setLocale(item.code)
                    setLangOpen(false)
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <button
          type="button"
          className="sidebar__row"
          onClick={toggleTheme}
          title={isDark ? 'Tungi rejim (yoqilgan)' : 'Kunduzgi rejim'}
          aria-pressed={isDark}
        >
          <MoonIcon />
          <span className="sidebar__row-label">Tungi rejim</span>
          <span className={`sidebar__toggle${isDark ? ' is-on' : ''}`} aria-hidden />
        </button>

        {user ? (
          <div className="sidebar__profile">
            <span className="sidebar__avatar" aria-hidden>
              {initials}
            </span>
            <span className="sidebar__profile-name">{user.username}</span>
            <div className="sidebar__profile-actions">
              {user.is_staff ? (
                <a
                  className="sidebar__icon-btn"
                  href="/admin/library/book/add/"
                  title="Kitob qo‘shish"
                  aria-label="Kitob qo‘shish"
                >
                  +
                </a>
              ) : null}
              <button
                type="button"
                className="sidebar__icon-btn"
                onClick={handleLogout}
                title="Chiqish"
                aria-label="Chiqish"
              >
                <GearIcon />
              </button>
            </div>
          </div>
        ) : (
          <div className="sidebar__guest">
            <Link className="sidebar__guest-login" to="/login" onClick={onCloseMobile}>
              Kirish
            </Link>
            <Link className="sidebar__guest-register" to="/register" onClick={onCloseMobile}>
              Hisob yaratish
            </Link>
          </div>
        )}
      </div>
    </aside>
  )
}
