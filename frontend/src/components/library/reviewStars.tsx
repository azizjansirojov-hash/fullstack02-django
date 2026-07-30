import { useState, type KeyboardEvent } from 'react'

export type StarsDisplayProps = {
  rating: number
  max?: number
  /** When true, show half-star for fractional averages (e.g. 4.3 → 4 filled + half). */
  allowHalf?: boolean
  className?: string
  size?: 'sm' | 'md'
}

/**
 * Read-only star display for aggregate averages.
 */
export function StarsDisplay({
  rating,
  max = 5,
  allowHalf = false,
  className = '',
  size = 'md',
}: StarsDisplayProps) {
  const clamped = Math.max(0, Math.min(max, Number(rating) || 0))
  const rounded = allowHalf ? Math.round(clamped * 2) / 2 : Math.round(clamped)

  return (
    <span
      className={`review-stars review-stars--${size}${className ? ` ${className}` : ''}`}
      aria-label={`${clamped.toFixed(1)} yulduz`}
    >
      {Array.from({ length: max }, (_, i) => {
        const n = i + 1
        let fill: 'empty' | 'half' | 'full' = 'empty'
        if (rounded >= n) fill = 'full'
        else if (allowHalf && rounded >= n - 0.5) fill = 'half'
        return (
          <span
            key={n}
            className={`review-stars__star${fill === 'full' ? ' is-filled' : ''}${fill === 'half' ? ' is-half' : ''}`}
            aria-hidden="true"
          >
            ★
          </span>
        )
      })}
    </span>
  )
}

export type InteractiveStarRatingProps = {
  value: number
  onChange: (rating: number) => void
  disabled?: boolean
  /** When true, guest clicks call onRequireAuth instead of onChange. */
  requireAuth?: boolean
  onRequireAuth?: () => void
  busy?: boolean
  className?: string
  'aria-label'?: string
}

/**
 * Keyboard- and mouse-operable 5-star rating control with brief select animation.
 */
export function InteractiveStarRating({
  value,
  onChange,
  disabled = false,
  requireAuth = false,
  onRequireAuth,
  busy = false,
  className = '',
  'aria-label': ariaLabel = 'Baholash',
}: InteractiveStarRatingProps) {
  const [hovered, setHovered] = useState(0)
  const [animating, setAnimating] = useState(0)
  const display = hovered || value

  function select(n: number) {
    if (disabled || busy) return
    if (requireAuth) {
      onRequireAuth?.()
      return
    }
    setAnimating(n)
    onChange(n)
    window.setTimeout(() => setAnimating(0), 220)
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled || busy) return
    const current = value || 0
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
      event.preventDefault()
      select(Math.min(5, current + 1 || 1))
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
      event.preventDefault()
      select(Math.max(1, current - 1))
    } else if (event.key === 'Home') {
      event.preventDefault()
      select(1)
    } else if (event.key === 'End') {
      event.preventDefault()
      select(5)
    }
  }

  return (
    <div
      className={`star-picker star-picker--interactive${className ? ` ${className}` : ''}`}
      role="radiogroup"
      aria-label={ariaLabel}
      aria-disabled={disabled || busy}
      onKeyDown={onKeyDown}
      onMouseLeave={() => setHovered(0)}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          className={`star-picker__btn${display >= n ? ' is-active' : ''}${animating === n ? ' is-pop' : ''}`}
          aria-label={`${n} yulduz bilan baholash`}
          aria-checked={value === n}
          disabled={disabled || busy}
          tabIndex={value === n || (value === 0 && n === 1) ? 0 : -1}
          onClick={(e) => {
            e.stopPropagation()
            select(n)
          }}
          onMouseEnter={() => setHovered(n)}
          onFocus={() => setHovered(n)}
        >
          ★
        </button>
      ))}
    </div>
  )
}
