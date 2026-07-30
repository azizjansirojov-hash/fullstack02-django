import { useRef } from 'react'
import type { LibraryBookActions } from './BookCard'
import type { LibraryBookView } from '../../types/library'

export type NewBooksCarouselProps = {
  books?: LibraryBookView[]
  canRead: boolean
  onLaunch?: (book: LibraryBookView) => void
  libraryActions?: LibraryBookActions | null
}

/**
 * Horizontal “Yangi kitoblar” carousel with arrow controls.
 */
export default function NewBooksCarousel({
  books = [],
  canRead,
  onLaunch,
  libraryActions = null,
}: NewBooksCarouselProps) {
  const viewportRef = useRef<HTMLUListElement>(null)

  function scrollBy(dir: number) {
    const el = viewportRef.current
    if (!el) return
    el.scrollBy({ left: dir * 200, behavior: 'smooth' })
  }

  if (!books.length) {
    return <p className="dash-empty">Hozircha yangi kitoblar yo‘q.</p>
  }

  return (
    <div className="books-carousel dash-card">
      <div className="dash-section__head">
        <h2 className="dash-section__title">Yangi kitoblar</h2>
        <div className="books-carousel__nav">
          <button type="button" className="books-carousel__btn" aria-label="Chapga" onClick={() => scrollBy(-1)}>
            ‹
          </button>
          <button type="button" className="books-carousel__btn" aria-label="O‘ngga" onClick={() => scrollBy(1)}>
            ›
          </button>
        </div>
      </div>
      <ul className="books-carousel__viewport" ref={viewportRef}>
        {books.map((book) => {
          const initial = (book.title || book.slug || 'K').trim().charAt(0).toUpperCase()
          const status = book.reading_status || null
          const showPlan =
            libraryActions?.showPlan && status !== 'reading' && status !== 'finished'
          return (
            <li key={book.slug} className="books-carousel__item">
              <div className="carousel-book-shell">
                {showPlan ? (
                  <button
                    type="button"
                    className={`shelf-card__action carousel-book__plan${status === 'planned' ? ' is-active' : ''}`}
                    title={status === 'planned' ? 'Rejadan olib tashlash' : 'Rejaga qo‘shish'}
                    aria-label={status === 'planned' ? 'Rejadan olib tashlash' : 'Rejaga qo‘shish'}
                    onClick={(e) => {
                      e.stopPropagation()
                      libraryActions?.onPlanToggle?.(book, status === 'planned')
                    }}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">
                      {status === 'planned' ? (
                        <path
                          fill="currentColor"
                          d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"
                        />
                      ) : (
                        <path
                          fill="currentColor"
                          d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2zm0 15-5-2.18L7 18V5h10v13z"
                        />
                      )}
                    </svg>
                  </button>
                ) : null}
                <button
                  type="button"
                  className="carousel-book"
                  onClick={() => {
                    if (canRead) onLaunch?.(book)
                    else
                      window.location.href = `/login?next=${encodeURIComponent(book.read_url || `/library/${book.slug}/`)}`
                  }}
                >
                  <div className="carousel-book__cover">
                    {book.cover_url ? (
                      <img src={book.cover_url} alt="" loading="lazy" />
                    ) : (
                      <div className="continue-card__placeholder">{initial}</div>
                    )}
                  </div>
                  <h3 className="carousel-book__title">{book.title}</h3>
                  <p className="carousel-book__author">{book.author_name}</p>
                  {(book.review_count ?? 0) > 0 || book.average_rating != null ? (
                    <p className="carousel-book__rating" aria-label="O‘rtacha baho">
                      <span className="carousel-book__stars" aria-hidden="true">
                        {'★'.repeat(Math.max(0, Math.min(5, Math.round(Number(book.average_rating) || 0))))}
                        {'☆'.repeat(Math.max(0, 5 - Math.max(0, Math.min(5, Math.round(Number(book.average_rating) || 0)))))}
                      </span>
                      <span>
                        {book.average_rating != null ? Number(book.average_rating).toFixed(1) : '—'}
                        {book.review_count ? ` (${book.review_count})` : ''}
                      </span>
                    </p>
                  ) : null}
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
