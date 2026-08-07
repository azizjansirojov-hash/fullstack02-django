import type { ReactElement } from 'react'

export function HomeIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

export function GridIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="4" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

export function CartIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3.5 5h1.8l1.4 10.2a1.5 1.5 0 0 0 1.5 1.3h8.6a1.5 1.5 0 0 0 1.5-1.2L19.5 8H7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="10" cy="19" r="1.2" fill="currentColor" />
      <circle cx="16.5" cy="19" r="1.2" fill="currentColor" />
    </svg>
  )
}

export function LibraryIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M5 5.5h4v13H5zM10.5 5.5h4v13h-4zM16 6.2l3.5-.9v13l-3.5.9V6.2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

export function BellIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 4a5 5 0 0 0-5 5v2.2c0 .7-.2 1.4-.6 2L5 16h14l-1.4-2.8a3.8 3.8 0 0 1-.6-2V9a5 5 0 0 0-5-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M10 18a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function GlobeIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4.5 12h15M12 4c2.5 2.8 2.5 12.2 0 16M12 4c-2.5 2.8-2.5 12.2 0 16" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

export function MoonIcon() {
  return (
    <svg className="sidebar__link-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M16.5 3.5A8.5 8.5 0 1 0 20.5 14 7 7 0 0 1 16.5 3.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

export function GearIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" stroke="currentColor" strokeWidth="1.6" />
      <path d="M19.4 12a7.4 7.4 0 0 0-.1-1l1.6-1.2-1.5-2.6-1.9.6a7.7 7.7 0 0 0-1.7-1L15.5 4h-3l-.3 2.1a7.7 7.7 0 0 0-1.7 1l-1.9-.6L7 9.8 8.6 11a7.4 7.4 0 0 0 0 2l-1.6 1.2 1.5 2.6 1.9-.6c.5.4 1.1.7 1.7 1L12.5 20h3l.3-2.1c.6-.3 1.2-.6 1.7-1l1.9.6 1.5-2.6-1.6-1.2c.1-.3.1-.7.1-1Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  )
}

export function ChevronIcon({ expand }: { expand: boolean }): ReactElement {
  return (
    <svg
      className={`sidebar__collapse-icon${expand ? ' is-expand' : ''}`}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <path d="M14.5 5.5 8 12l6.5 6.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
