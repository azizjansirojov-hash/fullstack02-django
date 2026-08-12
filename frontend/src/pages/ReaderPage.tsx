import { Link, Navigate, useLocation, useParams, useSearchParams } from 'react-router'
import { useEffect, useState } from 'react'
import { fetchBookReaderManifest } from '../api/library'
import FlipReaderView from '../components/reader/FlipReaderView'
import PdfReaderMode from '../components/reader/PdfReaderMode'
import type { ReaderManifest } from '../types/library'
import '../assets/css/library.css'
import '../assets/css/reader-shell.css'
import '../assets/css/reader-audio.css'
import '../assets/css/reader-pdf.css'
import '../assets/css/reader-flip.css'

function isReaderManifest(data: unknown): data is ReaderManifest {
  return (
    typeof data === 'object' &&
    data !== null &&
    'slug' in data &&
    typeof data.slug === 'string' &&
    'body' in data &&
    typeof data.body === 'string'
  )
}

/**
 * React immersive reader — flip (2B), PDF (2A), listen (2C).
 */
export default function ReaderPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const [manifest, setManifest] = useState<ReaderManifest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const mode = searchParams.get('mode') === 'pdf' ? 'pdf' : 'flip'
  const autoplay = location.hash.includes('autoplay=1')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setManifest(null)

    ;(async () => {
      try {
        const { response, data } = await fetchBookReaderManifest(slug)
        if (cancelled) return
        if (response.status === 403) {
          setError('forbidden')
          return
        }
        if (!response.ok) {
          setError(
            response.status === 404
              ? 'Bu kitobda hali o‘qiladigan kontent yo‘q.'
              : `Kitob yuklanmadi (${response.status})`,
          )
          return
        }
        if (!isReaderManifest(data)) {
          setError(
            typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string'
              ? data.detail
              : 'Kitob manifesti yaroqsiz.',
          )
          return
        }
        setManifest(data)
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Network error')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [slug])

  if (loading) {
    return (
      <div className="reader-shell reader-shell--loading" lang="uz">
        <p className="reader-shell__status">Kitob yuklanmoqda…</p>
      </div>
    )
  }

  if (error === 'forbidden') {
    return <Navigate to={`/library/${encodeURIComponent(slug)}`} replace />
  }

  if (error || !manifest) {
    return (
      <section className="library-empty reader-shell">
        <div className="library-empty__panel">
          <h1 className="library-empty__title">O‘qish mumkin emas</h1>
          <p className="library-empty__copy">{error || 'Noma’lum xato'}</p>
          <Link className="library-empty__cta" to={`/library/${encodeURIComponent(slug)}`}>
            Kitob sahifasiga qaytish
          </Link>
        </div>
      </section>
    )
  }

  const showPdf = mode === 'pdf' && manifest.has_pdf && manifest.pdf_url

  return (
    <div className="reader-shell reader-shell--reader" lang="uz" data-reader-mode={mode}>
      {showPdf ? (
        <PdfReaderMode slug={slug} manifest={manifest} />
      ) : mode === 'pdf' ? (
        <main className="reader-shell__stage">
          <p className="reader-shell__copy">PDF mavjud emas yoki tayyor emas.</p>
          <Link className="reader-shell__back" to={manifest.detail_url || `/library/${slug}/`}>
            ← Kitob sahifasiga
          </Link>
        </main>
      ) : (
        <FlipReaderView slug={slug} manifest={manifest} autoplay={autoplay} />
      )}
    </div>
  )
}

