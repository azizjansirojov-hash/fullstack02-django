import { useState, type MouseEvent } from 'react'
import { Link } from 'react-router'
import { saveReadingProgress } from '../../api/library'
import { useBookReviews } from '../../lib/reviews/useBookReviews'
import { buildReadHref } from '../../lib/readerOrigin'
import {
  readerPageKey,
  readerPageKeyLegacy,
  storageRemove,
} from '../../lib/storageKeys'
import type { ProgressCard, ProgressCardProgress } from '../../types/library'
import ReviewCommentForm from './ReviewCommentForm'
import { InteractiveStarRating, StarsDisplay } from './reviewStars'

const MODE_LABELS: Record<string, string> = {
  flip: 'Varaq',
  pdf: 'PDF',
  listen: 'Tinglash',
}

const STATUS_LABELS: Record<string, string> = {
  saving: 'Saqlanmoqda…',
  saved: 'Saqlandi ✓',
  error: 'Xatolik ✗',
}

function formatProgressMeta(progress: ProgressCardProgress | null | undefined) {
  if (!progress) return 'Jarayon'
  const modeLabel = MODE_LABELS[progress.mode] || progress.mode || ''
  if (progress.mode === 'listen') {
    const parts = [modeLabel]
    if (progress.chapter_id != null) parts.unshift(`Bob ${progress.chapter_id}`)
    return parts.filter(Boolean).join(' · ')
  }
  const displayPage = Math.max(0, Number(progress.page) || 0) + 1
  return modeLabel ? `Sahifa ${displayPage} · ${modeLabel}` : `Sahifa ${displayPage}`
}

function progressPercent(progress: ProgressCardProgress | null | undefined) {
  if (!progress) return 0
  if (progress.mode === 'listen') {
    const duration = Number(progress.audio_duration_seconds)
    const position = Number(progress.position) || 0
    if (!duration || duration <= 0) return 0
    return Math.min(100, Math.max(0, (position / duration) * 100))
  }
  const total = Number(progress.total_pages)
  if (!total || total <= 0) return 0
  const page = Math.max(0, Number(progress.page) || 0)
  return Math.min(100, Math.max(0, ((page + 1) / total) * 100))
}

