import { useEffect, useRef, useState } from 'react'
import {
  fetchBookDetail,
  getReadingProgress,
  saveReadingProgress,
  setReadingStatus,
} from '../../api/library'
import { buildDjangoReadHref } from '../../lib/readerOrigin'

function formatDuration(seconds) {
  if (!seconds || !Number.isFinite(seconds)) return ''
  const total = Math.round(seconds)
  const hours = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hours > 0) return `${hours} soat ${mins} daqiqa`
  if (mins > 0) return `${mins} daqiqa`
  return `${secs} soniya`
}

function getSavedPageIndex(slug) {
  try {
    const raw = localStorage.getItem(`luma-reader:${slug}:page`)
    const idx = parseInt(raw || '0', 10)
    return Number.isNaN(idx) ? 0 : Math.max(0, idx)
  } catch {
    return 0
  }
}

function getFormats(pdfUrl, audioUrl) {
  const formats = ['Matn']
  if (pdfUrl) formats.push('PDF')
  if (audioUrl) formats.push('Audio')
  return formats.join(' · ')
}

function mediaReady(status, hasFile) {
  const s = status || 'pending'
  if (s === 'ready' || s === 'legacy') return true
  if (hasFile && (s === 'pending' || !status)) return true
  return Boolean(hasFile && s === 'ready')
}

function mediaPreparing(status) {
  const s = status || 'pending'
  return s === 'pending' || s === 'generating'
}

function mediaFailed(status) {
  return (status || '') === 'failed'
}

/**
 * Reader launch modal — Continue / Listen / Start over / PDF / reading modes.
 * Continue navigates to the Django HTML reader until React reader exists.
 */
