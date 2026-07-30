import { useEffect, useRef, useState, type FormEvent, type ReactElement } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import Logo from './Logo'
import { useAuth } from '../../auth/AuthContext'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../api/notifications'
import type { Notification } from '../../types'
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

function HomeIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

function GridIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="4" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

function CartIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3.5 5h1.8l1.4 10.2a1.5 1.5 0 0 0 1.5 1.3h8.6a1.5 1.5 0 0 0 1.5-1.2L19.5 8H7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="10" cy="19" r="1.2" fill="currentColor" />
      <circle cx="16.5" cy="19" r="1.2" fill="currentColor" />
    </svg>
  )
}

function LibraryIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M5 5.5h4v13H5zM10.5 5.5h4v13h-4zM16 6.2l3.5-.9v13l-3.5.9V6.2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

function BellIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 4a5 5 0 0 0-5 5v2.2c0 .7-.2 1.4-.6 2L5 16h14l-1.4-2.8a3.8 3.8 0 0 1-.6-2V9a5 5 0 0 0-5-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M10 18a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

function GlobeIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4.5 12h15M12 4c2.5 2.8 2.5 12.2 0 16M12 4c-2.5 2.8-2.5 12.2 0 16" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M16.5 3.5A8.5 8.5 0 1 0 20.5 14 7 7 0 0 1 16.5 3.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

function GearIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" stroke="currentColor" strokeWidth="1.6" />
      <path d="M19.4 12a7.4 7.4 0 0 0-.1-1l1.6-1.2-1.5-2.6-1.9.6a7.7 7.7 0 0 0-1.7-1L15.5 4h-3l-.3 2.1a7.7 7.7 0 0 0-1.7 1l-1.9-.6L7 9.8 8.6 11a7.4 7.4 0 0 0 0 2l-1.6 1.2 1.5 2.6 1.9-.6c.5.4 1.1.7 1.7 1L12.5 20h3l.3-2.1c.6-.3 1.2-.6 1.7-1l1.9.6 1.5-2.6-1.6-1.2c.1-.3.1-.7.1-1Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  )
}

function ChevronIcon({ expand }: { expand: boolean }) {
  return (
    <svg
      className={`sidebar__collapse-icon${expand ? ' is-expand' : ''}`}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <path d="M14.5 5.5 8 12l6.5 6.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

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
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
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

  async function loadNotifications() {
    if (!user) {
      setNotifications([])
      setUnreadCount(0)
      return
    }
    try {
      const { response, data } = await fetchNotifications()
      if (response.ok && data) {
        setNotifications(data.results)
        setUnreadCount(data.unread_count)
      }
    } catch {
      // Notification availability must not block the rest of the sidebar.
    }
  }

  useEffect(() => {
    void loadNotifications()
  }, [user])

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
    setNotifOpen((isOpen) => {
      if (!isOpen) void loadNotifications()
      return !isOpen
    })
    setLangOpen(false)
  }

  async function handleNotificationClick(notification: Notification) {
    if (!notification.is_read) {
      try {
        const { response } = await markNotificationRead(notification.id)
        if (response.ok) {
          setNotifications((items) =>
            items.map((item) =>
              item.id === notification.id ? { ...item, is_read: true } : item,
            ),
          )
          setUnreadCount((count) => Math.max(0, count - 1))
        }
      } catch {
        // Continue to the target even if the read-state update fails.
      }
    }
    setNotifOpen(false)
    if (notification.link_url) {
      navigate(notification.link_url)
      onCloseMobile?.()
    }
  }

  async function handleMarkAllNotificationsRead() {
    try {
      const { response } = await markAllNotificationsRead()
      if (response.ok) {
        setNotifications((items) => items.map((item) => ({ ...item, is_read: true })))
        setUnreadCount(0)
      }
    } catch {
      // Keep the current state when the request could not be completed.
    }
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
        <div className="sidebar__control">
          <button
            type="button"
            className={`sidebar__row${notifOpen ? ' is-open' : ''}`}
            onClick={toggleNotif}
            title="Bildirishnomalar"
            aria-expanded={notifOpen}
          >
            <BellIcon />
            <span className="sidebar__row-label">Bildirishnomalar</span>
            {unreadCount > 0 ? (
              <span className="sidebar__notification-badge" aria-label={`${unreadCount} ta o‘qilmagan bildirishnoma`}>
                {unreadCount}
              </span>
            ) : null}
          </button>
          {notifOpen ? (
            <div className="sidebar__popover sidebar__popover--notif" role="dialog" aria-label="Bildirishnomalar">
              <div className="sidebar__popover-heading">
                <p className="sidebar__popover-title">Bildirishnomalar</p>
                {unreadCount > 0 ? (
                  <button type="button" className="sidebar__mark-all" onClick={() => void handleMarkAllNotificationsRead()}>
                    Barchasini o‘qilgan deb belgilash
                  </button>
                ) : null}
              </div>
              {notifications.length ? (
                <div className="sidebar__notification-list">
                  {notifications.map((notification) => (
                    <button
                      key={notification.id}
                      type="button"
                      className={`sidebar__notification${notification.is_read ? '' : ' is-unread'}`}
                      onClick={() => void handleNotificationClick(notification)}
                    >
                      {notification.message}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="sidebar__popover-empty">
                  Hozircha bildirishnomalar yo‘q.
                </p>
              )}
            </div>
          ) : null}
        </div>

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

