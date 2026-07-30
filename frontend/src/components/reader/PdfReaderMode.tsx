import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { saveReadingProgress } from '../../api/library'
import * as pdfjs from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import ReaderChrome from './ReaderChrome'
import type { ReaderManifest } from '../../types/library'

pdfjs.GlobalWorkerOptions.workerSrc = pdfjsWorker

const PDF_RENDER_SCALE = 1.1
/** Stall window for fetch OR per-page render — reset on each progress event. */
export const PDF_LOAD_TIMEOUT_MS = 12000
/** Debounce window for progress PUTs after scroll/nav. */
export const PDF_SAVE_DEBOUNCE_MS = 400
/** Render this many pages on either side of the current page. */
export const PDF_RENDER_WINDOW = 2
const MIN_ZOOM = 0.75
const MAX_ZOOM = 2
const PLACEHOLDER_HEIGHT_PX = 480

function bodyParagraphs(body: string) {
  return String(body || '')
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
}

/**
 * PDF reader mode — pdfjs-dist with windowed canvas render, scroll sync, debounce.
 * Timeout covers fetch and render: a rolling 12s stall timer resets on each
 * getDocument resolve and each page-render completion.
 */
export default function PdfReaderMode({ slug, manifest }: { slug: string; manifest: ReaderManifest }) {
  const navigate = useNavigate()
  const rootRef = useRef<HTMLDivElement | null>(null)
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const pdfDocRef = useRef<pdfjs.PDFDocumentProxy | null>(null)
  const renderedPagesRef = useRef<Set<number>>(new Set())
  const renderInFlightRef = useRef<Set<number>>(new Set())
  const currentPageRef = useRef(1)
  const totalPagesRef = useRef(1)
  const applyingScrollRef = useRef(false)
  const [loading, setLoading] = useState(true)
  const [stateMessage, setStateMessage] = useState('Sahifalar yuklanmoqda…')
  const [useFallback, setUseFallback] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [isLight, setIsLight] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const saveTimerRef = useRef<number | null>(null)
  const saveStatusTimerRef = useRef<number | null>(null)

  const pdfUrl = manifest.pdf_url
  const hasAudio = Boolean(manifest.has_audio && manifest.audio_chapters?.some((ch) => ch?.url))
  const hasPdf = Boolean(manifest.has_pdf && manifest.pdf_url)
  const savedPage =
    manifest.reading_progress?.exists && typeof manifest.reading_progress.page === 'number'
      ? manifest.reading_progress.page + 1
      : 1

  const persistPdfProgress = useCallback(
    (page1Based: number, total: number) => {
      if (!slug) return
      const totalSafe = Math.max(1, total || totalPagesRef.current || 1)
      const pageIndex = Math.max(0, Math.min(totalSafe - 1, page1Based - 1))
      setSaveStatus('saving')
      saveReadingProgress(slug, {
        mode: 'pdf',
        page: pageIndex,
        total_pages: totalSafe,
      }).then(() => {
        setSaveStatus('saved')
        if (saveStatusTimerRef.current !== null) window.clearTimeout(saveStatusTimerRef.current)
        saveStatusTimerRef.current = window.setTimeout(() => setSaveStatus('idle'), 2000)
      }).catch(() => {
        setSaveStatus('error')
        if (saveStatusTimerRef.current !== null) window.clearTimeout(saveStatusTimerRef.current)
        saveStatusTimerRef.current = window.setTimeout(() => setSaveStatus('idle'), 3000)
      })
    },
    [slug],
  )

  const scheduleSave = useCallback(
    (page1Based: number, total: number) => {
      if (saveTimerRef.current !== null) window.clearTimeout(saveTimerRef.current)
      saveTimerRef.current = window.setTimeout(() => {
        persistPdfProgress(page1Based, total)
      }, PDF_SAVE_DEBOUNCE_MS)
    },
    [persistPdfProgress],
  )

  const flushPendingSave = useCallback(() => {
    if (saveTimerRef.current !== null) window.clearTimeout(saveTimerRef.current)
    saveTimerRef.current = null
    persistPdfProgress(currentPageRef.current, totalPagesRef.current)
  }, [persistPdfProgress])

  const renderPageWindow = useCallback(async (centerPage: number, pdf: pdfjs.PDFDocumentProxy) => {
    const viewport = viewportRef.current
    if (!viewport || !pdf) return
    const pages = pdf.numPages
    const start = Math.max(1, centerPage - PDF_RENDER_WINDOW)
    const end = Math.min(pages, centerPage + PDF_RENDER_WINDOW)

    for (let pageNumber = start; pageNumber <= end; pageNumber += 1) {
      if (renderedPagesRef.current.has(pageNumber) || renderInFlightRef.current.has(pageNumber)) {
        continue
      }
      renderInFlightRef.current.add(pageNumber)
      try {
        const page = await pdf.getPage(pageNumber)
        if (!viewportRef.current || pdfDocRef.current !== pdf) return
        const wrapper = viewport.querySelector<HTMLElement>(`[data-page="${pageNumber}"]`)
        if (!wrapper || wrapper.querySelector('canvas')) {
          renderedPagesRef.current.add(pageNumber)
          continue
        }
        const canvas = document.createElement('canvas')
        const context = canvas.getContext('2d')
        if (!context) continue
        const viewportInfo = page.getViewport({ scale: PDF_RENDER_SCALE })
        canvas.height = viewportInfo.height
        canvas.width = viewportInfo.width
        canvas.className = 'pdf-reader__canvas'
        wrapper.style.minHeight = ''
        wrapper.appendChild(canvas)
        await page.render({ canvasContext: context, viewport: viewportInfo }).promise
        renderedPagesRef.current.add(pageNumber)
      } catch {
        /* page render failed — leave placeholder */
      } finally {
        renderInFlightRef.current.delete(pageNumber)
      }
    }

    // Drop canvases far from the window to limit memory.
    for (const pageNumber of Array.from(renderedPagesRef.current)) {
      if (pageNumber >= start && pageNumber <= end) continue
      const wrapper = viewport.querySelector<HTMLElement>(`[data-page="${pageNumber}"]`)
      const canvas = wrapper?.querySelector('canvas')
      if (canvas) {
        canvas.remove()
        if (wrapper) wrapper.style.minHeight = `${PLACEHOLDER_HEIGHT_PX}px`
      }
      renderedPagesRef.current.delete(pageNumber)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    let fellBack = false
    let stallTimeoutId: number | null = null
    const viewport = viewportRef.current
    if (!viewport) return undefined
    const activeViewport = viewport

    function clearStallTimer() {
      if (stallTimeoutId !== null) window.clearTimeout(stallTimeoutId)
      stallTimeoutId = null
    }

    function switchToTimeoutFallback() {
      if (cancelled || fellBack) return
      fellBack = true
      clearStallTimer()
      pdfDocRef.current = null
      setUseFallback(true)
      setStateMessage('PDF juda sekin yuklanmoqda. Matn ko‘rinishiga o‘tildi.')
      const total = Math.max(1, bodyParagraphs(manifest.body).length)
      setTotalPages(total)
      totalPagesRef.current = total
      setLoading(false)
    }

    /** Rolling stall timer — any 12s gap without progress triggers fallback. */
    function armStallTimer() {
      clearStallTimer()
      stallTimeoutId = window.setTimeout(switchToTimeoutFallback, PDF_LOAD_TIMEOUT_MS)
    }

    async function renderPdf() {
      if (!pdfUrl) {
        setUseFallback(true)
        setStateMessage('PDF mavjud emas.')
        const total = Math.max(1, bodyParagraphs(manifest.body).length)
        setTotalPages(total)
        totalPagesRef.current = total
        setLoading(false)
        return
      }

      armStallTimer()
      renderedPagesRef.current = new Set()
      renderInFlightRef.current = new Set()

      try {
        const loadingTask = pdfjs.getDocument({ url: pdfUrl })
        const pdf = await loadingTask.promise
        if (cancelled || fellBack) return
        armStallTimer()
        pdfDocRef.current = pdf

        const pages = pdf.numPages
        setTotalPages(pages)
        totalPagesRef.current = pages
        activeViewport.innerHTML = ''

        for (let pageNumber = 1; pageNumber <= pages; pageNumber += 1) {
          const wrapper = document.createElement('article')
          wrapper.className = 'pdf-reader__page'
          wrapper.dataset.page = String(pageNumber)
          wrapper.style.minHeight = `${PLACEHOLDER_HEIGHT_PX}px`
          activeViewport.appendChild(wrapper)
        }

        const startPage = Math.max(1, Math.min(pages, savedPage))
        currentPageRef.current = startPage
        setCurrentPage(startPage)

        await renderPageWindow(startPage, pdf)
        if (cancelled || fellBack) return
        armStallTimer()

        clearStallTimer()
        if (cancelled || fellBack) return

        setLoading(false)
        setStateMessage('')
        applyingScrollRef.current = true
        requestAnimationFrame(() => {
          const target = activeViewport.querySelector(`[data-page="${startPage}"]`)
          target?.scrollIntoView({ behavior: 'auto', block: 'start' })
          requestAnimationFrame(() => {
            applyingScrollRef.current = false
          })
        })
      } catch {
        if (cancelled || fellBack) return
        clearStallTimer()
        pdfDocRef.current = null
        setUseFallback(true)
        setStateMessage('PDF yuklanmadi. Matn ko‘rinishiga o‘tildi.')
        const total = Math.max(1, bodyParagraphs(manifest.body).length)
        setTotalPages(total)
        totalPagesRef.current = total
        setLoading(false)
      }
    }

    renderPdf()

    return () => {
      cancelled = true
      clearStallTimer()
      if (saveTimerRef.current !== null) window.clearTimeout(saveTimerRef.current)
      pdfDocRef.current = null
      renderedPagesRef.current = new Set()
      renderInFlightRef.current = new Set()
    }
  }, [manifest.body, pdfUrl, renderPageWindow, savedPage])

  // Scroll → page sync via IntersectionObserver
  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport || useFallback || loading) return undefined

    const ratios = new Map<number, number>()
    const observer = new IntersectionObserver(
      (entries) => {
        if (applyingScrollRef.current) return
        for (const entry of entries) {
          const page = Number(entry.target.getAttribute('data-page'))
          if (!Number.isFinite(page)) continue
          ratios.set(page, entry.isIntersecting ? entry.intersectionRatio : 0)
        }
        let bestPage = currentPageRef.current
        let bestRatio = -1
        for (const [page, ratio] of ratios) {
          if (ratio > bestRatio) {
            bestRatio = ratio
            bestPage = page
          }
        }
        if (bestRatio <= 0 || bestPage === currentPageRef.current) return
        currentPageRef.current = bestPage
        setCurrentPage(bestPage)
        scheduleSave(bestPage, totalPagesRef.current)
        const pdf = pdfDocRef.current
        if (pdf) renderPageWindow(bestPage, pdf)
      },
      { root: viewport, threshold: [0.25, 0.5, 0.75] },
    )

    viewport.querySelectorAll('[data-page]').forEach((el: Element) => observer.observe(el))
    return () => observer.disconnect()
  }, [loading, renderPageWindow, scheduleSave, useFallback, totalPages])

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return
    viewport.style.setProperty('--pdf-zoom', String(zoom))
  }, [zoom])

  useEffect(() => {
    function onHide() {
      flushPendingSave()
    }
    window.addEventListener('pagehide', onHide)
    return () => window.removeEventListener('pagehide', onHide)
  }, [flushPendingSave])

  function goToPage(nextPage: number) {
    if (loading) return
    const clamped = Math.max(1, Math.min(totalPages, nextPage))
    currentPageRef.current = clamped
    setCurrentPage(clamped)
    scheduleSave(clamped, totalPages)
    const pdf = pdfDocRef.current
    if (pdf) renderPageWindow(clamped, pdf)
    applyingScrollRef.current = true
    const target = viewportRef.current?.querySelector(`[data-page="${clamped}"]`)
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    window.setTimeout(() => {
      applyingScrollRef.current = false
    }, 400)
  }

  if (!pdfUrl && !manifest.has_pdf) {
    return (
      <p className="pdf-reader-mode__empty" role="status">
        PDF mavjud emas.
      </p>
    )
  }

  const paragraphs = bodyParagraphs(manifest.body)

  function toggleFullscreen() {
    const root = rootRef.current
    if (!root) return
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
      return
    }
    root.requestFullscreen?.().catch(() => {})
  }

  return (
    <div
      ref={rootRef}
      className={`pdf-reader-mode book-reader${isLight ? ' is-light' : ''}`}
      data-reader-mode="pdf"
    >
      <ReaderChrome
        mode="pdf"
        title={manifest.title || ''}
        author={manifest.author_name || ''}
        backHref={manifest.detail_url}
        hasPdf={hasPdf}
        hasAudio={hasAudio}
        currentPage={currentPage}
        totalPages={totalPages}
        zoom={zoom}
        darkActive={!isLight}
        saveStatus={saveStatus}
        onPrev={() => goToPage(currentPage - 1)}
        onNext={() => goToPage(currentPage + 1)}
        onZoomOut={() => setZoom((z) => Math.max(MIN_ZOOM, z - 0.1))}
        onZoomIn={() => setZoom((z) => Math.min(MAX_ZOOM, z + 0.1))}
        navigationEnabled={!loading}
        onListen={() => {
          if (!hasAudio || !slug) return
          navigate(`/library/${encodeURIComponent(slug)}/read#autoplay=1`)
        }}
        onToggleDark={() => setIsLight((v) => !v)}
        onFullscreen={toggleFullscreen}
        onDownload={() => {
          if (pdfUrl) window.open(pdfUrl, '_blank', 'noopener,noreferrer')
        }}
      />

      <div className="pdf-reader">
        {stateMessage && !useFallback ? (
          <p className="pdf-reader__state">{stateMessage}</p>
        ) : null}
        {useFallback ? (
          <>
            {stateMessage ? <p className="pdf-reader__state">{stateMessage}</p> : null}
            <div className="pdf-reader__viewport" ref={viewportRef}>
              {paragraphs.map((paragraph, index) => (
                <article key={`fb-${index}`} className="pdf-reader__page" data-page={index + 1}>
                  <h3 className="pdf-reader__page-number">{index + 1}-sahifa</h3>
                  <p>{paragraph}</p>
                </article>
              ))}
            </div>
          </>
        ) : (
          <div className="pdf-reader__viewport" ref={viewportRef} />
        )}
        {loading && !useFallback ? (
          <p className="pdf-reader__state">{stateMessage || 'Sahifalar yuklanmoqda…'}</p>
        ) : null}
      </div>
    </div>
  )
}

