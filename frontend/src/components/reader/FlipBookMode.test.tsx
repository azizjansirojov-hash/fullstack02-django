import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FlipBookMode, { MAX_ZOOM, MIN_ZOOM, RESIZE_DELAY_MS } from './FlipBookMode'
import * as libraryApi from '../../api/library'

const flipHandlers = {}

const pageFlipState = vi.hoisted(() => ({
  instance: null,
  PageFlip: vi.fn(function MockPageFlip() {
    let pageCount = 0
    let currentIndex = 0

    const api = {
      loadFromHTML(elements) {
        pageCount = Math.max(elements.length, 4)
      },
      on(event, handler) {
        flipHandlers[event] = handler
      },
      getPageCount: () => pageCount,
      getCurrentPageIndex: () => currentIndex,
      flipNext() {
        if (currentIndex < pageCount - 1) {
          currentIndex += 1
          flipHandlers.flip?.({ data: currentIndex })
        }
      },
      flipPrev() {
        if (currentIndex > 0) {
          currentIndex -= 1
          flipHandlers.flip?.({ data: currentIndex })
        }
      },
      turnToPage(index) {
        currentIndex = Math.max(0, Math.min(pageCount - 1, index))
      },
      destroy: vi.fn(),
    }

    pageFlipState.instance = api
    return api
  }),
}))

vi.mock('page-flip', () => ({
  PageFlip: pageFlipState.PageFlip,
}))

vi.mock('../../api/library', () => ({
  saveReadingProgress: vi.fn().mockResolvedValue({ response: { ok: true }, data: {} }),
}))

const manifest = {
  slug: 'flip-book',
  body: `${'First paragraph with enough words to paginate. '.repeat(20)}\n\n${'Second paragraph here with more words. '.repeat(20)}`,
  has_audio: false,
  reading_progress: { exists: true, mode: 'flip', page: 1, total_pages: 4, status: 'reading' },
}

