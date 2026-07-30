"""Playwright + axe-core accessibility sweep for audit."""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000'
ROUTES = ['/login', '/register', '/library', '/library/dokon', '/password-reset']

AXE_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js'


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        console_msgs = []
        page.on('console', lambda msg: console_msgs.append({'type': msg.type, 'text': msg.text}))
        page.on('pageerror', lambda err: console_msgs.append({'type': 'pageerror', 'text': str(err)}))

        for route in ROUTES:
            url = BASE.rstrip('/') + route
            page.goto(url, wait_until='networkidle', timeout=60000)
            page.add_script_tag(url=AXE_CDN)
            page.wait_for_timeout(500)
            axe = page.evaluate(
                """async () => {
                  if (!window.axe) return {error: 'axe missing'};
                  const r = await window.axe.run(document, {runOnly: {type:'tag', values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
                  return {
                    violations: r.violations.map(v => ({
                      id: v.id, impact: v.impact, description: v.description,
                      help: v.help, nodes: v.nodes.length,
                      targets: v.nodes.slice(0,5).map(n => n.target)
                    })),
                    passes: r.passes.length,
                    incomplete: r.incomplete.length
                  };
                }"""
            )
            results.append({'route': route, 'axe': axe})
            print(json.dumps({'section': 's9_axe', 'route': route, 'axe': axe}, ensure_ascii=False), flush=True)

        # Exercise login form for console warnings
        page.goto(BASE.rstrip('/') + '/login', wait_until='networkidle')
        page.fill('input[name="username"], #id_username, input[type="text"]', 'x')
        page.fill('input[name="password"], #id_password, input[type="password"]', 'y')
        page.wait_for_timeout(300)
        print(
            json.dumps(
                {
                    'section': 's9_console',
                    'messages': console_msgs[:50],
                    'count': len(console_msgs),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        browser.close()
    print('A11Y_DONE', flush=True)


if __name__ == '__main__':
    main()
