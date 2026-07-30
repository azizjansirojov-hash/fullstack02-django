import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { PageFlip } from 'page-flip'
import { saveReadingProgress } from '../../api/library'
import type { ProgressUpsertBody, ReaderManifest } from '../../types/library'
import {
  FONT_STEPS,
  LINE_STEPS,
  PAGE_FLIP_OPTIONS,
  applyReaderSettingsToRoot,
  buildPageElements,
  cycleFontIndex,
  cycleLineIndex,
  getFlipTime,
  getPageDimensions,
  getParagraphsFromBody,
  getSavedPageIndex,
  loadReaderSettings,
  paginateContent,
  saveReaderSettings,
} from '../../lib/reader/flipPagination'
import ReaderChrome from './ReaderChrome'

const MIN_ZOOM = 0.75
const MAX_ZOOM = 2
const RESIZE_DELAY_MS = 250

function createMountElement() {
  const mount = document.createElement('div')
  mount.className = 'book-reader__mount'
  return mount
}

/**
 * Flip-book reader — St.PageFlip 2.0.7 direct port of Django reader.js.
 */
type FlipBookModeProps = {
  slug: string
  manifest: ReaderManifest
  onFlipReady?: () => void
  onListenClick?: () => void
  onPageChange?: (pageIndex: number) => void
}

