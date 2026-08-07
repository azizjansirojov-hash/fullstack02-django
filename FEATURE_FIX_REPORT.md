# FEATURE_FIX_REPORT.md — Activity correctness fixes

Branch: `remediation/full-pass-2026-07-30`  
Date: 2026-08-08

Order applied: **Fix 4 → Fix 1 → Fix 2 → Fix 3** (migration conflict first, then abuse caps, finished-at, streak SSOT).

| Fix | Commit | Summary |
|-----|--------|---------|
| 4 | `cde1420` | Commit notification read-index migration as `0023` |
| 1 | `72aade9` | Daily minutes ceiling + increment gap / wall-clock bound |
| 2 | `ac4d223` | `ReadingProgress.finished_at` for finished-month badges |
| 3 | `81d48dd` | `activity_stats.current_streak_days` / `next_milestone_days` SSOT |

---

## Fix 4 — Migration graph

**Before:** Untracked [`0023_notification_user_read_created_index.py`](backend/library/migrations/0023_notification_user_read_created_index.py) sat beside committed `0021`/`0022`. `Notification.Meta` already declared `lib_notif_user_read_created`, but `0019` never created the index.

**After:** `0023` committed, depends on `0022`. `makemigrations --check --dry-run` reported no pending model changes. No divergent heads. Migration tree linear through `0024` (added in Fix 2).

**Tests:** Backend 200 OK (1 skipped); frontend 104 + typecheck.

---

## Fix 1 — Cap `minutes_read` inflation

**Files:** [`backend/library/activity.py`](backend/library/activity.py), [`backend/library/test_activity_goal.py`](backend/library/test_activity_goal.py)

**Before:** Client `minutes_delta` (0–15) was accepted every progress upsert with no daily ceiling and no minimum gap — rapid-fire requests could inflate today/week stats.

**After:**
- `MAX_DAILY_READING_MINUTES = 720`
- `MIN_SESSION_INCREMENT_GAP = 50s` (zero credit if last session write was closer)
- Within `IDLE_GAP` (20m), explicit deltas also capped to `floor(elapsed_seconds/60)`
- No-op writes when both minute and page deltas are zero (does not refresh `updated_at` to defeat the gap)
- First session create for the day is not gap-throttled against its own insert timestamp

**Throttle follow-up:** `ReadingProgressAPIView` still has **no** `throttle_classes`. Per-day/gap caps are the primary defense; endpoint-level throttling remains a recommended follow-up.

**Tests:** Backend 203 OK (1 skipped); frontend 104 + typecheck.

---

## Fix 2 — `finished_at` for finished-month badges

**Files:** [`backend/library/models.py`](backend/library/models.py), [`backend/library/api/progress.py`](backend/library/api/progress.py), [`backend/library/activity.py`](backend/library/activity.py), [`backend/library/migrations/0024_readingprogress_finished_at.py`](backend/library/migrations/0024_readingprogress_finished_at.py), tests

**Before:** `books_finished_this_month` filtered on `updated_at` month — reopening/touching a finished book could move it into the current month.

**After:**
- Nullable `finished_at` on `ReadingProgress`
- Set **once** on first transition to `finished` (`ReadingStatusAPIView`); kept on reopen / re-finish
- Badge query uses `finished_at__year` / `finished_at__month`
- Backfill: existing `status=finished` rows get `finished_at = updated_at` (**approximation** — true first-completion time is not recoverable)

**Migration:** `library.0024_readingprogress_finished_at`

**Tests:** Backend 205 OK (1 skipped); frontend 104 + typecheck.

---

## Fix 3 — Server streak as source of truth

**Files:** [`backend/library/activity.py`](backend/library/activity.py), [`frontend/src/components/library/WeeklyActivityWidget.tsx`](frontend/src/components/library/WeeklyActivityWidget.tsx), types + tests

**Before:** Widget recomputed streak from `activity_timestamps`; badges used `compute_streak_days` from sessions + progress — values could disagree.

**After:** Additive `activity_stats` fields (authenticated catalog only):

```json
{
  "today_minutes_read": 0,
  "daily_goal_minutes": 20,
  "goal_progress_percent": 0,
  "week_minutes_total": 0,
  "week_pages_total": 0,
  "current_streak_days": 0,
  "next_milestone_days": 3,
  "badges": []
}
```

- `current_streak_days` — from `compute_streak_days` (same value passed into badge selection)
- `next_milestone_days` — absolute Keyingi marra target from `(3, 7, 14, 21, 30, 60, 100)`, or `null`
- Widget uses server fields when `activityStats != null`; client `computeStreak` only for guests/`null` stats
- Day-dot UI unchanged (still from timestamps)

**Tests:** Backend 206 OK (1 skipped); frontend 106 + typecheck.

---

## Migrations added this pass

| Migration | Purpose |
|-----------|---------|
| `library.0023_notification_user_read_created_index` | Notification `(user, is_read, -created_at)` index |
| `library.0024_readingprogress_finished_at` | `finished_at` field + backfill |

---

## Out of scope (unchanged)

- Global DRF throttle on progress upsert (noted as follow-up)
- Streak circle / day-dot redesign
- Purchase / Review / Notification / GenerationJob schema changes beyond the additive notification index migration
- Payment, TTS, RBAC
