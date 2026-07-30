/**
 * Libro.UZ vertical lockup: gradient book icon + wordmark (app --grad tokens).
 * size: "sm" (header/sidebar) | "lg" (splash)
 */
export type LogoProps = {
  size?: 'sm' | 'lg'
  className?: string
}

export default function Logo({ size = 'sm', className = '' }: LogoProps) {
  const isLg = size === 'lg'
  const gradId = `libro-logo-grad-${size}`

  return (
    <span
      className={`brand-lockup brand-lockup--${size}${className ? ` ${className}` : ''}`}
      aria-hidden="true"
    >
      <svg
        className="brand-lockup__icon"
        viewBox="0 0 64 64"
        width={isLg ? 96 : 28}
        height={isLg ? 96 : 28}
        role="img"
        focusable="false"
      >
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#e4ff54" />
            <stop offset="55%" stopColor="#4fe08a" />
            <stop offset="100%" stopColor="#2fd39b" />
          </linearGradient>
        </defs>
        <path
          fill={`url(#${gradId})`}
          d="M6.5 14c0-1.7 1.1-3.1 2.8-3.4 4-.8 9.2-1.6 14.2-1.6 2 0 3.5 1.5 3.5 3.5v31.5c0 2.4-1.6 4.5-3.9 5.1-4 1.1-9.1 2.1-14.1 1.3-1.7-.3-2.9-1.8-2.9-3.5V14z"
        />
        <path
          fill={`url(#${gradId})`}
          d="M57.5 14c0-1.7-1.1-3.1-2.8-3.4-4-.8-9.2-1.6-14.2-1.6-2 0-3.5 1.5-3.5 3.5v31.5c0 2.4 1.6 4.5 3.9 5.1 4 1.1 9.1 2.1 14.1 1.3 1.7-.3 2.9-1.8 2.9-3.5V14z"
        />
      </svg>
      <span className="brand-lockup__wordmark">
        Libro<span className="brand-lockup__dot">.</span>UZ
      </span>
    </span>
  )
}
