import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AppSidebar from './AppSidebar'
import * as notificationsApi from '../../api/notifications'
import * as AuthContextModule from '../../auth/AuthContext'

vi.mock('../../api/notifications', () => ({
  fetchNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}))

function mockAuth() {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user: { id: 1, username: 'tester', email: 't@e.c', is_staff: false },
    isAuthenticated: true,
    ready: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  })
}

function renderSidebar() {
  return render(
    <MemoryRouter>
      <AppSidebar
        collapsed={false}
        onToggleCollapse={() => {}}
        mobileOpen={false}
      />
    </MemoryRouter>,
  )
}

describe('AppSidebar notifications', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
    vi.mocked(notificationsApi.fetchNotifications).mockResolvedValue({
      response: { ok: true } as Response,
      data: {
        count: 1,
        next: null,
        previous: null,
        unread_count: 1,
        results: [{
          id: 7,
          message: 'Audio tayyor',
          type: 'audio_ready',
          is_read: false,
          link_url: '/library/book/',
          book_slug: 'book',
          created_at: '2026-07-30T12:00:00Z',
        }],
      },
    })
    vi.mocked(notificationsApi.markNotificationRead).mockResolvedValue({
      response: { ok: true } as Response,
      data: null,
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('shows unread badge and marks a clicked notification read', async () => {
    renderSidebar()

    await waitFor(() => {
      expect(screen.getByLabelText('1 ta o‘qilmagan bildirishnoma')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Bildirishnomalar/ }))
    const notification = await screen.findByRole('button', { name: 'Audio tayyor' })
    fireEvent.click(notification)

    await waitFor(() => {
      expect(notificationsApi.markNotificationRead).toHaveBeenCalledWith(7)
    })
    expect(screen.queryByLabelText('1 ta o‘qilmagan bildirishnoma')).not.toBeInTheDocument()
  })
})

