"""Helpers for Django → React SPA navigation."""

from django.conf import settings


def _spa_origin():
    origin = (getattr(settings, 'SPA_ORIGIN', '') or '').rstrip('/')
    if not origin or origin == 'same':
        return ''
    return origin


def _spa_url(path):
    """Return an SPA path, absolute when the SPA uses another origin."""
    origin = _spa_origin()
    return f'{origin}{path}' if origin else path


def spa_login_url():
    """URL for the SPA login page."""
    return _spa_url('/login/')


def spa_register_url():
    """URL for the SPA registration page."""
    return _spa_url('/register/')


def spa_password_reset_url():
    """URL for the SPA password-reset request page."""
    return _spa_url('/password-reset/')


def spa_library_home_url():
    """URL for the SPA library dashboard (/library), absolute when cross-origin."""
    return _spa_url('/library/')


def spa_book_detail_url(slug):
    """URL for the SPA book detail page, absolute when cross-origin."""
    path = f'/library/{slug}/'
    return _spa_url(path)


def spa_book_read_url(slug):
    """URL for the SPA immersive reader, absolute when cross-origin."""
    path = f'/library/{slug}/read'
    return _spa_url(path)


def spa_password_reset_confirm_url(uidb64, token):
    """URL for the SPA password-reset confirm page."""
    path = f'/password-reset/{uidb64}/{token}/'
    return _spa_url(path)
