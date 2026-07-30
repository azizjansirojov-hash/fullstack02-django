"""Orchestrate PDF + audio generation after book content is saved."""

from __future__ import annotations

import logging

from .pdf_service import ensure_book_pdf
from .tts_service import ensure_book_audio

logger = logging.getLogger(__name__)


def generate_book_media(book, *, force_pdf: bool = False, force_audio: bool = False) -> dict:
    """
    Ensure PDF and audio exist for the book from Uzbek translation text.

    Returns {'pdf': status, 'audio': status}.
    """
    # Refresh related rows after admin inline saves.
    book.refresh_from_db()
    pdf_status = ensure_book_pdf(book, force=force_pdf)
    audio_status = ensure_book_audio(book, force=force_audio)
    logger.info(
        'Media generation for book pk=%s slug=%s pdf=%s audio=%s',
        book.pk,
        book.slug,
        pdf_status,
        audio_status,
    )
    return {'pdf': pdf_status, 'audio': audio_status}
