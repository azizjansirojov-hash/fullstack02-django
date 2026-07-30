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
