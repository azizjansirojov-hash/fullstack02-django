"""End-to-end verification tests for Phase 1–3 hardening (JWT media, stale queue)."""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from .admin import BookAdmin
from .generation_health import book_generation_ops_summary
from .models import Book, BookTranslation, GenerationJob, Purchase
from .spa_urls import spa_book_read_url
from .test_auth_helpers import authenticate_jwt

User = get_user_model()


class ReaderSpaRedirectTests(TestCase):
    """Django HTML reader removed — /read/ always redirects to the SPA."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='xssreader', password='Str0ng-Passw0rd!'
        )
        self.book = Book.objects.create(
            author_name='XSS Author',
            slug='xss-escape-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='XSS Escape Book',
            body='<script>alert(1)</script>',
        )
        Purchase.objects.create(
            user=self.user,
            book=self.book,
            status=Purchase.Status.PAID,
        )

    def test_read_url_redirects_to_spa(self):
        self.client.login(username='xssreader', password='Str0ng-Passw0rd!')
        url = reverse('library:book-read', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_read_url(self.book.slug))

    def test_django_escape_still_escapes_markup(self):
        dangerous = '<script>alert(1)</script> and <b>x</b> & y'
        escaped = escape(dangerous)
        self.assertIn('&lt;script&gt;', escaped)
        self.assertIn('&amp;', escaped)


class ReaderAuthUnificationTests(TestCase):
    """Gated media accepts JWT cookies only; /read/ remains an SPA redirect."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='authy', password='Str0ng-Passw0rd!'
        )
        self.book = Book.objects.create(
            author_name='Auth Author',
            slug='auth-unify-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Auth Unify',
            body='O‘qish matni.',
        )
        Purchase.objects.create(
            user=self.user,
            book=self.book,
            status=Purchase.Status.PAID,
        )
        self.read_url = reverse(
            'library:book-read', kwargs={'slug': self.book.slug}
        )
        self.pdf_url = reverse(
            'library:book-media-pdf', kwargs={'slug': self.book.slug}
        )

    def test_jwt_only_read_redirects_to_spa(self):
        client = Client()
        authenticate_jwt(client, self.user)
        response = client.get(self.read_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_read_url(self.book.slug))

    def test_session_only_read_redirects_to_spa(self):
        client = Client()
        self.assertTrue(client.login(username='authy', password='Str0ng-Passw0rd!'))
        client.cookies.pop(settings.JWT_ACCESS_COOKIE_NAME, None)
        client.cookies.pop(settings.JWT_REFRESH_COOKIE_NAME, None)
        response = client.get(self.read_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_read_url(self.book.slug))

    def test_session_only_media_rejected(self):
        client = Client()
        self.assertTrue(client.login(username='authy', password='Str0ng-Passw0rd!'))
        client.cookies.pop(settings.JWT_ACCESS_COOKIE_NAME, None)
        client.cookies.pop(settings.JWT_REFRESH_COOKIE_NAME, None)
        response = client.get(self.pdf_url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 401)

    def test_anonymous_read_still_redirects_to_spa(self):
        """Auth is enforced by the SPA; Django only redirects."""
        client = Client()
        response = client.get(self.read_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_read_url(self.book.slug))


