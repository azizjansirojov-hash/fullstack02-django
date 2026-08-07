import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../api/notifications'
import type { Notification } from '../../types'
import { BellIcon } from './sidebarIcons'

export type SidebarNotificationsProps = {
  user: { id: number; username: string } | null | undefined
  open: boolean
  onToggle: () => void
  onCloseMobile?: () => void
}

/**
 * Bell control + notifications popover for AppSidebar.
 */
export default function SidebarNotifications({
  user,
  open,
  onToggle,
  onCloseMobile,
}: SidebarNotificationsProps) {
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifError, setNotifError] = useState<string | null>(null)

  async function loadNotifications() {
    if (!user) {
      setNotifications([])
      setUnreadCount(0)
      setNotifError(null)
      return
    }
    try {
      const { response, data } = await fetchNotifications()
      if (response.ok && data) {
        setNotifications(data.results)
        setUnreadCount(data.unread_count)
        setNotifError(null)
      } else {
        setNotifError("Bildirishnomalarni yuklab bo‘lmadi.")
      }
    } catch {
      setNotifError("Bildirishnomalarni yuklab bo‘lmadi.")
    }
  }

  useEffect(() => {
    void loadNotifications()
  }, [user])

  useEffect(() => {
    if (open) void loadNotifications()
  }, [open])

  async function handleNotificationClick(notification: Notification) {
    if (!notification.is_read) {
      try {
        const { response } = await markNotificationRead(notification.id)
        if (response.ok) {
          setNotifications((items) =>
            items.map((item) =>
              item.id === notification.id ? { ...item, is_read: true } : item,
            ),
          )
          setUnreadCount((count) => Math.max(0, count - 1))
          setNotifError(null)
        } else {
          setNotifError("Bildirishnomani o‘qilgan deb belgilab bo‘lmadi.")
        }
      } catch {
        setNotifError("Bildirishnomani o‘qilgan deb belgilab bo‘lmadi.")
      }
    }
    onToggle()
    if (notification.link_url) {
      navigate(notification.link_url)
      onCloseMobile?.()
    }
  }

  async function handleMarkAllNotificationsRead() {
    try {
      const { response } = await markAllNotificationsRead()
      if (response.ok) {
        setNotifications((items) => items.map((item) => ({ ...item, is_read: true })))
        setUnreadCount(0)
        setNotifError(null)
      } else {
        setNotifError("Bildirishnomalarni yangilab bo‘lmadi.")
      }
    } catch {
      setNotifError("Bildirishnomalarni yangilab bo‘lmadi.")
    }
  }

  return (
    <div className="sidebar__control">
      <button
        type="button"
        className={`sidebar__row${open ? ' is-open' : ''}`}
        onClick={onToggle}
        title="Bildirishnomalar"
        aria-expanded={open}
      >
        <BellIcon />
        <span className="sidebar__row-label">Bildirishnomalar</span>
        {unreadCount > 0 ? (
          <span className="sidebar__notification-badge" aria-label={`${unreadCount} ta o‘qilmagan bildirishnoma`}>
            {unreadCount}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="sidebar__popover sidebar__popover--notif" role="dialog" aria-label="Bildirishnomalar">
          <div className="sidebar__popover-heading">
            <p className="sidebar__popover-title">Bildirishnomalar</p>
            {unreadCount > 0 ? (
              <button type="button" className="sidebar__mark-all" onClick={() => void handleMarkAllNotificationsRead()}>
                Barchasini o‘qilgan deb belgilash
              </button>
            ) : null}
          </div>
          {notifError ? (
            <p className="sidebar__popover-empty" role="alert">
              {notifError}
            </p>
          ) : null}
          {notifications.length ? (
            <div className="sidebar__notification-list">
              {notifications.map((notification) => (
                <button
                  key={notification.id}
                  type="button"
                  className={`sidebar__notification${notification.is_read ? '' : ' is-unread'}`}
                  onClick={() => void handleNotificationClick(notification)}
                >
                  {notification.message}
                </button>
              ))}
            </div>
          ) : (
            <p className="sidebar__popover-empty">
              Hozircha bildirishnomalar yo‘q.
            </p>
          )}
        </div>
      ) : null}
    </div>
  )
}
