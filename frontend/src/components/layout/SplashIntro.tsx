import { useEffect, useRef, useState } from 'react'
import NightWaterCanvas from './NightWaterCanvas'
import Logo from './Logo'
import '../../assets/css/splash.css'

const FONT_TIMEOUT_MS = 1200
/** Full cinematic duration before fade-out (ms). */
const DURATION_MS = 3500
const REDUCED_HOLD_MS = 400
const FADE_MS = 400
/** Ignore accidental Skip/Escape right after mount. */
const SKIP_GUARD_MS = 400

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

async function waitForFonts(): Promise<void> {
  const fontsReady = document.fonts?.ready ?? Promise.resolve()
  await Promise.race([
    fontsReady,
    new Promise<void>((resolve) => {
      window.setTimeout(resolve, FONT_TIMEOUT_MS)
    }),
  ])
}

export type SplashIntroProps = {
  onComplete?: () => void
}

/**
 * Cinematic intro — night water + star reflections, ~3.5s on app entry.
 */
export default function SplashIntro({ onComplete }: SplashIntroProps) {
  const [progress, setProgress] = useState(0)
  const [fading, setFading] = useState(false)
  const onCompleteRef = useRef(onComplete)
  const completedRef = useRef(false)
  const mountedAtRef = useRef(0)
  const timersRef = useRef<number[]>([])
  const rafRef = useRef(0)

  onCompleteRef.current = onComplete

  useEffect(() => {
    mountedAtRef.current = performance.now()
    completedRef.current = false
    let cancelled = false

    const clearTimers = () => {
      timersRef.current.forEach((id) => window.clearTimeout(id))
      timersRef.current = []
      cancelAnimationFrame(rafRef.current)
    }

    const finish = () => {
      if (cancelled || completedRef.current) return
      completedRef.current = true
      setProgress(100)
      setFading(true)
      const fadeId = window.setTimeout(() => {
        onCompleteRef.current?.()
      }, FADE_MS)
      timersRef.current.push(fadeId)
    }

    async function run() {
      await waitForFonts()
      if (cancelled) return

      if (prefersReducedMotion()) {
        setProgress(100)
        const holdId = window.setTimeout(finish, REDUCED_HOLD_MS)
        timersRef.current.push(holdId)
        return
      }

      const start = performance.now()

      const tick = (now: number) => {
        if (cancelled || completedRef.current) return
        const t = Math.min(1, (now - start) / DURATION_MS)
        const eased = 1 - (1 - t) ** 3
        setProgress(Math.round(eased * 100))
        if (t < 1) {
          rafRef.current = requestAnimationFrame(tick)
        } else {
          finish()
        }
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    void run()

    return () => {
      cancelled = true
      clearTimers()
    }
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (performance.now() - mountedAtRef.current < SKIP_GUARD_MS) return
      event.preventDefault()
      if (completedRef.current) return
      completedRef.current = true
      setProgress(100)
      setFading(true)
      const fadeId = window.setTimeout(() => {
        onCompleteRef.current?.()
      }, FADE_MS)
      timersRef.current.push(fadeId)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  function handleSkip() {
    if (performance.now() - mountedAtRef.current < SKIP_GUARD_MS) return
    if (completedRef.current) return
    completedRef.current = true
    setProgress(100)
    setFading(true)
    const fadeId = window.setTimeout(() => {
      onCompleteRef.current?.()
    }, FADE_MS)
    timersRef.current.push(fadeId)
  }

  return (
    <div
      className={`splash${fading ? ' splash--fade' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-label="Libro.UZ kirish"
    >
      <NightWaterCanvas />

      <button type="button" className="splash__skip" onClick={handleSkip}>
        Skip
      </button>

      <div className="splash__title">
        <Logo size="lg" />
      </div>

      <div className="splash__loader" aria-hidden={false}>
        <div
          className="splash__progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          aria-label="Yuklanish"
        >
          <div className="splash__track">
            <div className="splash__fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="splash__percent">{progress}%</span>
        </div>
      </div>
    </div>
  )
}
