import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  BackIcon,
  DarkIcon,
  DownloadIcon,
  FocusIcon,
  FullscreenIcon,
  ListenIcon,
  LockIcon,
  NextIcon,
  PageIcon,
  PrevIcon,
  PrintIcon,
  ShareIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from './readerIcons'
import '../../assets/css/reader-chrome.css'

/**
 * Django-parity reader chrome: header + Fokus/PDF tabs + Liquid Glass toolbar.
 */
const SAVE_STATUS_LABELS = {
  saving: 'Saqlanmoqda…',
  saved: 'Saqlandi ✓',
  error: 'Xatolik ✗',
}

type SaveStatus = 'idle' | keyof typeof SAVE_STATUS_LABELS
type ReaderChromeProps = {
  mode?: 'flip' | 'pdf'
  title?: string
  author?: string
  backHref?: string
  hasPdf?: boolean
  hasAudio?: boolean
  currentPage?: number
  totalPages?: number
  zoom?: number
  darkActive?: boolean
  fontTitle?: string
  lineTitle?: string
  saveStatus?: SaveStatus
  onPrev: () => void
  onNext: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onFontCycle?: () => void
  onLineCycle?: () => void
  onListen?: () => void
  onToggleDark?: () => void
  onFullscreen?: () => void
  onDownload?: () => void
  navigationEnabled?: boolean
}

