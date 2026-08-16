"""Browser hardening headers (CSP, Permissions-Policy).

Django 6's ContentSecurityPolicyMiddleware is the source of truth for CSP in
every environment Django serves (runserver, Gunicorn behind nginx, tests).
nginx must not also emit Content-Security-Policy — a second header can
conflict, and nginx cannot mint the per-request nonce Django uses.

Vite's dev server serves the SPA HTML in local/E2E dual-stack mode, so
frontend/vite.config.js mirrors the DEBUG SPA policy (HMR needs extra
connect-src / script-src tokens Django HTML never needs).
"""

from django.conf import settings
from django.utils.csp import CSP
from django.utils.deprecation import MiddlewareMixin

# TTS/listen uses HTMLAudioElement + same-origin files, not the mic.
# PDF/flip fullscreen is used; camera/geo/payment APIs are not.
PERMISSIONS_POLICY = (
    'accelerometer=(), autoplay=(self), camera=(), display-capture=(), '
    'fullscreen=(self), geolocation=(), gyroscope=(), magnetometer=(), '
    'microphone=(), midi=(), payment=(), usb=(), browsing-topics=()'
)


def spa_csp_policy():
    """Enforcing policy for the SPA, legal HTML, APIs, and media responses."""
    return {
        'default-src': [CSP.SELF],
        'script-src': [CSP.SELF],
        'style-src': [CSP.SELF],
        'font-src': [CSP.SELF, 'data:'],
        'img-src': [CSP.SELF, 'data:', 'blob:'],
        'media-src': [CSP.SELF, 'blob:'],
        'worker-src': [CSP.SELF, 'blob:'],
        'connect-src': [CSP.SELF],
        'frame-src': [CSP.NONE],
        'frame-ancestors': [CSP.NONE],
        'object-src': [CSP.NONE],
        'base-uri': [CSP.SELF],
        'form-action': [CSP.SELF],
    }


def admin_csp_policy():
    """Admin shares style-src 'self' after moving inline CSS to static files."""
    return spa_csp_policy()


def vite_dev_csp_header():
    """Static header for Vite's HTML/HMR (no Django nonce)."""
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-eval' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "worker-src 'self' blob:; "
        "connect-src 'self' ws://127.0.0.1:5173 ws://localhost:5173 "
        "http://127.0.0.1:5173 http://localhost:5173 "
        "http://127.0.0.1:8000 http://localhost:8000; "
        "frame-src 'none'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


class BrowserHardeningMiddleware(MiddlewareMixin):
    """Permissions-Policy plus admin-path CSP override (see SECURE_CSP_ADMIN)."""

    def process_response(self, request, response):
        if request.path.startswith('/admin/'):
            response._csp_config = getattr(
                settings, 'SECURE_CSP_ADMIN', admin_csp_policy()
            )
        response.headers.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        return response
