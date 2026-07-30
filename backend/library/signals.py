"""Signals to enqueue PDF/audio generation when Uzbek content is saved."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .jobs import book_allows_generation, schedule_generation_job
from .models import GenerationJob

logger = logging.getLogger(__name__)


@receiver(post_save, sender='library.BookTranslation')
def generate_media_on_translation_save(sender, instance, **kwargs):
    """When Uzbek body text is saved, enqueue PDF + TTS after commit."""
    if instance.language != 'uz':
        return
    if not (instance.body or '').strip():
        return
    book = instance.book
    if not book_allows_generation(book):
        logger.info(
            'Skipped media enqueue for book_id=%s: rights_status=%s',
            instance.book_id,
            book.rights_status,
        )
        return
    schedule_generation_job(
        instance.book_id,
        job_type=GenerationJob.JobType.ALL,
        force=False,
    )
    logger.info(
        'Enqueued media generation for book_id=%s after translation save',
        instance.book_id,
    )
