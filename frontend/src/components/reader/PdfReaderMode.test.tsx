import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as pdfjs from 'pdfjs-dist'
import PdfReaderMode, { PDF_LOAD_TIMEOUT_MS } from './PdfReaderMode'
import * as libraryApi from '../../api/library'

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(() => ({
    promise: Promise.resolve({
      numPages: 4,
      getPage: vi.fn(async () => ({
        getViewport: () => ({ width: 200, height: 300 }),
        render: () => ({ promise: Promise.resolve() }),
      })),
    }),
  })),
}))

vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({
  default: '/pdf.worker.min.mjs',
}))

vi.mock('../../api/library', () => ({
  saveReadingProgress: vi.fn().mockResolvedValue({ response: { ok: true }, data: {} }),
}))

const manifest = {
  slug: 'pdf-book',
  body: 'First paragraph.\n\nSecond paragraph.',
  pdf_url: '/library/media/pdf-book/pdf/',
  has_pdf: true,
  reading_progress: { exists: true, mode: 'pdf', page: 2, total_pages: 4, status: 'reading' },
}

function renderPdf(ui, { slug = 'pdf-book' } = {}) {
  return render(
    <MemoryRouter initialEntries={[`/library/${slug}/read?mode=pdf`]}>
      <Routes>
        <Route path="/library/:slug/read" element={ui} />
      </Routes>
    </MemoryRouter>,
  )
}

