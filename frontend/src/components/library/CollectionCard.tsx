import { Link } from 'react-router-dom'
import type { CatalogCategoryGroup } from '../../types/library'

export type CollectionCardProps = {
  category: Pick<CatalogCategoryGroup, 'code' | 'label' | 'count'>
}

/**
 * Category-as-collection card for To‘plamlar grid.
 * Structure is identical for empty and populated categories (no cover thumbs).
 */
export default function CollectionCard({ category }: CollectionCardProps) {
  return (
    <Link
      className="collection-card"
      to={`/library/dokon?category=${encodeURIComponent(category.code)}`}
    >
      <div className="collection-card__body">
        <p className="collection-card__label">To‘plam</p>
        <h2 className="collection-card__title">{category.label}</h2>
        <p className="collection-card__count">{category.count} ta kitob</p>
      </div>
      <div className="collection-card__footer" aria-hidden />
    </Link>
  )
}
