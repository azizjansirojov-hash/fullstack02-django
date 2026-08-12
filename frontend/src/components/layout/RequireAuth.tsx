import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../../auth/AuthContext'

/**
 * Redirect unauthenticated users to /login?next=….
 *
 * Runtime contract (unchanged):
 * 1. While `ready === false`, render nothing (do not redirect yet — bootstrap may still set user).
 * 2. After ready, `isAuthenticated === Boolean(user)` — redirect if false, else render outlet.
 */
export default function RequireAuth() {
  const { ready, isAuthenticated } = useAuth()
  const location = useLocation()

  if (!ready) {
    return null
  }

  if (!isAuthenticated) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }

  return <Outlet />
}
