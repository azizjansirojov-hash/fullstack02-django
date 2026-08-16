"""Disposable-email denylist snapshot.

Source: https://github.com/disposable-email-domains/disposable-email-domains
(disposable_email_blocklist.conf). Refresh the sibling data file periodically.
"""

from functools import lru_cache
from pathlib import Path

_BLOCKLIST_PATH = Path(__file__).resolve().parent / 'data' / 'disposable_email_blocklist.txt'


@lru_cache(maxsize=1)
def disposable_email_domains() -> frozenset[str]:
    domains = set()
    if not _BLOCKLIST_PATH.is_file():
        return frozenset()
    for line in _BLOCKLIST_PATH.read_text(encoding='utf-8').splitlines():
        domain = line.strip().lower()
        if domain and not domain.startswith('#'):
            domains.add(domain)
    return frozenset(domains)


def is_disposable_email_domain(domain: str) -> bool:
    return (domain or '').strip().lower() in disposable_email_domains()
