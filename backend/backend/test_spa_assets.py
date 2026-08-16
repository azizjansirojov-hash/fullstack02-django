"""SPA hashed assets are served by WhiteNoise, not django.views.static.serve."""

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
from whitenoise import WhiteNoise


class SpaAssetWhiteNoiseTests(SimpleTestCase):
    def test_urlconf_does_not_static_serve_frontend_assets(self):
        src = Path(__file__).with_name('urls.py').read_text(encoding='utf-8')
        self.assertNotIn("str(dist / 'assets')", src)
        self.assertIn('WHITENOISE_ROOT', src)

    def test_whitenoise_serves_files_from_dist_root(self):
        def fallback(environ, start_response):
            start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
            return [b'miss']

        with TemporaryDirectory() as tmp:
            assets = Path(tmp) / 'assets'
            assets.mkdir()
            (assets / 'app.js').write_bytes(b'console.log(1)')
            app = WhiteNoise(fallback, root=tmp)
            captured = {}

            def start_response(status, headers, exc_info=None):
                captured['status'] = status
                captured['headers'] = headers

            body = b''.join(
                app(
                    {
                        'REQUEST_METHOD': 'GET',
                        'PATH_INFO': '/assets/app.js',
                        'SERVER_PROTOCOL': 'HTTP/1.1',
                    },
                    start_response,
                )
            )
            self.assertTrue(captured['status'].startswith('200'))
            self.assertEqual(body, b'console.log(1)')
