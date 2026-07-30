"""Enqueue and process durable GenerationJob rows."""

from __future__ import annotations

import logging
import socket
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from .media_generation import generate_book_media
from .models import Book, GenerationJob
from .pdf_service import ensure_book_pdf
from .tts_service import ensure_book_audio

logger = logging.getLogger(__name__)

# Reclaim running jobs stuck longer than this (worker crash / restart).
STALE_RUNNING_SECONDS = 60 * 30


class GenerationEnqueueError(Exception):
    """Raised when a job cannot be enqueued (rights, quota, etc.)."""


def book_allows_generation(book: Book) -> bool:
    return book.rights_status in {
        Book.RightsStatus.PUBLIC_DOMAIN,
        Book.RightsStatus.LICENSED,
    }


def _regenerate_cache_key(user_id: int) -> str:
    day = timezone.now().strftime('%Y-%m-%d')
    return f'gen-regen:{user_id}:{day}'


def check_regenerate_quota(user) -> None:
    """Raise GenerationEnqueueError if staff daily regenerate cap is exceeded."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return
    limit = getattr(settings, 'GENERATION_REGENERATE_DAILY_LIMIT', 10)
    key = _regenerate_cache_key(user.pk)
    used = cache.get(key, 0)
    if used >= limit:
        raise GenerationEnqueueError(
            f'Daily regenerate limit reached ({limit}/day). Try again tomorrow.'
        )


def record_regenerate_quota(user) -> None:
    if user is None or not getattr(user, 'is_authenticated', False):
        return
    key = _regenerate_cache_key(user.pk)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=60 * 60 * 26)


def _active_jobs_qs(book_id: int, job_type: str):
    return GenerationJob.objects.filter(
        book_id=book_id,
        job_type=job_type,
        status__in=[GenerationJob.Status.QUEUED, GenerationJob.Status.RUNNING],
    )


def enqueue_generation_job(
    book_id: int,
    *,
    job_type: str = GenerationJob.JobType.ALL,
    force: bool = False,
    user=None,
) -> GenerationJob | None:
    """
    Queue a generation job for a book.

    Skips creating a duplicate when a queued/running job already exists for the
    same book + job_type. If an existing queued job is found, OR's force=True.
    Uses select_for_update + partial unique constraint against races.
    """
    if not book_id:
        return None

    try:
        book = Book.objects.get(pk=book_id)
    except Book.DoesNotExist:
        return None

    if not book_allows_generation(book):
        raise GenerationEnqueueError(
            'Cannot generate media until rights_status is public_domain or licensed '
            f'(current={book.rights_status}).'
        )

    if force:
        check_regenerate_quota(user)

    with transaction.atomic():
        active = (
            _active_jobs_qs(book_id, job_type)
            .select_for_update()
            .order_by('pk')
            .first()
        )
        if active:
            if force and not active.force:
                active.force = True
                active.save(update_fields=['force', 'updated_at'])
                if force:
                    record_regenerate_quota(user)
            return active

        try:
            job = GenerationJob.objects.create(
                book_id=book_id,
                job_type=job_type,
                force=force,
                status=GenerationJob.Status.QUEUED,
            )
        except IntegrityError:
            job = _active_jobs_qs(book_id, job_type).order_by('pk').first()
            if job is None:
                raise
            if force and not job.force:
                job.force = True
                job.save(update_fields=['force', 'updated_at'])
            if force:
                record_regenerate_quota(user)
            return job

    if force:
        record_regenerate_quota(user)
    return job


def schedule_generation_job(
    book_id: int,
    *,
    job_type: str = GenerationJob.JobType.ALL,
    force: bool = False,
    user=None,
) -> None:
    """Enqueue after the current DB transaction commits."""

    def _on_commit() -> None:
        try:
            enqueue_generation_job(
                book_id, job_type=job_type, force=force, user=user
            )
        except GenerationEnqueueError as exc:
            logger.warning(
                'Skipped generation enqueue: %s',
                exc,
                extra={'book_id': book_id, 'job_id': '-'},
            )

    transaction.on_commit(_on_commit)


def _worker_id() -> str:
    return f'{socket.gethostname()[:32]}-{uuid.uuid4().hex[:8]}'


def _reclaim_stale_jobs() -> int:
    cutoff = timezone.now() - timedelta(seconds=STALE_RUNNING_SECONDS)
    return GenerationJob.objects.filter(
        status=GenerationJob.Status.RUNNING,
        locked_at__lt=cutoff,
    ).update(
        status=GenerationJob.Status.QUEUED,
        locked_at=None,
        locked_by='',
        updated_at=timezone.now(),
    )


def claim_next_job() -> GenerationJob | None:
    """Atomically claim the oldest queued job (SQLite + Postgres safe)."""
    _reclaim_stale_jobs()
    max_running = getattr(settings, 'GENERATION_MAX_RUNNING', 2)
    running_count = GenerationJob.objects.filter(
        status=GenerationJob.Status.RUNNING
    ).count()
    if running_count >= max_running:
        return None

    worker = _worker_id()
    with transaction.atomic():
        job = (
            GenerationJob.objects.select_for_update()
            .filter(status=GenerationJob.Status.QUEUED)
            .order_by('created_at', 'pk')
            .first()
        )
        if not job:
            return None
        updated = GenerationJob.objects.filter(
            pk=job.pk,
            status=GenerationJob.Status.QUEUED,
        ).update(
            status=GenerationJob.Status.RUNNING,
            locked_at=timezone.now(),
            locked_by=worker,
            attempts=job.attempts + 1,
            updated_at=timezone.now(),
        )
        if updated != 1:
            return None
        job.refresh_from_db()
        return job


def run_job(job: GenerationJob) -> None:
    """Execute one claimed job and mark done/failed."""
    log_extra = {'book_id': job.book_id, 'job_id': job.pk}

    try:
        book = Book.objects.get(pk=job.book_id)
    except Book.DoesNotExist:
        job.status = GenerationJob.Status.FAILED
        job.error_message = 'Book no longer exists.'
        job.locked_at = None
        job.locked_by = ''
        job.save(
            update_fields=[
                'status',
                'error_message',
                'locked_at',
                'locked_by',
                'updated_at',
            ]
        )
        logger.error(
            'GenerationJob failed: book missing',
            extra=log_extra,
        )
        return

    if not book_allows_generation(book):
        job.status = GenerationJob.Status.FAILED
        job.error_message = (
            f'Rights status {book.rights_status} does not allow generation.'
        )
        job.locked_at = None
        job.locked_by = ''
        job.save(
            update_fields=[
                'status',
                'error_message',
                'locked_at',
                'locked_by',
                'updated_at',
            ]
        )
        logger.error(
            'GenerationJob failed: rights block',
            extra=log_extra,
        )
        return

    try:
        if job.job_type == GenerationJob.JobType.PDF:
            status = ensure_book_pdf(book, force=job.force)
            result = {'pdf': status}
        elif job.job_type == GenerationJob.JobType.AUDIO:
            status = ensure_book_audio(book, force=job.force)
            result = {'audio': status}
        else:
            result = generate_book_media(
                book, force_pdf=job.force, force_audio=job.force
            )

        failed_parts = [k for k, v in result.items() if v == 'failed']
        if failed_parts:
            raise RuntimeError(
                f'Generation failed for: {", ".join(failed_parts)} '
                f'(statuses={result})'
            )

        job.status = GenerationJob.Status.DONE
        job.error_message = ''
        job.locked_at = None
        job.locked_by = ''
        job.save(
            update_fields=[
                'status',
                'error_message',
                'locked_at',
                'locked_by',
                'updated_at',
            ]
        )
        if job.job_type in (
            GenerationJob.JobType.AUDIO,
            GenerationJob.JobType.ALL,
        ):
            from .notifications import notify_audio_ready

            notify_audio_ready(book)
        logger.info('GenerationJob done: %s', result, extra=log_extra)
    except Exception as exc:
        logger.exception('GenerationJob failed', extra=log_extra)
        job.error_message = str(exc)[:2000]
        job.locked_at = None
        job.locked_by = ''
        if job.attempts >= job.max_attempts:
            job.status = GenerationJob.Status.FAILED
            logger.error(
                'GenerationJob terminal failure: %s',
                exc,
                extra=log_extra,
            )
        else:
            job.status = GenerationJob.Status.QUEUED
        job.save(
            update_fields=[
                'status',
                'error_message',
                'locked_at',
                'locked_by',
                'updated_at',
            ]
        )


def process_one() -> bool:
    """Claim and run one job. Returns True if a job was processed."""
    job = claim_next_job()
    if not job:
        return False
    run_job(job)
    return True


def process_loop(*, poll_seconds: float = 2.0, once: bool = False) -> None:
    """Run until interrupted (or a single pass when once=True)."""
    while True:
        worked = process_one()
        if once:
            return
        if not worked:
            time.sleep(poll_seconds)
