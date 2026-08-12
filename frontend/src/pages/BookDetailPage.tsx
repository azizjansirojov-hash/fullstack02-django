import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import ReaderLaunchModal from '../components/library/ReaderLaunchModal'
import ReviewSection from '../components/library/ReviewSection'
import CheckoutButton from '../components/library/CheckoutButton'
import {
  fetchBookDetail,
  removePlanned,
  setReadingStatus,
} from '../api/library'
import { buildReadHref } from '../lib/readerOrigin'
import type { BookDetailResponse } from '../types/library'
import '../assets/css/library.css'

/**
 * Book detail — preview + launch actions inside DashboardLayout chrome.
 */
export default function BookDetailPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const [book, setBook] = useState<BookDetailResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [launchBook, setLaunchBook] = useState<BookDetailResponse | null>(null)
  const [statusBusy, setStatusBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const { response, data } = await fetchBookDetail(slug)
        if (cancelled) return
        if (!response.ok) {
          setError((data as { detail?: string } | null)?.detail || `Kitob yuklanmadi (${response.status})`)
          setBook(null)
          return
        }
        setBook(data)
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Network error')
          setBook(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [slug])

  useEffect(() => {
    if (book?.title) {
      document.title = `${book.title} · Libro.UZ`
    } else {
      document.title = 'Kitob · Libro.UZ'
    }
  }, [book?.title])

  const readingStatus = book?.reading_status || null
  const hasAccess = Boolean(book?.has_access)
  const canOpenReader = hasAccess && Boolean(book?.can_read)
  const isPurchasable = Boolean(book?.is_purchasable)
  const rightsStatus = book?.rights_status || ''
  const readHref = book
    ? buildReadHref(book.read_url || `/library/${book.slug}/read/`, 'focus', false)
    : '#'
  const initial = (book?.title || book?.slug || 'K').trim().charAt(0).toUpperCase()

  async function refreshStatus() {
    if (!slug) return
    try {
      const { response, data } = await fetchBookDetail(slug)
      if (response.ok && data) setBook(data)
    } catch {
      /* ignore */
    }
  }

  async function handleAddToPlan() {
    if (!book || statusBusy) return
    setStatusBusy(true)
    try {
      if (readingStatus === 'planned') {
        const { response } = await removePlanned(book.slug)
        if (!response.ok) throw new Error('Rejadan olib tashlanmadi')
      } else {
        const { response } = await setReadingStatus(book.slug, 'planned')
        if (!response.ok) throw new Error('Rejaga qo‘shilmadi')
      }
      await refreshStatus()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Amaliyot bajarilmadi')
    } finally {
      setStatusBusy(false)
    }
  }

  async function handleMarkFinished() {
    if (!book || statusBusy) return
    setStatusBusy(true)
    try {
      const { response } = await setReadingStatus(book.slug, 'finished')
      if (!response.ok) throw new Error('Tugatilgan deb belgilanmadi')
      await refreshStatus()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Amaliyot bajarilmadi')
    } finally {
      setStatusBusy(false)
    }
  }

  async function handleUndoFinished() {
    if (!book || statusBusy) return
    setStatusBusy(true)
    try {
      const { response } = await setReadingStatus(book.slug, 'reading')
      if (!response.ok) throw new Error('Qaytarilmadi')
      await refreshStatus()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Amaliyot bajarilmadi')
    } finally {
      setStatusBusy(false)
    }
  }

  return (
    <div className="book-detail-page">
      {loading && (
        <section className="library-empty">
          <div className="library-empty__panel">
            <p className="library-empty__copy">Yuklanmoqda…</p>
          </div>
        </section>
      )}

      {!loading && error && !book && (
        <section className="library-empty">
          <div className="library-empty__panel">
            <h1 className="library-empty__title">Xatolik</h1>
            <p className="library-empty__copy">{error}</p>
            <Link className="library-empty__cta" to="/library">
              Kutubxonaga qaytish
            </Link>
          </div>
        </section>
      )}

      {!loading && !error && book && !book.title && (
        <section className="library-empty">
          <div className="library-empty__panel">
            <h1 className="library-empty__title">Tarjima mavjud emas</h1>
            <p className="library-empty__copy">Bu kitobda hali o‘qiladigan kontent yo‘q.</p>
            <Link className="library-empty__cta" to="/library">
              Kutubxonaga qaytish
            </Link>
          </div>
        </section>
      )}

      {!loading && book && book.title && (
        <article className="reader reader--preview" lang="uz">
          <header className="reader-hero">
            <div className="reader-hero__cover">
              {book.cover_url ? (
                <img src={book.cover_url} alt={`${book.title} muqovasi`} />
              ) : (
                <div className="reader-hero__placeholder" aria-hidden="true">
                  <span>{initial}</span>
                </div>
              )}
            </div>
            <div className="reader-hero__copy">
              <p className="reader-hero__brand">Libro.UZ Kutubxonasi</p>
              <h1 className="reader-hero__title">{book.title}</h1>
              <p className="reader-hero__byline">
                {book.category_label}
                {' · '}
                {book.author_name}
                {book.published_year ? ` · ${book.published_year}` : ''}
              </p>
              {book.summary ? <p className="reader-hero__summary">{book.summary}</p> : null}
              {error ? <p className="reader-hero__status-error">{error}</p> : null}
              {!hasAccess && isPurchasable ? (
                <CheckoutButton
                  bookSlug={book.slug}
                  priceTiyin={book.book_price_tiyin ?? null}
                />
              ) : null}
              {!hasAccess && !isPurchasable ? (
                <p className="reader-hero__status-error" role="status">
                  {rightsStatus === 'unset' || rightsStatus === 'pending_clearance'
                    ? 'Bu kitob hozircha sotuvda emas (huquq holati tasdiqlanmagan).'
                    : 'Bu kitob pullik. To‘liq o‘qish, tinglash va PDF uchun xarid talab qilinadi.'}
                </p>
              ) : null}
              <div className="reader-actions">
                {canOpenReader ? (
                  <a className="reader-hero__read" href={readHref}>
                    O‘qishni davom ettirish
                  </a>
                ) : !hasAccess ? (
                  isPurchasable ? null : (
                    <button type="button" className="reader-hero__read reader-hero__read--ghost" disabled>
                      Sotib olish kerak
                    </button>
                  )
                ) : (
                  <p className="reader-hero__unavailable">O‘qiladigan kontent hali mavjud emas.</p>
                )}
                <button
                  type="button"
                  className="reader-hero__read reader-hero__read--ghost"
                  disabled={!hasAccess}
                  onClick={() => hasAccess && setLaunchBook(book)}
                >
                  {hasAccess ? 'Tinglash' : 'Tinglash (yopiq)'}
                </button>
                <button
                  type="button"
                  className="reader-hero__read reader-hero__read--ghost"
                  disabled={!hasAccess}
                  onClick={() => hasAccess && setLaunchBook(book)}
                >
                  {hasAccess ? 'Boshidan boshlash' : 'Boshidan (yopiq)'}
                </button>
                {!readingStatus || readingStatus === 'planned' ? (
                  <button
                    type="button"
                    className="reader-hero__read reader-hero__read--ghost"
                    disabled={statusBusy}
                    onClick={handleAddToPlan}
                  >
                    {readingStatus === 'planned' ? 'Rejadan olib tashlash' : 'Rejaga qo‘shish'}
                  </button>
                ) : null}
                {readingStatus === 'reading' ? (
                  <button
                    type="button"
                    className="reader-hero__read reader-hero__read--ghost"
                    disabled={statusBusy}
                    onClick={handleMarkFinished}
                  >
                    Tugatdim
                  </button>
                ) : null}
                {readingStatus === 'finished' ? (
                  <button
                    type="button"
                    className="reader-hero__read reader-hero__read--ghost"
                    disabled={statusBusy}
                    onClick={handleUndoFinished}
                  >
                    O‘qiyotganlarga qaytarish
                  </button>
                ) : null}
                {hasAccess && (book.pdf_url || book.has_pdf) ? (
                  <a
                    className="reader-hero__read reader-hero__read--ghost"
                    href={book.pdf_url || '#'}
                  >
                    PDF yuklab olish
                  </a>
                ) : book.has_pdf && !hasAccess ? (
                  <span className="reader-hero__read reader-hero__read--ghost" aria-disabled="true">
                    PDF (xarid kerak)
                  </span>
                ) : null}
              </div>
            </div>
          </header>
        </article>
      )}

      {!loading && book && Array.isArray(book.similar_books) && book.similar_books.length > 0 && (
        <section className="similar-books" aria-labelledby="similar-books-heading">
          <div className="similar-books__inner">
            <h2 className="similar-books__heading" id="similar-books-heading">
              O&apos;xshash kitoblar
            </h2>
            <div className="similar-books__grid">
              {book.similar_books.map((sim) => {
                const simInitial = (sim.title || sim.slug || 'K').trim().charAt(0).toUpperCase()
                return (
                  <Link
                    key={sim.slug}
                    className="similar-books__card"
                    to={`/library/${encodeURIComponent(sim.slug)}/`}
                  >
                    <div className="similar-books__cover">
                      {sim.cover_url ? (
                        <img src={sim.cover_url} alt={`${sim.title} muqovasi`} />
                      ) : (
                        <div className="similar-books__placeholder" aria-hidden="true">
                          <span>{simInitial}</span>
                        </div>
                      )}
                    </div>
                    <p className="similar-books__title">{sim.title || sim.slug}</p>
                    <p className="similar-books__author">{sim.author_name}</p>
                  </Link>
                )
              })}
            </div>
          </div>
        </section>
      )}

      {!loading && book && book.title ? <ReviewSection slug={slug} /> : null}

      <ReaderLaunchModal
        book={launchBook}
        open={Boolean(launchBook)}
        onClose={() => setLaunchBook(null)}
        onStatusChange={refreshStatus}
      />
    </div>
  )
}

