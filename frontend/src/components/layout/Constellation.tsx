import { useEffect, useRef } from 'react'

type PaletteKey = 'default' | 'brand'

type Palette = {
  node: string
  line: string
  accent: string
}

type Point = {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  accent: boolean
}

const PALETTES: Record<PaletteKey, Palette> = {
  default: {
    node: 'rgba(180, 200, 220, 0.7)',
    line: 'rgba(120, 160, 200,',
    accent: 'rgba(120, 220, 150, 0.9)',
  },
  /** Libro.UZ brand — lime / green accents from --lime / --grad */
  brand: {
    node: 'rgba(214, 255, 69, 0.55)',
    line: 'rgba(79, 224, 138,',
    accent: 'rgba(214, 255, 69, 0.95)',
  },
}

export type ConstellationProps = {
  palette?: PaletteKey
}

/**
 * Port of users/js/constellation.js as a React effect on a canvas ref.
 */
export default function Constellation({ palette = 'default' }: ConstellationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || typeof canvas.getContext !== 'function') return undefined

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const maybeCtx = canvas.getContext('2d')
    if (!maybeCtx) return undefined
    // Locals with non-null types so nested effect closures type-check.
    const surface: HTMLCanvasElement = canvas
    const ctx: CanvasRenderingContext2D = maybeCtx
    const COLORS = PALETTES[palette] ?? PALETTES.default

    let width = 0
    let height = 0
    let dpr = 1
    let points: Point[] = []
    let animationId: number | null = null
    const pointer = { x: -9999, y: -9999 }

    function pointCount() {
      return Math.min(110, Math.max(36, Math.round((width * height) / 16000)))
    }

    function createPoints() {
      const count = pointCount()
      points = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.28,
        vy: (Math.random() - 0.5) * 0.28,
        r: Math.random() * 1.4 + 0.6,
        accent: Math.random() < 0.12,
      }))
    }

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = window.innerWidth
      height = window.innerHeight
      surface.width = Math.floor(width * dpr)
      surface.height = Math.floor(height * dpr)
      surface.style.width = `${width}px`
      surface.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      createPoints()
    }

    function draw() {
      ctx.clearRect(0, 0, width, height)
      const linkDistance = width < 640 ? 110 : 150

      for (let i = 0; i < points.length; i += 1) {
        const p = points[i]!
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0 || p.x > width) p.vx *= -1
        if (p.y < 0 || p.y > height) p.vy *= -1

        const pdx = pointer.x - p.x
        const pdy = pointer.y - p.y
        const pDist = Math.hypot(pdx, pdy)
        if (pDist < 160 && pDist > 0.5) {
          p.x += (pdx / pDist) * 0.25
          p.y += (pdy / pDist) * 0.25
        }

        for (let j = i + 1; j < points.length; j += 1) {
          const q = points[j]!
          const dx = p.x - q.x
          const dy = p.y - q.y
          const dist = Math.hypot(dx, dy)
          if (dist < linkDistance) {
            const alpha = (1 - dist / linkDistance) * 0.55
            ctx.strokeStyle = `${COLORS.line} ${alpha})`
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.moveTo(p.x, p.y)
            ctx.lineTo(q.x, q.y)
            ctx.stroke()
          }
        }

        ctx.fillStyle = p.accent ? COLORS.accent : COLORS.node
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fill()
      }

      animationId = window.requestAnimationFrame(draw)
    }

    function renderStatic() {
      ctx.clearRect(0, 0, width, height)
      points.forEach((p) => {
        ctx.fillStyle = p.accent ? COLORS.accent : COLORS.node
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fill()
      })
    }

    function start() {
      if (reduceMotion) {
        renderStatic()
        return
      }
      if (animationId === null) draw()
    }

    function stop() {
      if (animationId !== null) {
        window.cancelAnimationFrame(animationId)
        animationId = null
      }
    }

    let resizeTimer: number | null = null
    const onResize = () => {
      if (resizeTimer !== null) window.clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(() => {
        resize()
        if (reduceMotion) renderStatic()
      }, 150)
    }
    const onPointerMove = (event: PointerEvent) => {
      pointer.x = event.clientX
      pointer.y = event.clientY
    }
    const onPointerLeave = () => {
      pointer.x = -9999
      pointer.y = -9999
    }
    const onVisibility = () => {
      if (document.hidden) stop()
      else start()
    }

    window.addEventListener('resize', onResize)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerleave', onPointerLeave)
    document.addEventListener('visibilitychange', onVisibility)

    resize()
    start()

    return () => {
      stop()
      if (resizeTimer !== null) window.clearTimeout(resizeTimer)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerleave', onPointerLeave)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [palette])

  return (
    <canvas
      id={palette === 'brand' ? 'constellation-dash' : 'constellation'}
      ref={canvasRef}
      className="constellation"
      aria-hidden="true"
    />
  )
}

