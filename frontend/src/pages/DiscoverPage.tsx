import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import CategoryPills from '../components/library/CategoryPills'
import NewBooksCarousel from '../components/library/NewBooksCarousel'
import BookCard from '../components/library/BookCard'
import ReaderLaunchModal from '../components/library/ReaderLaunchModal'
import { useCatalog } from '../lib/useCatalog'
import type { CatalogPagination } from '../types/library'

function buildDiscoverHref(params: {
  q: string
  category: string
  page: number
}): string {
  const search = new URLSearchParams()
  if (params.q) search.set('q', params.q)
  if (params.category) search.set('category', params.category)
  if (params.page > 1) search.set('page', String(params.page))
  const qs = search.toString()
  return qs ? `/library/dokon?${qs}` : '/library/dokon'
}

function DiscoverPagination({
  pagination,
  q,
  category,
}: {
  pagination: CatalogPagination
  q: string
  category: string
}) {
  if (pagination.num_pages <= 1) return null
  return (
    <nav className="library-pagination" aria-label="Sahifalar">
      {pagination.has_previous && pagination.previous_page != null ? (
        <Link
          to={buildDiscoverHref({ q, category, page: pagination.previous_page })}
        >
          Oldingi
        </Link>
      ) : (
        <span aria-hidden="true" />
      )}
      <span className="library-pagination__status">
        {pagination.page} / {pagination.num_pages}
      </span>
      {pagination.has_next && pagination.next_page != null ? (
        <Link to={buildDiscoverHref({ q, category, page: pagination.next_page })}>
          Keyingi
        </Link>
      ) : (
        <span aria-hidden="true" />
      )}
    </nav>
  )
}

/**
 * Kutubxona do‘koni — curated discovery (not a paid store).
 */
export default function DiscoverPage() {
  const { isAuthenticated } = useAuth()
  const [searchParams] = useSearchParams()
  const q = searchParams.get('q') || ''
  const category = searchParams.get('category') || ''
  const page = Number(searchParams.get('page') || '1') || 1

  const {
    catalog,
    error,
    planError,
    loading,
    launchBook,
    setLaunchBook,
    handlePlanToggle,
  } = useCatalog({ q, category, page })

  useEffect(() => {
    document.title = "Kutubxona do'koni · Libro.UZ"
  }, [])

  const canRead = Boolean(catalog?.can_read ?? isAuthenticated)
  const categories = catalog?.category_lists || []
  const shelf = catalog?.shelf || []
  const featured = categories.filter((c) => c.count > 0).slice(0, 3)
  const pagination = catalog?.pagination
  const planActions = isAuthenticated
    ? { showPlan: true as const, onPlanToggle: handlePlanToggle }
    : null

  if (loading) return <p className="dash-loading">Yuklanmoqda…</p>
  if (error) return <p className="dash-empty">{error}</p>

  return (
    <>
      <section className="discover-hero">
        <div className="discover-hero__copy">
          <h1>Izlagan kitoblaringiz shu yerda</h1>
          <p>
            Tanlangan ruknlar va yangi asarlar — Libro.UZ kashfiyoti (savdo emas, tanlangan
            katalog).
          </p>
        </div>

        {!q && !category && featured.length ? (
          <div className="discover-banners">
            {featured.map((cat) => (
              <Link
                key={cat.code}
                className="discover-banner"
                to={`/library/dokon?category=${encodeURIComponent(cat.code)}`}
              >
                <div>
                  <h2 className="discover-banner__title">{cat.label}</h2>
                  <p className="discover-banner__meta">{cat.count} ta kitob</p>
                </div>
                <div className="discover-banner__covers" aria-hidden>
                  {(cat.items || []).slice(0, 3).map((book) =>
                    book.cover_url ? (
                      <img key={book.slug} src={book.cover_url} alt="" />
                    ) : null,
                  )}
                </div>
              </Link>
            ))}
          </div>
        ) : null}
      </section>

      {(q || category) && (
        <p style={{ color: 'var(--secondary)', marginBottom: '1rem', fontSize: '0.9rem' }}>
          {q ? `Qidiruv: “${q}”` : null}
          {q && category ? ' · ' : null}
          {category
            ? `Rukn: ${categories.find((c) => c.code === category)?.label || category}`
            : null}
          {' · '}
          <Link to="/library/dokon">Tozalash</Link>
        </p>
      )}

      {planError ? (
        <p className="dash-empty" role="alert">
          {planError}
        </p>
      ) : null}

      <section className="dash-section" aria-labelledby="discover-ruknlar">
        <div className="dash-section__head">
          <h2 id="discover-ruknlar" className="dash-section__title">
            Javonlar
          </h2>
        </div>
        <CategoryPills categories={categories} activeCode={category} />
      </section>

      {!q && !category ? (
        <section className="dash-section">
          <NewBooksCarousel
            books={shelf}
            canRead={canRead}
            onLaunch={setLaunchBook}
            libraryActions={planActions}
          />
          {pagination ? (
            <DiscoverPagination pagination={pagination} q={q} category={category} />
          ) : null}
        </section>
      ) : (
        <section className="dash-section">
          <div className="dash-section__head">
            <h2 className="dash-section__title">Natijalar</h2>
          </div>
          {shelf.length ? (
            <ul className="reading-grid">
              {shelf.map((book, index) => (
                <BookCard
                  key={book.slug}
                  book={book}
                  canRead={canRead}
                  index={index}
                  onLaunch={setLaunchBook}
                  libraryActions={planActions}
                />
              ))}
            </ul>
          ) : (
            <p className="dash-empty">Hech narsa topilmadi.</p>
          )}
          {pagination ? (
            <DiscoverPagination pagination={pagination} q={q} category={category} />
          ) : null}
        </section>
      )}

      {launchBook ? (
        <ReaderLaunchModal
          book={launchBook}
          open={Boolean(launchBook)}
          onClose={() => setLaunchBook(null)}
        />
      ) : null}
    </>
  )
}
