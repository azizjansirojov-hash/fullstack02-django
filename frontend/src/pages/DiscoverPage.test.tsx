import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DiscoverPage from './DiscoverPage'
import * as libraryApi from '../api/library'
import * as AuthContextModule from '../auth/AuthContext'
import type { CatalogResponse } from '../types/library'

vi.mock('../api/library', () => ({
  fetchCatalog: vi.fn(),
  removePlanned: vi.fn(),
  setReadingStatus: vi.fn(),
  getReviews: vi.fn(),
  createReview: vi.fn(),
  updateReview: vi.fn(),
  deleteReview: vi.fn(),
  upsertProgress: vi.fn(),
  fetchBookDetail: vi.fn(),
}))

function mockAuth({ user = null as null | { id: number; username: string; email: string; is_staff: boolean } } = {}) {
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

function baseCatalog(overrides: Partial<CatalogResponse> = {}): CatalogResponse {
  return {
    query: 'test',
    category: 'novel',
    is_empty: false,
    can_read: false,
    shelf: [
      {
        slug: 'book-a',
        title: 'Kitob A',
        author_name: 'Author',
        category: 'novel',
        category_label: 'Romanlar',
        published_year: 2020,
        cover_url: '',
        has_pdf: true,
        has_audio: false,
        has_access: false,
        rights_status: 'public_domain',
        pdf_generation_status: 'ready',
        audio_generation_status: 'ready',
        pdf_url: '',
        read_url: '/library/book-a/read/',
        audio_url: '',
        audio_duration_seconds: null,
        summary: '',
        average_rating: null,
        review_count: 0,
        reading_status: null,
      },
    ],
    category_lists: [
      {
        code: 'novel',
        label: 'Romanlar',
        count: 30,
        items: [],
      },
    ],
    continue_reading: [],
    activity_timestamps: [],
    activity_stats: null,
    pagination: {
      page: 2,
      num_pages: 3,
      has_previous: true,
      has_next: true,
      previous_page: 1,
      next_page: 3,
    },
    user: null,
    ...overrides,
  }
}

function renderDiscover(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/library/dokon" element={<DiscoverPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DiscoverPage pagination', () => {
  beforeEach(() => {
    mockAuth()
    vi.mocked(libraryApi.fetchCatalog).mockResolvedValue({
      response: { ok: true, status: 200 } as Response,
      data: baseCatalog(),
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders prev/next links that preserve filters and set page', async () => {
    renderDiscover('/library/dokon?q=test&category=novel&page=2')

    await waitFor(() => {
      expect(screen.getByRole('navigation', { name: 'Sahifalar' })).toBeInTheDocument()
    })

    const prev = screen.getByRole('link', { name: 'Oldingi' })
    const next = screen.getByRole('link', { name: 'Keyingi' })
    expect(prev).toHaveAttribute('href', '/library/dokon?q=test&category=novel')
    expect(next).toHaveAttribute('href', '/library/dokon?q=test&category=novel&page=3')
    expect(screen.getByText('2 / 3')).toBeInTheDocument()
  })

  it('hides pagination when only one page', async () => {
    vi.mocked(libraryApi.fetchCatalog).mockResolvedValue({
      response: { ok: true, status: 200 } as Response,
      data: baseCatalog({
        pagination: {
          page: 1,
          num_pages: 1,
          has_previous: false,
          has_next: false,
          previous_page: null,
          next_page: null,
        },
      }),
    })
    renderDiscover('/library/dokon?category=novel')
    await waitFor(() => {
      expect(screen.getByText('Natijalar')).toBeInTheDocument()
    })
    expect(screen.queryByRole('navigation', { name: 'Sahifalar' })).not.toBeInTheDocument()
  })
})
