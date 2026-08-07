"""Daily reading goal / session helpers for the weekly activity widget."""

from datetime import timedelta

from django.db.models import F, Sum
from django.utils import timezone

from users.models import (
    DEFAULT_DAILY_GOAL_MINUTES,
    UserPreferences,
)

from .models import ReadingSession

# Cap per progress heartbeat so a stale tab cannot dump huge deltas.
MAX_MINUTES_DELTA_PER_SAVE = 15
# Ignore gaps longer than this when estimating from wall-clock (new bout).
IDLE_GAP = timedelta(minutes=20)


def get_daily_goal_minutes(user) -> int:
    prefs = UserPreferences.objects.filter(user_id=user.pk).first()
    if prefs is None:
        return DEFAULT_DAILY_GOAL_MINUTES
    return int(prefs.daily_goal_minutes)


def today_minutes_read(user, *, on_date=None) -> int:
    day = on_date or timezone.localdate()
    value = (
        ReadingSession.objects.filter(user=user, date=day)
        .values_list('minutes_read', flat=True)
        .first()
    )
    return int(value or 0)


def goal_progress_percent(minutes_read: int, goal_minutes: int) -> int:
    if goal_minutes <= 0:
        return 0
    return min(100, int(round((minutes_read / goal_minutes) * 100)))


def serialize_activity_stats(user) -> dict:
    """Catalog payload fragment for daily goal progress."""
    goal = get_daily_goal_minutes(user)
    today = today_minutes_read(user)
    return {
        'today_minutes_read': today,
        'daily_goal_minutes': goal,
        'goal_progress_percent': goal_progress_percent(today, goal),
    }


def record_reading_session_minutes(user, *, minutes_delta=None, previous_heartbeat_at=None):
    """Accumulate today's ReadingSession from a progress upsert heartbeat.

    Prefer an explicit ``minutes_delta`` from the client when present.
    Otherwise estimate from wall-clock since the previous heartbeat
    (session ``updated_at`` or progress ``updated_at``), capped per save.
    """
    now = timezone.now()
    today = timezone.localdate()

    if minutes_delta is not None:
        try:
            add = int(minutes_delta)
        except (TypeError, ValueError):
            add = 0
        add = max(0, min(MAX_MINUTES_DELTA_PER_SAVE, add))
    else:
        add = 0
        anchor = previous_heartbeat_at
        session_preview = (
            ReadingSession.objects.filter(user=user, date=today)
            .values_list('updated_at', flat=True)
            .first()
        )
        if session_preview is not None:
            anchor = session_preview
        if anchor is not None:
            elapsed = now - anchor
            if timedelta(0) < elapsed <= IDLE_GAP:
                add = min(
                    MAX_MINUTES_DELTA_PER_SAVE,
                    max(0, int(elapsed.total_seconds() // 60)),
                )

    session, _created = ReadingSession.objects.get_or_create(
        user=user,
        date=today,
        defaults={'minutes_read': 0},
    )
    if add > 0:
        ReadingSession.objects.filter(pk=session.pk).update(
            minutes_read=F('minutes_read') + add,
            updated_at=now,
        )
    else:
        ReadingSession.objects.filter(pk=session.pk).update(updated_at=now)
    session.refresh_from_db()
    return session


def week_minutes_total(user, *, end_date=None) -> int:
    """Sum minutes_read over the last 7 local calendar days (inclusive)."""
    end = end_date or timezone.localdate()
    start = end - timedelta(days=6)
    total = (
        ReadingSession.objects.filter(user=user, date__gte=start, date__lte=end)
        .aggregate(s=Sum('minutes_read'))
        .get('s')
    )
    return int(total or 0)
