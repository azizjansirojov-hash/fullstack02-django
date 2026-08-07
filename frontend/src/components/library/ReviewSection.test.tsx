import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ReviewSection from './ReviewSection'
import * as libraryApi from '../../api/library'
import * as AuthContextModule from '../../auth/AuthContext'

function mockAuth({ user = null } = {}) {
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

vi.mock('../../api/library', () => ({
  getReviews: vi.fn(),
  createReview: vi.fn(),
  updateReview: vi.fn(),
  deleteReview: vi.fn(),
}))

const emptyReviewsResponse = {
  response: { ok: true },
  data: {
    count: 0,
    average_rating: null,
    results: [],
    pagination: {
      page: 1,
      num_pages: 1,
      has_previous: false,
      has_next: false,
      previous_page: null,
      next_page: null,
    },
  },
}

const reviewsWithItems = {
  response: { ok: true },
  data: {
    count: 2,
    average_rating: 4.0,
    results: [
      {
        id: 1,
        username: 'alice',
        rating: 5,
        text: 'Ajoyib!',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 2,
        username: 'bob',
        rating: 3,
        text: '',
        created_at: '2026-01-02T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
    ],
    pagination: {
      page: 1,
      num_pages: 1,
      has_previous: false,
      has_next: false,
      previous_page: null,
      next_page: null,
    },
  },
}

const myReviewResponse = {
  response: { ok: true },
  data: {
    count: 1,
    average_rating: 4.0,
    results: [
      {
        id: 10,
        username: 'currentuser',
        rating: 4,
        text: 'Yaxshi kitob.',
        created_at: '2026-01-10T00:00:00Z',
        updated_at: '2026-01-10T00:00:00Z',
      },
    ],
    my_review: {
      id: 10,
      username: 'currentuser',
      rating: 4,
      text: 'Yaxshi kitob.',
      created_at: '2026-01-10T00:00:00Z',
      updated_at: '2026-01-10T00:00:00Z',
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
}

function renderSection(slug = 'test-book') {
  return render(
    <MemoryRouter>
      <ReviewSection slug={slug} />
    </MemoryRouter>,
  )
}

describe('ReviewSection', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders reviews list and aggregate when reviews exist', async () => {
    mockAuth()
    libraryApi.getReviews.mockResolvedValue(reviewsWithItems)

    renderSection()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sharhlar' })).toBeInTheDocument()
    })

    expect(screen.getByText('2 sharh')).toBeInTheDocument()
    expect(screen.getByText('Ajoyib!')).toBeInTheDocument()
    expect(screen.getByText('alice')).toBeInTheDocument()
    expect(screen.getByText('bob')).toBeInTheDocument()
  })

  it('shows empty state message when there are no reviews', async () => {
    mockAuth()
    libraryApi.getReviews.mockResolvedValue(emptyReviewsResponse)

    renderSection()

    await waitFor(() => {
      expect(
        screen.getByText(/Birinchi bo.lib sharh qoldiring!/),
      ).toBeInTheDocument()
    })
  })

  it('shows submit form for authenticated user without a review', async () => {
    mockAuth({ user: { username: 'newuser', id: 5 } })
    libraryApi.getReviews.mockResolvedValue(emptyReviewsResponse)

    renderSection()

    await waitFor(() => {
      expect(screen.getByRole('form', { name: 'Sharh yozish' })).toBeInTheDocument()
    })

    expect(screen.getByPlaceholderText(/Fikringizni yozing/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Yuborish' })).toBeInTheDocument()
  })

  it('calls createReview with text and rating on submit', async () => {
    mockAuth({ user: { username: 'newuser', id: 5 } })
    libraryApi.createReview.mockResolvedValue({
      response: { ok: true },
      data: {
        id: 99,
        username: 'newuser',
        rating: 5,
        text: "Zo'r!",
        created_at: '2026-02-01T00:00:00Z',
        updated_at: '2026-02-01T00:00:00Z',
      },
    })

    libraryApi.getReviews
      .mockResolvedValueOnce(emptyReviewsResponse)
      .mockResolvedValueOnce({
        response: { ok: true },
        data: {
          count: 1,
          average_rating: 5.0,
          results: [
            {
              id: 99,
              username: 'newuser',
              rating: 5,
              text: "Zo'r!",
              created_at: '2026-02-01T00:00:00Z',
              updated_at: '2026-02-01T00:00:00Z',
            },
          ],
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

    renderSection()

    await waitFor(() => {
      expect(screen.getByRole('form', { name: 'Sharh yozish' })).toBeInTheDocument()
    })

    const stars = screen.getAllByRole('radio', { name: /yulduz/ })
    fireEvent.click(stars[4])
    fireEvent.change(screen.getByPlaceholderText(/Fikringizni yozing/), {
      target: { value: "Zo'r!" },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Yuborish' }))

    await waitFor(() => {
      expect(libraryApi.createReview).toHaveBeenCalledWith('test-book', {
        rating: 5,
        text: "Zo'r!",
      })
    })
  })

  it('keeps visible comment form and delete when user already has a review', async () => {
    mockAuth({ user: { username: 'currentuser', id: 3 } })
    libraryApi.getReviews.mockResolvedValue(myReviewResponse)

    renderSection()

    await waitFor(() => {
      expect(screen.getByRole('form', { name: 'Sharh yozish' })).toBeInTheDocument()
    })

    expect(screen.getByDisplayValue('Yaxshi kitob.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: "O'chirish" })).toBeInTheDocument()
  })

  it('shows login prompt and no form for unauthenticated user', async () => {
    mockAuth({ user: null })
    libraryApi.getReviews.mockResolvedValue(reviewsWithItems)

    renderSection()

    await waitFor(() => {
      expect(screen.getByText(/Sharh yozish uchun kiring/)).toBeInTheDocument()
    })

    expect(screen.queryByRole('form', { name: 'Sharh yozish' })).not.toBeInTheDocument()
  })
})

