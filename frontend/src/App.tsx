import { lazy, Suspense, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { AuthProvider, useAuth } from './auth/AuthContext'
import RequireAuth from './components/layout/RequireAuth'
import GuestOnly from './components/layout/GuestOnly'
import SplashIntro from './components/layout/SplashIntro'
import DashboardLayout from './components/layout/DashboardLayout'
import {
  INTRO_SEEN_KEY,
  INTRO_SEEN_KEY_LEGACY,
  storageGet,
  storageSet,
} from './lib/storageKeys'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const PasswordResetPage = lazy(() => import('./pages/PasswordResetPage'))
const PasswordResetConfirmPage = lazy(() => import('./pages/PasswordResetConfirmPage'))
const HomePage = lazy(() => import('./pages/HomePage'))
const CollectionsPage = lazy(() => import('./pages/CollectionsPage'))
const DiscoverPage = lazy(() => import('./pages/DiscoverPage'))
const MyLibraryPage = lazy(() => import('./pages/MyLibraryPage'))
const BookDetailPage = lazy(() => import('./pages/BookDetailPage'))
const ReaderPage = lazy(() => import('./pages/ReaderPage'))
const PaymentStatusPage = lazy(() => import('./pages/PaymentStatusPage'))

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

function PageFallback() {
  return (
    <div className="dash-loading" aria-busy="true">
      Yuklanmoqda…
    </div>
  )
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
      <Suspense fallback={<PageFallback />}>
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
            <Route path="/payment/status/:transactionId" element={<PaymentStatusPage />} />
          </Route>

          <Route path="*" element={<HomeRedirect />} />
        </Routes>
      </Suspense>
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
