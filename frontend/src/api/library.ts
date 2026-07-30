import type {
  BookDetailResponse,
  MyLibraryResponse,
  CatalogResponse,
  ProgressGetResponse,
  ProgressPayload,
  ProgressUpsertBody,
  ReaderManifest,
  ReadingStatus,
  ApiErrorDetail,
  ReviewItem,
  ReviewsResponse,
} from '../types/library'
import { apiFetch } from './client'

export async function fetchCatalog({
  q = '',
  category = '',
  page = 1,
}: { q?: string; category?: string; page?: number } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (category) params.set('category', category)
  if (page && page !== 1) params.set('page', String(page))
  const qs = params.toString()
  return apiFetch<CatalogResponse>(`/api/library/${qs ? `?${qs}` : ''}`)
}

export async function fetchMyLibrary({ status }: { status?: ReadingStatus | string } = {}) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  const qs = params.toString()
  return apiFetch<MyLibraryResponse>(`/api/library/my/${qs ? `?${qs}` : ''}`)
}

export async function fetchBookDetail(slug: string) {
  return apiFetch<BookDetailResponse>(`/api/library/${encodeURIComponent(slug)}/`)
}

export async function fetchBookReaderManifest(slug: string) {
  return apiFetch<ReaderManifest | ApiErrorDetail>(
    `/api/library/${encodeURIComponent(slug)}/reader/`,
  )
}

export async function getReadingProgress(slug: string) {
  return apiFetch<ProgressGetResponse>(
    `/api/library/${encodeURIComponent(slug)}/progress/`,
  )
}

export async function saveReadingProgress(slug: string, payload: ProgressUpsertBody) {
  return apiFetch<ProgressPayload>(`/api/library/${encodeURIComponent(slug)}/progress/`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function setReadingStatus(slug: string, status: ReadingStatus | string) {
  return apiFetch<ProgressPayload>(`/api/library/${encodeURIComponent(slug)}/status/`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  })
}

export async function removePlanned(slug: string) {
  return apiFetch<ProgressGetResponse | ApiErrorDetail>(
    `/api/library/${encodeURIComponent(slug)}/status/`,
    {
      method: 'DELETE',
    },
  )
}

export async function getReviews(slug: string) {
  return apiFetch<ReviewsResponse>(`/api/library/${encodeURIComponent(slug)}/reviews/`)
}

export async function createReview(
  slug: string,
  payload: { rating: number; text?: string },
) {
  return apiFetch<ReviewItem>(`/api/library/${encodeURIComponent(slug)}/reviews/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateReview(
  slug: string,
  payload: { rating: number; text?: string },
) {
  return apiFetch<ReviewItem>(`/api/library/${encodeURIComponent(slug)}/reviews/`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteReview(slug: string) {
  return apiFetch<null>(`/api/library/${encodeURIComponent(slug)}/reviews/`, {
    method: 'DELETE',
  })
}
