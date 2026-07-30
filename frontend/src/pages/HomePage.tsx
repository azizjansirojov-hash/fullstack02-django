import { useEffect } from 'react'
import { useAuth } from '../auth/AuthContext'
import ContinueReadingCard from '../components/library/ContinueReadingCard'
import WeeklyActivityWidget from '../components/library/WeeklyActivityWidget'
import CategoryPills from '../components/library/CategoryPills'
import NewBooksCarousel from '../components/library/NewBooksCarousel'
import ReaderLaunchModal from '../components/library/ReaderLaunchModal'
import { useCatalog } from '../lib/useCatalog'

/**
 * Asosiy sahifa — continue + activity + ruknlar + yangi kitoblar.
 */
export default function HomePage() {
  const { isAuthenticated } = useAuth()
  const {
    catalog,
    error,
    loading,
    launchBook,
    setLaunchBook,
    reload,
    handlePlanToggle,
  } = useCatalog({ refreshOnFocus: true })

  useEffect(() => {
    document.title = 'Asosiy sahifa · Libro.UZ'
  }, [])

  const canRead = Boolean(catalog?.can_read ?? isAuthenticated)
  const continueReading = catalog?.continue_reading || []
  const activityTimestamps = catalog?.activity_timestamps || []
  const categories = catalog?.category_lists || []
  const newBooks = catalog?.shelf || []
  const planActions = isAuthenticated
    ? { showPlan: true as const, onPlanToggle: handlePlanToggle }
    : null

  if (loading) return <p className="dash-loading">Yuklanmoqda…</p>
  if (error) return <p className="dash-empty">{error}</p>

  return (
    <>
      <div className="dash-top">
        <ContinueReadingCard
          book={continueReading[0] || null}
          onLaunch={setLaunchBook}
          emptyHint={
            isAuthenticated
              ? 'Hozircha o‘qish jarayoni yo‘q. Yangi kitob oching.'
              : 'Davom ettirish uchun tizimga kiring.'
          }
        />
        <WeeklyActivityWidget
          continueReading={continueReading}
          activityTimestamps={activityTimestamps}
        />
      </div>

      <section className="dash-section" aria-labelledby="ruknlar-title">
        <div className="dash-section__head">
          <h2 id="ruknlar-title" className="dash-section__title">
            Javonlar
          </h2>
        </div>
        <CategoryPills categories={categories} />
      </section>

      <section className="dash-section">
        <NewBooksCarousel
          books={newBooks}
          canRead={canRead}
          onLaunch={setLaunchBook}
          libraryActions={planActions}
        />
      </section>

      {launchBook ? (
        <ReaderLaunchModal
          book={launchBook}
          open={Boolean(launchBook)}
          onClose={() => setLaunchBook(null)}
          onStatusChange={() => reload({ silent: true })}
        />
      ) : null}
    </>
  )
}
