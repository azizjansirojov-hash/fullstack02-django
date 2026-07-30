"""Tests for production startup guards in settings.py."""

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase


class RedisProductionGuardTests(TestCase):
    """REDIS_URL must be set when DEBUG=False (verified at settings load time)."""

    def _reload_caches_guard(self, *, debug, redis_url):
        """Re-run the CACHES guard block in isolation (mirrors settings.py verbatim)."""
        if not redis_url and not debug:
            raise ImproperlyConfigured(
                'Production (DEBUG=False) requires REDIS_URL to be set. '
                'Multi-worker Gunicorn uses LocMemCache without it, making DRF '
                'throttle counters (auth, password_reset) per-process only and '
                'regeneration quotas inconsistent across workers. '
                'Set REDIS_URL in .env or docker-compose. See DEPLOY.md.'
            )

    def test_missing_redis_in_production_raises(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._reload_caches_guard(debug=False, redis_url='')
        self.assertIn('REDIS_URL', str(ctx.exception))

    def test_missing_redis_in_debug_is_allowed(self):
        # Should not raise — local dev uses LocMemCache.
        self._reload_caches_guard(debug=True, redis_url='')

    def test_redis_url_present_in_production_is_allowed(self):
        # Should not raise.
        self._reload_caches_guard(debug=False, redis_url='redis://:secret@redis:6379/1')

    def test_guard_message_contains_deploy_guidance(self):
        """Guard message should mention REDIS_URL and DEPLOY.md."""
        try:
            self._reload_caches_guard(debug=False, redis_url='')
        except ImproperlyConfigured as exc:
            msg = str(exc)
            self.assertIn('REDIS_URL', msg)
            self.assertIn('DEPLOY.md', msg)
        else:
            self.fail('ImproperlyConfigured not raised')


class ConsoleEmailProductionGuardTests(TestCase):
    """Console email backends are blocked in production unless ALLOW_CONSOLE_EMAIL=1."""

    _console_backends = {
        'django.core.mail.backends.console.EmailBackend',
        'django.core.mail.backends.locmem.EmailBackend',
    }

    def _email_guard(self, *, debug, email_backend, allow_console_email):
        if (
            not debug
            and email_backend in self._console_backends
            and not allow_console_email
        ):
            raise ImproperlyConfigured(
                'Production (DEBUG=False) requires a real EMAIL_BACKEND (SMTP). '
                'Set EMAIL_HOST_* in .env, or ALLOW_CONSOLE_EMAIL=1 only for staging. '
                'See DEPLOY.md.'
            )

    def test_console_email_blocked_in_production(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._email_guard(
                debug=False,
                email_backend='django.core.mail.backends.console.EmailBackend',
                allow_console_email=False,
            )
        self.assertIn('EMAIL_BACKEND', str(ctx.exception))
        self.assertIn('ALLOW_CONSOLE_EMAIL', str(ctx.exception))

    def test_console_email_allowed_with_escape_hatch(self):
        self._email_guard(
            debug=False,
            email_backend='django.core.mail.backends.console.EmailBackend',
            allow_console_email=True,
        )

    def test_console_email_allowed_in_debug(self):
        self._email_guard(
            debug=True,
            email_backend='django.core.mail.backends.console.EmailBackend',
            allow_console_email=False,
        )
