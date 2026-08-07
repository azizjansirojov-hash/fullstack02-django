# FEATURE_REPORT — Haftalik faollik (Features A/B/C)

Branch: `remediation/full-pass-2026-07-30`  
Date: 2026-08-08

## Step 0 findings

| Item | Detail |
|------|--------|
| **X — Existing streak logic** | Client-side in `frontend/src/components/library/WeeklyActivityWidget.tsx` (`computeStreak`). Labels **Joriy ko‘rsatkich** / **Keyingi marra** unchanged. |
| **Y — Data source** | `ReadingProgress.updated_at` via catalog `activity_timestamps` (`serialize_activity_timestamps` in `library/api/_common.py`), plus `continue_reading[].progress.updated_at`. **No per-day minutes/pages existed** before Feature A. |
| **Z — Response shape (before)** | `GET /api/library/` → `activity_timestamps: string[]` (ISO datetimes, excl. planned, capped at 50). Guests: empty list. |
| **User prefs** | `users/models.py` was empty — no `UserPreferences` / `UserProfile`. |
| **TIME_ZONE** | `TIME_ZONE = 'UTC'`, `USE_TZ = True` — session dates use `timezone.localdate()` (no new TZ strategy). |

## What shipped

### Feature A — Daily reading goal

- **Models**
  - `users.UserPreferences` — OneToOne to `auth.User`, `daily_goal_minutes` (default **20**, validators **5–300**).
  - `library.ReadingSession` — `(user, date)` unique; `minutes_read`, `updated_at`.
- **Recording** — On `ReadingProgressAPIView` upsert with status `reading`, `record_reading_session` accumulates today’s session:
  - Optional body field `minutes_delta` (0–15).
  - Else wall-clock estimate since last session/progress heartbeat (cap 15 min, idle gap 20 min).
- **Endpoints**
  - Catalog adds `activity_stats` (authenticated) / `null` (guest).
  - `GET`/`PUT /api/preferences/` (CSRF + JWT) — `{ daily_goal_minutes }`.
- **UI** — Slim progress bar under streak ring: **Bugungi maqsad: X / Y daq**; gear opens chips 10/20/30/60 + custom input. Zero-data shows `0 / 20`.

### Feature B — Mini statistics

- **Model** — `ReadingSession.pages_read` (page-index advances on flip/pdf upserts).
- **Stats** — Same `activity_stats` payload:
  - `week_minutes_total` — sum of `minutes_read` over last **7** local days.
  - `week_pages_total` — sum of `pages_read` over last **7** local days (chosen over avg: cheaper + more accurate with session rows).
- **UI** — Two compact `activity-stat` cells: **Haftalik daqiqa** / **Haftalik sahifa**.

### Feature C — Achievement badges

- Computed **on read** (no Badge model):
  - Streak milestones **3 / 7 / 14 / 30** — only the **highest** earned.
  - Books finished this calendar month **1 / 3 / 5** — only the **highest** earned (count of `ReadingProgress` with `status=finished` and `updated_at` in current month).
- Streak days = union of `ReadingSession` dates with `minutes_read > 0` and non-planned `ReadingProgress.updated_at` local dates (same “idle today → count from yesterday” rule as the widget).
- **UI** — 0–2 chips; section hidden when `badges` empty.

## Migrations

| App | Migration |
|-----|-----------|
| `users` | `0002_userpreferences` |
| `library` | `0021_readingsession` |
| `library` | `0022_readingsession_pages_read` |

Note: an unrelated local notification index migration may appear as `0023_notification_user_read_created_index` (not part of these feature commits).

## Exact JSON shape

### `GET /api/library/` (authenticated excerpt)

```json
{
  "activity_timestamps": ["2026-08-08T12:00:00+00:00"],
  "activity_stats": {
    "today_minutes_read": 0,
    "daily_goal_minutes": 20,
    "goal_progress_percent": 0,
    "week_minutes_total": 0,
    "week_pages_total": 0,
    "badges": [
      {
        "id": "streak_7",
        "kind": "streak",
        "value": 7,
        "label": "7 kunlik seriya"
      },
      {
        "id": "finished_1",
        "kind": "finished_month",
        "value": 1,
        "label": "1 kitob shu oy"
      }
    ]
  }
}
```

Guests: `"activity_stats": null`.

### `PUT /api/preferences/`

Request: `{ "daily_goal_minutes": 30 }`  
Response: `{ "daily_goal_minutes": 30 }`  
Errors: 400 when outside 5–300.

### Progress upsert (optional)

`PUT /api/library/<slug>/progress/` may include `"minutes_delta": 1..15`.

## UI states

| State | Behavior |
|-------|----------|
| Guest / no stats | Ring + day dots + streak labels; no goal bar gear, no week stats, no badges. |
| Zero activity | Goal `0 / 20`, bar empty, week `0`, badges hidden. |
| Goal met | `goal_progress_percent` 100; bar full. |
| Goal editor | Gear toggles chips + number input; silent catalog reload on save. |
| Badges | Up to two chips under week stats; omitted when none. |

## Commits

1. `6f0c3a1` — feat(activity): add daily reading goal with ReadingSession tracking  
2. `d806432` — feat(activity): add weekly minutes and pages mini-stats  
3. `e45ae7d` — feat(activity): add streak and finished-month achievement badges  
4. (this report) — docs: FEATURE_REPORT for weekly activity A/B/C  

## Test results

| Stage | Backend `library users backend` | Frontend `npm test` + `typecheck` |
|-------|----------------------------------|-------------------------------------|
| After A | 196 OK (1 skipped) | 104 OK + typecheck pass |
| After B | 198 OK (1 skipped) | 104 OK + typecheck pass |
| After C | 200 OK (1 skipped) | 104 OK + typecheck pass |

## Design decisions / caveats

1. **New schema for minutes** — Required: `ReadingSession` because `ReadingProgress` only stores latest position/`updated_at`, not per-day time.
2. **Minutes accuracy** — Heartbeat estimation floors whole minutes within a 20-minute idle window; clients may send `minutes_delta` for explicit increments. Rapid page turns under 60s may not add minutes until enough wall-clock elapses.
3. **Pages** — Only counted when flip/pdf page index **increases**; listen mode does not change page counters.
4. **Finished-month badges** — Use `ReadingProgress.updated_at` in the current month while status is finished (no separate `finished_at` field).
5. **Streak UI vs badges** — Widget streak remains client-computed from timestamps; badge streak is server-computed from sessions + progress dates (aligned rules, possibly richer once sessions exist).
6. **Preferences** — Lazy `get_or_create` on first GET/PUT; catalog uses default 20 if no row.
7. **Out of scope (honored)** — No streak-circle redesign, push notifications, social, generic achievement framework, Purchase/Review/Notification/GenerationJob schema changes, JWT/CSRF redesign, payment/TTS/RBAC.
