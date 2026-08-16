"""Manual Playwright helper for reader-bug debugging — not used by CI or production.

Writes NDJSON to debug-c49e1c.log at the repo root (gitignored via *.log).
"""
import json
import os
import sys
import time
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parent
LOG_PATH = REPO_ROOT / "debug-c49e1c.log"
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.contrib.auth import get_user_model
from library.models import Book, BookTranslation

from django.core.files.base import ContentFile
from django.test import Client

from playwright.sync_api import sync_playwright


def log(hypothesis_id, location, message, data):
    entry = {
        "sessionId": "c49e1c",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
        "runId": "playwright-verify",
    }
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def ensure_book_with_audio():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="reader")
    user.set_password("testpass123")
    user.save()

    book = Book.objects.filter(is_published=True).first()
    if not book:
        book = Book.objects.create(
            author_name="Test Author",
            slug="verify-reader-book",
            is_published=True,
        )
        BookTranslation.objects.create(
            book=book,
            title="Verify Reader",
            body="Birinchi jumla. Ikkinchi jumla. Uchinchi jumla.",
        )
    if not book.audio_file:
        book.audio_file.save("verify-test.mp3", ContentFile(b"\x00" * 128), save=True)
    translation = book.get_translation("uz")
    if translation and not translation.audio_sync:
        translation.audio_sync = []
        translation.save(update_fields=["audio_sync"])
    return book


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    book = ensure_book_with_audio()
    read_url = f"http://127.0.0.1:8000/library/{book.slug}/read/"

    client = Client()
    assert client.login(username="reader", password="testpass123"), "login failed"
    session = client.cookies.get("sessionid")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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

        page.goto(f"{read_url}?mode=flip", wait_until="networkidle")
        page.wait_for_selector(".reader-chrome", timeout=15000)
        page.wait_for_selector("#book-mount .page, #book-mount .stf__parent", timeout=15000)
        page.wait_for_timeout(500)

        loading_hidden_flip = page.locator("#book-loading.is-hidden").count() > 0
        assert loading_hidden_flip, "loading overlay should be hidden in flip mode"
        log("L", "verify_reader_bugs.py:loading-flip", "loading hidden in flip", {"hidden": loading_hidden_flip})

        legacy_nav_count = page.locator("nav.book-reader__toolbar").count()
        prev_in_chrome = page.locator(".reader-chrome [data-action='prev']").count()
        legacy_prev = page.locator("#btn-prev").count()
        assert legacy_nav_count == 0, "legacy nav should be removed from DOM"
        assert legacy_prev == 0, "legacy #btn-prev should not exist"
        assert prev_in_chrome == 1, "ReaderToolbar should have exactly one prev button"
        log(
            "F",
            "verify_reader_bugs.py:toolbar",
            "toolbar duplicate check",
            {
                "legacy_nav_count": legacy_nav_count,
                "chrome_prev_count": prev_in_chrome,
                "legacy_prev_count": legacy_prev,
            },
        )

        flip_page_before = page.locator("#reader-page-count").inner_text()
        next_btn = page.locator(".reader-chrome [data-action='next']")
        page.wait_for_function(
            "(btn) => !btn.disabled",
            arg=next_btn.element_handle(),
            timeout=15000,
        )
        next_btn.click()
        page.wait_for_timeout(800)
        flip_page_after = page.locator("#reader-page-count").inner_text()
        assert flip_page_before != flip_page_after, f"flip next should change page label ({flip_page_before!r} -> {flip_page_after!r})"
        log("N", "verify_reader_bugs.py:flip-nav", "flip navigation", {"before": flip_page_before, "after": flip_page_after})

        pdf_tab = page.locator(".reader-chrome [data-action='page']")
        if pdf_tab.is_enabled():
            page.click(".reader-chrome [data-action='page']")
            page.wait_for_timeout(1200)
            flip_hidden_after_pdf = page.locator("#book-mount").is_hidden()
            pdf_hidden_after_pdf = page.locator("#pdf-reader").is_hidden()
            loading_hidden_pdf = page.locator("#book-loading.is-hidden").count() > 0
            pdf_has_content = page.locator("#pdf-reader .pdf-reader__page, #pdf-reader .pdf-reader__canvas").count()
            assert flip_hidden_after_pdf, "flip mount should be hidden in pdf mode"
            assert not pdf_hidden_after_pdf, "pdf reader should be visible in pdf mode"
            assert loading_hidden_pdf, "loading overlay should be hidden in pdf mode"
            assert pdf_has_content > 0, "pdf reader should render content"
            log(
                "B",
                "verify_reader_bugs.py:mode-pdf",
                "switched to pdf mode",
                {
                    "flip_hidden_after": flip_hidden_after_pdf,
                    "pdf_hidden_after": pdf_hidden_after_pdf,
                    "loading_hidden": loading_hidden_pdf,
                    "pdf_content_nodes": pdf_has_content,
                    "reader_mode": page.locator("#book-reader").get_attribute("data-reader-mode"),
                },
            )

            page.click(".reader-chrome [data-action='focus']")
            page.wait_for_timeout(1200)
            flip_hidden_after_flip = page.locator("#book-mount").is_hidden()
            pdf_hidden_after_flip = page.locator("#pdf-reader").is_hidden()
            flip_has_content = page.locator("#book-mount .page, #book-mount .stf__parent").count()
            assert not flip_hidden_after_flip, "flip mount should be visible after switching back"
            assert flip_has_content > 0, "flip reader should have pages"
            log(
                "C",
                "verify_reader_bugs.py:mode-flip",
                "switched back to flip mode",
                {
                    "flip_hidden_after": flip_hidden_after_flip,
                    "pdf_hidden_after": pdf_hidden_after_flip,
                    "flip_content_nodes": flip_has_content,
                    "reader_mode": page.locator("#book-reader").get_attribute("data-reader-mode"),
                },
            )

        has_audio = page.locator("#book-reader").evaluate(
            "el => Boolean(el.dataset.audioUrl)"
        )
        assert has_audio, "test book should expose data-audio-url"
        page.click('[data-action="listen"]')
        page.wait_for_timeout(300)
        counter_text = page.locator("#audio-sentence-count").inner_text()
        assert counter_text and counter_text != "0 / 0", "audio sentence counter should be populated"
        page.click('[data-audio-action="toggle"]')
        page.wait_for_timeout(500)
        audio_playback_visible = page.locator(".audio-playback:not([hidden])").count() > 0
        assert audio_playback_visible, "audio bar should remain visible after toggle"
        log(
            "D",
            "verify_reader_bugs.py:audio",
            "audio bar state",
            {
                "counter_text": counter_text,
                "audio_playback_visible": audio_playback_visible,
                "audio_url": page.locator("#book-reader").evaluate(
                    "el => el.dataset.audioUrl || ''"
                ),
            },
        )

        browser.close()

    print("Wrote logs to", LOG_PATH)
    print(LOG_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
