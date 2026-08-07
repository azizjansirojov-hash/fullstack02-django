"""Daily reading goal / session helpers for the weekly activity widget."""

from datetime import timedelta

from django.db.models import F, Sum
from django.utils import timezone

from users.models import (
    DEFAULT_DAILY_GOAL_MINUTES,
    UserPreferences,
)

from .models import ReadingProgress, ReadingSession

# Cap per progress heartbeat so a stale tab cannot dump huge deltas.
MAX_MINUTES_DELTA_PER_SAVE = 15
MAX_PAGES_DELTA_PER_SAVE = 50
# Ignore gaps longer than this when estimating from wall-clock (new bout).
IDLE_GAP = timedelta(minutes=20)
# Hard ceiling per local calendar day (12 hours) — abuse / fat-finger guard.
MAX_DAILY_READING_MINUTES = 720
# Reject minute credits closer than this after the last session write.
MIN_SESSION_INCREMENT_GAP = timedelta(seconds=50)

STREAK_BADGE_MILESTONES = (3, 7, 14, 30)
FINISHED_MONTH_BADGE_MILESTONES = (1, 3, 5)


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


def week_pages_total(user, *, end_date=None) -> int:
    """Sum pages_read over the last 7 local calendar days (inclusive)."""
    end = end_date or timezone.localdate()
    start = end - timedelta(days=6)
    total = (
        ReadingSession.objects.filter(user=user, date__gte=start, date__lte=end)
        .aggregate(s=Sum('pages_read'))
        .get('s')
    )
    return int(total or 0)


def _active_day_keys(user) -> set:
    """Local calendar dates with reading activity (sessions + progress updates)."""
    keys = set(
        ReadingSession.objects.filter(user=user, minutes_read__gt=0).values_list(
            'date', flat=True
        )
    )
    for ts in (
        ReadingProgress.objects.filter(user=user)
        .exclude(status=ReadingProgress.Status.PLANNED)
        .values_list('updated_at', flat=True)
    ):
        if ts is not None:
            keys.add(timezone.localdate(ts))
    return keys


def compute_streak_days(user, *, today=None) -> int:
    """Consecutive active days ending today, or yesterday if today is idle."""
    today = today or timezone.localdate()
    active = _active_day_keys(user)
    cursor = today
    if cursor not in active:
        cursor = today - timedelta(days=1)
        if cursor not in active:
            return 0
    streak = 0
    while cursor in active:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def books_finished_this_month(user, *, today=None) -> int:
    today = today or timezone.localdate()
    return (
        ReadingProgress.objects.filter(
            user=user,
            status=ReadingProgress.Status.FINISHED,
            updated_at__year=today.year,
            updated_at__month=today.month,
        ).count()
    )


def _highest_milestone(value: int, milestones: tuple[int, ...]) -> int | None:
    earned = [m for m in milestones if value >= m]
    return max(earned) if earned else None


def compute_active_badges(user, *, today=None) -> list[dict]:
    """Return currently-active badges only (highest milestone per kind, max 2)."""
    today = today or timezone.localdate()
    badges: list[dict] = []

    streak = compute_streak_days(user, today=today)
    streak_m = _highest_milestone(streak, STREAK_BADGE_MILESTONES)
    if streak_m is not None:
        badges.append(
            {
                'id': f'streak_{streak_m}',
                'kind': 'streak',
                'value': streak_m,
                'label': f'{streak_m} kunlik seriya',
            }
        )

    finished = books_finished_this_month(user, today=today)
    finished_m = _highest_milestone(finished, FINISHED_MONTH_BADGE_MILESTONES)
    if finished_m is not None:
        badges.append(
            {
                'id': f'finished_{finished_m}',
                'kind': 'finished_month',
                'value': finished_m,
                'label': f'{finished_m} kitob shu oy',
            }
        )

    return badges


def serialize_activity_stats(user) -> dict:
    """Catalog payload fragment for daily goal, week stats, and badges."""
    goal = get_daily_goal_minutes(user)
    today = today_minutes_read(user)
    return {
        'today_minutes_read': today,
        'daily_goal_minutes': goal,
        'goal_progress_percent': goal_progress_percent(today, goal),
        'week_minutes_total': week_minutes_total(user),
        'week_pages_total': week_pages_total(user),
        'badges': compute_active_badges(user),
    }


def record_reading_session(
    user,
    *,
    minutes_delta=None,
    pages_delta=0,
    previous_heartbeat_at=None,
):
    """Accumulate today's ReadingSession from a progress upsert heartbeat.

    Prefer an explicit ``minutes_delta`` from the client when present.
    Otherwise estimate from wall-clock since the previous heartbeat
    (session ``updated_at`` or progress ``updated_at``), capped per save.
    Explicit deltas are also wall-clock-bounded and subject to a minimum
    gap plus a per-day ceiling so rapid-fire clients cannot inflate stats.
    ``pages_delta`` counts flip/pdf page advances (non-negative).
    """
    now = timezone.now()
    today = timezone.localdate()

    session, created = ReadingSession.objects.get_or_create(
        user=user,
        date=today,
        defaults={'minutes_read': 0, 'pages_read': 0},
    )
    # Reload so ceiling uses current minutes_read after concurrent updates.
    session.refresh_from_db()

    # Fresh row has auto_now updated_at ≈ now — do not gap-throttle the first credit.
    session_updated_at = None if created else session.updated_at
    anchor = session_updated_at or previous_heartbeat_at

    if minutes_delta is not None:
        try:
            add_minutes = int(minutes_delta)
        except (TypeError, ValueError):
            add_minutes = 0
        add_minutes = max(0, min(MAX_MINUTES_DELTA_PER_SAVE, add_minutes))
    else:
        add_minutes = 0
        if anchor is not None:
            elapsed = now - anchor
            if timedelta(0) < elapsed <= IDLE_GAP:
                add_minutes = min(
                    MAX_MINUTES_DELTA_PER_SAVE,
                    max(0, int(elapsed.total_seconds() // 60)),
                )

    # Gap + wall-clock bound apply after an earlier accepted write today.
    if add_minutes > 0 and session_updated_at is not None:
        elapsed = now - session_updated_at
        if elapsed < MIN_SESSION_INCREMENT_GAP:
            add_minutes = 0
        elif timedelta(0) < elapsed <= IDLE_GAP:
            wall_cap = max(0, int(elapsed.total_seconds() // 60))
            add_minutes = min(add_minutes, wall_cap, MAX_MINUTES_DELTA_PER_SAVE)

    if add_minutes > 0:
        remaining = max(0, MAX_DAILY_READING_MINUTES - int(session.minutes_read))
        add_minutes = min(add_minutes, remaining)

    try:
        add_pages = int(pages_delta or 0)
    except (TypeError, ValueError):
        add_pages = 0
    add_pages = max(0, min(MAX_PAGES_DELTA_PER_SAVE, add_pages))

    if add_minutes <= 0 and add_pages <= 0:
        return session

    updates = {'updated_at': now}
    if add_minutes > 0:
        updates['minutes_read'] = F('minutes_read') + add_minutes
    if add_pages > 0:
        updates['pages_read'] = F('pages_read') + add_pages
    ReadingSession.objects.filter(pk=session.pk).update(**updates)
    session.refresh_from_db()
    return session


# Back-compat alias used by Feature A call sites / tests.
def record_reading_session_minutes(user, *, minutes_delta=None, previous_heartbeat_at=None):
    return record_reading_session(
        user,
        minutes_delta=minutes_delta,
        previous_heartbeat_at=previous_heartbeat_at,
    )
