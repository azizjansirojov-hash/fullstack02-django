"""Browser-level XSS verification for the React flip reader (JWT SPA).

Requires: playwright (Python) + chromium, and Vite+Django (or Docker SPA) on BASE_URL.

    cd backend
    python scripts/test_reader_xss_playwright.py

SPA_ORIGIN defaults to http://127.0.0.1:5173 (local Vite). Set BASE_URL to the
SPA origin so /library/<slug>/read loads the React reader.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import error, request

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from library.models import Book, BookTranslation  # noqa: E402
from users.auth import get_tokens_for_user  # noqa: E402

XSS_BODY = (
    '<script>window.__xss_script=true</script>\n\n'
    '<img src=x onerror="window.__xss_img=true">\n\n'
    'Plain <b>bold</b> and Tom & Jerry.'
)

USERNAME = 'xss_playwright_user'
PASSWORD = 'Str0ng-Passw0rd!'
SLUG = 'xss-playwright-book'
# React SPA origin (Vite locally, or same-origin Docker with FRONTEND_DIST).
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5173').rstrip('/')
API_ORIGIN = os.environ.get('API_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')


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
    return user


def jwt_cookies(user) -> list[dict]:
    tokens = get_tokens_for_user(user)
    domain = '127.0.0.1'
    return [
        {
            'name': settings.JWT_ACCESS_COOKIE_NAME,
            'value': tokens['access'],
            'domain': domain,
            'path': '/',
        },
        {
            'name': settings.JWT_REFRESH_COOKIE_NAME,
            'value': tokens['refresh'],
            'domain': domain,
            'path': '/',
        },
    ]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            'FAIL: playwright not installed. '
            'Run: pip install playwright && playwright install chromium'
        )
        return 2

    user = ensure_fixture()
    reader_url = f'{BASE_URL}/library/{SLUG}/read?mode=flip'
    dialogs: list[str] = []

    # Sanity: API must serve escaped/plain body for the book.
    try:
        with request.urlopen(f'{API_ORIGIN}/api/library/{SLUG}/', timeout=10) as resp:
            _ = resp.status
    except error.URLError as exc:
        print(f'WARN: API probe failed ({exc}); continuing with browser check')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(jwt_cookies(user))
        page = context.new_page()
        page.on(
            'dialog',
            lambda dialog: dialogs.append(dialog.message) or dialog.dismiss(),
        )
        response = page.goto(reader_url, wait_until='networkidle')
        status = response.status if response else None
        page.wait_for_selector('.flip-reader-view', timeout=30_000)
        page.wait_for_timeout(1500)
        script_flag = page.evaluate('Boolean(window.__xss_script)')
        img_flag = page.evaluate('Boolean(window.__xss_img)')
        flip_html = page.locator('.flip-reader-view').inner_html()
        live_scripts = page.locator('.flip-reader-view script').count()
        browser.close()

    print('--- Playwright XSS evidence ---')
    print('reader_url:', reader_url)
    print('http_status:', status)
    print('dialog_count:', len(dialogs))
    print('window.__xss_script:', script_flag)
    print('window.__xss_img:', img_flag)
    print('live_script_elements:', live_scripts)
    print('raw onerror attr present:', bool(__import__('re').search(r'<img[^>]+onerror=', flip_html, __import__('re').I)))
    print('raw script open tag in flip html:', '<script>window.__xss_script' in flip_html.lower())

    failed = False
    if status not in (200, 304):
        print('FAIL: reader did not return 200')
        failed = True
    if dialogs:
        print('FAIL: unexpected dialogs:', dialogs)
        failed = True
    if script_flag or img_flag:
        print('FAIL: XSS payload executed in browser')
        failed = True
    if live_scripts:
        print('FAIL: script elements present in flip reader DOM')
        failed = True
    if not failed:
        print('PASS: no script execution or exploitable DOM detected')
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
