import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ReaderPage from './ReaderPage'
import * as libraryApi from '../api/library'

vi.mock('../api/library', () => ({
  fetchBookReaderManifest: vi.fn(),
  saveReadingProgress: vi.fn(),
}))

vi.mock('../components/reader/FlipReaderView', () => ({
  default: ({ autoplay }) => (
    <div data-testid="flip-reader-view">{autoplay ? 'autoplay-on' : 'autoplay-off'}</div>
  ),
}))

vi.mock('../components/reader/PdfReaderMode', () => ({
  default: () => <div data-testid="pdf-reader-mode">PDF reader</div>,
}))

const manifest = {
  slug: 'test-book',
  title: 'Test kitob',
  author_name: 'Muallif',
  body: 'Matn.',
  audio_sync: [],
  audio_chapters: [{ id: 1, title: '1-qism', url: '/library/media/test-book/audio/1/', order: 0 }],
  has_audio: true,
  has_pdf: true,
  pdf_url: '/library/media/test-book/pdf/',
  detail_url: '/library/test-book/',
  reading_progress: { exists: false, status: null },
}

function renderReader(initialEntry = '/library/test-book/read?mode=flip') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/library/:slug/read" element={<ReaderPage />} />
        <Route path="/library/:slug" element={<div>Detail page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ReaderPage', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads manifest and mounts flip reader for audio books', async () => {
    libraryApi.fetchBookReaderManifest.mockResolvedValue({
      response: { ok: true, status: 200 },
      data: manifest,
    })

    renderReader()

    await waitFor(() => {
      expect(screen.getByTestId('flip-reader-view')).toBeInTheDocument()
    })

    expect(libraryApi.fetchBookReaderManifest).toHaveBeenCalledWith('test-book')
  })

  it('redirects to detail when access is denied (403 manifest)', async () => {
    libraryApi.fetchBookReaderManifest.mockResolvedValue({
      response: { ok: false, status: 403 },
      data: { detail: 'Purchase required' },
    })

    renderReader()

    await waitFor(() => {
      expect(screen.getByText('Detail page')).toBeInTheDocument()
    })
  })

  it('passes autoplay hash to flip reader view', async () => {
    libraryApi.fetchBookReaderManifest.mockResolvedValue({
      response: { ok: true, status: 200 },
      data: manifest,
    })

    renderReader('/library/test-book/read?mode=flip#autoplay=1')

    await waitFor(() => {
      expect(screen.getByText('autoplay-on')).toBeInTheDocument()
    })
  })

  it('mounts pdf mode when query param is pdf', async () => {
    libraryApi.fetchBookReaderManifest.mockResolvedValue({
      response: { ok: true, status: 200 },
      data: manifest,
    })

    renderReader('/library/test-book/read?mode=pdf')

    await waitFor(() => {
      expect(screen.getByTestId('pdf-reader-mode')).toBeInTheDocument()
    })
  })

  it('mounts flip reader when book has no audio', async () => {
    libraryApi.fetchBookReaderManifest.mockResolvedValue({
      response: { ok: true, status: 200 },
      data: { ...manifest, has_audio: false, audio_chapters: [] },
    })

    renderReader('/library/test-book/read?mode=flip')

    await waitFor(() => {
      expect(screen.getByTestId('flip-reader-view')).toBeInTheDocument()
    })
  })
})

