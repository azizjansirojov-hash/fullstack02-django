import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'

/**
 * Redirect authenticated users away from login/register to the library.
 *
 * Runtime contract (unchanged):
 * 1. While `ready === false`, render nothing (avoid bouncing guests to /library mid-bootstrap).
 * 2. After ready, if `isAuthenticated`, Navigate to /library; else render guest outlet.
 */
export default function GuestOnly() {
  const { ready, isAuthenticated } = useAuth()

  if (!ready) {
    return null
  }

  if (isAuthenticated) {
    return <Navigate to="/library" replace />
  }

  return <Outlet />
}
