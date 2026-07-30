"""Generation queue health helpers (stale queue / worker-down signals)."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .jobs import STALE_RUNNING_SECONDS
from .models import GenerationJob


def stale_queued_cutoff():
    seconds = getattr(settings, 'GENERATION_STALE_QUEUED_SECONDS', 300)
    return timezone.now() - timedelta(seconds=seconds)


def generation_health_payload() -> dict:
    """Return counts distinguishing queued vs stale (worker likely down) vs failed.

    worker_likely_down is True when either:
    - A queued job has been waiting longer than GENERATION_STALE_QUEUED_SECONDS, or
    - A running job's lock is older than STALE_RUNNING_SECONDS (the worker reclaim
      window defined in jobs.py), meaning the worker holding it has likely crashed.
    """
    queued_cutoff = stale_queued_cutoff()
    running_cutoff = timezone.now() - timedelta(seconds=STALE_RUNNING_SECONDS)

    queued = GenerationJob.objects.filter(status=GenerationJob.Status.QUEUED)
    stale_queued = queued.filter(created_at__lt=queued_cutoff).count()
    fresh_queued = queued.filter(created_at__gte=queued_cutoff).count()

    running_qs = GenerationJob.objects.filter(status=GenerationJob.Status.RUNNING)
    running = running_qs.count()
    stale_running = running_qs.filter(locked_at__lt=running_cutoff).count()

    failed_recent = GenerationJob.objects.filter(
        status=GenerationJob.Status.FAILED,
        updated_at__gte=timezone.now() - timedelta(hours=24),
    ).count()

    worker_likely_down = stale_queued > 0 or stale_running > 0
    return {
        'queued': fresh_queued + stale_queued,
        'queued_fresh': fresh_queued,
        'stale_queued': stale_queued,
        'running': running,
        'stale_running': stale_running,
        'failed_recent_24h': failed_recent,
        'worker_likely_down': worker_likely_down,
        'stale_after_seconds': getattr(
            settings, 'GENERATION_STALE_QUEUED_SECONDS', 300
        ),
        'stale_running_after_seconds': STALE_RUNNING_SECONDS,
        'status': 'degraded' if worker_likely_down else 'ok',
    }


def book_generation_ops_summary(book) -> dict:
    """Per-book admin summary for queued / stale / last failure."""
    jobs = book.generation_jobs.all()
    queued = jobs.filter(status=GenerationJob.Status.QUEUED).order_by('created_at')
    oldest_queued = queued.first()
    last_failed = (
        jobs.filter(status=GenerationJob.Status.FAILED)
        .order_by('-updated_at')
        .first()
    )
    cutoff = stale_queued_cutoff()
    stale = bool(oldest_queued and oldest_queued.created_at < cutoff)
    return {
        'queued_count': queued.count(),
        'oldest_queued': oldest_queued,
        'stale': stale,
        'last_failed': last_failed,
    }
