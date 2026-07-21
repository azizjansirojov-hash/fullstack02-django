"""End-to-end reader smoke test via Playwright."""
import os
import sys
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from library.models import Book
from playwright.sync_api import sync_playwright


def main():
    user_model = get_user_model()
    user, _ = user_model.objects.get_or_create(username="reader")
    user.set_password("testpass123")
    user.save()

    book = Book.objects.filter(is_published=True).first()
    if not book:
        raise SystemExit("No published book found")

    client = Client()
    assert client.login(username="reader", password="testpass123")
    session = client.cookies.get("sessionid")
    base = f"http://127.0.0.1:8000/library/{book.slug}/read/"
    errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(
            [
                {
                    "name": "sessionid",
                    "value": session.value,
                    "domain": "127.0.0.1",
                    "path": "/",
                }
            ]
        )
        page = context.new_page()
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        page.goto(f"{base}?mode=flip", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        flip_pages = page.evaluate(
            'document.querySelectorAll("#book-mount .page, #book-mount .stf__parent").length'
        )
        assert flip_pages > 0, f"Expected flip pages, got {flip_pages}"

        page.locator("[data-action='next']").click(force=True)
        page.wait_for_timeout(800)
        counter = page.locator("#book-counter").inner_text()
        assert "2" in counter, f"Expected page 2, got {counter}"

        page.locator('[data-mode="pdf"]').click(force=True)
        page.wait_for_timeout(5000)
        pdf_mode = page.evaluate('document.getElementById("book-reader").dataset.readerMode')
        assert pdf_mode == "pdf", f"Expected pdf mode, got {pdf_mode}"

        page.locator("[data-action='listen']").click(force=True)
        page.wait_for_timeout(500)
        assert page.locator(".audio-playback:not([hidden])").count() > 0

        page.locator('[data-mode="flip"]').click(force=True)
        page.wait_for_timeout(2500)
        flip_mode = page.evaluate('document.getElementById("book-reader").dataset.readerMode')
        assert flip_mode == "flip", f"Expected flip mode, got {flip_mode}"

        browser.close()

    if errors:
        raise SystemExit(f"JS errors: {errors}")

    print("Reader E2E smoke test passed for", book.slug)


if __name__ == "__main__":
    main()
