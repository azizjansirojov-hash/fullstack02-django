"""Download-time identifier stamp for licensed (purchased) PDFs."""

from __future__ import annotations

WATERMARK_PREFIX = 'LibroUZ-license:'


def license_identifier(*, user, purchase) -> str:
    """Stable per-purchase marker: purchaser email plus Purchase primary key."""
    email = (getattr(user, 'email', None) or '').strip()
    if not email:
        email = f'user:{getattr(user, "pk", "unknown")}'
    purchase_id = getattr(purchase, 'pk', None) or 'none'
    return f'{email}|purchase:{purchase_id}'


def stamp_pdf_bytes(pdf_bytes: bytes, identifier: str) -> bytes:
    """Embed ``identifier`` as a PDF comment without rewriting page content."""
    safe = identifier.replace('\n', ' ').replace('\r', ' ')
    comment = f'\n% {WATERMARK_PREFIX} {safe}\n'.encode('utf-8')
    # Append after the existing file, including %%EOF. Inserting the comment
    # immediately before %%EOF breaks startxref discovery in pypdf (and some
    # viewers): the xref offset is unchanged, but parsers that require
    # startxref to sit directly above %%EOF fail with "startxref not found".
    return pdf_bytes + comment
