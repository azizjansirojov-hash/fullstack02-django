import { useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import RequireAuth from './components/layout/RequireAuth'
import GuestOnly from './components/layout/GuestOnly'
import SplashIntro from './components/layout/SplashIntro'
import DashboardLayout from './components/layout/DashboardLayout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import PasswordResetPage from './pages/PasswordResetPage'
import PasswordResetConfirmPage from './pages/PasswordResetConfirmPage'
import HomePage from './pages/HomePage'
import CollectionsPage from './pages/CollectionsPage'
import DiscoverPage from './pages/DiscoverPage'
import MyLibraryPage from './pages/MyLibraryPage'
import BookDetailPage from './pages/BookDetailPage'
import ReaderPage from './pages/ReaderPage'
import {
  INTRO_SEEN_KEY,
  INTRO_SEEN_KEY_LEGACY,
  storageGet,
  storageSet,
} from './lib/storageKeys'

function hasSeenIntro() {
  return storageGet(sessionStorage, INTRO_SEEN_KEY, INTRO_SEEN_KEY_LEGACY) === '1'
}

function markIntroSeen() {
  storageSet(sessionStorage, INTRO_SEEN_KEY, '1', INTRO_SEEN_KEY_LEGACY)
}

function HomeRedirect() {
  const { ready, isAuthenticated } = useAuth()
  if (!ready) return null
  return <Navigate to={isAuthenticated ? '/library' : '/login'} replace />
}

function AppRoutes() {
  const [showIntro, setShowIntro] = useState(() => !hasSeenIntro())

  function handleIntroComplete() {
    markIntroSeen()
    setShowIntro(false)
  }

  return (
    <BrowserRouter>
      {showIntro ? <SplashIntro onComplete={handleIntroComplete} /> : null}
      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route element={<GuestOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route path="/password-reset" element={<PasswordResetPage />} />
        <Route path="/password-reset/:uidb64/:token" element={<PasswordResetConfirmPage />} />

        <Route path="/library" element={<DashboardLayout />}>
          <Route index element={<HomePage />} />
          <Route path="toplamlar" element={<CollectionsPage />} />
          <Route path="dokon" element={<DiscoverPage />} />
          <Route path="mening" element={<MyLibraryPage />} />
          <Route element={<RequireAuth />}>
            <Route path=":slug" element={<BookDetailPage />} />
          </Route>
        </Route>

        <Route element={<RequireAuth />}>
          <Route path="/library/:slug/read" element={<ReaderPage />} />
        </Route>

        <Route path="*" element={<HomeRedirect />} />
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