@override_settings(GENERATION_STALE_QUEUED_SECONDS=300)
class StaleGenerationQueueTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_superuser(
            username='staleadmin',
            email='stale@example.com',
            password='Str0ng-Passw0rd!',
        )
        self.book = Book.objects.create(
            author_name='Stale Author',
            slug='stale-queue-book',
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='pending',
            audio_generation_status='pending',
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Stale Queue',
            body='Navbatda turgan ish.',
        )
        self.job = GenerationJob.objects.create(
            book=self.book,
            job_type=GenerationJob.JobType.ALL,
            status=GenerationJob.Status.QUEUED,
        )
        GenerationJob.objects.filter(pk=self.job.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        self.job.refresh_from_db()

    def test_health_endpoint_reports_stale(self):
        authenticate_jwt(self.client, self.staff)
        response = self.client.get(reverse('generation-health'))
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertTrue(data['worker_likely_down'])
        self.assertGreaterEqual(data['stale_queued'], 1)
        self.assertEqual(data['status'], 'degraded')

    def test_admin_generation_ops_display_contains_stale_queue(self):
        summary = book_generation_ops_summary(self.book)
        self.assertTrue(summary['stale'])
        self.assertGreaterEqual(summary['queued_count'], 1)

        admin = BookAdmin(Book, None)
        html = str(admin.generation_ops_display(self.book))
        self.assertIn('STALE QUEUE', html)
        self.assertIn('process_generation_jobs', html)

    def test_admin_changelist_renders_stale_warning(self):
        self.client.login(username='staleadmin', password='Str0ng-Passw0rd!')
        url = reverse('admin:library_book_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('STALE QUEUE', content)
        self.assertIn('Stale Queue', content)  # display title, not slug
        self.assertIn('field-generation_ops_display', content)


class ProductionSettingsRejectionTests(SimpleTestCase):
    """Boot-time ImproperlyConfigured for weak secrets / wildcard hosts."""

    # ≥50 chars, no weak-marker substrings (secret/test/password/…).
    _STRONG_SECRET = (
        'qa-hardening-boot-key-abcdefghijklmnopqrstuvwxyz0123456789!!'
    )

    def _reject_secret_proc(self, secret_key):
        import os
        import subprocess
        import sys

        return subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import os; '
                    f"os.environ['SECRET_KEY']={secret_key!r}; "
                    "os.environ['DEBUG']='False'; "
                    "os.environ['ALLOWED_HOSTS']='localhost'; "
                    "os.environ['ALLOW_CONSOLE_EMAIL']='1'; "
                    "os.environ['ENVIRONMENT']='staging'; "
                    "os.environ['USE_TLS']='0'; "
                    "os.environ['DJANGO_SETTINGS_MODULE']='backend.settings'; "
                    'import django; django.setup()'
                ),
            ],
            cwd=str(Path(settings.BASE_DIR)),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                'SECRET_KEY': secret_key,
                'DEBUG': 'False',
                'ALLOWED_HOSTS': 'localhost',
                'ALLOW_CONSOLE_EMAIL': '1',
                'ENVIRONMENT': 'staging',
                'USE_TLS': '0',
            },
        )

    def test_weak_secret_rejected_when_debug_false(self):
        proc = self._reject_secret_proc('change-me-to-a-long-random-string')
        self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertIn('SECRET_KEY', combined)

    def test_changeme_secret_rejected_when_debug_false(self):
        proc = self._reject_secret_proc('changeme')
        self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertIn('SECRET_KEY', combined)

    def test_short_secret_rejected_when_debug_false(self):
        proc = self._reject_secret_proc('short')
        self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertIn('SECRET_KEY', combined)

    def test_star_allowed_hosts_rejected_when_debug_false(self):
        import os
        import subprocess
        import sys

        strong = self._STRONG_SECRET
        proc = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import os; '
                    f"os.environ['SECRET_KEY']={strong!r}; "
                    "os.environ['DEBUG']='False'; "
                    "os.environ['ALLOWED_HOSTS']='*'; "
                    "os.environ['ALLOW_CONSOLE_EMAIL']='1'; "
                    "os.environ['ENVIRONMENT']='staging'; "
                    "os.environ['USE_TLS']='0'; "
                    "os.environ['DJANGO_SETTINGS_MODULE']='backend.settings'; "
                    'import django; django.setup()'
                ),
            ],
            cwd=str(Path(settings.BASE_DIR)),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                'SECRET_KEY': strong,
                'DEBUG': 'False',
                'ALLOWED_HOSTS': '*',
                'ALLOW_CONSOLE_EMAIL': '1',
                'ENVIRONMENT': 'staging',
                'USE_TLS': '0',
            },
        )
        self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertIn('ALLOWED_HOSTS', combined)

    def test_strong_secret_boots_with_debug_false(self):
        import os
        import subprocess
        import sys

        strong = self._STRONG_SECRET
        # Production boot also requires REDIS_URL (settings.py cache guard).
        # Use a URL only for config load — django.setup() does not connect.
        boot_env = {
            **os.environ,
            'SECRET_KEY': strong,
            'DEBUG': 'False',
            'ALLOWED_HOSTS': 'localhost,127.0.0.1',
            'ALLOW_CONSOLE_EMAIL': '1',
            'ENVIRONMENT': 'staging',
            'USE_TLS': '0',
            'REDIS_URL': 'redis://127.0.0.1:6379/15',
            'E2E_RELAX_THROTTLE': '0',
        }
        proc = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import os; '
                    f"os.environ['SECRET_KEY']={strong!r}; "
                    "os.environ['DEBUG']='False'; "
                    "os.environ['ALLOWED_HOSTS']='localhost,127.0.0.1'; "
                    "os.environ['ALLOW_CONSOLE_EMAIL']='1'; "
                    "os.environ['ENVIRONMENT']='staging'; "
                    "os.environ['USE_TLS']='0'; "
                    "os.environ['REDIS_URL']='redis://127.0.0.1:6379/15'; "
                    "os.environ['E2E_RELAX_THROTTLE']='0'; "
                    "os.environ['DJANGO_SETTINGS_MODULE']='backend.settings'; "
                    'import django; django.setup(); print("BOOT_OK")'
                ),
            ],
            cwd=str(Path(settings.BASE_DIR)),
            capture_output=True,
            text=True,
            env=boot_env,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn('BOOT_OK', proc.stdout)
