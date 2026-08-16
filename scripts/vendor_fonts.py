"""One-shot helper to vendor latin Sora/Fraunces woff2 files."""

import re
import urllib.request
from pathlib import Path

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
CSS_URL = (
    'https://fonts.googleapis.com/css2'
    '?family=Sora:wght@400;600'
    '&family=Fraunces:opsz,wght@9..144,500;9..144,650'
    '&display=swap'
)


def main():
    root = Path(__file__).resolve().parents[1]
    req = urllib.request.Request(CSS_URL, headers={'User-Agent': UA})
    css = urllib.request.urlopen(req, timeout=30).read().decode()
    wanted = {}
    for block in re.split(r'(?=/\* )', css):
        if '/* latin */' not in block:
            continue
        fam = re.search(r"font-family: '([^']+)'", block)
        weight = re.search(r'font-weight: (\d+)', block)
        src = re.search(r'url\((https://[^)]+)\)', block)
        if not (fam and weight and src):
            continue
        name = f'{fam.group(1).lower()}-{weight.group(1)}.woff2'
        wanted[name] = src.group(1)
    fe = root / 'frontend' / 'public' / 'fonts'
    be = root / 'backend' / 'static' / 'fonts'
    fe.mkdir(parents=True, exist_ok=True)
    be.mkdir(parents=True, exist_ok=True)
    for name, href in wanted.items():
        data = urllib.request.urlopen(
            urllib.request.Request(href, headers={'User-Agent': UA}),
            timeout=30,
        ).read()
        (fe / name).write_bytes(data)
        (be / name).write_bytes(data)
        print(name, len(data))


if __name__ == '__main__':
    main()