export default function ReaderLaunchModal({ book, open, onClose, onStatusChange }) {
  const dialogRef = useRef(null)
  const [audioDurationSec, setAudioDurationSec] = useState(null)
  const [audioDurationFailed, setAudioDurationFailed] = useState(false)
  const [liveBook, setLiveBook] = useState(book)
  const [pageIndex, setPageIndex] = useState(0)
  const [totalPages, setTotalPages] = useState(null)
  const [readingStatus, setReadingStatusState] = useState(null)
  const [finishBusy, setFinishBusy] = useState(false)

  useEffect(() => {
    setLiveBook(book)
  }, [book])

  const slug = liveBook?.slug || book?.slug || ''

  useEffect(() => {
    if (!open || !slug) return undefined
    let cancelled = false

    async function loadProgress() {
      const local = getSavedPageIndex(slug)
      try {
        const { response, data } = await getReadingProgress(slug)
        if (cancelled) return
        if (response.ok && data?.exists) {
          const serverPage = Math.max(0, Number(data.page) || 0)
          setPageIndex(serverPage)
          setTotalPages(data.total_pages != null ? Number(data.total_pages) : null)
          setReadingStatusState(data.status || null)
          try {
            localStorage.setItem(`luma-reader:${slug}:page`, String(serverPage))
          } catch {
            /* ignore */
          }
          return
        }
        setTotalPages(null)
        setReadingStatusState(null)
      } catch {
        /* fall through to local */
      }
      if (!cancelled) setPageIndex(local)
    }

    loadProgress()
    return () => {
      cancelled = true
    }
  }, [open, slug])

  useEffect(() => {
    if (!open || !slug) return undefined
    let cancelled = false

    async function refresh() {
      try {
        const { response, data } = await fetchBookDetail(slug)
        if (cancelled || !response.ok) return
        setLiveBook(data)
        return data
      } catch {
        return null
      }
    }

    function stillPreparing(data) {
      if (!data) return true
      const pdf = data.pdf_generation_status || 'pending'
      const audio = data.audio_generation_status || 'pending'
      return (
        pdf === 'pending' ||
        pdf === 'generating' ||
        audio === 'pending' ||
        audio === 'generating'
      )
    }

    refresh()
    const id = window.setInterval(async () => {
      const data = await refresh()
      if (data && !stillPreparing(data)) {
        window.clearInterval(id)
      }
    }, 4000)

    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [open, slug])

  useEffect(() => {
    if (!open) return undefined
    document.body.classList.add('has-launch-modal')
    dialogRef.current?.querySelector('#launch-read')?.focus()
    return () => {
      document.body.classList.remove('has-launch-modal')
    }
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    function onKey(event) {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const pdfUrl = liveBook?.pdf_url || ''
  const audioUrl = liveBook?.audio_url || ''
  const pdfReady = mediaReady(liveBook?.pdf_generation_status, liveBook?.has_pdf || Boolean(pdfUrl))
  const audioReady = mediaReady(
    liveBook?.audio_generation_status,
    liveBook?.has_audio || Boolean(audioUrl),
  )
  const pdfPreparing = !pdfReady && mediaPreparing(liveBook?.pdf_generation_status)
  const audioPreparing = !audioReady && mediaPreparing(liveBook?.audio_generation_status)
  const pdfFailed = mediaFailed(liveBook?.pdf_generation_status)
  const audioFailed = mediaFailed(liveBook?.audio_generation_status)

  useEffect(() => {
    if (!open || !audioReady) {
      setAudioDurationSec(null)
      setAudioDurationFailed(false)
      return undefined
    }
    const fromApi = Number(liveBook?.audio_duration_seconds)
    if (Number.isFinite(fromApi) && fromApi > 0) {
      setAudioDurationSec(fromApi)
      setAudioDurationFailed(false)
      return undefined
    }
    if (!audioUrl) {
      setAudioDurationSec(null)
      setAudioDurationFailed(true)
      return undefined
    }
    setAudioDurationSec(null)
    setAudioDurationFailed(false)
    const probe = new Audio()
    probe.preload = 'metadata'
    let settled = false
    const finishOk = (seconds) => {
      if (settled) return
      settled = true
      setAudioDurationSec(seconds)
      setAudioDurationFailed(false)
    }
    const finishFail = () => {
      if (settled) return
      settled = true
      setAudioDurationFailed(true)
    }
    const onMeta = () => {
      if (probe.duration && Number.isFinite(probe.duration)) {
        finishOk(probe.duration)
      } else {
        finishFail()
      }
    }
    const onErr = () => finishFail()
    probe.addEventListener('loadedmetadata', onMeta)
    probe.addEventListener('error', onErr)
    probe.src = audioUrl
    const timeoutId = window.setTimeout(finishFail, 4000)
    return () => {
      window.clearTimeout(timeoutId)
      probe.removeEventListener('loadedmetadata', onMeta)
      probe.removeEventListener('error', onErr)
      probe.src = ''
    }
  }, [open, audioUrl, audioReady, liveBook?.audio_duration_seconds])

  if (!open || !liveBook) return null

  const readUrl = liveBook.read_url || (slug ? `/library/${slug}/read/` : '')
  const title = liveBook.title || 'Kitob'
  const author = liveBook.author_name || ''
  const summary = liveBook.summary || ''
  const coverUrl = liveBook.cover_url || ''
  const year = liveBook.published_year || ''
  const category = liveBook.category_label || ''

  const hasAccess = Boolean(liveBook?.has_access)
  const progressStarted = pageIndex > 0
  const byline = author
    ? `muallif ${author}${summary ? ` · ${summary}` : ''}`
    : summary || ''
  const listenLabel = !hasAccess
    ? 'Xarid kerak'
    : audioReady && (audioUrl || liveBook?.audio_duration_seconds)
      ? audioDurationSec
        ? formatDuration(audioDurationSec)
        : audioDurationFailed
          ? 'Noma’lum'
          : 'Yuklanmoqda…'
      : null

  async function persistProgressReset() {
    try {
      localStorage.removeItem(`luma-reader:${slug}:page`)
    } catch {
      /* ignore */
    }
    setPageIndex(0)
    try {
      await saveReadingProgress(slug, {
        mode: 'flip',
        page: 0,
        position: 0,
        reopen: true,
        status: 'reading',
      })
      setReadingStatusState('reading')
      onStatusChange?.()
    } catch {
      /* server may be unreachable; local reset still applies */
    }
  }

  async function ensureReadingStatus() {
    if (readingStatus === 'finished' || readingStatus === 'planned') {
      try {
        await saveReadingProgress(slug, {
          mode: 'flip',
          page: pageIndex,
          position: 0,
          reopen: true,
          status: 'reading',
        })
        setReadingStatusState('reading')
        onStatusChange?.()
      } catch {
        /* continue navigation even if status update fails */
      }
    }
  }

  async function handleMarkFinished() {
    if (finishBusy || !slug) return
    setFinishBusy(true)
    try {
      const { response } = await setReadingStatus(slug, 'finished')
      if (response.ok) {
        setReadingStatusState('finished')
        onStatusChange?.()
      }
    } finally {
      setFinishBusy(false)
    }
  }

  function navigateRead(mode, autoplay, resetProgress) {
    if (!hasAccess) return
    if (mode === 'page' && !pdfReady) return
    if (autoplay && !audioReady) return
    const go = async () => {
      if (resetProgress) {
        await persistProgressReset()
      } else {
        await ensureReadingStatus()
      }
      try {
        localStorage.setItem(`luma-reader:${slug}:mode`, mode === 'page' ? 'pdf' : 'flip')
      } catch {
        /* ignore */
      }
      window.location.href = buildDjangoReadHref(readUrl, mode, autoplay)
    }
    go()
  }

  const nearEnd =
    totalPages != null &&
    totalPages > 0 &&
    pageIndex >= totalPages - 1 &&
    readingStatus !== 'finished'

  const initial = title.trim().charAt(0).toUpperCase() || 'K'
  const readDisabled = !hasAccess
  const pdfActionsDisabled = !hasAccess || !pdfReady
  const listenDisabled = !hasAccess || !audioReady || !audioUrl

  return (
    <div className="reader-launch-modal" id="reader-launch-modal">
      <div className="reader-launch-modal__backdrop" onClick={onClose} data-launch-close />
      <section
        className="reader-launch-modal__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="launch-title"
        ref={dialogRef}
      >
        <header className="reader-launch-modal__header">
          <button
            type="button"
            className="reader-launch-modal__back"
            onClick={onClose}
            aria-label="Kutubxonaga qaytish"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
            </svg>
            <span>Kutubxonaga qaytish</span>
          </button>
        </header>

        <div className="reader-launch-modal__hero">
          <div className="reader-launch-modal__cover" id="launch-cover">
            {coverUrl ? (
              <img src={coverUrl} alt="" loading="lazy" />
            ) : (
              <div className="reader-launch-modal__placeholder">{initial}</div>
            )}
          </div>
          <div className="reader-launch-modal__intro">
            <p className="reader-launch-modal__eyebrow">✦ KITOBLAR KUTUBXONASI</p>
            <h2 className="reader-launch-modal__title" id="launch-title">
              {title}
            </h2>
            <p className="reader-launch-modal__byline" id="launch-byline">
              {byline}
            </p>
            {(pdfPreparing || audioPreparing || pdfFailed || audioFailed || !hasAccess) && (
              <p className="reader-launch-modal__status" role="status">
                {!hasAccess
                  ? 'Bu kitob pullik — o‘qish/tinglash/PDF uchun xarid talab qilinadi. '
                  : ''}
                {hasAccess && pdfPreparing ? 'PDF tayyorlanmoqda… ' : ''}
                {hasAccess && audioPreparing ? 'Audio tayyorlanmoqda… ' : ''}
                {hasAccess && pdfFailed ? 'PDF yaratilmadi. Keyinroq urinib ko‘ring. ' : ''}
                {hasAccess && audioFailed ? 'Audio yaratilmadi. Keyinroq urinib ko‘ring.' : ''}
              </p>
            )}
            <div className="reader-launch-modal__meta" id="launch-meta">
              {category ? (
                <span className="reader-launch-modal__pill">{category}</span>
              ) : null}
              {year ? <span className="reader-launch-modal__pill">{year}</span> : null}
              {pdfReady ? <span className="reader-launch-modal__pill">PDF</span> : null}
              {audioReady ? <span className="reader-launch-modal__pill">Audio</span> : null}
            </div>
            <div className="reader-launch-modal__progress">
              <div className="reader-launch-modal__progress-labels">
                <span id="launch-progress-text">
                  {progressStarted ? 'O‘qish jarayoni saqlangan' : 'Hali boshlanmagan'}
                </span>
                <span id="launch-page-text">
                  {progressStarted ? `${pageIndex + 1}-sahifadan davom etasiz` : ''}
                </span>
              </div>
              <div className="reader-launch-modal__progress-track">
                <span
                  className={`reader-launch-modal__progress-bar${progressStarted ? ' is-indeterminate' : ''}`}
                  id="launch-progress-bar"
                  style={progressStarted ? undefined : { width: '0%' }}
                />
              </div>
            </div>
            <div className="reader-launch-modal__cta-row">
              <a
                href={readDisabled ? undefined : buildDjangoReadHref(readUrl, 'focus', false)}
                className="reader-launch-modal__btn reader-launch-modal__btn--primary"
                id="launch-read"
                aria-disabled={readDisabled}
                onClick={(event) => {
                  event.preventDefault()
                  if (readDisabled) return
                  navigateRead('focus', false, false)
                }}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z" />
                </svg>
                <span>{hasAccess ? 'O‘qishni davom ettirish' : 'Sotib olish kerak'}</span>
                <span aria-hidden="true">→</span>
              </a>
              <button
                type="button"
                className="reader-launch-modal__btn reader-launch-modal__btn--listen"
                id="launch-listen"
                disabled={listenDisabled}
                aria-disabled={listenDisabled}
                onClick={() => {
                  if (listenDisabled) return
                  navigateRead('focus', true, false)
                }}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 1a9 9 0 0 0-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7a9 9 0 0 0-9-9z" />
                </svg>
                <span>
                  {!hasAccess
                    ? 'Sotib olish kerak'
                    : audioPreparing
                      ? 'Audio tayyorlanmoqda…'
                      : audioFailed
                        ? 'Audio yo‘q'
                        : 'Tinglash'}
                </span>
              </button>
              <button
                type="button"
                className="reader-launch-modal__btn reader-launch-modal__btn--ghost"
                id="launch-start-over"
                disabled={!hasAccess}
                onClick={() => navigateRead('focus', false, true)}
              >
                {hasAccess ? 'Boshidan boshlash' : 'Boshidan (yopiq)'}
              </button>
            </div>
            {nearEnd ? (
              <div className="reader-launch-modal__finish-prompt" role="status">
                <p>Oxirgi sahifadasiz. Kitobni tugatilgan deb belgilaysizmi?</p>
                <button
                  type="button"
                  className="reader-launch-modal__btn reader-launch-modal__btn--primary"
                  disabled={finishBusy}
                  onClick={handleMarkFinished}
                >
                  Tugatdim
                </button>
              </div>
            ) : null}
            {readingStatus === 'finished' ? (
              <p className="reader-launch-modal__finished-note">Bu kitob tugatilgan deb belgilangan.</p>
            ) : null}
            <a
              href={hasAccess && pdfReady && pdfUrl ? pdfUrl : '#'}
              className={`reader-launch-modal__download${hasAccess && pdfReady && pdfUrl ? '' : ' is-disabled'}`}
              id="launch-download"
              aria-disabled={pdfActionsDisabled || !pdfUrl}
              onClick={(event) => {
                if (pdfActionsDisabled || !pdfUrl) event.preventDefault()
              }}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2z" />
              </svg>
              <span>
                {!hasAccess
                  ? 'PDF (xarid kerak)'
                  : pdfPreparing
                    ? 'PDF tayyorlanmoqda…'
                    : pdfFailed
                      ? 'PDF yaratilmadi'
                      : 'PDF yuklab olish'}
              </span>
            </a>
          </div>
        </div>

        <div className="reader-launch-modal__panels">
          <section className="reader-launch-modal__panel" aria-labelledby="launch-methods-title">
            <h3 className="reader-launch-modal__panel-title" id="launch-methods-title">
              O‘QISH USULLARI
            </h3>
            <div className="reader-launch-modal__methods">
              <button
                type="button"
                className="reader-launch-modal__method"
                data-launch-choice="focus"
                onClick={() => navigateRead('focus', false, false)}
              >
                <span className="reader-launch-modal__method-icon" aria-hidden="true">
                  🪶
                </span>
                <span className="reader-launch-modal__method-name">Fokus rejimi</span>
                <span className="reader-launch-modal__method-desc">
                  Moslashuvchan matn formati — shrift va mavzuni tanlang.
                </span>
              </button>
              <button
                type="button"
                className="reader-launch-modal__method"
                data-launch-choice="page"
                disabled={pdfActionsDisabled}
                onClick={() => navigateRead('page', false, false)}
              >
                <span className="reader-launch-modal__method-icon" aria-hidden="true">
                  📄
                </span>
                <span className="reader-launch-modal__method-name">Sahifa rejimi</span>
                <span className="reader-launch-modal__method-desc">
                  {pdfPreparing
                    ? 'PDF tayyorlanmoqda…'
                    : pdfFailed
                      ? 'PDF mavjud emas.'
                      : 'Asl PDF tartibi — diagrammalar uchun ideal.'}
                </span>
              </button>
              <button
                type="button"
                className="reader-launch-modal__method"
                data-launch-choice="audio"
                disabled={listenDisabled}
                onClick={() => navigateRead('focus', true, false)}
              >
                <span className="reader-launch-modal__method-icon" aria-hidden="true">
                  🎧
                </span>
                <span className="reader-launch-modal__method-name">Avto-o‘qish</span>
                <span className="reader-launch-modal__method-desc">
                  {audioPreparing
                    ? 'Audio tayyorlanmoqda…'
                    : audioFailed
                      ? 'Audio mavjud emas.'
                      : 'Tabiiy ovoz — matn bilan sinxronlashtirilgan.'}
                </span>
              </button>
            </div>
          </section>
          <section
            className="reader-launch-modal__panel reader-launch-modal__panel--about"
            aria-labelledby="launch-about-title"
          >
            <h3 className="reader-launch-modal__panel-title" id="launch-about-title">
              KITOB HAQIDA
            </h3>
            <dl className="reader-launch-modal__facts" id="launch-facts">
              {author ? (
                <div>
                  <dt>Muallif</dt>
                  <dd>{author}</dd>
                </div>
              ) : null}
              {category ? (
                <div>
                  <dt>Kategoriya</dt>
                  <dd>{category}</dd>
                </div>
              ) : null}
              {year ? (
                <div>
                  <dt>Nashr yili</dt>
                  <dd>{year}</dd>
                </div>
              ) : null}
              <div>
                <dt>Til</dt>
                <dd>O‘zbek tili</dd>
              </div>
              <div>
                <dt>Format</dt>
                <dd>{getFormats(pdfReady ? pdfUrl : '', audioReady ? audioUrl : '')}</dd>
              </div>
              {audioReady && audioUrl ? (
                <div>
                  <dt>Tinglash vaqti</dt>
                  <dd>{listenLabel}</dd>
                </div>
              ) : null}
            </dl>
          </section>
        </div>
      </section>
    </div>
  )
}
