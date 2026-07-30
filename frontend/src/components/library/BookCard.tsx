import type { CSSProperties, MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { truncateWords } from '../../lib/readerOrigin'
import type { LibraryBookView } from '../../types/library'

export type LibraryBookActions = {
  showPlan?: boolean
  showRemovePlanned?: boolean
  showUndoFinished?: boolean
  showFinish?: boolean
  onPlanToggle?: (book: LibraryBookView, removing: boolean) => void
  onRemovePlanned?: (book: LibraryBookView) => void
  onUndoFinished?: (book: LibraryBookView) => void
  onMarkFinished?: (book: LibraryBookView) => void
}

export type BookCardProps = {
  book: LibraryBookView
  canRead: boolean
  index?: number
  onLaunch?: (book: LibraryBookView) => void
  libraryActions?: LibraryBookActions | null
}

/**
 * Shelf card — whole card is one link (matches Django catalog.html).
 * Optional libraryActions: plan / finish / remove controls for authenticated shelves.
 */
export default function BookCard({
  book,
  canRead,
  index = 0,
  onLaunch,
  libraryActions = null,
}: BookCardProps) {
  const loginNext = book.read_url || `/library/${book.slug}/read/`
  const loginHref = `/login?next=${encodeURIComponent(loginNext)}`
  const initial = (book.title || book.slug || 'K').trim().charAt(0).toUpperCase()
  const status = book.reading_status || book.progress?.status || null
  const showPlanBtn =
    Boolean(libraryActions?.showPlan) && status !== 'reading' && status !== 'finished'
  const showRemovePlannedBtn =
    Boolean(libraryActions?.showRemovePlanned) && status === 'planned'
  const showUndoFinishedBtn =
    Boolean(libraryActions?.showUndoFinished) && status === 'finished'
  const showFinishBtn = Boolean(libraryActions?.showFinish) && status === 'reading'
  const hasOverlayActions = showPlanBtn || showRemovePlannedBtn || showUndoFinishedBtn

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (!canRead) return
    event.preventDefault()
    onLaunch?.(book)
  }

  return (
    <li className="shelf-card" style={{ '--i': index } as CSSProperties}>
      <div className="shelf-card__shell">
        {hasOverlayActions ? (
          <div className="shelf-card__actions">
            {showPlanBtn ? (
              <button
                type="button"
                className={`shelf-card__action${status === 'planned' ? ' is-active' : ''}`}
                title={status === 'planned' ? 'Rejadan olib tashlash' : 'Rejaga qo‘shish'}
                aria-label={status === 'planned' ? 'Rejadan olib tashlash' : 'Rejaga qo‘shish'}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  libraryActions?.onPlanToggle?.(book, status === 'planned')
                }}
              >
                <BookmarkIcon filled={status === 'planned'} />
              </button>
            ) : null}
            {showRemovePlannedBtn ? (
              <button
                type="button"
                className="shelf-card__action"
                title="Rejadan olib tashlash"
                aria-label="Rejadan olib tashlash"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  libraryActions?.onRemovePlanned?.(book)
                }}
              >
                <CloseIcon />
              </button>
            ) : null}
            {showUndoFinishedBtn ? (
              <button
                type="button"
                className="shelf-card__action"
                title="O‘qiyotganlarga qaytarish"
                aria-label="O‘qiyotganlarga qaytarish"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  libraryActions?.onUndoFinished?.(book)
                }}
              >
                <UndoIcon />
              </button>
            ) : null}
          </div>
        ) : null}
        <a
          className={`shelf-card__link${canRead ? '' : ' shelf-card__link--preview'}`}
          href={canRead ? book.read_url || '#' : loginHref}
          title={canRead ? undefined : 'Bu kitobni o‘qish uchun kiring'}
          onClick={handleClick}
        >
          <div className="shelf-card__cover">
            {book.cover_url ? (
              <img src={book.cover_url} alt="" loading="lazy" />
            ) : (
              <div className="shelf-card__placeholder" aria-hidden="true">
                <span>{initial}</span>
              </div>
            )}
            {!canRead && <span className="shelf-card__lock">O‘qish uchun kirish</span>}
          </div>
          <div className="shelf-card__meta">
            <p className="shelf-card__category">{book.category_label}</p>
            <h2 className="shelf-card__title">{book.title}</h2>
            <p className="shelf-card__author">{book.author_name}</p>
            {book.summary ? (
              <p className="shelf-card__summary">{truncateWords(book.summary, 18)}</p>
            ) : null}
          </div>
        </a>
        {showFinishBtn ? (
          <button
            type="button"
            className="shelf-card__finish"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              libraryActions?.onMarkFinished?.(book)
            }}
          >
            Tugatdim
          </button>
        ) : null}
      </div>
    </li>
  )
}

function BookmarkIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18">
      {filled ? (
        <path fill="currentColor" d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z" />
      ) : (
        <path
          fill="currentColor"
          d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2zm0 15-5-2.18L7 18V5h10v13z"
        />
      )}
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18">
      <path
        fill="currentColor"
        d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"
      />
    </svg>
  )
}

function UndoIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18">
      <path
        fill="currentColor"
        d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"
      />
    </svg>
  )
}

export type ShelfPreviewLinkProps = {
  book: LibraryBookView
  canRead: boolean
  onLaunch?: (book: LibraryBookView) => void
}

/** Category-panel preview link that opens the same launch modal when readable. */
export function ShelfPreviewLink({ book, canRead, onLaunch }: ShelfPreviewLinkProps) {
  const loginNext = book.read_url || `/library/${book.slug}/read/`
  const loginHref = `/login?next=${encodeURIComponent(loginNext)}`

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (!canRead) return
    event.preventDefault()
    onLaunch?.(book)
  }

  if (!canRead) {
    return (
      <Link to={loginHref}>
        <span className="category-list__book">{book.title}</span>
        <span className="category-list__author">{book.author_name}</span>
      </Link>
    )
  }

  return (
    <a href={book.read_url || '#'} className="js-book-launch" onClick={handleClick}>
      <span className="category-list__book">{book.title}</span>
      <span className="category-list__author">{book.author_name}</span>
    </a>
  )
}
