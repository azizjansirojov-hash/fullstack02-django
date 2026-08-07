import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import WeeklyActivityWidget from './WeeklyActivityWidget'

vi.mock('../../api/library', () => ({
  updateDailyGoal: vi.fn(),
}))

describe('WeeklyActivityWidget', () => {
  it('shows zero-data daily goal gracefully', () => {
    render(
      <WeeklyActivityWidget
        activityStats={{
          today_minutes_read: 0,
          daily_goal_minutes: 20,
          goal_progress_percent: 0,
          week_minutes_total: 0,
          week_pages_total: 0,
          current_streak_days: 0,
          next_milestone_days: 3,
          badges: [],
        }}
      />,
    )
    expect(screen.getByText(/Bugungi maqsad: 0 \/ 20 daq/)).toBeInTheDocument()
    expect(screen.getByText('Joriy ko‘rsatkich')).toBeInTheDocument()
    expect(screen.getByText('Keyingi marra')).toBeInTheDocument()
    expect(screen.getByText('0 kun')).toBeInTheDocument()
    expect(screen.getByText('3 kun')).toBeInTheDocument()
    expect(screen.getByText('Haftalik daqiqa')).toBeInTheDocument()
    expect(screen.getByText('0 daq')).toBeInTheDocument()
    expect(screen.getByText('Haftalik sahifa')).toBeInTheDocument()
    expect(screen.queryByLabelText('Yutuqlar')).not.toBeInTheDocument()
  })

  it('renders server-provided streak when activity_stats is present', () => {
    render(
      <WeeklyActivityWidget
        activityTimestamps={[]}
        continueReading={[]}
        activityStats={{
          today_minutes_read: 5,
          daily_goal_minutes: 20,
          goal_progress_percent: 25,
          week_minutes_total: 5,
          week_pages_total: 2,
          current_streak_days: 12,
          next_milestone_days: 14,
          badges: [],
        }}
      />,
    )
    expect(screen.getByText('12 kun')).toBeInTheDocument()
    expect(screen.getByText('14 kun')).toBeInTheDocument()
  })

  it('falls back to client streak only when activity_stats is null', () => {
    const today = new Date()
    today.setHours(12, 0, 0, 0)
    const yesterday = new Date(today)
    yesterday.setDate(today.getDate() - 1)

    const { container } = render(
      <WeeklyActivityWidget
        activityStats={null}
        activityTimestamps={[today.toISOString(), yesterday.toISOString()]}
      />,
    )
    const currentStat = container.querySelectorAll('.activity-stat')[0]
    expect(currentStat).toBeTruthy()
    expect(currentStat).toHaveTextContent('Joriy')
    // Client computeStreak with today+yesterday → 2 kun.
    expect(currentStat?.querySelector('strong')?.textContent).toBe('2 kun')
  })

  it('shows goal exactly met', () => {
    render(
      <WeeklyActivityWidget
        activityStats={{
          today_minutes_read: 20,
          daily_goal_minutes: 20,
          goal_progress_percent: 100,
          week_minutes_total: 45,
          week_pages_total: 12,
          current_streak_days: 7,
          next_milestone_days: 14,
          badges: [
            { id: 'streak_7', kind: 'streak', value: 7, label: '7 kunlik seriya' },
          ],
        }}
      />,
    )
    expect(screen.getByText(/Bugungi maqsad: 20 \/ 20 daq/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Bugungi maqsad: 20 \/ 20 daqiqa/)).toBeInTheDocument()
    expect(screen.getByText('45 daq')).toBeInTheDocument()
    expect(screen.getByText('12 sah')).toBeInTheDocument()
    expect(screen.getByText('7 kunlik seriya')).toBeInTheDocument()
    expect(screen.getByText('7 kun')).toBeInTheDocument()
  })
})
