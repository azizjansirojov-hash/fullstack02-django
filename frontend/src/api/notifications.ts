import { apiFetch } from './client'
import type { Notification, NotificationsResponse } from '../types'

export async function fetchNotifications(page = 1) {
  return apiFetch<NotificationsResponse>(`/api/notifications/?page=${page}`)
}

export async function markNotificationRead(notificationId: number) {
  return apiFetch<Notification>(`/api/notifications/${notificationId}/read/`, {
    method: 'POST',
  })
}

export async function markAllNotificationsRead() {
  return apiFetch<{ unread_count: number }>('/api/notifications/read-all/', {
    method: 'POST',
  })
}
