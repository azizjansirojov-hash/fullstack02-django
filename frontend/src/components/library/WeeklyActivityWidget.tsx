import { useEffect, useState } from 'react'
import type { ActivityStats, ProgressCard } from '../../types/library'
import { updateDailyGoal } from '../../api/library'

const DAY_LABELS = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'] as const
const STREAK_MILESTONES = [3, 7, 14, 21, 30, 60, 100] as const
const GOAL_CHIPS = [10, 20, 30, 60] as const
const DEFAULT_GOAL = 20

function startOfLocalDay(date: Date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

function dayKey(date: Date) {
  const d = startOfLocalDay(date)
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

function collectActiveKeys(timestamps: string[] = [], continueReading: ProgressCard[] = []) {
  const activeKeys = new Set<string>()
  timestamps.forEach((raw) => {
    const updated = new Date(raw)
    if (!Number.isNaN(updated.getTime())) activeKeys.add(dayKey(updated))
  })
  continueReading.forEach((book) => {
    const raw = book.progress?.updated_at
    if (!raw) return
    const updated = new Date(raw)
    if (!Number.isNaN(updated.getTime())) activeKeys.add(dayKey(updated))
  })
  return activeKeys
}

/** Consecutive active days ending today, or yesterday if today is idle. */
function computeStreak(activeKeys: Set<string>, today: Date) {
  const cursor = startOfLocalDay(today)
  if (!activeKeys.has(dayKey(cursor))) {
    cursor.setDate(cursor.getDate() - 1)
    if (!activeKeys.has(dayKey(cursor))) return 0
  }
  let streak = 0
  while (activeKeys.has(dayKey(cursor))) {
    streak += 1
    cursor.setDate(cursor.getDate() - 1)
  }
  return streak
}

function nextMilestone(streak: number) {
  return STREAK_MILESTONES.find((m) => m > streak) ?? null
}

export type WeeklyActivityWidgetProps = {
  continueReading?: ProgressCard[]
  activityTimestamps?: string[]
  activityStats?: ActivityStats | null
  onGoalUpdated?: (stats: ActivityStats) => void
}

/**
 * Weekly activity — day dots, daily goal, and streak from real reading progress.
 */
export default function WeeklyActivityWidget({
  continueReading = [],
  activityTimestamps = [],
  activityStats = null,
  onGoalUpdated,
}: WeeklyActivityWidgetProps) {
  const today = startOfLocalDay(new Date())
  const activeKeys = collectActiveKeys(activityTimestamps, continueReading)

  const days = Array.from({ length: 7 }, (_, i) => {
    const mondayOffset = (today.getDay() + 6) % 7
    const d = new Date(today)
    d.setDate(today.getDate() - mondayOffset + i)
    const key = dayKey(d)
    return {
      label: DAY_LABELS[i],
      key,
      isToday: key === dayKey(today),
      active: activeKeys.has(key),
    }
  })

  const activeThisWeek = days.filter((d) => d.active).length
  const streak = computeStreak(activeKeys, today)
  const milestone = nextMilestone(streak)
  const ringProgress = activeThisWeek / 7

  const todayMinutes = activityStats?.today_minutes_read ?? 0
  const [goalMinutes, setGoalMinutes] = useState(
    activityStats?.daily_goal_minutes ?? DEFAULT_GOAL,
  )
  const [goalEditorOpen, setGoalEditorOpen] = useState(false)
  const [goalDraft, setGoalDraft] = useState(String(goalMinutes))
  const [goalSaving, setGoalSaving] = useState(false)
  const [goalError, setGoalError] = useState('')

  useEffect(() => {
    if (activityStats?.daily_goal_minutes != null) {
      setGoalMinutes(activityStats.daily_goal_minutes)
      setGoalDraft(String(activityStats.daily_goal_minutes))
    }
  }, [activityStats?.daily_goal_minutes])

  const goalProgressPercent =
    activityStats?.goal_progress_percent ??
    (goalMinutes > 0 ? Math.min(100, Math.round((todayMinutes / goalMinutes) * 100)) : 0)

  async function saveGoal(nextGoal: number) {
    if (nextGoal < 5 || nextGoal > 300) {
      setGoalError('5–300 daqiqa oralig‘ida kiriting.')
      return
    }
    setGoalSaving(true)
    setGoalError('')
    try {
      const { response, data } = await updateDailyGoal(nextGoal)
      if (!response.ok || !data) {
        setGoalError('Saqlab bo‘lmadi. Qayta urinib ko‘ring.')
        return
      }
      const saved = data.daily_goal_minutes
      setGoalMinutes(saved)
      setGoalDraft(String(saved))
      setGoalEditorOpen(false)
      onGoalUpdated?.({
        today_minutes_read: todayMinutes,
        daily_goal_minutes: saved,
        goal_progress_percent: Math.min(100, Math.round((todayMinutes / saved) * 100)),
        week_minutes_total: activityStats?.week_minutes_total ?? 0,
        week_pages_total: activityStats?.week_pages_total ?? 0,
        badges: activityStats?.badges ?? [],
      })
    } catch {
      setGoalError('Saqlab bo‘lmadi. Qayta urinib ko‘ring.')
    } finally {
      setGoalSaving(false)
    }
  }

  return (
    <div className="dash-card">
      <div className="dash-section__head" style={{ marginBottom: '0.85rem' }}>
        <h2 className="dash-section__title" style={{ fontSize: '1rem' }}>
          Haftalik faollik
        </h2>
        {activityStats != null ? (
          <button
            type="button"
            className="activity-goal-settings"
            aria-label="Kunlik maqsadni sozlash"
            aria-expanded={goalEditorOpen}
            onClick={() => {
              setGoalDraft(String(goalMinutes))
              setGoalError('')
              setGoalEditorOpen((open) => !open)
            }}
          >
            ⚙
          </button>
        ) : null}
      </div>
      <div className="activity-widget">
        <div className="activity-ring-col">
          <div
            className="activity-ring"
            aria-label={`Bugungi maqsad: ${todayMinutes} / ${goalMinutes} daqiqa`}
          >
            <svg viewBox="0 0 120 120" aria-hidden>
              <circle
                cx="60"
                cy="60"
                r="52"
                fill="none"
                stroke="rgba(214,255,69,0.15)"
                strokeWidth="6"
              />
              <circle
                cx="60"
                cy="60"
                r="52"
                fill="none"
                stroke="url(#activity-grad)"
                strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray={`${ringProgress * 327} 327`}
              />
              <defs>
                <linearGradient id="activity-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#e4ff54" />
                  <stop offset="55%" stopColor="#4fe08a" />
                  <stop offset="100%" stopColor="#2fd39b" />
                </linearGradient>
              </defs>
            </svg>
            <div className="activity-ring__label">
              <small>Bugun</small>
              <strong>
                {todayMinutes}/{goalMinutes}
              </strong>
            </div>
          </div>
          <div className="activity-goal-bar" aria-hidden={activityStats == null}>
            <div className="activity-goal-bar__track">
              <div
                className="activity-goal-bar__fill"
                style={{ width: `${goalProgressPercent}%` }}
              />
            </div>
            <span className="activity-goal-bar__label">
              Bugungi maqsad: {todayMinutes} / {goalMinutes} daq
            </span>
          </div>
        </div>

        <div>
          <div className="activity-days">
            {days.map((d) => (
              <div
                key={d.key}
                className={`activity-day${d.active ? ' is-active' : ''}${d.isToday ? ' is-today' : ''}`}
                title={d.active ? 'Faoliyat bor' : 'Faoliyat yo‘q'}
              >
                <span className="activity-day__dot" />
                <span>{d.label}</span>
              </div>
            ))}
          </div>
          <div className="activity-stats">
            <div className="activity-stat">
              <span>Joriy ko‘rsatkich</span>
              <strong>{streak} kun</strong>
            </div>
            <div className="activity-stat">
              <span>Keyingi marra</span>
              <strong>{milestone != null ? `${milestone} kun` : '—'}</strong>
            </div>
          </div>
          {activityStats != null ? (
            <div className="activity-stats activity-stats--week">
              <div className="activity-stat">
                <span>Haftalik daqiqa</span>
                <strong>{activityStats.week_minutes_total ?? 0} daq</strong>
              </div>
              <div className="activity-stat">
                <span>Haftalik sahifa</span>
                <strong>{activityStats.week_pages_total ?? 0} sah</strong>
              </div>
            </div>
          ) : null}
          {activityStats?.badges && activityStats.badges.length > 0 ? (
            <div className="activity-badges" aria-label="Yutuqlar">
              {activityStats.badges.slice(0, 2).map((badge) => (
                <span key={badge.id} className="activity-badge">
                  {badge.label}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {goalEditorOpen ? (
        <div className="activity-goal-editor" role="group" aria-label="Kunlik maqsad">
          <div className="activity-goal-chips">
            {GOAL_CHIPS.map((chip) => (
              <button
                key={chip}
                type="button"
                className={`activity-goal-chip${goalDraft === String(chip) ? ' is-active' : ''}`}
                disabled={goalSaving}
                onClick={() => {
                  setGoalDraft(String(chip))
                  void saveGoal(chip)
                }}
              >
                {chip} daq
              </button>
            ))}
          </div>
          <div className="activity-goal-custom">
            <label htmlFor="activity-goal-input">Boshqa</label>
            <input
              id="activity-goal-input"
              type="number"
              min={5}
              max={300}
              value={goalDraft}
              disabled={goalSaving}
              onChange={(e) => setGoalDraft(e.target.value)}
            />
            <button
              type="button"
              className="activity-goal-save"
              disabled={goalSaving}
              onClick={() => void saveGoal(Number(goalDraft))}
            >
              Saqlash
            </button>
          </div>
          {goalError ? (
            <p className="activity-goal-error" role="alert">
              {goalError}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
