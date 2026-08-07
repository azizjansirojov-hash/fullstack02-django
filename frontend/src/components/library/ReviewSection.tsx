import { useState } from 'react'
import { useBookReviews } from '../../lib/reviews/useBookReviews'
import ReviewCommentForm from './ReviewCommentForm'
import { StarsDisplay } from './reviewStars'

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('uz-UZ', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

export default function ReviewSection({ slug }: { slug: string }) {
  const {
    reviews,
    count,
    averageRating,
    loading: loadingReviews,
    loadingMore,
    hasMore,
    error: reviewError,
    myReview,
    formStatus,
    formError,
    isAuthenticated,
    ready,
    submitReview,
    removeReview,
    clearFormFeedback,
    loadMore,
  } = useBookReviews(slug)

  const [formRating, setFormRating] = useState(0)

  const effectiveRating = myReview?.rating || formRating

  async function handleDelete() {
    if (!window.confirm("Sharhingizni o'chirishni xohlaysizmi?")) return
    await removeReview()
    setFormRating(0)
    clearFormFeedback()
  }

  if (!ready || loadingReviews) {
    return (
      <section className="reviews-section" aria-label="Sharhlar">
        <p className="reviews-section__loading">Sharhlar yuklanmoqda…</p>
      </section>
    )
  }

  if (reviewError) {
    return (
      <section className="reviews-section" aria-label="Sharhlar">
        <p className="reviews-section__error">{reviewError}</p>
      </section>
    )
  }

  return (
    <section className="reviews-section" aria-labelledby="reviews-heading">
      <div className="reviews-section__inner">
        <div className="reviews-section__header">
          <h2 className="reviews-section__heading" id="reviews-heading">
            Sharhlar
          </h2>
          <div className="reviews-section__aggregate">
            {averageRating ? (
              <>
                <StarsDisplay rating={averageRating} allowHalf />
                <span className="reviews-section__avg">{averageRating.toFixed(1)}</span>
              </>
            ) : null}
            <span className="reviews-section__count">
              {count === 0
                ? "Hali sharh yo'q"
                : count === 1
                  ? '1 sharh'
                  : `${count} sharh`}
            </span>
          </div>
        </div>

        {/* Always-visible create/update form for authenticated users */}
        <ReviewCommentForm
          rating={effectiveRating}
          onRatingChange={(n) => {
            setFormRating(n)
          }}
          showStars
          initialText={myReview?.text || ''}
          formStatus={formStatus}
          formError={formError}
          isAuthenticated={isAuthenticated}
          loginHref="/login"
          onSubmit={async (text, rating) => {
            const mode = myReview ? 'update' : 'create'
            const ok = await submitReview(rating, text, mode)
            if (ok) setFormRating(rating)
            return ok
          }}
        />

        {isAuthenticated && myReview ? (
          <div className="review-own">
            <p className="review-own__label">Sizning sharhingiz:</p>
            <div className="review-card review-card--own">
              <div className="review-card__header">
                <StarsDisplay rating={myReview.rating} />
                <span className="review-card__date">{formatDate(myReview.created_at)}</span>
              </div>
              {myReview.text ? <p className="review-card__text">{myReview.text}</p> : null}
              <div className="review-own__actions">
                <button
                  type="button"
                  className="review-own__btn review-own__btn--delete"
                  onClick={handleDelete}
                  disabled={formStatus === 'saving'}
                >
                  O&apos;chirish
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {reviews.length === 0 ? (
          <p className="reviews-section__empty">
            Hali sharh yo&apos;q. Birinchi bo&apos;lib sharh qoldiring!
          </p>
        ) : (
          <>
            <ul className="reviews-list" aria-label="Barcha sharhlar">
              {reviews.map((r) => (
                <li
                  key={r.id}
                  className={`review-card${r.username === myReview?.username ? ' review-card--own' : ''}`}
                >
                  <div className="review-card__header">
                    <StarsDisplay rating={r.rating} />
                    <span className="review-card__username">{r.username}</span>
                    <span className="review-card__date">{formatDate(r.created_at)}</span>
                  </div>
                  {r.text ? <p className="review-card__text">{r.text}</p> : null}
                </li>
              ))}
            </ul>
            {hasMore ? (
              <button
                type="button"
                className="reviews-section__load-more"
                onClick={() => void loadMore()}
                disabled={loadingMore}
              >
                {loadingMore ? 'Yuklanmoqda…' : 'Yana yuklash'}
              </button>
            ) : null}
          </>
        )}
      </div>
    </section>
  )
}

