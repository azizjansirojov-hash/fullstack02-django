import { useEffect } from 'react'
import CollectionCard from '../components/library/CollectionCard'
import { useCatalog } from '../lib/useCatalog'

/**
 * To‘plamlar — category grid from real category_lists.
 */
export default function CollectionsPage() {
  const { catalog, error, loading } = useCatalog({
    errorLabel: 'To‘plamlar yuklanmadi',
  })
  const categories = catalog?.category_lists || []

  useEffect(() => {
    document.title = "To'plamlar · Libro.UZ"
  }, [])

  if (loading) return <p className="dash-loading">Yuklanmoqda…</p>
  if (error) return <p className="dash-empty">{error}</p>

  return (
    <>
      <h1 className="dash-page-title">To‘plamlar</h1>
      {categories.length ? (
        <ul className="collections-grid">
          {categories.map((cat) => (
            <li key={cat.code}>
              <CollectionCard category={cat} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="dash-empty">Hozircha to‘plamlar yo‘q.</p>
      )}
    </>
  )
}