export default function FlipBookMode({
  slug,
  manifest,
  onFlipReady,
  onListenClick,
  onPageChange,
}: FlipBookModeProps) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const mountHostRef = useRef<HTMLDivElement | null>(null)
  const pageFlipRef = useRef<PageFlip | null>(null)
  const navZonesRef = useRef<HTMLButtonElement[]>([])
  const resizeTimerRef = useRef<number | null>(null)
  const lastDimsRef = useRef<ReturnType<typeof getPageDimensions> | null>(null)
  const lastProgressRef = useRef({ page: 0, total: 0 })
  const onFlipReadyRef = useRef(onFlipReady)
  onFlipReadyRef.current = onFlipReady
  const onPageChangeRef = useRef(onPageChange)
  onPageChangeRef.current = onPageChange

  const [loading, setLoading] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [readerSettings, setReaderSettings] = useState(() => loadReaderSettings())
  const [isLight, setIsLight] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const saveStatusTimerRef = useRef<number | null>(null)

  const hasAudio = Boolean(manifest.has_audio && manifest.audio_chapters?.some((ch) => ch?.url))
  const hasPdf = Boolean(manifest.has_pdf && manifest.pdf_url)
  const sentenceWrap = hasAudio

  const persistFlipProgress = useCallback(
    (pageIndex: number, total: number) => {
      if (!slug) return
      const payload: ProgressUpsertBody = {
        mode: 'flip',
        page: pageIndex,
        position: 0,
      }
      if (total && total > 0) {
        payload.total_pages = total
      }
      setSaveStatus('saving')
      saveReadingProgress(slug, payload).then(() => {
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

  const updateCounterFromFlip = useCallback((pageFlip: PageFlip | null) => {
    if (!pageFlip) return
    const index = pageFlip.getCurrentPageIndex()
    const total = pageFlip.getPageCount()
    setCurrentPage(index + 1)
    setTotalPages(total)
    lastProgressRef.current = { page: index, total }
    onPageChangeRef.current?.(index)
  }, [])

  const destroyFlip = useCallback(() => {
    const host = mountHostRef.current
    if (pageFlipRef.current) {
      try {
        pageFlipRef.current.destroy()
      } catch {
        /* ignore */
      }
      pageFlipRef.current = null
    }
    navZonesRef.current.forEach((zone) => {
      zone.remove()
    })
    navZonesRef.current = []
    if (host) {
      host.replaceChildren()
    }
  }, [])

  const addNavZones = useCallback((mount: HTMLDivElement | null, pageFlip: PageFlip | null) => {
    if (!mount || !pageFlip) return

    const prev = document.createElement('button')
    prev.type = 'button'
    prev.className = 'book-reader__nav-zone book-reader__nav-zone--prev'
    prev.setAttribute('aria-label', 'Previous page')
    prev.addEventListener('click', () => {
      pageFlip.flipPrev()
    })

    const next = document.createElement('button')
    next.type = 'button'
    next.className = 'book-reader__nav-zone book-reader__nav-zone--next'
    next.setAttribute('aria-label', 'Next page')
    next.addEventListener('click', () => {
      pageFlip.flipNext()
    })

    mount.appendChild(prev)
    mount.appendChild(next)
    navZonesRef.current = [prev, next]
  }, [])

  const initReader = useCallback(
    (preserveIndex?: number) => {
      const host = mountHostRef.current
      if (!host) return

      applyReaderSettingsToRoot(readerSettings)

      const dims = getPageDimensions()
      const paragraphs = getParagraphsFromBody(manifest.body)
      const pagesHtml = paginateContent(paragraphs, dims.width, dims.height)
      const pageElements = buildPageElements(pagesHtml, { sentenceWrap })

      const targetIndex =
        typeof preserveIndex === 'number'
          ? Math.max(0, Math.min(pagesHtml.length - 1, preserveIndex))
          : getSavedPageIndex(pagesHtml.length, manifest.reading_progress)

      destroyFlip()

      const mount = createMountElement()
      host.appendChild(mount)
      pageElements.forEach((el) => {
        mount.appendChild(el)
      })

      const pageFlip = new PageFlip(mount, {
        width: dims.width,
        height: dims.height,
        ...PAGE_FLIP_OPTIONS,
        usePortrait: dims.isPortrait,
        flippingTime: getFlipTime(),
      })

      pageFlip.loadFromHTML(pageElements)

      pageFlip.on('flip', (e) => {
        const total = pageFlip.getPageCount()
        lastProgressRef.current = { page: e.data, total }
        persistFlipProgress(e.data, total)
        updateCounterFromFlip(pageFlip)
      })

      pageFlip.on('changeState', (e) => {
        if (e.data === 'read') updateCounterFromFlip(pageFlip)
      })

      if (targetIndex > 0) {
        pageFlip.turnToPage(targetIndex)
      }

      addNavZones(mount, pageFlip)
      updateCounterFromFlip(pageFlip)
      pageFlipRef.current = pageFlip
      lastDimsRef.current = dims
      setLoading(false)

      // Persist restored page on first open only — not on font/line/resize rebuilds.
      if (typeof preserveIndex !== 'number' && targetIndex > 0) {
        persistFlipProgress(targetIndex, pageFlip.getPageCount())
      }

      onFlipReadyRef.current?.()
    },
    [
      addNavZones,
      destroyFlip,
      manifest.body,
      manifest.reading_progress,
      persistFlipProgress,
      readerSettings,
      sentenceWrap,
      updateCounterFromFlip,
    ],
  )

  const rebuildReader = useCallback(() => {
    const currentIndex = pageFlipRef.current ? pageFlipRef.current.getCurrentPageIndex() : 0
    setLoading(true)
    requestAnimationFrame(() => {
      initReader(currentIndex)
    })
  }, [initReader])

  const cycleFont = useCallback(() => {
    const next = {
      ...readerSettings,
      fontIndex: cycleFontIndex(readerSettings.fontIndex),
    }
    setReaderSettings(next)
    saveReaderSettings(next)
    applyReaderSettingsToRoot(next)
    rebuildReader()
  }, [readerSettings, rebuildReader])

  const cycleLine = useCallback(() => {
    const next = {
      ...readerSettings,
      lineIndex: cycleLineIndex(readerSettings.lineIndex),
    }
    setReaderSettings(next)
    saveReaderSettings(next)
    applyReaderSettingsToRoot(next)
    rebuildReader()
  }, [readerSettings, rebuildReader])

  useEffect(() => {
    initReader()

    const onResize = () => {
      if (resizeTimerRef.current !== null) window.clearTimeout(resizeTimerRef.current)
      resizeTimerRef.current = window.setTimeout(() => {
        const dims = getPageDimensions()
        const prev = lastDimsRef.current
        if (
          prev &&
          prev.width === dims.width &&
          prev.height === dims.height &&
          prev.isPortrait === dims.isPortrait
        ) {
          return
        }
        rebuildReader()
      }, RESIZE_DELAY_MS)
    }

    const onKeydown = (e: KeyboardEvent) => {
      const pageFlip = pageFlipRef.current
      const root = rootRef.current
      if (!pageFlip || !root) return
      if (!root.isConnected) return

      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        pageFlip.flipNext()
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        pageFlip.flipPrev()
      }
    }

    window.addEventListener('resize', onResize)
    document.addEventListener('keydown', onKeydown)

    return () => {
      if (resizeTimerRef.current !== null) window.clearTimeout(resizeTimerRef.current)
      window.removeEventListener('resize', onResize)
      document.removeEventListener('keydown', onKeydown)
      destroyFlip()
    }
  }, [destroyFlip, initReader, rebuildReader])

  useEffect(() => {
    function onHide() {
      const { page, total } = lastProgressRef.current
      if (total > 0) persistFlipProgress(page, total)
    }
    window.addEventListener('pagehide', onHide)
    return () => window.removeEventListener('pagehide', onHide)
  }, [persistFlipProgress])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    root.style.setProperty('--flip-zoom', String(zoom))
  }, [zoom])

  const fontLabel = FONT_STEPS[readerSettings.fontIndex] ?? ''
  const lineLabel = LINE_STEPS[readerSettings.lineIndex] ?? ''

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
      className={`flip-book-mode book-reader${isLight ? ' is-light' : ''}`}
      data-reader-mode="flip"
      style={{ '--flip-zoom': zoom } as CSSProperties & Record<string, string | number>}
    >
      <ReaderChrome
        mode="flip"
        title={manifest.title || ''}
        author={manifest.author_name || ''}
        backHref={manifest.detail_url}
        hasPdf={hasPdf}
        hasAudio={hasAudio}
        currentPage={currentPage}
        totalPages={totalPages}
        zoom={zoom}
        darkActive={!isLight}
        fontTitle={`Shrift: ${fontLabel}`}
        lineTitle={`Satr oralig'i: ${lineLabel}`}
        navigationEnabled={!loading}
        saveStatus={saveStatus}
        onPrev={() => pageFlipRef.current?.flipPrev()}
        onNext={() => pageFlipRef.current?.flipNext()}
        onZoomOut={() => setZoom((z) => Math.max(MIN_ZOOM, z - 0.1))}
        onZoomIn={() => setZoom((z) => Math.min(MAX_ZOOM, z + 0.1))}
        onFontCycle={cycleFont}
        onLineCycle={cycleLine}
        onListen={onListenClick}
        onToggleDark={() => setIsLight((v) => !v)}
        onFullscreen={toggleFullscreen}
      />

      <div className="book-reader__stage">
        <div className={`book-reader__loading${loading ? '' : ' is-hidden'}`} aria-hidden={!loading}>
          <div className="book-reader__loading-spread">
            <span className="book-reader__loading-page" />
            <span className="book-reader__loading-page" />
          </div>
        </div>
        <div ref={mountHostRef} className="book-reader__mount-host" />
        <div className="book-reader__counter" aria-live="polite">
          {currentPage} / {totalPages} sahifa
        </div>
      </div>
    </div>
  )
}

export { MIN_ZOOM, MAX_ZOOM, RESIZE_DELAY_MS }

