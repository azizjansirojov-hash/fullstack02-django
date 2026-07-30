import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import AppSidebar from './AppSidebar'
import Constellation from './Constellation'
import {
  SIDEBAR_COLLAPSE_KEY,
  SIDEBAR_COLLAPSE_KEY_LEGACY,
  storageGet,
  storageSet,
} from '../../lib/storageKeys'
import '../../assets/css/dashboard.css'
import '../../assets/css/library.css'

/**
 * Sidebar + main outlet for library dashboard pages.
 */
export default function DashboardLayout() {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(() => {
    return storageGet(localStorage, SIDEBAR_COLLAPSE_KEY, SIDEBAR_COLLAPSE_KEY_LEGACY) === '1'
  })
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname, location.search])

  useEffect(() => {
    storageSet(
      localStorage,
      SIDEBAR_COLLAPSE_KEY,
      collapsed ? '1' : '0',
      SIDEBAR_COLLAPSE_KEY_LEGACY,
    )
  }, [collapsed])

  useEffect(() => {
    document.title = 'Libro.UZ'
  }, [])

  return (
    <div className="dash">
      <Constellation palette="brand" />
      <div className="dash__glow" aria-hidden="true" />

      {mobileOpen ? (
        <button
          type="button"
          className="sidebar__backdrop"
          aria-label="Menyuni yopish"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <AppSidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((v) => !v)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="dash__main">
        <div className="dash__mobile-bar">
          <button
            type="button"
            className="dash__menu-btn"
            aria-label="Menyuni ochish"
            onClick={() => setMobileOpen(true)}
          >
            ☰
          </button>
          <span>Libro.UZ</span>
        </div>
        <div className="dash__content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
