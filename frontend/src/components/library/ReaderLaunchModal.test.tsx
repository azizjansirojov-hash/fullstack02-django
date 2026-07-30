import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ReaderLaunchModal from './ReaderLaunchModal'
import * as libraryApi from '../../api/library'
import * as AuthContextModule from '../../auth/AuthContext'
import type { BookDetailResponse } from '../../types/library'

vi.mock('../../api/library', () => ({
  fetchBookDetail: vi.fn(),
  getReadingProgress: vi.fn(),
  saveReadingProgress: vi.fn(),
  setReadingStatus: vi.fn(),
  getReviews: vi.fn(),
  createReview: vi.fn(),
  updateReview: vi.fn(),
  deleteReview: vi.fn(),
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
const gatedBook = {
  slug: 'gated-book',
  title: 'Pullik kitob',
  author_name: 'Licensed Author',
  category_label: 'Roman',
  has_access: false,
  has_pdf: true,
  has_audio: true,
  pdf_url: '',
  audio_url: '',
  read_url: '/library/gated-book/read/',
  pdf_generation_status: 'ready',
  audio_generation_status: 'ready',
} as BookDetailResponse

const publicBook = {
  slug: 'public-book',
  title: 'Bepul kitob',
  author_name: 'Public Author',
  category_label: 'Roman',
  has_access: true,
  has_pdf: true,
  has_audio: true,
  pdf_url: '/library/media/public-book/pdf/',
  audio_url: '/library/media/public-book/audio/',
  read_url: '/library/public-book/read/',
  pdf_generation_status: 'ready',
  audio_generation_status: 'ready',
  audio_duration_seconds: 3720,
} as BookDetailResponse

function renderModal(book: BookDetailResponse) {
  return render(
    <MemoryRouter>
      <ReaderLaunchModal book={book} open onClose={() => {}} />
    </MemoryRouter>,
  )
}

describe('ReaderLaunchModal purchase gating', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
    vi.mocked(libraryApi.getReadingProgress).mockResolvedValue({
      response: { ok: false } as Response,
      data: null,
    })
    vi.mocked(libraryApi.fetchBookDetail).mockImplementation(async (slug) => ({
      response: { ok: true } as Response,
      data: (slug === 'gated-book' ? gatedBook : publicBook) as BookDetailResponse,
    }))
    vi.mocked(libraryApi.getReviews).mockResolvedValue({
      response: { ok: true } as Response,
      data: { count: 0, average_rating: null, results: [] },
    })
  })

  it('disables listen and PDF actions when access is denied', async () => {
    renderModal(gatedBook)

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    expect(document.getElementById('launch-read')).toHaveAttribute('aria-disabled', 'true')
    expect(document.getElementById('launch-listen')).toBeDisabled()
    expect(screen.getByText('PDF (xarid kerak)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Boshidan (yopiq)' })).toBeDisabled()
  })

  it('shows audio duration when access is granted', async () => {
    renderModal(publicBook)

    await waitFor(() => {
      expect(screen.getByText('Tinglash vaqti')).toBeInTheDocument()
    })

    expect(screen.getByText('1 soat 2 daqiqa')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Tinglash/i })).not.toBeDisabled()
    expect(screen.getByText('PDF yuklab olish')).toBeInTheDocument()
  })

  it('shows compact reviews panel when open', async () => {
    renderModal(publicBook)
    const dialog = await screen.findByRole('dialog')
    await waitFor(() => {
      expect(within(dialog).getByRole('link', { name: /Barchasini ko/ })).toBeInTheDocument()
    })
    expect(within(dialog).getByRole('radio', { name: '5 yulduz bilan baholash' })).toBeInTheDocument()
  })
})