export default function ReaderChrome({
  mode = 'flip',
  title = '',
  author = '',
  backHref,
  hasPdf = false,
  hasAudio = false,
  currentPage = 1,
  totalPages = 1,
  zoom = 1,
  darkActive = false,
  fontTitle = '',
  lineTitle = '',
  saveStatus = 'idle',
  onPrev,
  onNext,
  onZoomIn,
  onZoomOut,
  onFontCycle = undefined,
  onLineCycle = undefined,
  onListen = undefined,
  onToggleDark = undefined,
  onFullscreen = undefined,
  onDownload = undefined,
  navigationEnabled = true,
}: ReaderChromeProps) {
  const navigate = useNavigate()
  const { slug } = useParams()
  const downloadLocked = !hasPdf
  const listenDisabled = !hasAudio
  const pdfTabDisabled = !hasPdf
  const activeTab = mode === 'pdf' && hasPdf ? 'page' : 'focus'
  const pageLabel = `${totalPages} betdan ${currentPage}-bet`
  const zoomLabel = `${Math.round(zoom * 100)}%`
  const resolvedBack = backHref || `/library/${slug || ''}/`

  function goFocus() {
    if (!slug) return
    navigate(`/library/${encodeURIComponent(slug)}/read`)
  }

  function goPdf() {
    if (!slug || !hasPdf) return
    navigate(`/library/${encodeURIComponent(slug)}/read?mode=pdf`)
  }

  function handleShare() {
    const url = window.location.href
    if (navigator.share) {
      navigator.share({ title, url }).catch(() => {})
      return
    }
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(url).catch(() => {})
    }
  }

  function handleDownload() {
    if (downloadLocked) return
    if (onDownload) {
      onDownload()
      return
    }
  }

  return (
    <div className="book-reader__toolbar-shell">
      <div className="reader-chrome" data-mode={mode === 'pdf' ? 'pdf' : 'flipbook'}>
        <header className="reader-chrome__header">
          <Link className="reader-chrome__back" to={resolvedBack} aria-label="Kutubxonaga qaytish">
            <BackIcon />
            <span>Kutubxonaga qaytish</span>
          </Link>
          <div className="reader-chrome__meta">
            <h1 className="reader-chrome__title">{title}</h1>
            {author ? <p className="reader-chrome__author">{author}</p> : null}
          </div>
          <div className="reader-chrome__header-spacer" aria-hidden="true" />
        </header>

        <div className="reader-chrome__panel">
          <div className="reader-toolbar__row reader-toolbar__row--top">
            <div className="reader-toolbar__tabs" role="tablist" aria-label="O'qish rejimi">
              <button
                type="button"
                className={`reader-toolbar__tab${activeTab === 'focus' ? ' is-active' : ''}`}
                role="tab"
                aria-label="Real Book rejimi"
                aria-selected={activeTab === 'focus'}
                onClick={goFocus}
              >
                <FocusIcon />
                <span>Fokus</span>
              </button>
              <button
                type="button"
                className={`reader-toolbar__tab${activeTab === 'page' ? ' is-active' : ''}`}
                role="tab"
                aria-label="PDF rejimi"
                aria-selected={activeTab === 'page'}
                disabled={pdfTabDisabled}
                aria-disabled={pdfTabDisabled}
                onClick={goPdf}
              >
                <PageIcon />
                <span>PDF</span>
              </button>
            </div>

            <div className="reader-toolbar__top-end">
              {onFontCycle ? (
                <button
                  type="button"
                  className="reader-toolbar__icon-btn reader-toolbar__icon-btn--text"
                  aria-label="Shrift sozlamalari"
                  title={fontTitle || 'Shrift sozlamalari'}
                  onClick={onFontCycle}
                >
                  <span aria-hidden="true">Aa</span>
                </button>
              ) : null}
              {onLineCycle ? (
                <button
                  type="button"
                  className="reader-toolbar__icon-btn reader-toolbar__icon-btn--text"
                  aria-label="Satr oralig'i"
                  title={lineTitle || "Satr oralig'i"}
                  onClick={onLineCycle}
                >
                  <span aria-hidden="true">Tt</span>
                </button>
              ) : null}
              <button
                type="button"
                className="reader-toolbar__listen"
                aria-label="Tinglash"
                disabled={listenDisabled}
                aria-disabled={listenDisabled}
                onClick={onListen}
              >
                <ListenIcon />
                <span>Tinglash</span>
              </button>
            </div>
          </div>

          <div className="reader-toolbar__row reader-toolbar__row--bottom">
            <div className="reader-toolbar__group reader-toolbar__group--pages">
              <button
                type="button"
                className="reader-toolbar__icon-btn"
                data-action="prev"
                aria-label="Oldingi sahifa"
                disabled={!navigationEnabled || currentPage <= 1}
                onClick={onPrev}
              >
                <PrevIcon />
              </button>
              <span className="reader-toolbar__page-label" aria-live="polite">
                {pageLabel}
              </span>
              {saveStatus !== 'idle' ? (
                <span
                  className={`reader-chrome__save-status reader-chrome__save-status--${saveStatus}`}
                  aria-live="polite"
                >
                  {SAVE_STATUS_LABELS[saveStatus]}
                </span>
              ) : null}
              <button
                type="button"
                className="reader-toolbar__icon-btn"
                data-action="next"
                aria-label="Keyingi sahifa"
                disabled={!navigationEnabled || currentPage >= totalPages}
                onClick={onNext}
              >
                <NextIcon />
              </button>
            </div>

            <span className="reader-toolbar__divider" aria-hidden="true" />

            <div className="reader-toolbar__group reader-toolbar__group--zoom">
              <button
                type="button"
                className="reader-toolbar__icon-btn"
                aria-label="Kichiklashtirish"
                onClick={onZoomOut}
              >
                <ZoomOutIcon />
              </button>
              <span className="reader-toolbar__zoom">{zoomLabel}</span>
              <button
                type="button"
                className="reader-toolbar__icon-btn"
                aria-label="Kattalashtirish"
                onClick={onZoomIn}
              >
                <ZoomInIcon />
              </button>
            </div>

            <span className="reader-toolbar__divider" aria-hidden="true" />

            <div className="reader-toolbar__group reader-toolbar__group--tools">
              <button
                type="button"
                className={`reader-toolbar__icon-btn${darkActive ? ' is-active' : ''}`}
                aria-label="Tungi rejim"
                aria-pressed={darkActive}
                onClick={onToggleDark}
              >
                <DarkIcon />
              </button>
              <button
                type="button"
                className="reader-toolbar__icon-btn"
                aria-label="To'liq ekran"
                onClick={onFullscreen}
              >
                <FullscreenIcon />
              </button>
            </div>

            <span className="reader-toolbar__divider" aria-hidden="true" />

            <div className="reader-toolbar__group reader-toolbar__group--actions">
              <button
                type="button"
                className="reader-toolbar__action"
                aria-label="Chop etish"
                onClick={() => window.print()}
              >
                <PrintIcon />
                <span>Chop etish</span>
              </button>
              <button
                type="button"
                className={`reader-toolbar__action reader-toolbar__action--primary${downloadLocked ? ' is-locked' : ''}`}
                aria-label="Yuklab olish"
                aria-disabled={downloadLocked}
                disabled={downloadLocked}
                onClick={handleDownload}
              >
                {downloadLocked ? <LockIcon /> : <DownloadIcon />}
                <span>Yuklab olish</span>
              </button>
              <button
                type="button"
                className="reader-toolbar__action"
                aria-label="Ulashish"
                onClick={handleShare}
              >
                <ShareIcon />
                <span>Ulashish</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