function renderFlip(ui, { slug = 'flip-book' } = {}) {
  return render(
    <MemoryRouter initialEntries={[`/library/${slug}/read`]}>
      <Routes>
        <Route path="/library/:slug/read" element={ui} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('FlipBookMode', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    Object.keys(flipHandlers).forEach((key) => {
      delete flipHandlers[key]
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    Object.keys(flipHandlers).forEach((key) => {
      delete flipHandlers[key]
    })
    pageFlipState.instance = null
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    )
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1200 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 900 })
    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
      configurable: true,
      get() {
        if (this.classList?.contains('page-content')) {
          return (this.innerHTML || '').length > 120 ? 900 : 120
        }
        return 0
      },
    })
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      get() {
        if (this.classList?.contains('page-content')) return 380
        return 0
      },
    })
  })

  it('initializes PageFlip and restores saved page with flip progress payload', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalled()
    })

    expect(pageFlipState.PageFlip.mock.calls[0][1]).toMatchObject({
      size: 'stretch',
      minWidth: 280,
      maxWidth: 520,
      drawShadow: true,
    })

    await waitFor(() => {
      expect(libraryApi.saveReadingProgress).toHaveBeenCalledWith('flip-book', {
        mode: 'flip',
        page: 1,
        position: 0,
        total_pages: expect.any(Number),
      })
    })
  })

  it('navigates via toolbar and saves progress on flip', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalled()
    })

    vi.clearAllMocks()
    fireEvent.click(screen.getByRole('button', { name: 'Keyingi sahifa' }))

    await waitFor(() => {
      expect(libraryApi.saveReadingProgress).toHaveBeenCalledWith('flip-book', {
        mode: 'flip',
        page: 2,
        position: 0,
        total_pages: expect.any(Number),
      })
    })
  })

  it('handles keyboard navigation', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalled()
    })

    vi.clearAllMocks()
    fireEvent.keyDown(document, { key: 'ArrowRight' })

    await waitFor(() => {
      expect(libraryApi.saveReadingProgress).toHaveBeenCalled()
    })
  })

  it('destroys PageFlip on unmount', async () => {
    const { unmount } = renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalled()
    })

    unmount()
    expect(pageFlipState.instance.destroy).toHaveBeenCalled()
  })

  it('skips relayout when resize does not change page dimensions', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalledTimes(1)
    })

    fireEvent(window, new Event('resize'))

    await new Promise((r) => setTimeout(r, RESIZE_DELAY_MS + 100))
    expect(pageFlipState.PageFlip.mock.calls.length).toBe(1)
  })

  it('relayouts on window resize when dimensions change', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalledTimes(1)
    })

    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 480 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
    fireEvent(window, new Event('resize'))

    await waitFor(
      () => {
        expect(pageFlipState.PageFlip.mock.calls.length).toBeGreaterThan(1)
      },
      { timeout: RESIZE_DELAY_MS + 500 },
    )
  })

  it('applies flip zoom CSS variable', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalled()
    })

    const root = document.querySelector('.flip-book-mode.book-reader')
    expect(root).toBeTruthy()
    expect(root.style.getPropertyValue('--flip-zoom') || '1').toBe('1')

    fireEvent.click(screen.getByRole('button', { name: 'Kattalashtirish' }))
    expect(parseFloat(root.style.getPropertyValue('--flip-zoom'))).toBeGreaterThan(1)
    expect(parseFloat(root.style.getPropertyValue('--flip-zoom'))).toBeLessThanOrEqual(MAX_ZOOM)

    fireEvent.click(screen.getByRole('button', { name: 'Kichiklashtirish' }))
    expect(parseFloat(root.style.getPropertyValue('--flip-zoom'))).toBeGreaterThanOrEqual(MIN_ZOOM)
  })

  it('cycles font size and rebuilds flip book', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.PageFlip).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByRole('button', { name: 'Shrift sozlamalari' }))

    await waitFor(() => {
      expect(pageFlipState.PageFlip.mock.calls.length).toBeGreaterThan(1)
    })
  })

  it('adds nav zone buttons to mount', async () => {
    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(document.querySelector('.book-reader__nav-zone--prev')).toBeTruthy()
      expect(document.querySelector('.book-reader__nav-zone--next')).toBeTruthy()
    })
  })

  it('shows "Saqlandi" badge after successful progress save then hides it', async () => {
    libraryApi.saveReadingProgress.mockResolvedValue({ response: { ok: true }, data: {} })

    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.instance).toBeTruthy()
    })

    // Trigger a page flip to fire persistFlipProgress
    flipHandlers.flip?.({ data: 1 })

    await waitFor(() => {
      expect(screen.queryByText(/Saqlandi/)).toBeTruthy()
    }, { timeout: 3000 })
  })

  it('shows error badge when progress save fails', async () => {
    libraryApi.saveReadingProgress.mockRejectedValue(new Error('network error'))

    renderFlip(<FlipBookMode slug="flip-book" manifest={manifest} />)

    await waitFor(() => {
      expect(pageFlipState.instance).toBeTruthy()
    })

    flipHandlers.flip?.({ data: 1 })

    await waitFor(() => {
      expect(screen.queryByText(/Xatolik/)).toBeTruthy()
    }, { timeout: 3000 })
  })

  it('paginates a long body into more than one flip page (collapse regression)', async () => {
    // Trust real element count so a 1-page collapse is visible (default mock
    // forces Math.max(elements.length, 4) which would hide the bug).
    const previousImpl = pageFlipState.PageFlip.getMockImplementation()
    pageFlipState.PageFlip.mockImplementation(function MockPageFlip() {
      let pageCount = 0
      const api = {
        loadFromHTML(elements) {
          pageCount = elements.length
        },
        on: vi.fn(),
        getPageCount: () => pageCount,
        getCurrentPageIndex: () => 0,
        flipNext: vi.fn(),
        flipPrev: vi.fn(),
        turnToPage: vi.fn(),
        destroy: vi.fn(),
      }
      pageFlipState.instance = api
      return api
    })

    try {
      const longBody = Array.from(
        { length: 20 },
        (_, i) => `Chapter block ${i}. ${'Word '.repeat(80)}`,
      ).join('\n\n')

      renderFlip(
        <FlipBookMode
          slug="flip-book"
          manifest={{ ...manifest, body: longBody, reading_progress: { exists: false } }}
        />,
      )

      await waitFor(() => {
        expect(pageFlipState.instance).toBeTruthy()
      })

      expect(pageFlipState.instance.getPageCount()).toBeGreaterThan(1)
      const counters = screen.getAllByText(/\d+ \/ \d+ sahifa/)
      const pageLabels = screen.getAllByText(/\d+ betdan \d+-bet/)
      expect(
        counters.some((el) => !/^1 \/ 1\b/.test(el.textContent || '')) ||
          pageLabels.some((el) => !/1 betdan 1-bet/.test(el.textContent || '')),
      ).toBe(true)
    } finally {
      if (previousImpl) {
        pageFlipState.PageFlip.mockImplementation(previousImpl)
      } else {
        pageFlipState.PageFlip.mockReset()
      }
    }
  })
})

