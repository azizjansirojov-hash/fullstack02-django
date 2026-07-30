import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FlipReaderView from './FlipReaderView'
import * as libraryApi from '../../api/library'

const pageFlipState = vi.hoisted(() => ({
  PageFlip: vi.fn(function MockPageFlip() {
    let pageCount = 0
    return {
      loadFromHTML(elements) {
        pageCount = Math.max(elements.length, 2)
      },
      on: vi.fn(),
      getPageCount: () => pageCount,
      getCurrentPageIndex: () => 0,
      flipNext: vi.fn(),
      flipPrev: vi.fn(),
      turnToPage: vi.fn(),
      destroy: vi.fn(),
    }
  }),
}))

vi.mock('page-flip', () => ({
  PageFlip: pageFlipState.PageFlip,
}))

vi.mock('../../api/library', () => ({
  saveReadingProgress: vi.fn().mockResolvedValue({ response: { ok: true }, data: {} }),
}))

const audioManifest = {
  slug: 'audio-book',
  body: 'Birinchi jumla. Ikkinchi jumla.',
  has_audio: true,
  audio_sync: [{ start: 0, end: 2, index: 0, text: 'Birinchi jumla.' }],
  audio_chapters: [{ id: 1, title: '1-qism', url: '/library/media/audio-book/audio/1/', order: 0 }],
  reading_progress: { exists: false, status: null },
}

function renderView(ui, { slug = 'audio-book' } = {}) {
  return render(
    <MemoryRouter initialEntries={[`/library/${slug}/read`]}>
      <Routes>
        <Route path="/library/:slug/read" element={ui} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('FlipReaderView', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
    HTMLMediaElement.prototype.pause = vi.fn()
    HTMLMediaElement.prototype.load = vi.fn()
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1200 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 900 })
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('keeps flip mounted for audio books and hides audio bar by default', async () => {
    renderView(<FlipReaderView slug="audio-book" manifest={audioManifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalled()
    })

    expect(screen.getByRole('button', { name: 'Tinglash' })).toBeInTheDocument()
    expect(document.querySelector('.flip-reader-view__audio-shell')).toHaveAttribute('hidden')
    expect(document.querySelector('.book-reader__mount')).toBeTruthy()
  })

  it('shows audio overlay and starts playback when Tinglash is clicked', async () => {
    renderView(<FlipReaderView slug="audio-book" manifest={audioManifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalled()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Tinglash' }))

    expect(document.querySelector('.flip-reader-view__audio-shell')).not.toHaveAttribute('hidden')
    expect(document.querySelector('.book-reader__mount')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Tinglash' })).toBeInTheDocument()
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled()
  })

  it('auto-shows audio bar on autoplay while flip stays mounted', async () => {
    renderView(<FlipReaderView slug="audio-book" manifest={audioManifest} autoplay />)

    await waitFor(() => {
      expect(document.querySelector('.flip-reader-view__audio-shell')).not.toHaveAttribute('hidden')
    })

    expect(pageFlipState.PageFlip).toHaveBeenCalled()
    expect(document.querySelector('.book-reader__mount')).toBeTruthy()
  })

  it('embeds sentence spans in flip pages when audio is available', async () => {
    renderView(<FlipReaderView slug="audio-book" manifest={audioManifest} />)

    await waitFor(() => {
      expect(document.querySelector('[data-sentence-index="0"]')).toBeTruthy()
    })
  })
})

