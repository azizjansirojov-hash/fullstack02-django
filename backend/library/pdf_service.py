"""Generate a book PDF from Uzbek translation text (ReportLab + Noto Sans)."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .generation_utils import (
    GENERATION_FAILED,
    GENERATION_LEGACY,
    GENERATION_PENDING,
    GENERATION_READY,
    content_hash,
    split_body_paragraphs,
)

logger = logging.getLogger(__name__)

_FONTS_REGISTERED = False


def _font_dir() -> Path:
    return Path(settings.BASE_DIR) / 'static' / 'fonts'


def _ensure_fonts() -> tuple[str, str]:
    global _FONTS_REGISTERED
    regular = 'NotoSans'
    bold = 'NotoSans-Bold'
    if not _FONTS_REGISTERED:
        font_dir = _font_dir()
        regular_path = font_dir / 'NotoSans-Regular.ttf'
        bold_path = font_dir / 'NotoSans-Bold.ttf'
        if not regular_path.is_file() or not bold_path.is_file():
            raise FileNotFoundError(
                f'Noto Sans fonts missing under {font_dir}. '
                'Expected NotoSans-Regular.ttf and NotoSans-Bold.ttf.'
            )
        pdfmetrics.registerFont(TTFont(regular, str(regular_path)))
        pdfmetrics.registerFont(TTFont(bold, str(bold_path)))
        _FONTS_REGISTERED = True
    return regular, bold


def build_pdf_bytes(*, title: str, author: str, language_label: str, body: str) -> bytes:
    """Return PDF bytes for the given book metadata and body text."""
    regular, bold = _ensure_fonts()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title,
        author=author,
    )
    styles = getSampleStyleSheet()
    cover_title = ParagraphStyle(
        'CoverTitle',
        parent=styles['Title'],
        fontName=bold,
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=18,
    )
    cover_meta = ParagraphStyle(
        'CoverMeta',
        parent=styles['Normal'],
        fontName=regular,
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        'BookBody',
        parent=styles['Normal'],
        fontName=regular,
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=10,
    )
    chapter_style = ParagraphStyle(
        'ChapterHead',
        parent=styles['Heading2'],
        fontName=bold,
        fontSize=14,
        leading=18,
        spaceBefore=6,
        spaceAfter=12,
    )

    story = [
        Spacer(1, 4 * cm),
        Paragraph(_escape(title), cover_title),
        Paragraph(_escape(author), cover_meta),
        Paragraph(_escape(language_label), cover_meta),
        PageBreak(),
    ]

    paragraphs = split_body_paragraphs(body)
    if not paragraphs:
        story.append(Paragraph('—', body_style))
    else:
        for index, para in enumerate(paragraphs):
            # Treat short ALL-CAPS / numbered lines as soft chapter markers.
            if index > 0 and _looks_like_heading(para):
                story.append(PageBreak())
                story.append(Paragraph(_escape(para), chapter_style))
            else:
                story.append(Paragraph(_escape(para).replace('\n', '<br/>'), body_style))

    doc.build(story)
    return buffer.getvalue()


def _escape(text: str) -> str:
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _looks_like_heading(para: str) -> bool:
    stripped = para.strip()
    if len(stripped) > 80:
        return False
    lower = stripped.lower()
    return lower.startswith(('bob', 'qism', 'chapter', '1.', '2.', '3.')) or (
        len(stripped) < 40 and stripped.endswith(':')
    )


def ensure_book_pdf(book, *, force: bool = False) -> str:
    """
    Generate and attach PDF for book from Uzbek translation body.

    Returns status string. Skips legacy uploads (file present, no source hash)
    unless force=True. Skips when hash unchanged.
    """
    from .models import BookTranslation

    translation = book.translations.filter(language=BookTranslation.Language.UZ).first()
    if not translation or not (translation.body or '').strip():
        book.pdf_generation_status = GENERATION_PENDING
        book.save(update_fields=['pdf_generation_status', 'updated_at'])
        return GENERATION_PENDING

    digest = content_hash(translation.body)

    if (
        book.pdf_file
        and not book.pdf_source_hash
        and not force
    ):
        # Legacy manually uploaded PDF — leave alone.
        if book.pdf_generation_status != GENERATION_LEGACY:
            book.pdf_generation_status = GENERATION_LEGACY
            book.save(update_fields=['pdf_generation_status', 'updated_at'])
        return GENERATION_LEGACY

    if (
        book.pdf_file
        and book.pdf_source_hash == digest
        and book.pdf_generation_status == GENERATION_READY
        and not force
    ):
        return GENERATION_READY

    book.pdf_generation_status = 'generating'
    book.save(update_fields=['pdf_generation_status', 'updated_at'])

    try:
        pdf_bytes = build_pdf_bytes(
            title=translation.title,
            author=book.author_name,
            language_label='O‘zbek',
            body=translation.body,
        )
        filename = f'{book.slug or book.pk}.pdf'
        if book.pdf_file:
            book.pdf_file.delete(save=False)
        book.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
        book.pdf_source_hash = digest
        book.pdf_generation_status = GENERATION_READY
        from django.utils import timezone

        book.pdf_generated_at = timezone.now()
        book.save(
            update_fields=[
                'pdf_file',
                'pdf_source_hash',
                'pdf_generation_status',
                'pdf_generated_at',
                'updated_at',
            ]
        )
        return GENERATION_READY
    except Exception:
        logger.exception('PDF generation failed for book pk=%s', book.pk)
        book.pdf_generation_status = GENERATION_FAILED
        book.save(update_fields=['pdf_generation_status', 'updated_at'])
        return GENERATION_FAILED
