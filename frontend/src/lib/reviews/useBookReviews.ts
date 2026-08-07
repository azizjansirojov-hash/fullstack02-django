import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import {
  createReview,
  deleteReview,
  getReviews,
  updateReview,
} from '../../api/library'
import type { ReviewItem } from '../../types/library'

export type ReviewFormStatus = 'idle' | 'saving' | 'saved' | 'error'

export type UseBookReviewsResult = {
  reviews: ReviewItem[]
  count: number
  averageRating: number | null
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  error: string | null
  myReview: ReviewItem | null
  formStatus: ReviewFormStatus
  formError: string | null
  isAuthenticated: boolean
  ready: boolean
  reload: () => Promise<void>
  loadMore: () => Promise<void>
  /** POST or PUT rating; preserves existing text when updating. */
  submitRating: (rating: number, text?: string) => Promise<boolean>
  /** Full create/update with explicit text (ReviewSection form). */
  submitReview: (rating: number, text: string, mode: 'create' | 'update') => Promise<boolean>
  removeReview: () => Promise<boolean>
  clearFormFeedback: () => void
}

/**
 * Shared reviews fetch + mutation for ReviewSection and dashboard card/modal UI.
 */
export function useBookReviews(slug: string | null | undefined): UseBookReviewsResult {
  const { user, isAuthenticated, ready } = useAuth()

  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [count, setCount] = useState(0)
  const [averageRating, setAverageRating] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(Boolean(slug))
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [myReview, setMyReview] = useState<ReviewItem | null>(null)
  const [formStatus, setFormStatus] = useState<ReviewFormStatus>('idle')
  const [formError, setFormError] = useState<string | null>(null)

  const applyMyReview = useCallback(
    (data: {
      my_review?: ReviewItem | null
      results: ReviewItem[]
    }) => {
      if (data.my_review !== undefined) {
        setMyReview(data.my_review)
        return
      }
      if (user) {
        setMyReview(data.results.find((r) => r.username === user.username) || null)
      } else {
        setMyReview(null)
      }
    },
    [user],
  )

  const reload = useCallback(async () => {
    if (!slug) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const { response, data } = await getReviews(slug, 1)
      if (!response.ok || !data) {
        setError('Sharhlar yuklanmadi.')
        return
      }
      setReviews(data.results)
      setCount(data.count)
      setAverageRating(data.average_rating)
      setPage(data.pagination?.page ?? 1)
      setHasMore(Boolean(data.pagination?.has_next))
      applyMyReview(data)
    } catch {
      setError('Sharhlar yuklanmadi.')
    } finally {
      setLoading(false)
    }
  }, [slug, applyMyReview])

  const loadMore = useCallback(async () => {
    if (!slug || !hasMore || loadingMore) return
    const nextPage = page + 1
    setLoadingMore(true)
    setError(null)
    try {
      const { response, data } = await getReviews(slug, nextPage)
      if (!response.ok || !data) {
        setError('Sharhlar yuklanmadi.')
        return
      }
      setReviews((prev) => {
        const seen = new Set(prev.map((r) => r.id))
        const appended = data.results.filter((r) => !seen.has(r.id))
        return [...prev, ...appended]
      })
      setCount(data.count)
      setAverageRating(data.average_rating)
      setPage(data.pagination?.page ?? nextPage)
      setHasMore(Boolean(data.pagination?.has_next))
      if (data.my_review !== undefined) {
        setMyReview(data.my_review)
      }
    } catch {
      setError('Sharhlar yuklanmadi.')
    } finally {
      setLoadingMore(false)
    }
  }, [slug, hasMore, loadingMore, page])

  useEffect(() => {
    if (!ready || !slug) {
      if (!slug) setLoading(false)
      return
    }
    void reload()
  }, [ready, slug, reload])

  const clearFormFeedback = useCallback(() => {
    setFormStatus('idle')
    setFormError(null)
  }, [])

  const submitReview = useCallback(
    async (rating: number, text: string, mode: 'create' | 'update') => {
      if (!slug) return false
      if (!rating) {
        setFormError('Iltimos, yulduz baholashni tanlang.')
        return false
      }
      setFormStatus('saving')
      setFormError(null)
      try {
        const payload = { rating, text: text.trim() }
        const fn = mode === 'update' ? updateReview : createReview
        const { response, data } = await fn(slug, payload)
        if (!response.ok) {
          const msg =
            data && typeof data === 'object' && 'detail' in data
              ? String((data as { detail?: string }).detail || 'Sharh saqlanmadi.')
              : 'Sharh saqlanmadi.'
          setFormError(msg)
          setFormStatus('error')
          return false
        }
        setFormStatus('saved')
        await reload()
        window.setTimeout(() => setFormStatus('idle'), 2000)
        return true
      } catch {
        setFormStatus('error')
        setFormError('Tarmoq xatoligi yuz berdi.')
        return false
      }
    },
    [slug, reload],
  )

  const submitRating = useCallback(
    async (rating: number, text?: string) => {
      if (!slug || !isAuthenticated) return false
      const existing = myReview
      const preserved =
        text !== undefined ? text : existing?.text != null ? existing.text : ''
      return submitReview(rating, preserved, existing ? 'update' : 'create')
    },
    [slug, isAuthenticated, myReview, submitReview],
  )

  const removeReview = useCallback(async () => {
    if (!slug) return false
    setFormStatus('saving')
    try {
      const { response } = await deleteReview(slug)
      if (!response.ok) {
        setFormStatus('error')
        return false
      }
      setMyReview(null)
      setFormStatus('idle')
      await reload()
      return true
    } catch {
      setFormStatus('error')
      setFormError("Sharhni o‘chirib bo‘lmadi.")
      return false
    }
  }, [slug, reload])

  return {
    reviews,
    count,
    averageRating,
    loading,
    loadingMore,
    hasMore,
    error,
    myReview,
    formStatus,
    formError,
    isAuthenticated,
    ready,
    reload,
    loadMore,
    submitRating,
    submitReview,
    removeReview,
    clearFormFeedback,
  }
}
