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
        }}
      />,
    )
    expect(screen.getByText(/Bugungi maqsad: 0 \/ 20 daq/)).toBeInTheDocument()
    expect(screen.getByText('Joriy ko‘rsatkich')).toBeInTheDocument()
    expect(screen.getByText('Keyingi marra')).toBeInTheDocument()
    expect(screen.getByText('Haftalik daqiqa')).toBeInTheDocument()
    expect(screen.getByText('0 daq')).toBeInTheDocument()
    expect(screen.getByText('Haftalik sahifa')).toBeInTheDocument()
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
        }}
      />,
    )
    expect(screen.getByText(/Bugungi maqsad: 20 \/ 20 daq/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Bugungi maqsad: 20 \/ 20 daqiqa/)).toBeInTheDocument()
    expect(screen.getByText('45 daq')).toBeInTheDocument()
    expect(screen.getByText('12 sah')).toBeInTheDocument()
  })
})
