"""Browser-level XSS verification for the Django flip reader.

Requires: pip install playwright && playwright install chromium
Run with Django serving on BASE_URL (default http://127.0.0.1:8000):

    cd backend
    python scripts/test_reader_xss_playwright.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from library.models import Book, BookTranslation, Purchase  # noqa: E402

XSS_BODY = (
    '<script>window.__xss_script=true</script>\n\n'
    '<img src=x onerror="window.__xss_img=true">\n\n'
    'Plain <b>bold</b> and Tom & Jerry.'
)

USERNAME = 'xss_playwright_user'
PASSWORD = 'Str0ng-Passw0rd!'
SLUG = 'xss-playwright-book'
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:8000')


def ensure_fixture():
    User = get_user_model()
    User.objects.filter(username=USERNAME).delete()
    Book.objects.filter(slug=SLUG).delete()
    user = User.objects.create_user(USERNAME, 'xss@example.com', PASSWORD)
    book = Book.objects.create(
        author_name='XSS QA',
        slug=SLUG,
        is_published=True,
        rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
        pdf_generation_status='ready',
        audio_generation_status='ready',
    )
    BookTranslation.objects.create(
        book=book,
        language=BookTranslation.Language.UZ,
        title='XSS Playwright Book',
        body=XSS_BODY,
    )
    Purchase.objects.filter(user=user, book=book).delete()
    return user


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('FAIL: playwright not installed. Run: pip install playwright && playwright install chromium')
        return 2

    from django.conf import settings
    from django.test import Client

    ensure_fixture()
    reader_url = f'{BASE_URL}/library/{SLUG}/read/'
    dialogs: list[str] = []

    client = Client()
    if not client.login(username=USERNAME, password=PASSWORD):
        print('FAIL: could not log in test user via Django session')
        return 1

    cookie_payload = []
    for name, morsel in client.cookies.items():
        cookie_payload.append(
            {
                'name': name,
                'value': morsel.value,
                'domain': '127.0.0.1',
                'path': '/',
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        if cookie_payload:
            context.add_cookies(cookie_payload)
        page = context.new_page()
        page.on('dialog', lambda dialog: dialogs.append(dialog.message) or dialog.dismiss())
        response = page.goto(reader_url, wait_until='networkidle')
        status = response.status if response else None
        script_flag = page.evaluate('window.__xss_script')
        img_flag = page.evaluate('window.__xss_img')
        source_html = page.locator('#book-source').inner_html()
        browser.close()

    print('--- Playwright XSS evidence ---')
    print('reader_url:', reader_url)
    print('http_status:', status)
    print('dialog_count:', len(dialogs))
    print('window.__xss_script:', script_flag)
    print('window.__xss_img:', img_flag)
    print('raw <script> in #book-source:', '<script>' in source_html)
    print('escaped script entity present:', '&lt;script&gt;' in source_html)

    failed = False
    if status != 200:
        print('FAIL: reader did not return 200')
        failed = True
    if dialogs:
        print('FAIL: unexpected dialogs:', dialogs)
        failed = True
    if script_flag or img_flag:
        print('FAIL: XSS payload executed in browser')
        failed = True
    if '<script>' in source_html:
        print('FAIL: unescaped script tag in live DOM')
        failed = True
    if not failed:
        print('PASS: no script execution or exploitable DOM detected')
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
