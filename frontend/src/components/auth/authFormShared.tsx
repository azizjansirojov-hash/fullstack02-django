/** Shared helpers for login / register form UI. */

export function firstErrorMessage(value: unknown): string {
  if (Array.isArray(value)) return firstErrorMessage(value[0])
  if (value && typeof value === 'object') {
    return firstErrorMessage(Object.values(value)[0])
  }
  return typeof value === 'string' ? value : 'Something went wrong. Please try again.'
}

export function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.5" />
    </svg>
  )
}
