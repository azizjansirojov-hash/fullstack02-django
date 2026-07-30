import { ShelfPreviewLink } from './BookCard'
import type { CatalogCategoryGroup, LibraryBookView } from '../../types/library'

export type ShelvesPanelProps = {
  open: boolean
  categoryLists?: CatalogCategoryGroup[]
  activeCategory?: string
  query?: string
  canRead?: boolean
  onLaunch?: (book: LibraryBookView) => void
  onSelectCategory?: (code: string) => void
}

/**
 * Collapsible category shelves panel (matches Django catalog.html).
 */
export default function ShelvesPanel({
  open,
  categoryLists = [],
  activeCategory = '',
  query = '',
  canRead = false,
  onLaunch,
  onSelectCategory,
}: ShelvesPanelProps) {
  return (
    <section
      id="shelves-panel"
      className={`shelves-panel${open ? ' is-open' : ''}`}
      aria-label="Kitob yo‘nalishlari"
      hidden={!open}
    >
      <header className="shelves-panel__header">
        <p className="panel-eyebrow">Yo‘nalishlar</p>
        <p className="shelves-panel__lede">
          Har bir ro‘yxat o‘z turidagi kitoblarni saqlaydi — aralashmaydi.
        </p>
      </header>
      <div className="shelves-panel__grid">
        {categoryLists.map((group) => (
          <div
            key={group.code}
            className={`category-list${activeCategory === group.code ? ' is-active' : ''}`}
          >
            <div className="category-list__head">
              <button
                type="button"
                className="category-list__name"
                onClick={() => onSelectCategory?.(group.code)}
              >
                {group.label}
              </button>
              <span className="category-list__count">{group.count}</span>
            </div>
            {group.items?.length ? (
              <>
                <ul className="category-list__items">
                  {group.items.slice(0, 5).map((item) => (
                    <li key={item.slug}>
                      <ShelfPreviewLink book={item} canRead={canRead} onLaunch={onLaunch} />
                    </li>
                  ))}
                </ul>
                {group.count > 5 ? (
                  <button
                    type="button"
                    className="category-list__more"
                    onClick={() => onSelectCategory?.(group.code)}
                  >
                    Barchasi · {group.count}
                  </button>
                ) : null}
              </>
            ) : (
              <p className="category-list__empty">Sarlavhalar kutilmoqda</p>
            )}
          </div>
        ))}
      </div>
      {query ? <span className="visually-hidden">Qidiruv: {query}</span> : null}
    </section>
  )
}
