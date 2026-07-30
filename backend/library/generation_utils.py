"""Shared helpers for auto-generated PDF and TTS audio."""

from __future__ import annotations

import hashlib
import re

DEFAULT_TTS_VOICE = 'uz-UZ-MadinaNeural'
TTS_PROVIDER = 'edge-tts'
# Refuse TTS above this body length to bound time/cost (PDF may still succeed).
MAX_TTS_CHARS = 150_000

GENERATION_PENDING = 'pending'
GENERATION_GENERATING = 'generating'
GENERATION_READY = 'ready'
GENERATION_FAILED = 'failed'
GENERATION_LEGACY = 'legacy'

GENERATION_STATUS_CHOICES = [
    (GENERATION_PENDING, 'Not generated'),
    (GENERATION_GENERATING, 'Generating'),
    (GENERATION_READY, 'Ready'),
    (GENERATION_FAILED, 'Failed'),
    (GENERATION_LEGACY, 'Legacy upload'),
]


def content_hash(text: str) -> str:
    """Stable SHA-256 of normalized book body text."""
    normalized = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def split_body_paragraphs(body: str) -> list[str]:
    """Split body into paragraphs on blank lines (same as flip reader)."""
    text = (body or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        return []
    parts = re.split(r'\n\s*\n+', text)
    return [p.strip() for p in parts if p.strip()]


def chunk_paragraphs_for_tts(paragraphs: list[str], max_chars: int = 3500) -> list[str]:
    """Group paragraphs into TTS-sized chunks without splitting mid-paragraph when possible."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        extra = len(para) + (2 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append('\n\n'.join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += extra
    if current:
        chunks.append('\n\n'.join(current))
    return chunks