function mockFastPdf(numPages = 4) {
  pdfjs.getDocument.mockImplementation(() => ({
    promise: Promise.resolve({
      numPages,
      getPage: vi.fn(async () => ({
        getViewport: () => ({ width: 200, height: 300 }),
        render: () => ({ promise: Promise.resolve() }),
      })),
    }),
  }))
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('PdfReaderMode', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    Element.prototype.scrollIntoView = vi.fn()
    mockFastPdf(4)
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
  })

  it('renders toolbar without clobbering saved progress on load', async () => {
    renderPdf(<PdfReaderMode slug="pdf-book" manifest={manifest} />)

    await waitFor(() => {
      expect(screen.getByText('4 betdan 3-bet')).toBeInTheDocument()
    })

    expect(libraryApi.saveReadingProgress).not.toHaveBeenCalled()
  })

  it('navigates pages and persists progress', async () => {
    renderPdf(<PdfReaderMode slug="pdf-book" manifest={manifest} />)

    await waitFor(() => {
      expect(screen.getByText('4 betdan 3-bet')).toBeInTheDocument()
    })

    vi.clearAllMocks()
    fireEvent.click(screen.getByRole('button', { name: 'Keyingi sahifa' }))

    await waitFor(() => {
      expect(libraryApi.saveReadingProgress).toHaveBeenCalledWith('pdf-book', {
        mode: 'pdf',
        page: 3,
        total_pages: 4,
      })
    })
    expect(screen.getByText('4 betdan 4-bet')).toBeInTheDocument()
  })

  it('ignores rapid next clicks while loading and only saves after load', async () => {
    const docGate = deferred()
    pdfjs.getDocument.mockImplementation(() => ({
      promise: docGate.promise,
    }))

    renderPdf(<PdfReaderMode slug="pdf-book" manifest={manifest} />)

    // While loading, navigation buttons are disabled by ReaderChrome.
    const next = await screen.findByRole('button', { name: 'Keyingi sahifa' })
    expect(next).toBeDisabled()
    fireEvent.click(next)
    fireEvent.click(next)
    fireEvent.click(next)
    expect(libraryApi.saveReadingProgress).not.toHaveBeenCalled()
    expect(screen.queryByText('Saqlandi ✓')).not.toBeInTheDocument()

    // Finish PDF load and verify reading position initializes correctly.
    docGate.resolve({
      numPages: 4,
      getPage: vi.fn(async () => ({
        getViewport: () => ({ width: 200, height: 300 }),
        render: () => ({ promise: Promise.resolve() }),
      })),
    })

    await waitFor(() => {
      expect(screen.getByText('4 betdan 3-bet')).toBeInTheDocument()
    })
    expect(next).toBeEnabled()

    // First deliberate click after load should persist page 4 (index 3).
    fireEvent.click(next)
    await waitFor(() => {
      expect(libraryApi.saveReadingProgress).toHaveBeenCalledWith('pdf-book', {
        mode: 'pdf',
        page: 3,
        total_pages: 4,
      })
    })
  })

  it('shows empty state when no pdf', () => {
    renderPdf(
      <PdfReaderMode
        slug="pdf-book"
        manifest={{ ...manifest, pdf_url: '', has_pdf: false }}
      />,
    )
    expect(screen.getByText('PDF mavjud emas.')).toBeInTheDocument()
  })

  it('falls back when getDocument hangs past the stall window', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    pdfjs.getDocument.mockImplementation(() => ({
      promise: new Promise(() => {}),
    }))

    renderPdf(<PdfReaderMode slug="pdf-book" manifest={manifest} />)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PDF_LOAD_TIMEOUT_MS)
    })

    expect(
      screen.getByText('PDF juda sekin yuklanmoqda. Matn ko‘rinishiga o‘tildi.'),
    ).toBeInTheDocument()
    expect(screen.getByText('First paragraph.')).toBeInTheDocument()
    const next = screen.getByRole('button', { name: 'Keyingi sahifa' })
    expect(next).toBeEnabled()
  })

  it('falls back when a per-page render stalls past the stall window', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })

    let resolvePage1
    const page1Done = new Promise((resolve) => {
      resolvePage1 = resolve
    })
    let renderCalls = 0

    pdfjs.getDocument.mockImplementation(() => ({
      promise: Promise.resolve({
        numPages: 3,
        getPage: vi.fn(async () => ({
          getViewport: () => ({ width: 200, height: 300 }),
          render: () => {
            renderCalls += 1
            if (renderCalls === 1) {
              return { promise: page1Done }
            }
            return { promise: new Promise(() => {}) }
          },
        })),
      }),
    }))

    renderPdf(<PdfReaderMode slug="pdf-book" manifest={manifest} />)

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(renderCalls).toBeGreaterThanOrEqual(1)

    await act(async () => {
      resolvePage1()
      await Promise.resolve()
      await Promise.resolve()
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(PDF_LOAD_TIMEOUT_MS - 500)
    })
    expect(
      screen.queryByText('PDF juda sekin yuklanmoqda. Matn ko‘rinishiga o‘tildi.'),
    ).not.toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })

    expect(
      screen.getByText('PDF juda sekin yuklanmoqda. Matn ko‘rinishiga o‘tildi.'),
    ).toBeInTheDocument()
    expect(screen.getByText('First paragraph.')).toBeInTheDocument()
  })

  it('does not fall back when each page finishes before the stall window', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const resolvers = []

    pdfjs.getDocument.mockImplementation(() => ({
      promise: Promise.resolve({
        numPages: 2,
        getPage: vi.fn(async () => ({
          getViewport: () => ({ width: 200, height: 300 }),
          render: () => {
            let resolve
            const promise = new Promise((r) => {
              resolve = r
            })
            resolvers.push(resolve)
            return { promise }
          },
        })),
      }),
    }))

    renderPdf(<PdfReaderMode slug="pdf-book" manifest={manifest} />)

    // Drive every queued render to completion, resetting the stall timer each time
    // (Strict Mode may schedule extra mounts; resolve whatever is pending).
    for (let step = 0; step < 8; step += 1) {
      await act(async () => {
        await Promise.resolve()
        await Promise.resolve()
      })
      if (resolvers.length === 0) break

      await act(async () => {
        await vi.advanceTimersByTimeAsync(PDF_LOAD_TIMEOUT_MS - 1000)
      })
      expect(
        screen.queryByText('PDF juda sekin yuklanmoqda. Matn ko‘rinishiga o‘tildi.'),
      ).not.toBeInTheDocument()

      const pending = resolvers.splice(0, resolvers.length)
      await act(async () => {
        pending.forEach((resolve) => resolve())
        await Promise.resolve()
        await Promise.resolve()
      })

      if (screen.queryByText('2 betdan 2-bet')) break
    }

    expect(screen.getByText('2 betdan 2-bet')).toBeInTheDocument()
    expect(
      screen.queryByText('PDF juda sekin yuklanmoqda. Matn ko‘rinishiga o‘tildi.'),
    ).not.toBeInTheDocument()
  })

  it('keeps loading gate scoped to active mount (book/mode switch remount works)', async () => {
    const firstDoc = deferred()
    pdfjs.getDocument.mockImplementationOnce(() => ({ promise: firstDoc.promise }))

    const { rerender } = renderPdf(
      <PdfReaderMode slug="pdf-book" manifest={manifest} />,
    )
    const next = await screen.findByRole('button', { name: 'Keyingi sahifa' })
    expect(next).toBeDisabled()

    // Simulate mode/book switch by remounting with a new slug/manifest.
    mockFastPdf(2)
    rerender(
      <MemoryRouter initialEntries={['/library/other-book/read?mode=pdf']}>
        <Routes>
          <Route
            path="/library/:slug/read"
            element={
              <PdfReaderMode
                slug="other-book"
                manifest={{
                  ...manifest,
                  slug: 'other-book',
                  reading_progress: { exists: false, status: null },
                }}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('2 betdan 1-bet')).toBeInTheDocument()
    })
    const nextAfterSwitch = screen.getByRole('button', { name: 'Keyingi sahifa' })
    expect(nextAfterSwitch).toBeEnabled()
  })
})

