import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './assets/css/auth.css'
import './assets/css/logo.css'
import App from './App'
import {
  THEME_KEY,
  THEME_KEY_LEGACY,
  migrateAllLegacyBrowserStorage,
  storageGet,
} from './lib/storageKeys'

// One-time copy of legacy luma-/libro- keys → librouz_* before any UI reads storage.
migrateAllLegacyBrowserStorage()

try {
  const theme = storageGet(localStorage, THEME_KEY, THEME_KEY_LEGACY)
  document.documentElement.dataset.theme = theme === 'light' ? 'light' : 'dark'
} catch {
  document.documentElement.dataset.theme = 'dark'
}

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element not found')

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
