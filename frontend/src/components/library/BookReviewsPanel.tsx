import { useState } from 'react'
import { Link } from 'react-router'
import { useBookReviews } from '../../lib/reviews/useBookReviews'
import ReviewCommentForm from './ReviewCommentForm'
import { InteractiveStarRating, StarsDisplay } from './reviewStars'

const STATUS_LABELS: Record<string, string> = {
  saving: 'Saqlanmoqda…',
  saved: 'Saqlandi ✓',
  error: 'Xatolik ✗',
}

function truncate(text: string, max = 90) {
  const t = (text || '').trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

export type BookReviewsPanelProps = {
  slug: string
  variant?: 'card' | 'modal'
  maxComments?: number
}

/**
 * Compact ratings + comment form + recent comments for launch modal.
 */
export default function BookReviewsPanel({
  slug,
  variant = 'card',
  maxComments = 3,
}: BookReviewsPanelProps) {
  const {
    reviews,
    count,
    averageRating,
    loading,
    error,
    myReview,
    formStatus,
    formError,
    isAuthenticated,
    ready,
    submitRating,
    submitReview,
  } = useBookReviews(slug)

  const [draftRating, setDraftRating] = useState(0)
  const effectiveRating = myReview?.rating || draftRating

  const detailHref = `/library/${encodeURIComponent(slug)}/`
  const withText = reviews.filter((r) => (r.text || '').trim()).slice(0, maxComments)
  const loginNext = `/login?next=${encodeURIComponent(detailHref)}`

  if (!ready || loading) {
    return (
      <div className={`book-reviews-panel book-reviews-panel--${variant}`} aria-busy="true">
        <p className="book-reviews-panel__muted">Sharhlar yuklanmoqda…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`book-reviews-panel book-reviews-panel--${variant}`}>
        <p className="book-reviews-panel__error" role="status">
          {error}
        </p>
      </div>
    )
  }

  return (
    <div className={`book-reviews-panel book-reviews-panel--${variant}`}>
      <div className="book-reviews-panel__rating-row">
        <div className="book-reviews-panel__aggregate" title="O‘rtacha baho">
          {averageRating != null ? (
            <>
              <StarsDisplay rating={averageRating} allowHalf size="sm" />
              <span className="book-reviews-panel__avg">{averageRating.toFixed(1)}</span>
            </>
          ) : (
            <StarsDisplay rating={0} size="sm" />
          )}
          <span className="book-reviews-panel__count">
            {count === 0
              ? "Hali sharh yo'q"
              : count === 1
                ? '(1 sharh)'
                : `(${count} sharh)`}
          </span>
        </div>

        <div className="book-reviews-panel__mine">
          <InteractiveStarRating
            value={effectiveRating}
            busy={formStatus === 'saving'}
            requireAuth={!isAuthenticated}
            onRequireAuth={() => {
              window.location.href = loginNext
            }}
            onChange={(rating) => {
              setDraftRating(rating)
              void submitRating(rating)
            }}
            aria-label="Sizning bahongiz"
          />
          {formStatus !== 'idle' && (
            <span
              className={`book-reviews-panel__status book-reviews-panel__status--${formStatus}`}
              aria-live="polite"
            >
              {STATUS_LABELS[formStatus]}
            </span>
          )}
          {formError && formStatus === 'error' ? (
            <span className="book-reviews-panel__status book-reviews-panel__status--error" aria-live="polite">
              {formError}
            </span>
          ) : null}
          {!isAuthenticated ? (
            <Link className="book-reviews-panel__login" to={loginNext}>
              Baholash uchun kiring
            </Link>
          ) : null}
        </div>
      </div>

      <div className="book-reviews-panel__comments">
        {withText.length === 0 ? (
          <p className="book-reviews-panel__empty">
            Hali sharh yo&apos;q. Birinchi bo&apos;lib fikr bildiring!
          </p>
        ) : (
          <ul className="book-reviews-panel__list" aria-label="So‘nggi sharhlar">
            {withText.map((r) => (
              <li key={r.id} className="book-reviews-panel__item">
                <div className="book-reviews-panel__item-head">
                  <StarsDisplay rating={r.rating} size="sm" />
                  <span className="book-reviews-panel__user">{r.username}</span>
                </div>
                <p className="book-reviews-panel__text">{truncate(r.text)}</p>
              </li>
            ))}
          </ul>
        )}

        <ReviewCommentForm
          compact
          rating={effectiveRating}
          showStars={false}
          initialText={myReview?.text || ''}
          formStatus={formStatus}
          formError={formError}
          isAuthenticated={isAuthenticated}
          loginHref={loginNext}
          onSubmit={async (text, rating) => {
            const mode = myReview ? 'update' : 'create'
            return submitReview(rating, text, mode)
          }}
        />

        <Link className="book-reviews-panel__all" to={detailHref}>
          Barchasini ko&apos;rish
        </Link>
      </div>
    </div>
  )
}
