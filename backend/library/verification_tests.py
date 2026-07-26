"""End-to-end verification tests for Phase 1–3 hardening (XSS, JWT, stale queue)."""

from datetime import timedelta
from html import unescape
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from users.auth import get_tokens_for_user

from .admin import BookAdmin
from .generation_health import book_generation_ops_summary
from .models import Book, BookTranslation, GenerationJob, Purchase

User = get_user_model()

XSS_BODY = (
    '<script>alert(1)</script>\n\n'
    'Plain <b>bold</b> and ampersand Tom & Jerry.'
)


class ReaderXssEscapingTests(TestCase):
    """Verify book body XSS vectors are escaped in the served reader HTML."""

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
            body=XSS_BODY,
        )
        Purchase.objects.create(
            user=self.user,
            book=self.book,
            status=Purchase.Status.PAID,
        )

    def test_reader_page_escapes_script_b_and_ampersand(self):
        self.client.login(username='xssreader', password='Str0ng-Passw0rd!')
        url = reverse('library:book-read', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        start = html.find('id="book-source"')
        self.assertGreater(start, -1, 'book-source missing')
        region = html[start : start + 2500]

        self.assertNotIn('<script>alert(1)</script>', region)
        self.assertIn('&lt;script&gt;', region)
        self.assertIn('alert(1)', region)
        self.assertIn('&lt;/script&gt;', region)

        self.assertNotIn('<b>bold</b>', region)
        self.assertIn('&lt;b&gt;bold&lt;/b&gt;', region)

        self.assertIn('Tom &amp; Jerry', region)

    def test_reader_js_always_escapes_branch_present(self):
        """Guard against regressing the unsafe indexOf('<') branch."""
        js_path = Path(settings.BASE_DIR) / 'static' / 'library' / 'js' / 'reader.js'
        source = js_path.read_text(encoding='utf-8')
        self.assertNotIn("para.indexOf('<') >= 0", source)
        self.assertIn('escapeHtml(para)', source)
        self.assertIn('Always escape', source)

    def test_escapeHtml_logic_matches_browser_textcontent_behavior(self):
        """Mirror reader.js escapeHtml (textContent → innerHTML) in Python."""
        dangerous = '<script>alert(1)</script> and <b>x</b> & y'
        escaped = escape(dangerous)
        self.assertEqual(
            escaped,
            '&lt;script&gt;alert(1)&lt;/script&gt; and &lt;b&gt;x&lt;/b&gt; &amp; y',
        )
        self.assertEqual(unescape(escaped), dangerous)
        para_html = '<p>' + escaped + '</p>'
        self.assertIn('&lt;script&gt;', para_html)


class ReaderAuthUnificationTests(TestCase):
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

    def test_jwt_only_without_sessionid_returns_200(self):
        tokens = get_tokens_for_user(self.user)
        client = Client()
        client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']
        client.cookies.pop('sessionid', None)
        response = client.get(self.read_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'book-reader')
        self.assertContains(response, 'O‘qish matni')

    def test_session_only_without_jwt_returns_200(self):
        client = Client()
        self.assertTrue(client.login(username='authy', password='Str0ng-Passw0rd!'))
        client.cookies.pop(settings.JWT_ACCESS_COOKIE_NAME, None)
        client.cookies.pop(settings.JWT_REFRESH_COOKIE_NAME, None)
        response = client.get(self.read_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'book-reader')

    def test_invalid_jwt_without_session_redirects_to_login(self):
        client = Client()
        client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = 'not.a.valid.jwt'
        client.cookies.pop('sessionid', None)
        response = client.get(self.read_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response.url)

    def test_garbage_jwt_without_session_redirects(self):
        client = Client()
        client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = (
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
            'eyJ1c2VyX2lkIjoxLCJleHAiOjE2MDAwMDAwMDB9.'
            'invalidsignature'
        )
        response = client.get(self.read_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response.url)


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
        self.client.login(username='staleadmin', password='Str0ng-Passw0rd!')
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

    def test_weak_secret_rejected_when_debug_false(self):
        import os
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import os; '
                    "os.environ['SECRET_KEY']='change-me-to-a-long-random-string'; "
                    "os.environ['DEBUG']='False'; "
                    "os.environ['ALLOWED_HOSTS']='localhost'; "
                    "os.environ['ALLOW_CONSOLE_EMAIL']='1'; "
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
                'SECRET_KEY': 'change-me-to-a-long-random-string',
                'DEBUG': 'False',
                'ALLOWED_HOSTS': 'localhost',
                'ALLOW_CONSOLE_EMAIL': '1',
                'USE_TLS': '0',
            },
        )
        self.assertNotEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertIn('SECRET_KEY', combined)

    def test_star_allowed_hosts_rejected_when_debug_false(self):
        import os
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import os; '
                    "os.environ['SECRET_KEY']='qa-strong-secret-key-32chars-min!!'; "
                    "os.environ['DEBUG']='False'; "
                    "os.environ['ALLOWED_HOSTS']='*'; "
                    "os.environ['ALLOW_CONSOLE_EMAIL']='1'; "
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
                'SECRET_KEY': 'qa-strong-secret-key-32chars-min!!',
                'DEBUG': 'False',
                'ALLOWED_HOSTS': '*',
                'ALLOW_CONSOLE_EMAIL': '1',
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

        proc = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import os; '
                    "os.environ['SECRET_KEY']='qa-strong-secret-key-32chars-min!!'; "
                    "os.environ['DEBUG']='False'; "
                    "os.environ['ALLOWED_HOSTS']='localhost,127.0.0.1'; "
                    "os.environ['ALLOW_CONSOLE_EMAIL']='1'; "
                    "os.environ['USE_TLS']='0'; "
                    "os.environ['DJANGO_SETTINGS_MODULE']='backend.settings'; "
                    'import django; django.setup(); print("BOOT_OK")'
                ),
            ],
            cwd=str(Path(settings.BASE_DIR)),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                'SECRET_KEY': 'qa-strong-secret-key-32chars-min!!',
                'DEBUG': 'False',
                'ALLOWED_HOSTS': 'localhost,127.0.0.1',
                'ALLOW_CONSOLE_EMAIL': '1',
                'USE_TLS': '0',
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn('BOOT_OK', proc.stdout)
