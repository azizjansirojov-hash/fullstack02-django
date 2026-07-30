import { useCallback, useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  fetchMyLibrary,
  removePlanned,
  setReadingStatus,
} from '../api/library'
import ContinueReadingCard from '../components/library/ContinueReadingCard'
import BookCard from '../components/library/BookCard'
import ReaderLaunchModal from '../components/library/ReaderLaunchModal'
import type { LibraryBookView, MyLibraryResponse, ProgressCard } from '../types/library'

const TABS = [
  { id: 'reading', label: "O'qiyotgan kitoblarim" },
  { id: 'planned', label: 'Rejamdagi kitoblar' },
  { id: 'finished', label: "O'qilgan kitoblar" },
] as const

type LibraryTab = (typeof TABS)[number]['id']

/**
 * Mening kutubxonam — continue hero + status tabs (reading / planned / finished).
 */
export default function MyLibraryPage() {
  const { isAuthenticated } = useAuth()
  const [library, setLibrary] = useState<MyLibraryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<LibraryTab>('reading')
  const [launchBook, setLaunchBook] = useState<LibraryBookView | null>(null)
  const [busySlug, setBusySlug] = useState<string | null>(null)

  const loadLibrary = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) {
      setLoading(true)
      setError(null)
    }
    try {
      const { response, data } = await fetchMyLibrary()
      if (!response.ok) {
        if (!silent) setError(`Ma’lumot yuklanmadi (${response.status})`)
        return
      }
      setLibrary(data)
      if (!silent) setError(null)
    } catch (err: unknown) {
      if (!silent) setError(err instanceof Error ? err.message : 'Network error')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    document.title = 'Mening kutubxonam · Libro.UZ'
  }, [])

  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false)
      setLibrary(null)
      return undefined
    }
    let cancelled = false
    ;(async () => {
      if (cancelled) return
      await loadLibrary()
    })()
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, loadLibrary])

  async function withBusy(slug: string, fn: () => Promise<void>) {
    setBusySlug(slug)
    try {
      await fn()
      await loadLibrary({ silent: true })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Amaliyot bajarilmadi')
    } finally {
      setBusySlug(null)
    }
  }

  function handleRemovePlanned(book: LibraryBookView) {
    return withBusy(book.slug, async () => {
      const { response } = await removePlanned(book.slug)
      if (!response.ok) throw new Error('Rejadan olib tashlanmadi')
    })
  }

  function handleMarkFinished(book: LibraryBookView) {
    return withBusy(book.slug, async () => {
      const { response } = await setReadingStatus(book.slug, 'finished')
      if (!response.ok) throw new Error('Tugatilgan deb belgilanmadi')
    })
  }

  function handleUndoFinished(book: LibraryBookView) {
    return withBusy(book.slug, async () => {
      const { response } = await setReadingStatus(book.slug, 'reading')
      if (!response.ok) throw new Error('Qaytarilmadi')
    })
  }

  if (!isAuthenticated) {
    return (
      <div className="dash-empty">
        <strong>Mening kutubxonam</strong>
        Shaxsiy kutubxonangizni ko‘rish uchun{' '}
        <Link to={`/login?next=${encodeURIComponent('/library/mening')}`}>tizimga kiring</Link>.
      </div>
    )
  }

  if (loading) {
    return (
      <div className="library-tab-loading" aria-busy="true">
        <div className="library-skeleton-grid">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="library-skeleton-card"
              style={{ '--i': i } as CSSProperties & Record<string, string | number>}
            />
          ))}
        </div>
        <p className="dash-loading">Yuklanmoqda…</p>
      </div>
    )
  }

  if (error && !library) return <p className="dash-empty">{error}</p>

  const counts = library?.counts || { reading: 0, planned: 0, finished: 0 }
  const reading = library?.reading || []
  const planned = library?.planned || []
  const finished = library?.finished || []
  const canRead = Boolean(library?.can_read ?? true)
  const continueHero = reading[0] || null

  const tabBooks =
    tab === 'planned' ? planned : tab === 'finished' ? finished : reading

  const libraryActions =
    tab === 'planned'
      ? {
          showRemovePlanned: true,
          onRemovePlanned: handleRemovePlanned,
        }
      : tab === 'finished'
        ? {
            showUndoFinished: true,
            onUndoFinished: handleUndoFinished,
          }
        : {
            showFinish: true,
            onMarkFinished: handleMarkFinished,
          }

  return (
    <>
      <h1 className="dash-page-title">Mening kutubxonam</h1>

      {error ? <p className="dash-inline-error">{error}</p> : null}

      <ContinueReadingCard book={continueHero} onLaunch={(book: ProgressCard) => setLaunchBook(book)} />

      <div className="library-tabs" role="tablist" aria-label="Kutubxona bo‘limlari">
        {TABS.map((t) => {
          const count = counts[t.id] || 0
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`library-tab${tab === t.id ? ' is-active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {count > 0 ? <span className="library-tab__count">{count}</span> : null}
            </button>
          )
        })}
      </div>

      {tabBooks.length ? (
        <ul className={`reading-grid${busySlug ? ' is-busy' : ''}`}>
          {tabBooks.map((book, index) => (
            <BookCard
              key={book.slug}
              book={book}
              canRead={canRead}
              index={index}
              onLaunch={setLaunchBook}
              libraryActions={libraryActions}
            />
          ))}
        </ul>
      ) : (
        <LibraryTabEmpty tab={tab} />
      )}

      {launchBook ? (
        <ReaderLaunchModal
          book={launchBook}
          open={Boolean(launchBook)}
          onClose={() => {
            setLaunchBook(null)
            loadLibrary({ silent: true })
          }}
          onStatusChange={() => loadLibrary({ silent: true })}
        />
      ) : null}
    </>
  )
}

function LibraryTabEmpty({ tab }: { tab: LibraryTab }) {
  if (tab === 'planned') {
    return (
      <section className="library-empty library-empty--inline">
        <div className="library-empty__panel">
          <p className="library-empty__eyebrow">Reja</p>
          <h2 className="library-empty__title">Rejamda hali kitob yo‘q</h2>
          <p className="library-empty__copy">
            Katalogdan yoqqan kitobni «Rejaga qo‘shish» bilan saqlang — keyinroq o‘qish uchun.
          </p>
          <Link className="library-empty__cta" to="/library/dokon">
            Katalogni ko‘rish
          </Link>
        </div>
      </section>
    )
  }
  if (tab === 'finished') {
    return (
      <section className="library-empty library-empty--inline">
        <div className="library-empty__panel">
          <p className="library-empty__eyebrow">Yutuq</p>
          <h2 className="library-empty__title">Hali tugatilgan kitob yo‘q</h2>
          <p className="library-empty__copy">
            O‘qishni davom ettiring. Kitobni tugatganingizda «Tugatdim» tugmasini bosing.
          </p>
          <Link className="library-empty__cta" to="/library">
            O‘qishni davom ettirish
          </Link>
        </div>
      </section>
    )
  }
  return (
    <section className="library-empty library-empty--inline">
      <div className="library-empty__panel">
        <p className="library-empty__eyebrow">O‘qish</p>
        <h2 className="library-empty__title">Hozircha o‘qiyotgan kitoblaringiz yo‘q</h2>
        <p className="library-empty__copy">
          Biror kitobni oching yoki rejadagisini o‘qishni boshlang.
        </p>
        <Link className="library-empty__cta" to="/library/dokon">
          Katalogni ko‘rish
        </Link>
      </div>
    </section>
  )
}

