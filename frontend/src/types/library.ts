/**
 * Library API shapes — derived from backend/library/api_views.py serializers
 * and Book.get_audio_chapters_payload / ReadingProgress model choices.
 * Do not “fix” frontend assumptions here; keep the wire format accurate.
 */

/** ReadingProgress.Status */
export type ReadingStatus = 'planned' | 'reading' | 'finished'

/** ReadingProgress.Mode */
export type ReadingMode = 'flip' | 'pdf' | 'listen'

/**
 * Book.get_audio_chapters_payload — `id` is null for the legacy single-file
 * audio fallback row (no AudioChapter).
 */
export type AudioChapter = {
  id: number | null
  title: string
  url: string
  order: number
  duration_seconds: number | null
}

/**
 * serialize_book_card — base shelf/card fields.
 * `reading_status` is NOT on the base card; see BookCardWithStatus / ProgressCard.
 */
export type BookCard = {
  slug: string
  author_name: string
  category: string
  category_label: string
  published_year: number | null
  cover_url: string
  has_pdf: boolean
  has_audio: boolean
  has_access: boolean
  rights_status: string
  /** Global catalog price in tiyin when payments enabled; else null. */
  book_price_tiyin?: number | null
  /** Licensed + authenticated + no access — show checkout. */
  is_purchasable?: boolean
  pdf_generation_status: string
  audio_generation_status: string
  pdf_url: string
  read_url: string
  audio_url: string
  audio_duration_seconds: number | null
  title: string
  summary: string
  /** Present on annotated catalog / continue_reading cards. */
  average_rating?: number | null
  review_count?: number
}

/**
 * _card_with_status — authenticated catalog/shelf cards add reading_status
 * (value may be null when the user has no progress row for that book).
 * Anonymous responses omit the key entirely.
 */
export type BookCardWithStatus = BookCard & {
  reading_status?: ReadingStatus | null
}

/**
 * serialize_progress_payload — always exists: true.
 * DRF JSON-encodes updated_at as an ISO-8601 string.
 */
export type ProgressPayload = {
  exists: true
  status: ReadingStatus
  mode: ReadingMode
  page: number
  total_pages: number | null
  chapter_id: number | null
  position: number
  updated_at: string
}

/** GET progress when no row exists; also DELETE planned success / empty delete. */
export type ProgressMissing = {
  exists: false
  status: null
}

export type ProgressGetResponse = ProgressPayload | ProgressMissing

/**
 * Nested progress on serialize_progress_card (My Library / continue_reading).
 * Includes audio_duration_seconds + status; not identical to ProgressPayload.
 */
export type ProgressCardProgress = {
  mode: ReadingMode
  page: number
  total_pages: number | null
  chapter_id: number | null
  position: number
  updated_at: string
  audio_duration_seconds: number | null
  status: ReadingStatus
}

/** serialize_progress_card */
export type ProgressCard = BookCard & {
  reading_status: ReadingStatus
  progress: ProgressCardProgress
}

export type CatalogCategoryGroup = {
  code: string
  label: string
  count: number
  items: BookCardWithStatus[]
}

export type CatalogPagination = {
  page: number
  num_pages: number
  has_previous: boolean
  has_next: boolean
  previous_page: number | null
  next_page: number | null
}

export type CatalogUser = {
  id: number
  username: string
  is_staff: boolean
}

/** CatalogAPIView.get */
export type ActivityBadge = {
  id: string
  kind: 'streak' | 'finished_month' | string
  value: number
  label: string
}

export type ActivityStats = {
  today_minutes_read: number
  daily_goal_minutes: number
  goal_progress_percent: number
  week_minutes_total: number
  week_pages_total: number
  /** Server SSOT streak; prefer over client computeStreak when present. */
  current_streak_days?: number
  /** Absolute next Keyingi marra target (e.g. 7), or null past the last. */
  next_milestone_days?: number | null
  badges: ActivityBadge[]
}

export type CatalogResponse = {
  query: string
  category: string
  is_empty: boolean
  can_read: boolean
  shelf: BookCardWithStatus[]
  category_lists: CatalogCategoryGroup[]
  continue_reading: ProgressCard[]
  activity_timestamps: string[]
  activity_stats: ActivityStats | null
  pagination: CatalogPagination
  user: CatalogUser | null
}

/** MyLibraryAPIView.get */
export type MyLibraryResponse = {
  counts: {
    reading: number
    planned: number
    finished: number
  }
  can_read: boolean
  reading: ProgressCard[]
  planned: ProgressCard[]
  finished: ProgressCard[]
}

/** A single user review. */
export type ReviewItem = {
  id: number
  username: string
  rating: number
  text: string
  created_at: string
  updated_at: string
}

/** GET /api/library/<slug>/reviews/ response. */
export type ReviewsResponse = {
  count: number
  average_rating: number | null
  results: ReviewItem[]
  pagination: CatalogPagination
  /** Present when the request is authenticated. */
  my_review?: ReviewItem | null
}

/**
 * BookDetailAPIView.get — serialize_book_card + extras.
 * Note: does NOT include body, why_read, or audio_sync (those are on the manifest).
 */
export type BookDetailResponse = BookCard & {
  can_read: boolean
  has_access: boolean
  audio_chapters: AudioChapter[]
  summary: string
  reading_status: ReadingStatus | null
  average_rating: number | null
  review_count: number
  similar_books: BookCard[]
}

/** Manifest reading_progress field (payload or empty). */
export type ManifestReadingProgress = ProgressPayload | ProgressMissing

/**
 * BookReaderManifestAPIView.get — success body only.
 * 403/404 return { detail: string } instead (see ApiErrorDetail).
 */
export type ReaderManifest = {
  slug: string
  title: string
  author_name: string
  category: string
  category_label: string
  published_year: number | null
  body: string
  /** BookTranslation.audio_sync JSON list; row shape validated loosely server-side. */
  audio_sync: AudioSyncCue[]
  audio_chapters: AudioChapter[]
  pdf_url: string
  audio_url: string
  has_access: true
  has_pdf: boolean
  has_audio: boolean
  sentence_wrap: boolean
  read_url: string
  detail_url: string
  reading_progress: ManifestReadingProgress
}

/** Typical audio_sync row keys used by the reader (server allows flexible dicts). */
export type AudioSyncCue = {
  start?: number
  end?: number
  index?: number
  text?: string
  [key: string]: unknown
}

/** PUT/POST /progress/ body — fields accepted by ReadingProgressAPIView._upsert */
export type ProgressUpsertBody = {
  mode?: ReadingMode | string
  page?: number
  total_pages?: number | null
  chapter_id?: number | null
  position?: number
  reopen?: boolean
  status?: ReadingStatus | string
  clear_audio?: boolean
}

/** PUT /status/ body */
export type ReadingStatusPutBody = {
  status: ReadingStatus
}

export type ApiErrorDetail = {
  detail: string
}

/**
 * Shelf / launch UI prop: catalog card fields plus optional nested progress.
 * Catalog `BookCardWithStatus` has no `progress`; ProgressCard / continue heroes do.
 * Components that read `book.progress?.status` must treat progress as optional.
 */
export type LibraryBookView = BookCardWithStatus & {
  progress?: ProgressCardProgress | null
}
