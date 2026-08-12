import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { fetchPaymentTransaction, type TransactionStatusResponse } from '../api/payments'
import '../assets/css/library.css'

const TERMINAL = new Set(['paid', 'failed', 'cancelled'])
const POLL_MS = 2500

/**
 * Post-gateway return page — polls transaction status until terminal.
 */
export default function PaymentStatusPage() {
  const { transactionId = '' } = useParams<{ transactionId: string }>()
  const [tx, setTx] = useState<TransactionStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'To‘lov holati · Libro.UZ'
  }, [])

  useEffect(() => {
    if (!transactionId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    async function poll() {
      try {
        const { response, data } = await fetchPaymentTransaction(transactionId)
        if (cancelled) return
        if (!response.ok || !data) {
          setError(
            response.status === 404
              ? 'To‘lov topilmadi.'
              : `Holat yuklanmadi (${response.status})`,
          )
          return
        }
        setTx(data)
        setError(null)
        if (!TERMINAL.has(data.status)) {
          timer = setTimeout(poll, POLL_MS)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Tarmoq xatosi')
          timer = setTimeout(poll, POLL_MS * 2)
        }
      }
    }

    poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [transactionId])

  const status = tx?.status
  const bookHref = tx?.book_slug ? `/library/${tx.book_slug}` : '/library'

  return (
    <main className="payment-status" style={{ maxWidth: 480, margin: '3rem auto', padding: '0 1rem' }}>
      <h1>To‘lov holati</h1>
      {error ? <p role="alert">{error}</p> : null}
      {!error && !tx ? <p>Tekshirilmoqda…</p> : null}
      {tx ? (
        <>
          <p>
            Holat: <strong>{status}</strong>
            {tx.provider ? ` · ${tx.provider}` : ''}
          </p>
          {status === 'paid' ? (
            <p role="status">To‘lov qabul qilindi. Kitobga kirishingiz ochildi.</p>
          ) : null}
          {status === 'failed' || status === 'cancelled' ? (
            <p role="status">To‘lov yakunlanmadi. Qayta urinib ko‘ring.</p>
          ) : null}
          {status === 'created' || status === 'pending' ? (
            <p role="status">To‘lov tasdiqlanishi kutilmoqda…</p>
          ) : null}
          <p>
            <Link to={bookHref}>Kitob sahifasiga qaytish</Link>
            {' · '}
            <Link to="/library">Kutubxona</Link>
          </p>
        </>
      ) : null}
    </main>
  )
}
