import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Pin IPv4 so Django's port check (and browsers) hit the same listener.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // Local SPA HTML is served by Vite, not Django. Mirror DEBUG CSP here.
    // Production SPA is Gunicorn FileResponse — Django middleware owns headers.
    headers: {
      'Content-Security-Policy':
        "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob:; media-src 'self' blob:; worker-src 'self' blob:; connect-src 'self' ws://127.0.0.1:5173 ws://localhost:5173 http://127.0.0.1:5173 http://localhost:5173 http://127.0.0.1:8000 http://localhost:8000; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'",
      'Referrer-Policy': 'strict-origin-when-cross-origin',
      'Permissions-Policy':
        'accelerometer=(), autoplay=(self), camera=(), display-capture=(), fullscreen=(self), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), payment=(), usb=(), browsing-topics=()',
      'X-Content-Type-Options': 'nosniff',
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/library': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SPA owns catalog, detail, and reader HTML; media streams proxy to Django.
        bypass(req) {
          if (req.method !== 'GET' && req.method !== 'HEAD') return undefined
          const accept = req.headers.accept || ''
          if (!accept.includes('text/html')) return undefined
          const path = (req.url || '').split('?')[0]
          if (
            path === '/library' ||
            path === '/library/' ||
            /^\/library\/[^/]+\/?$/.test(path) ||
            /^\/library\/[^/]+\/read\/?$/.test(path)
          ) {
            return '/index.html'
          }
          return undefined
        },
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
