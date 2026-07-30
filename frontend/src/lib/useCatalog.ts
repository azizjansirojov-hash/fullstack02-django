import { useCallback, useEffect, useState } from 'react'
import { fetchCatalog, removePlanned, setReadingStatus } from '../api/library'
import type {
  BookCardWithStatus,
  CatalogResponse,
  LibraryBookView,
  ReadingStatus,
} from '../types/library'

export type UseCatalogOptions = {
  q?: string
  category?: string
  page?: number
  /** When true, silently refresh catalog when the tab becomes visible / window focused. */
  refreshOnFocus?: boolean
  errorLabel?: string
}

export type UseCatalogResult = {
  catalog: CatalogResponse | null
  error: string | null
  loading: boolean
  launchBook: LibraryBookView | null
  setLaunchBook: (book: LibraryBookView | null) => void
  reload: (opts?: { silent?: boolean }) => Promise<void>
  patchBookStatus: (slug: string, readingStatus: ReadingStatus | null) => void
  handlePlanToggle: (book: BookCardWithStatus, isPlanned: boolean) => Promise<void>
}

/**
 * Shared catalog fetch + plan-toggle + launch-modal book state for dashboard pages.
 */
export function useCatalog({
  q = '',
  category = '',
  page = 1,
  refreshOnFocus = false,
  errorLabel = 'Katalog yuklanmadi',
}: UseCatalogOptions = {}): UseCatalogResult {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [launchBook, setLaunchBook] = useState<LibraryBookView | null>(null)

  const loadCatalog = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!silent) {
        setLoading(true)
        setError(null)
      }
      try {
        const { response, data } = await fetchCatalog({ q, category, page })
        if (!response.ok) {
          if (!silent) setError(`${errorLabel} (${response.status})`)
          return
        }
        setCatalog(data)
        if (!silent) setError(null)
      } catch (err) {
        if (!silent) {
          setError(err instanceof Error ? err.message : 'Network error')
        }
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [q, category, page, errorLabel],
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (cancelled) return
      await loadCatalog()
    })()
    return () => {
      cancelled = true
    }
  }, [loadCatalog])

  useEffect(() => {
    if (!refreshOnFocus) return undefined
    function refreshIfVisible() {
      if (document.visibilityState === 'visible') {
        loadCatalog({ silent: true })
      }
    }
    function onFocus() {
      loadCatalog({ silent: true })
    }
    document.addEventListener('visibilitychange', refreshIfVisible)
    window.addEventListener('focus', onFocus)
    return () => {
      document.removeEventListener('visibilitychange', refreshIfVisible)
      window.removeEventListener('focus', onFocus)
    }
  }, [loadCatalog, refreshOnFocus])

  const patchBookStatus = useCallback((slug: string, readingStatus: ReadingStatus | null) => {
    setCatalog((prev) => {
      if (!prev) return prev
      const patch = (list: BookCardWithStatus[] | undefined) =>
        (list || []).map((b) => (b.slug === slug ? { ...b, reading_status: readingStatus } : b))
      return {
        ...prev,
        shelf: patch(prev.shelf),
        category_lists: (prev.category_lists || []).map((g) => ({
          ...g,
          items: patch(g.items),
        })),
      }
    })
  }, [])

  const handlePlanToggle = useCallback(
    async (book: BookCardWithStatus, isPlanned: boolean) => {
      try {
        if (isPlanned) {
          const { response } = await removePlanned(book.slug)
          if (!response.ok) return
          patchBookStatus(book.slug, null)
        } else {
          const { response, data } = await setReadingStatus(book.slug, 'planned')
          if (!response.ok) return
          patchBookStatus(book.slug, (data?.status as ReadingStatus) || 'planned')
        }
      } catch {
        /* ignore */
      }
    },
    [patchBookStatus],
  )

  return {
    catalog,
    error,
    loading,
    launchBook,
    setLaunchBook,
    reload: loadCatalog,
    patchBookStatus,
    handlePlanToggle,
  }
}
