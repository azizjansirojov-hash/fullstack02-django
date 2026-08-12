import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import type { ReviewFormStatus } from '../../lib/reviews/useBookReviews'
import { InteractiveStarRating } from './reviewStars'

const STATUS_LABELS: Record<string, string> = {
  saving: 'Saqlanmoqda…',
  saved: 'Saqlandi ✓',
  error: 'Xatolik ✗',
}

const MAX_TEXT = 2000

export type ReviewCommentFormProps = {
  /** Current / selected rating (1–5). Required by the Review model. */
  rating: number
  onRatingChange?: (rating: number) => void
  /** When false, stars are assumed to live elsewhere (e.g. continue-card top-right). */
  showStars?: boolean
  initialText?: string
  formStatus: ReviewFormStatus
  formError: string | null
  isAuthenticated: boolean
  loginHref?: string
  busy?: boolean
  compact?: boolean
  onSubmit: (text: string, rating: number) => Promise<boolean> | boolean
  /** Called after a successful submit so parents can clear local draft state. */
  onSubmitted?: () => void
}

/**
 * Shared comment textarea + submit used on detail page, continue card, and modal.
 * Rating is required by the backend Review model — text-only submit is rejected with
 * an inline error asking the user to pick stars first (or use the adjacent star widget).
 */
export default function ReviewCommentForm({
  rating,
  onRatingChange,
  showStars = true,
  initialText = '',
  formStatus,
  formError,
  isAuthenticated,
  loginHref = '/login',
  busy = false,
  compact = false,
  onSubmit,
  onSubmitted,
}: ReviewCommentFormProps) {
  const [text, setText] = useState(initialText)
  const [localError, setLocalError] = useState<string | null>(null)

  useEffect(() => {
    setText(initialText)
  }, [initialText])

  if (!isAuthenticated) {
    return (
      <p className="review-comment-form__login">
        <Link to={loginHref}>Sharh yozish uchun kiring</Link>
      </p>
    )
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLocalError(null)
    if (!rating) {
      setLocalError('Iltimos, avval yulduz baholashni tanlang.')
      return
    }
    const ok = await onSubmit(text.trim(), rating)
    if (ok) {
      onSubmitted?.()
      if (!initialText) setText('')
    }
  }

  const remaining = MAX_TEXT - text.length
  const nearLimit = remaining <= 100
  const errorMsg = localError || formError

  return (
    <form
      className={`review-comment-form${compact ? ' review-comment-form--compact' : ''}`}
      onSubmit={(e) => void handleSubmit(e)}
      aria-label="Sharh yozish"
    >
      {showStars && onRatingChange ? (
        <div className="review-comment-form__stars">
          <p className="review-comment-form__label">Sizning bahongiz:</p>
          <InteractiveStarRating
            value={rating}
            onChange={onRatingChange}
            busy={busy || formStatus === 'saving'}
            aria-label="Sizning bahongiz"
          />
        </div>
      ) : null}

      <label className="review-comment-form__label" htmlFor="review-comment-text">
        Sharhingiz
      </label>
      <textarea
        id="review-comment-text"
        className="review-comment-form__textarea"
        placeholder="Fikringizni yozing…"
        maxLength={MAX_TEXT}
        rows={compact ? 2 : 3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={busy || formStatus === 'saving'}
      />
      <div className="review-comment-form__meta">
        <span
          className={`review-comment-form__counter${nearLimit ? ' is-warn' : ''}`}
          aria-live="polite"
        >
          {text.length}/{MAX_TEXT}
        </span>
        {errorMsg ? (
          <p className="review-comment-form__error" role="status">
            {errorMsg}
          </p>
        ) : null}
      </div>
      <div className="review-comment-form__actions">
        <button
          type="submit"
          className="review-comment-form__submit"
          disabled={busy || formStatus === 'saving'}
        >
          Yuborish
        </button>
        {formStatus !== 'idle' && (
          <span
            className={`review-comment-form__status review-comment-form__status--${formStatus}`}
            aria-live="polite"
          >
            {STATUS_LABELS[formStatus]}
          </span>
        )}
      </div>
    </form>
  )
}
