import { Link } from 'react-router'
import type { CatalogCategoryGroup } from '../../types/library'

export type CategoryPillItem = Pick<CatalogCategoryGroup, 'code' | 'label'>

export type CategoryPillsProps = {
  categories?: CategoryPillItem[]
  activeCode?: string
  basePath?: string
}

/**
 * Category filter pills (“Javonlar”).
 */
export default function CategoryPills({
  categories = [],
  activeCode = '',
  basePath = '/library/dokon',
}: CategoryPillsProps) {
  if (!categories.length) return null

  return (
    <div className="category-pills" role="list" aria-label="Javonlar">
      <Link
        role="listitem"
        className={`category-pill${!activeCode ? ' is-active' : ''}`}
        to={basePath}
      >
        Barchasi
      </Link>
      {categories.map((cat) => (
        <Link
          key={cat.code}
          role="listitem"
          className={`category-pill${activeCode === cat.code ? ' is-active' : ''}`}
          to={`${basePath}?category=${encodeURIComponent(cat.code)}`}
        >
          #{cat.label}
        </Link>
      ))}
    </div>
  )
}
