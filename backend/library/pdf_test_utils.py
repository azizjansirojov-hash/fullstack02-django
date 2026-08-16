"""Real, parser-valid PDF fixtures for watermark tests (not toy %PDF comments)."""

from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def sample_pdf_bytes(*, title: str = 'Libro sample', pages: int = 2) -> bytes:
    """A small ReportLab PDF with xref/startxref — the structure that broke the old stamp."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(title)
    c.setAuthor('Libro.UZ tests')
    width, height = letter
    for i in range(1, pages + 1):
        c.setFont('Times-Roman', 14)
        c.drawString(72, height - 72, f'{title} — page {i} of {pages}')
        c.drawString(72, height - 108, 'Body text for overlay extraction tests.')
        c.showPage()
    c.save()
    return buf.getvalue()
