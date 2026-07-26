import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import ReaderLaunchModal from '../components/library/ReaderLaunchModal'
import {
  fetchBookDetail,
  removePlanned,
  setReadingStatus,
} from '../api/library'
import { buildDjangoReadHref } from '../lib/readerOrigin'
import '../assets/css/library.css'

/**
 * Book detail — port of Django book_detail.html (preview + launch actions).
 */
export default function BookDetailPage() {
  const { slug } = useParams()
  const [book, setBook] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [launchBook, setLaunchBook] = useState(null)
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
          setError(
            response.status === 401 || response.status === 403
              ? 'Kirish talab qilinadi.'
              : `Kitob yuklanmadi (${response.status})`
          )
          setBook(null)
          return
        }
        setBook(data)
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Network error')
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

  const initial = (book?.title || book?.slug || 'K').trim().charAt(0).toUpperCase()
  const hasAccess = Boolean(book?.has_access)
  const canOpenReader = Boolean(book?.can_read && hasAccess)
  const readHref = canOpenReader && book?.read_url
    ? buildDjangoReadHref(book.read_url, 'focus', false)
    : '#'
  const readingStatus = book?.reading_status || null

  async function refreshStatus() {
    const { response, data } = await fetchBookDetail(slug)
    if (response.ok) setBook(data)
  }

  async function handleAddToPlan() {
    if (!book || statusBusy) return
    setStatusBusy(true)
    try {
      if (readingStatus === 'planned') {
        const { response } = await removePlanned(book.slug)
        if (!response.ok) throw new Error('Rejadan olib tashlanmadi')
      } else if (!readingStatus) {
        const { response } = await setReadingStatus(book.slug, 'planned')
        if (!response.ok) throw new Error('Rejaga qo‘shilmadi')
      }
      await refreshStatus()
    } catch (err) {
      setError(err.message || 'Amaliyot bajarilmadi')
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
    } catch (err) {
      setError(err.message || 'Amaliyot bajarilmadi')
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
    } catch (err) {
      setError(err.message || 'Amaliyot bajarilmadi')
    } finally {
      setStatusBusy(false)
    }
  }

  return (
    <AppShell
      title={book?.title || 'Kitob'}
      metaDescription={book?.summary || 'Libro.UZ Kutubxonasida o‘qing.'}
      wordmarkTo="/library"
      navCenter={
        <div className="nav__center nav__center--library">
          <Link className="nav__link" to="/library">
            Kutubxona
          </Link>
          <span className="nav__muted">Kitob</span>
        </div>
      }
      navStatus={
        <span className="status-chip">
          <span className="status-chip__dot" />
          Ko‘rib chiqish
        </span>
      }
      navAction={
        <Link className="nav__cta" to="/library">
          Javonga qaytish
        </Link>
      }
    >
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
              {!hasAccess ? (
                <p className="reader-hero__status-error" role="status">
                  Bu kitob pullik. To‘liq o‘qish, tinglash va PDF uchun xarid (Purchase)
                  talab qilinadi. Hozircha to‘lov shlyuzi ulanmagan — admin orqali
                  “Mark as paid” qiling yoki huquq holatini public_domain qiling.
                </p>
              ) : null}
              <div className="reader-actions">
                {canOpenReader ? (
                  <a className="reader-hero__read" href={readHref}>
                    O‘qishni davom ettirish
                  </a>
                ) : !hasAccess ? (
                  <button type="button" className="reader-hero__read" disabled>
                    Sotib olish kerak
                  </button>
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

      <ReaderLaunchModal
        book={launchBook}
        open={Boolean(launchBook)}
        onClose={() => setLaunchBook(null)}
        onStatusChange={refreshStatus}
      />
    </AppShell>
  )
}
