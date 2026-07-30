"""Generate narrated audio from Uzbek book text via configured TTS provider.

Uses audiobook-style pacing: sentence cleanup, paragraph pauses, and the
configured female Uzbek voice (default Madina via edge provider).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .generation_utils import (
    GENERATION_FAILED,
    GENERATION_LEGACY,
    GENERATION_PENDING,
    GENERATION_READY,
    MAX_TTS_CHARS,
    chunk_paragraphs_for_tts,
    content_hash,
    split_body_paragraphs,
)
from .tts_providers import get_tts_provider

logger = logging.getLogger(__name__)

# Bump when narration style changes so cached audio is regenerated.
TTS_STYLE_VERSION = 'natural-woman-v2'


def _default_voice() -> str:
    return getattr(settings, 'TTS_VOICE', 'uz-UZ-MadinaNeural')


def _audio_content_digest(body: str) -> str:
    """Hash body + style version so style upgrades invalidate the cache."""
    return content_hash(f'{TTS_STYLE_VERSION}\n{body or ""}')


def _paragraph_pause_mp3() -> bytes:
    """~1s of silence between paragraphs (breath), loaded from static media."""
    path = Path(settings.BASE_DIR) / 'static' / 'audio' / 'silence-1s.mp3'
    if path.is_file():
        return path.read_bytes()
    return b''


def prepare_spoken_text(text: str) -> str:
    """Normalize text so neural TTS breathes and phrases more naturally."""
    t = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not t:
        return ''
    t = t.replace('…', '...').replace('...', '. ')
    t = re.sub(r'[–—−]', ', ', t)
    t = re.sub(r'[«»“”„]', '"', t)
    t = re.sub(r"[‘’]", "'", t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{2,}', '. ', t)
    t = re.sub(r'\n+', ' ', t)
    t = t.strip()
    if t and t[-1] not in '.!?…':
        t += '.'
    t = re.sub(r'([.!?]){2,}', r'\1', t)
    t = re.sub(r'\s+([,.!?])', r'\1', t)
    t = re.sub(r'\s{2,}', ' ', t)
    return t.strip()


def _synthesize_natural_mp3(text: str, voice: str | None = None) -> bytes:
    """
    Narrate like a real reader: each paragraph is spoken on its own with a short
    pause between paragraphs (breath).
    """
    voice = voice or _default_voice()
    provider = get_tts_provider()
    paragraphs = [p for p in split_body_paragraphs(text) if p.strip()]
    if not paragraphs:
        spoken = prepare_spoken_text(text)
        if not spoken:
            return b''
        return provider.synthesize(spoken, voice=voice)

    pause = _paragraph_pause_mp3()
    parts: list[bytes] = []
    for para in paragraphs:
        spoken = prepare_spoken_text(para)
        if not spoken:
            continue
        audio = provider.synthesize(spoken, voice=voice)
        if not audio:
            continue
        if parts and pause:
            parts.append(pause)
        parts.append(audio)
    return b''.join(parts)


def ensure_book_audio(book, *, force: bool = False) -> str:
    """
    Generate AudioChapter tracks from Uzbek body text.

    Legacy books with uploaded audio (and no hash) are left untouched unless force.
    """
    from .models import AudioChapter, BookTranslation

    translation = book.translations.filter(language=BookTranslation.Language.UZ).first()
    if not translation or not (translation.body or '').strip():
        book.audio_generation_status = GENERATION_PENDING
        book.save(update_fields=['audio_generation_status', 'updated_at'])
        return GENERATION_PENDING

    digest = _audio_content_digest(translation.body)

    body_len = len(translation.body or '')
    if body_len > MAX_TTS_CHARS:
        logger.error(
            'TTS refused for book pk=%s: body length %s exceeds MAX_TTS_CHARS=%s',
            book.pk,
            body_len,
            MAX_TTS_CHARS,
        )
        book.audio_generation_status = GENERATION_FAILED
        book.save(update_fields=['audio_generation_status', 'updated_at'])
        return GENERATION_FAILED

    has_any_audio = book.has_audio()
    if has_any_audio and not book.audio_source_hash and not force:
        if book.audio_generation_status != GENERATION_LEGACY:
            book.audio_generation_status = GENERATION_LEGACY
            book.save(update_fields=['audio_generation_status', 'updated_at'])
        return GENERATION_LEGACY

    if (
        has_any_audio
        and book.audio_source_hash == digest
        and book.audio_generation_status == GENERATION_READY
        and not force
    ):
        return GENERATION_READY

    book.audio_generation_status = 'generating'
    book.save(update_fields=['audio_generation_status', 'updated_at'])

    paragraphs = split_body_paragraphs(translation.body)
    chunks = chunk_paragraphs_for_tts(paragraphs, max_chars=2200)
    if not chunks:
        book.audio_generation_status = GENERATION_PENDING
        book.save(update_fields=['audio_generation_status', 'updated_at'])
        return GENERATION_PENDING

    provider = get_tts_provider()
    voice = _default_voice()

    try:
        generated: list[tuple[int, str, str, bytes]] = []
        for index, chunk in enumerate(chunks):
            mp3 = _synthesize_natural_mp3(chunk, voice=voice)
            if not mp3:
                raise RuntimeError(f'No audio produced for chapter {index + 1}')
            title = f'{index + 1}-qism' if len(chunks) > 1 else '1-qism'
            generated.append((index, title, chunk, mp3))

        with transaction.atomic():
            book.audio_chapters.all().delete()
            if book.audio_file and (force or book.audio_source_hash):
                book.audio_file.delete(save=False)
                book.audio_file = None

            for index, title, chunk, mp3 in generated:
                chapter = AudioChapter(
                    book=book,
                    title=title,
                    order=index,
                    source_text=chunk,
                    source_text_hash=content_hash(chunk),
                    tts_provider=provider.name,
                    voice_id=voice,
                    generated_at=timezone.now(),
                )
                chapter.audio_file.save(
                    f'{book.slug or book.pk}-ch{index + 1}.mp3',
                    ContentFile(mp3),
                    save=False,
                )
                chapter.save()

            book.audio_source_hash = digest
            book.audio_generation_status = GENERATION_READY
            book.audio_generated_at = timezone.now()
            book.save(
                update_fields=[
                    'audio_file',
                    'audio_source_hash',
                    'audio_generation_status',
                    'audio_generated_at',
                    'updated_at',
                ]
            )
        return GENERATION_READY
    except Exception:
        logger.exception('TTS generation failed for book pk=%s', book.pk)
        book.audio_generation_status = GENERATION_FAILED
        book.save(update_fields=['audio_generation_status', 'updated_at'])
        return GENERATION_FAILED
