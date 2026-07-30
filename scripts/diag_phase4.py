import json
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USER = "parity_tester"
PASS = "Parity-Test-1!"
SLUG = "jinoyat-va-jazo-2"
VITE = "http://127.0.0.1:5173"
DJANGO = "http://127.0.0.1:8000"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(f"{VITE}/login/", wait_until="networkidle")
    page.fill("#id_username", USER)
    page.fill('input[name="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_timeout(2000)
    me = page.request.get(f"{VITE}/api/me/")
    print("me", me.status)

    page.goto(f"{VITE}/library/{SLUG}/read?mode=flip", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    flip = page.evaluate(
        """() => ({
      shell: !!document.querySelector('.reader-shell'),
      flip: !!document.querySelector('.flip-reader-view'),
      django: !!document.querySelector('#book-reader'),
      pages: document.querySelectorAll('.page').length,
      counter: document.body.innerText.match(/\\d+\\s*\\/\\s*\\d+\\s*sahifa/)?.[0] || null,
    })"""
    )
    print("flip", json.dumps(flip))

    page.goto(f"{VITE}/library/{SLUG}/read?mode=pdf", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    pdf = page.evaluate(
        """() => ({
      shell: !!document.querySelector('.reader-shell'),
      pdf: !!document.querySelector('.pdf-reader-mode'),
      canvases: document.querySelectorAll('canvas.pdf-reader__canvas').length,
      counter: document.body.innerText.match(/\\d+\\s*\\/\\s*\\d+\\s*sahifa/)?.[0] || null,
      timeout: /taking too long/i.test(document.body.innerText),
    })"""
    )
    print("pdf", json.dumps(pdf))

    page.goto(f"{DJANGO}/library/{SLUG}/read/?mode=flip", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    django = page.evaluate(
        """() => ({
      django: !!document.querySelector('#book-reader'),
      url: location.href,
    })"""
    )
    print("django", json.dumps(django))
    browser.close()
