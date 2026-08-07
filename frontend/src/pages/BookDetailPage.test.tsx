import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BookDetailPage from './BookDetailPage'
import * as libraryApi from '../api/library'
import * as AuthContextModule from '../auth/AuthContext'

vi.mock('../api/library', () => ({
  fetchBookDetail: vi.fn(),
  removePlanned: vi.fn(),
  setReadingStatus: vi.fn(),
  getReviews: vi.fn(),
  createReview: vi.fn(),
  updateReview: vi.fn(),
  deleteReview: vi.fn(),
}))

function mockAuth({ user = { id: 1, username: 'reader', email: 'r@e.c', is_staff: false } } = {}) {
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

const publicBook = {
  slug: 'public-book',
  title: 'Bepul kitob',
  author_name: 'Public Author',
  category_label: 'Roman',
  summary: 'Qisqa xulosa.',
  has_access: true,
  can_read: true,
  has_pdf: true,
  has_audio: true,
  pdf_url: '/library/media/public-book/pdf/',
  audio_url: '/library/media/public-book/audio/',
  read_url: '/library/public-book/read/',
  pdf_generation_status: 'ready',
  audio_generation_status: 'ready',
  reading_status: null,
  average_rating: null,
  review_count: 0,
  similar_books: [],
}

const gatedBook = {
  slug: 'gated-book',
  title: 'Pullik kitob',
  author_name: 'Licensed Author',
  category_label: 'Roman',
  summary: 'Qisqa xulosa.',
  has_access: false,
  can_read: false,
  has_pdf: true,
  has_audio: true,
  pdf_url: '',
  audio_url: '',
  read_url: '/library/gated-book/read/',
  pdf_generation_status: 'ready',
  audio_generation_status: 'ready',
  reading_status: null,
  average_rating: null,
  review_count: 0,
  similar_books: [],
}

function renderPage(slug) {
  return render(
    <MemoryRouter initialEntries={[`/library/${slug}`]}>
      <Routes>
        <Route path="/library/:slug" element={<BookDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('BookDetailPage purchase gating', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    vi.resetAllMocks()
    mockAuth()
    libraryApi.getReviews.mockResolvedValue({
      response: { ok: true },
      data: { count: 0, average_rating: null, results: [], pagination: { page: 1, num_pages: 1, has_previous: false, has_next: false, previous_page: null, next_page: null } },
    })
  })

  it('renders working actions for a public_domain book', async () => {
    libraryApi.fetchBookDetail.mockImplementation(async () => ({
      response: { ok: true },
      data: publicBook,
    }))
    renderPage('public-book')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Bepul kitob' })).toBeInTheDocument()
    })

    const readLink = screen.getByRole('link', { name: 'O‘qishni davom ettirish' })
    expect(readLink).toHaveAttribute('href', expect.stringContaining('/library/public-book/read/'))

    expect(screen.getByRole('button', { name: 'Tinglash' })).not.toBeDisabled()
    expect(screen.getByRole('link', { name: 'PDF yuklab olish' })).toHaveAttribute(
      'href',
      '/library/media/public-book/pdf/',
    )
    expect(screen.queryByText(/pullik/i)).not.toBeInTheDocument()
  })

  it('renders locked purchase state for a gated book', async () => {
    libraryApi.fetchBookDetail.mockImplementation(async () => ({
      response: { ok: true },
      data: gatedBook,
    }))
    renderPage('gated-book')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Pullik kitob' })).toBeInTheDocument()
    })

    expect(screen.getByRole('status')).toHaveTextContent(/pullik/i)
    expect(screen.getByRole('button', { name: 'Sotib olish kerak' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Tinglash (yopiq)' })).toBeDisabled()
    expect(screen.getByText('PDF (xarid kerak)')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'PDF yuklab olish' })).not.toBeInTheDocument()
  })

  it('integrates ReviewSection with Sharhlar heading (not mocked away)', async () => {
    libraryApi.fetchBookDetail.mockImplementation(async () => ({
      response: { ok: true },
      data: publicBook,
    }))
    libraryApi.getReviews.mockResolvedValue({
      response: { ok: true },
      data: {
        count: 1,
        average_rating: 5,
        results: [
          {
            id: 1,
            username: 'alice',
            rating: 5,
            text: 'Zo‘r!',
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
    renderPage('public-book')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sharhlar' })).toBeInTheDocument()
    })
    expect(screen.getByText('Zo‘r!')).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'Sharh yozish' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Fikringizni yozing/)).toBeInTheDocument()
  })

  it('orders hero actions Davom → Tinglash → Boshidan with Continue as primary', async () => {
    libraryApi.fetchBookDetail.mockImplementation(async () => ({
      response: { ok: true },
      data: publicBook,
    }))
    renderPage('public-book')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Bepul kitob' })).toBeInTheDocument()
    })

    const actions = document.querySelector('.reader-actions')
    const labels = Array.from(actions.querySelectorAll('a, button'))
      .map((el) => el.textContent?.trim())
      .filter(Boolean)
    const davomIdx = labels.findIndex((t) => t === 'O‘qishni davom ettirish')
    const tinglashIdx = labels.findIndex((t) => t === 'Tinglash')
    const boshidanIdx = labels.findIndex((t) => t === 'Boshidan boshlash')
    expect(davomIdx).toBeGreaterThanOrEqual(0)
    expect(tinglashIdx).toBeGreaterThan(davomIdx)
    expect(boshidanIdx).toBeGreaterThan(tinglashIdx)

    const continueLink = screen.getByRole('link', { name: 'O‘qishni davom ettirish' })
    expect(continueLink.className).toContain('reader-hero__read')
    expect(continueLink.className).not.toContain('reader-hero__read--ghost')
    expect(screen.getByRole('button', { name: 'Tinglash' }).className).toContain(
      'reader-hero__read--ghost',
    )
  })
})
