import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ContinueReadingCard from './ContinueReadingCard'
import * as libraryApi from '../../api/library'
import * as AuthContextModule from '../../auth/AuthContext'

vi.mock('../../api/library', () => ({
  getReviews: vi.fn(),
  createReview: vi.fn(),
  updateReview: vi.fn(),
  deleteReview: vi.fn(),
  saveReadingProgress: vi.fn(),
}))

function mockAuth({ user = { id: 1, username: 'currentuser', email: 'a@b.c', is_staff: false } } = {}) {
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

const book = {
  slug: 'continue-book',
  title: 'Davom kitobi',
  author_name: 'Muallif',
  category: 'roman',
  category_label: 'Roman',
  published_year: 2020,
  cover_url: '',
  has_pdf: true,
  has_audio: true,
  has_access: true,
  rights_status: 'public_domain',
  pdf_generation_status: 'ready',
  audio_generation_status: 'ready',
  pdf_url: '/pdf',
  read_url: '/library/continue-book/read/',
  audio_url: '/audio',
  audio_duration_seconds: 100,
  summary: '',
  reading_status: 'reading',
  progress: {
    mode: 'listen',
    page: 0,
    total_pages: 10,
    chapter_id: 6,
    position: 40,
    updated_at: '2026-01-01T00:00:00Z',
    audio_duration_seconds: 100,
    status: 'reading',
  },
}

describe('ContinueReadingCard ratings', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
    libraryApi.getReviews.mockResolvedValue({
      response: { ok: true },
      data: {
        count: 1,
        average_rating: 4.0,
        results: [
          {
            id: 1,
            username: 'alice',
            rating: 4,
            text: 'Yaxshi kitob edi.',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
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
  })

  it('renders interactive stars, aggregate, actions in Davom→Tinglash→Boshidan order, and comment form', async () => {
    const onLaunch = vi.fn()
    render(
      <MemoryRouter>
        <ContinueReadingCard book={book} onLaunch={onLaunch} />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('continue-reading-card')).toBeInTheDocument()

    const actions = screen.getByTestId('continue-reading-card').querySelector('.continue-card__actions')
    const labels = Array.from(actions.querySelectorAll(':scope > button')).map((b) => b.textContent?.trim())
    expect(labels[0]).toMatch(/O'qishni davom ettirish|O‘qishni davom ettirish/)
    expect(labels[1]).toMatch(/Tinglash/)
    expect(labels[2]).toMatch(/Boshidan boshlash/)
    expect(actions.querySelector('.continue-card__btn--continue')).toHaveClass('continue-card__btn--primary')
    expect(actions.querySelector('.continue-card__btn--listen')).not.toHaveClass('continue-card__btn--primary')

    await waitFor(() => {
      expect(screen.getByText('4.0')).toBeInTheDocument()
    })
    expect(screen.getByText(/Yaxshi kitob edi/)).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'Sharh yozish' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Fikringizni yozing/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Barchasini ko/ })).toHaveAttribute(
      'href',
      '/library/continue-book/',
    )

    fireEvent.click(screen.getByRole('button', { name: /O.qishni davom ettirish/ }))
    expect(onLaunch).toHaveBeenCalledWith(book)
  })

  it('submits comment text via updateReview when user already rated', async () => {
    libraryApi.getReviews.mockResolvedValue({
      response: { ok: true },
      data: {
        count: 1,
        average_rating: 5,
        results: [
          {
            id: 9,
            username: 'currentuser',
            rating: 5,
            text: '',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
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
    libraryApi.updateReview.mockResolvedValue({
      response: { ok: true },
      data: {
        id: 9,
        username: 'currentuser',
        rating: 5,
        text: 'Yangi fikr',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
    })

    render(
      <MemoryRouter>
        <ContinueReadingCard book={book} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('form', { name: 'Sharh yozish' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText(/Fikringizni yozing/), {
      target: { value: 'Yangi fikr' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Yuborish' }))

    await waitFor(() => {
      expect(libraryApi.updateReview).toHaveBeenCalledWith('continue-book', {
        rating: 5,
        text: 'Yangi fikr',
      })
    })
  })

  it('submits a rating via createReview when user has no review', async () => {
    libraryApi.createReview.mockResolvedValue({
      response: { ok: true },
      data: { id: 9, username: 'currentuser', rating: 5, text: '', created_at: '', updated_at: '' },
    })
    libraryApi.getReviews
      .mockResolvedValueOnce({
        response: { ok: true },
        data: { count: 0, average_rating: null, results: [], pagination: { page: 1, num_pages: 1, has_previous: false, has_next: false, previous_page: null, next_page: null } },
      })
      .mockResolvedValueOnce({
        response: { ok: true },
        data: {
          count: 1,
          average_rating: 5,
          results: [
            {
              id: 9,
              username: 'currentuser',
              rating: 5,
              text: '',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
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

    render(
      <MemoryRouter>
        <ContinueReadingCard book={book} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('radio', { name: '5 yulduz bilan baholash' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('radio', { name: '5 yulduz bilan baholash' }))

    await waitFor(() => {
      expect(libraryApi.createReview).toHaveBeenCalledWith('continue-book', {
        rating: 5,
        text: '',
      })
    })
  })

  it('asks for confirmation before start-over reset', async () => {
    render(
      <MemoryRouter>
        <ContinueReadingCard book={book} />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Boshidan boshlash' }))
    expect(screen.getByText(/Ishonchingiz komilmi/)).toBeInTheDocument()
    expect(libraryApi.saveReadingProgress).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Yo‘q' }))
    expect(screen.queryByText(/Ishonchingiz komilmi/)).not.toBeInTheDocument()
  })
})

