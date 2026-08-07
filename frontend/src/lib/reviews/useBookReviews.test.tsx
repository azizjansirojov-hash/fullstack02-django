import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useBookReviews } from '../../lib/reviews/useBookReviews'
import * as libraryApi from '../../api/library'
import * as AuthContextModule from '../../auth/AuthContext'

vi.mock('../../api/library', () => ({
  getReviews: vi.fn(),
  createReview: vi.fn(),
  updateReview: vi.fn(),
  deleteReview: vi.fn(),
}))

function mockAuth({ user = { id: 1, username: 'u', email: 'u@e.c', is_staff: false } } = {}) {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user,
    isAuthenticated: Boolean(user),
    ready: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  })
}

function Probe({ slug }: { slug: string }) {
  const r = useBookReviews(slug)
  return (
    <div>
      <span data-testid="count">{r.count}</span>
      <span data-testid="avg">{r.averageRating ?? 'null'}</span>
      <span data-testid="loading">{String(r.loading)}</span>
      <button type="button" onClick={() => void r.submitRating(4)}>
        Rate
      </button>
    </div>
  )
}

describe('useBookReviews', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
  })

  it('loads reviews and updates rating via PUT when my review exists', async () => {
    libraryApi.getReviews.mockResolvedValue({
      response: { ok: true },
      data: {
        count: 1,
        average_rating: 3,
        results: [
          {
            id: 1,
            username: 'u',
            rating: 3,
            text: 'eski',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
        my_review: {
          id: 1,
          username: 'u',
          rating: 3,
          text: 'eski',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
        pagination: {
          page: 1,
          num_pages: 1,
          has_previous: false,
          has_next: false,
          previous_page: null,
          next_page: null,
        },
      },
    })
    libraryApi.updateReview.mockResolvedValue({
      response: { ok: true },
      data: {
        id: 1,
        username: 'u',
        rating: 4,
        text: 'eski',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
    })

    render(
      <MemoryRouter>
        <Probe slug="book-a" />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })
    expect(screen.getByTestId('count')).toHaveTextContent('1')

    screen.getByRole('button', { name: 'Rate' }).click()

    await waitFor(() => {
      expect(libraryApi.updateReview).toHaveBeenCalledWith('book-a', {
        rating: 4,
        text: 'eski',
      })
    })
  })
})

