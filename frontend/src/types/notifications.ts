/** Notification API payloads. */
export type Notification = {
  id: number
  message: string
  type: 'audio_ready' | 'purchase_paid' | 'purchase_refunded'
  is_read: boolean
  link_url: string
  book_slug: string | null
  created_at: string
}

export type NotificationsResponse = {
  count: number
  next: string | null
  previous: string | null
  unread_count: number
  results: Notification[]
}
