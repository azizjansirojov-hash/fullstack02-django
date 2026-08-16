# CONTENT_PROTECTION.md — what licensed-content controls actually do

This is an honesty note, not a DRM claim. Licensed books on Libro.UZ are **sold as a personal reading license**. After a paid `Purchase`, the entitled user can retrieve the full work through ordinary product APIs. Overlay watermarks and metadata help with leak attribution. They do **not** encrypt, wrap, or otherwise prevent copying.

## What is gated

[`user_can_access_book`](backend/library/access.py) is the entitlement check:

- `rights_status == public_domain` → anyone authenticated can stream PDF/audio and load the reader.
- otherwise → a `Purchase` with `status=paid` for that user+book.

Call sites: gated media ([`library/media_views.py`](backend/library/media_views.py)), reader manifest, book-detail `can_read` / media URLs, checkout `already_entitled`.

Unauthenticated catalog cards omit media URLs. Unpublished books 404.

## What an entitled user can extract today

1. **Reader manifest JSON** — `GET /api/library/<slug>/reader/` (`BookReaderManifestAPIView`) returns the full sanitized translation `body` plus chapter audio URLs and `pdf_url`. Copying that JSON is a complete text exfil of the licensed work. There is no page-windowed body API.
2. **PDF download** — `GET /library/media/<slug>/pdf/` after entitlement. Licensed files are stamped at serve time (visible overlay + Info/catalog/XMP). Public-domain files are byte-identical to storage and support HTTP Range. Licensed files are stamped once per purchase+source file into a local cache, then Range-served; the first miss still loads the whole PDF into memory (pypdf cannot stream a merge).
3. **Audio download** — chapter and book-level MP3s with HTTP Range. No forensic stamp.

A user who paid (or who stole a valid session) can save these responses with browser tools. That is expected for a web reader; it is not a bug in the entitlement check.

## What the PDF stamp survives / does not

See the table in [`SECURITY_HARDENING_REPORT.md`](SECURITY_HARDENING_REPORT.md) §3. Short version:

- Survives: opening in a normal viewer, many “print to PDF” paths (as pixels), cropping that leaves overlay repeats.
- Does not survive: re-typesetting, copying body text from the manifest JSON, metadata strippers (Info/XMP gone), determined PDF editors.

Helvetica cannot render non-Latin emails in the overlay (known limitation).

## What would actually change the threat model

Not in this codebase, and not faked here:

- Object storage + per-purchase pre-stamped objects (or encrypted blobs) so Gunicorn never holds 2× file RAM.
- Segmented body API (no full `body` in one JSON).
- True DRM (Widevine-class, ACS, etc.) — out of scope for this product and this stack.

Until product accepts one of those, treat licensed text as **copyable by any entitled account**. Watermarking is attribution, not prevention.

Related: [`PAYMENTS.md`](PAYMENTS.md) (checkout → `Purchase`), [`library/pdf_watermark.py`](backend/library/pdf_watermark.py).
