"""Sanitize BookTranslation.body before persist (defense in depth for XSS)."""

from __future__ import annotations

import bleach

# Keep formatting that staff may paste; reject script/iframe/on* via empty attrs.
ALLOWED_TAGS = frozenset(
    {
        'p',
        'br',
        'strong',
        'em',
        'h1',
        'h2',
        'h3',
        'ul',
        'ol',
        'li',
        'blockquote',
    }
)


def sanitize_book_body(value: str | None) -> str:
    """Strip dangerous HTML from book body; preserve allowlisted tags without attributes."""
    if not value:
        return ''
    return bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes={},
        protocols=[],
        strip=True,
    )
