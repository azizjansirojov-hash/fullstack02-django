"""Verify book detail -> reader flows via Playwright."""
import os
import sys
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.test import Client
from library.models import Book
from playwright.sync_api import sync_playwright


def main():
    client = Client()
    assert client.login(username="reader", password="testpass123")
    book = Book.objects.filter(is_published=True).first()
    session = client.cookies.get("sessionid")
    detail = f"http://127.0.0.1:8000/library/{book.slug}/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies(
            [{"name": "sessionid", "value": session.value, "domain": "127.0.0.1", "path": "/"}]
        )
        page = context.new_page()

        page.goto(detail, wait_until="networkidle")
        page.click("#btn-continue-reading")
        page.wait_for_url("**/read/**", timeout=15000)
        page.wait_for_selector("#book-mount .page, #book-mount .stf__parent", timeout=15000)
        assert page.locator("#book-loading.is-hidden").count() > 0
        assert page.locator(".reader-chrome [data-action='next']").is_visible()
        print("OK continue reading -> flip mode")

        page.goto(detail, wait_until="networkidle")
        page.click("#btn-listen-detail")
        page.wait_for_url("**/read/**", timeout=15000)
        page.wait_for_selector(".audio-playback:not([hidden])", timeout=15000)
        assert page.locator("#audio-sentence-count").inner_text() != "0 / 0"
        print("OK listen -> audio bar with sentences")

        page.wait_for_selector("#book-mount .page, #book-mount .stf__parent", timeout=15000)
        pdf_tab = page.locator(".reader-chrome [data-action='page']")
        if pdf_tab.is_enabled():
            pdf_tab.click()
            page.wait_for_timeout(1200)
            assert page.locator("#book-reader").get_attribute("data-reader-mode") == "pdf"
            assert page.locator("#pdf-reader .pdf-reader__page, #pdf-reader .pdf-reader__canvas").count() > 0
            print("OK pdf mode from reader toolbar")

        browser.close()

    print("Detail-page matrix passed")


if __name__ == "__main__":
    main()