function truncate(text: string, max = 90) {
  const t = (text || '').trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

export type ContinueReadingCardProps = {
  book: ProgressCard | null | undefined
  /** Opens the full launch modal (mode picker). */
  onLaunch?: (book: ProgressCard) => void
  emptyHint?: string
}

/**
 * Continue-reading hero card — progress, rating, continue / listen / start-over, comments.
 */
export default function ContinueReadingCard({ book, onLaunch, emptyHint }: ContinueReadingCardProps) {
  const [confirmRestart, setConfirmRestart] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [draftRating, setDraftRating] = useState(0)

  const reviews = useBookReviews(book?.slug)
  const effectiveRating = reviews.myReview?.rating || draftRating

  if (!book) {
    return (
      <div className="dash-card continue-card--empty">
        <p className="continue-card__eyebrow">Davom ettirish</p>
        <p>{emptyHint || 'Hozircha o‘qish jarayoni yo‘q. Katalogdan kitob oching.'}</p>
      </div>
    )
  }

  const activeBook = book
  const initial = (activeBook.title || activeBook.slug || 'K').trim().charAt(0).toUpperCase()
  const meta = formatProgressMeta(activeBook.progress)
  const percent = progressPercent(activeBook.progress)
  const readUrl = activeBook.read_url || `/library/${activeBook.slug}/read/`
  const detailHref = `/library/${encodeURIComponent(activeBook.slug)}/`
  const loginNext = `/login?next=${encodeURIComponent(detailHref)}`
  const withText = reviews.reviews.filter((r) => (r.text || '').trim()).slice(0, 2)
  const hasAccess = Boolean(activeBook.has_access)
  const canListen = hasAccess && Boolean(activeBook.has_audio || activeBook.audio_url)

  function handleContinue(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    onLaunch?.(activeBook)
  }

  function handleListen(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (!canListen) return
    window.location.href = buildReadHref(readUrl, 'focus', true)
  }

  async function persistReset() {
    storageRemove(
      localStorage,
      readerPageKey(activeBook.slug),
      readerPageKeyLegacy(activeBook.slug),
    )
    await saveReadingProgress(activeBook.slug, {
      mode: 'flip',
      page: 0,
      position: 0,
      chapter_id: null,
      clear_audio: true,
      reopen: true,
      status: 'reading',
    })
  }

  async function handleStartOverConfirmed() {
    if (actionBusy) return
    setActionBusy(true)
    try {
      await persistReset()
      window.location.href = buildReadHref(readUrl, 'focus', false)
    } catch {
      setConfirmRestart(false)
    } finally {
      setActionBusy(false)
    }
  }

  return (
    <div className="dash-card continue-card-shell" data-testid="continue-reading-card">
      <div className="continue-card continue-card--static">
        <div className="continue-card__cover">
          {book.cover_url ? (
            <img src={book.cover_url} alt="" />
          ) : (
            <div className="continue-card__placeholder">{initial}</div>
          )}
        </div>
        <div className="continue-card__body">
          <div className="continue-card__top">
            <p className="continue-card__eyebrow">Davom ettirish</p>
            <div className="continue-card__rate">
              <InteractiveStarRating
                value={effectiveRating}
                busy={reviews.formStatus === 'saving'}
                requireAuth={!reviews.isAuthenticated}
                onRequireAuth={() => {
                  window.location.href = loginNext
                }}
                onChange={(rating) => {
                  setDraftRating(rating)
                  void reviews.submitRating(rating)
                }}
                aria-label="Sizning bahongiz"
              />
              {reviews.formStatus !== 'idle' && (
                <span
                  className={`continue-card__rate-status continue-card__rate-status--${reviews.formStatus}`}
                  aria-live="polite"
                >
                  {STATUS_LABELS[reviews.formStatus]}
                </span>
              )}
            </div>
          </div>
          <h2 className="continue-card__title">{book.title}</h2>
          <p className="continue-card__author">{book.author_name}</p>

          <div className="continue-card__aggregate">
            {reviews.averageRating != null ? (
              <>
                <StarsDisplay rating={reviews.averageRating} allowHalf size="sm" />
                <span className="continue-card__avg">{reviews.averageRating.toFixed(1)}</span>
              </>
            ) : (
              <StarsDisplay rating={0} size="sm" />
            )}
            <span className="continue-card__review-count">
              {reviews.count === 0
                ? "Hali sharh yo'q"
                : reviews.count === 1
                  ? '(1 sharh)'
                  : `(${reviews.count} sharh)`}
            </span>
          </div>

          <div className="continue-card__progress">
            <div
              className="continue-card__bar"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(percent)}
              aria-label="O‘qish jarayoni"
            >
              <div className="continue-card__fill" style={{ width: `${percent}%` }} />
            </div>
            <span className="continue-card__meta">{meta}</span>
          </div>

          <div className="continue-card__actions">
            <button
              type="button"
              className="continue-card__btn continue-card__btn--primary continue-card__btn--continue"
              onClick={handleContinue}
              disabled={actionBusy}
            >
              O&apos;qishni davom ettirish
            </button>
            <button
              type="button"
              className="continue-card__btn continue-card__btn--listen"
              onClick={handleListen}
              disabled={actionBusy || !canListen}
            >
              {canListen ? 'Tinglash' : 'Tinglash (yopiq)'}
            </button>
            {!confirmRestart ? (
              <button
                type="button"
                className="continue-card__btn continue-card__btn--ghost"
                onClick={(e) => {
                  e.stopPropagation()
                  setConfirmRestart(true)
                }}
                disabled={actionBusy || !hasAccess}
              >
                {hasAccess ? 'Boshidan boshlash' : 'Boshidan (yopiq)'}
              </button>
            ) : (
              <span className="continue-card__confirm" role="status">
                <span className="continue-card__confirm-text">Ishonchingiz komilmi?</span>
                <button
                  type="button"
                  className="continue-card__btn continue-card__btn--danger"
                  disabled={actionBusy}
                  onClick={(e) => {
                    e.stopPropagation()
                    void handleStartOverConfirmed()
                  }}
                >
                  Ha
                </button>
                <button
                  type="button"
                  className="continue-card__btn continue-card__btn--ghost"
                  disabled={actionBusy}
                  onClick={(e) => {
                    e.stopPropagation()
                    setConfirmRestart(false)
                  }}
                >
                  Yo‘q
                </button>
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="continue-card__comments">
        {!reviews.ready || reviews.loading ? (
          <p className="continue-card__comments-muted">Sharhlar yuklanmoqda…</p>
        ) : reviews.error ? (
          <p className="continue-card__comments-error" role="status">
            {reviews.error}
          </p>
        ) : withText.length === 0 ? (
          <p className="continue-card__comments-muted">
            Hali sharh yo&apos;q. Birinchi bo&apos;lib fikr bildiring!
          </p>
        ) : (
          <ul className="continue-card__comments-list" aria-label="So‘nggi sharhlar">
            {withText.map((r) => (
              <li key={r.id}>
                <div className="continue-card__comments-head">
                  <StarsDisplay rating={r.rating} size="sm" />
                  <span>{r.username}</span>
                </div>
                <p>{truncate(r.text)}</p>
              </li>
            ))}
          </ul>
        )}

        <ReviewCommentForm
          compact
          rating={effectiveRating}
          showStars={false}
          initialText={reviews.myReview?.text || ''}
          formStatus={reviews.formStatus}
          formError={reviews.formError}
          isAuthenticated={reviews.isAuthenticated}
          loginHref={loginNext}
          busy={reviews.formStatus === 'saving'}
          onSubmit={async (text, rating) => {
            const mode = reviews.myReview ? 'update' : 'create'
            return reviews.submitReview(rating, text, mode)
          }}
        />

        <Link className="continue-card__comments-all" to={detailHref}>
          Barchasini ko&apos;rish
        </Link>
      </div>
    </div>
  )
}
