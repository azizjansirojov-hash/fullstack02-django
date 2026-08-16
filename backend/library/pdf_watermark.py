"""Download-time visible overlay + forensic marker for licensed PDFs.

Uses ReportLab (already a project dependency) to draw page content, then pypdf
to merge that overlay onto every page and write Info / catalog / XMP markers.

This is attribution DRM, not encryption: a determined user can still screenshot,
crop, or re-export through a processor that strips metadata and redraws pages.
"""

from __future__ import annotations

import hashlib
import xml.sax.saxutils
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas as pdf_canvas

WATERMARK_PREFIX = 'LibroUZ-license:'
INFO_KEY = '/LibroUZ-License'
CATALOG_KEY = '/LibroUZ'
XMP_NS = 'https://libro.uz/ns/pdf/1.0/'


def license_identifier(*, user, purchase) -> str:
    """Stable per-purchase marker: purchaser email plus Purchase primary key."""
    email = (getattr(user, 'email', None) or '').strip()
    if not email:
        email = f'user:{getattr(user, "pk", "unknown")}'
    purchase_id = getattr(purchase, 'pk', None) or 'none'
    return f'{email}|purchase:{purchase_id}'


def license_fingerprint(identifier: str) -> str:
    """Short, unique-per-identifier hash shown on the page and stored in XMP."""
    return hashlib.sha256(identifier.encode('utf-8')).hexdigest()[:16]


def overlay_label(identifier: str, stamped_at_iso: str) -> str:
    safe_id = identifier.replace('\n', ' ').replace('\r', ' ')
    return f'{WATERMARK_PREFIX} {safe_id} {stamped_at_iso} #{license_fingerprint(identifier)}'


def _copy_attachments(reader: PdfReader, writer: PdfWriter) -> None:
    """``append()`` does not keep embedded files; copy them explicitly."""
    attachments = getattr(reader, 'attachments', None) or {}
    for filename, files in attachments.items():
        blobs = [files] if isinstance(files, (bytes, bytearray)) else files
        for blob in blobs:
            writer.add_attachment(filename, blob)


def _overlay_page(width: float, height: float, label: str):
    buf = BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(width, height))
    c.setTitle('')
    fill = Color(0.15, 0.15, 0.18, alpha=0.16)
    c.setFillColor(fill)
    c.setFont('Helvetica', 11)
    c.saveState()
    c.translate(width / 2.0, height / 2.0)
    c.rotate(32)
    # Repeat so cropping a corner still leaves some of the string.
    step = 48
    for offset in range(-4, 5):
        c.drawCentredString(0, offset * step, label)
    c.restoreState()
    c.setFillColor(Color(0.12, 0.12, 0.14, alpha=0.35))
    c.setFont('Helvetica', 8)
    c.drawString(18, 16, label[:240])
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def _xmp_packet(identifier: str) -> str:
    ident = xml.sax.saxutils.escape(identifier)
    digest = license_fingerprint(identifier)
    return (
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        f'<rdf:Description xmlns:librouz="{XMP_NS}" '
        f'librouz:licenseId="{ident}" '
        f'librouz:licenseHash="{digest}"/>'
        '</rdf:RDF></x:xmpmeta>'
        '<?xpacket end="w"?>'
    )


def stamp_pdf_bytes(pdf_bytes: bytes, identifier: str, *, stamped_at_iso: str = '') -> bytes:
    """Merge a visible overlay and embed forensic identifiers. Rewrites the PDF."""
    safe = identifier.replace('\n', ' ').replace('\r', ' ')
    label = overlay_label(safe, stamped_at_iso)
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    except PdfReadError as exc:
        raise ValueError('Licensed PDF could not be parsed for watermarking.') from exc
    if not reader.pages:
        raise ValueError('Licensed PDF has no pages to watermark.')

    writer = PdfWriter()
    writer.append(reader)
    _copy_attachments(reader, writer)

    overlays: dict[tuple[float, float], object] = {}
    for page in writer.pages:
        box = page.mediabox
        width = float(box.width)
        height = float(box.height)
        key = (round(width, 2), round(height, 2))
        if key not in overlays:
            overlays[key] = _overlay_page(width, height, label)
        page.merge_page(overlays[key])

    meta = {}
    if reader.metadata:
        for key, value in reader.metadata.items():
            if value is not None:
                meta[key] = value
    meta[INFO_KEY] = safe
    writer.add_metadata(meta)

    writer._root_object[NameObject(CATALOG_KEY)] = DictionaryObject(
        {
            NameObject('/LicenseId'): TextStringObject(safe),
            NameObject('/LicenseHash'): TextStringObject(license_fingerprint(safe)),
        }
    )
    try:
        writer.xmp_metadata = _xmp_packet(safe).encode('utf-8')
    except Exception:
        # XMP assignment is best-effort; Info + catalog markers still apply.
        pass

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
