from playwright.sync_api import sync_playwright
import json

USER = "parity_tester"
PASS = "Parity-Test-1!"
SLUG = "jinoyat-va-jazo-2"
VITE = "http://127.0.0.1:5173"
DJANGO = "http://127.0.0.1:8000"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    logs = []
    page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"PAGEERROR: {e}"))
    reqs = []

    def on_resp(r):
        if any(x in r.url for x in ("pdf", "reader", "media", "worker")):
            reqs.append((r.status, r.url[:120]))

    page.on("response", on_resp)
    page.goto(f"{VITE}/login/", wait_until="networkidle")
    page.fill("#id_username", USER)
    page.fill('input[name="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_timeout(1500)

    man = page.request.get(f"{VITE}/api/library/{SLUG}/reader/")
    print("manifest", man.status)
    data = man.json()
    print("pdf_url", data.get("pdf_url"), "has_pdf", data.get("has_pdf"))
    pdf = page.request.get(f"{VITE}{data['pdf_url']}")
    print("pdf via vite", pdf.status, pdf.headers.get("content-type"), len(pdf.body()))
    pdf2 = page.request.get(f"{DJANGO}{data['pdf_url']}")
    print("pdf via django", pdf2.status, pdf2.headers.get("content-type"), len(pdf2.body()))

    page.goto(f"{VITE}/library/{SLUG}/read?mode=pdf", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(8000)
    print("title", page.title())
    print("url", page.url)
    print(
        "dom",
        page.evaluate(
            """() => ({
      hasPdfMode: !!document.querySelector('.pdf-reader-mode, .pdf-reader'),
      hasFlip: !!document.querySelector('.book-reader__mount, .flip-reader-view'),
      shell: document.querySelector('.reader-shell')?.className,
      mode: document.querySelector('[data-reader-mode]')?.getAttribute('data-reader-mode'),
      bodySnippet: document.body.innerText.slice(0,240),
      canvases: document.querySelectorAll('canvas').length,
      states: Array.from(document.querySelectorAll('.pdf-reader__state')).map(el => el.innerText),
    })"""
        ),
    )
    print("responses", json.dumps(reqs[-30:], indent=2))
    print("logs:\n" + "\n".join(logs[-40:]))
    browser.close()
