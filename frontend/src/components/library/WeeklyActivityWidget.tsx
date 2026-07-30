import type { ProgressCard } from '../../types/library'

const DAY_LABELS = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'] as const
const STREAK_MILESTONES = [3, 7, 14, 21, 30, 60, 100] as const
const DAILY_GOAL = 1

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
}

/**
 * Weekly activity — day dots, daily goal, and streak from real reading progress.
 */
export default function WeeklyActivityWidget({
  continueReading = [],
  activityTimestamps = [],
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
  const todayActive = activeKeys.has(dayKey(today))
  const todayProgress = todayActive ? DAILY_GOAL : 0
  const streak = computeStreak(activeKeys, today)
  const milestone = nextMilestone(streak)
  const ringProgress = activeThisWeek / 7

  return (
    <div className="dash-card">
      <div className="dash-section__head" style={{ marginBottom: '0.85rem' }}>
        <h2 className="dash-section__title" style={{ fontSize: '1rem' }}>
          Haftalik faollik
        </h2>
      </div>
      <div className="activity-widget">
        <div
          className="activity-ring"
          aria-label={`Bugungi maqsad: ${todayProgress} / ${DAILY_GOAL}`}
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
              {todayProgress}/{DAILY_GOAL}
            </strong>
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
        </div>
      </div>
    </div>
  )
}
