import { useState } from 'react'
import { createCheckout, type CheckoutProvider } from '../../api/payments'

type Props = {
  bookSlug: string
  priceTiyin: number | null
}

function formatUzs(tiyin: number): string {
  const uzs = tiyin / 100
  return new Intl.NumberFormat('uz-UZ').format(uzs) + " so'm"
}

/**
 * Payme / Click checkout launcher for licensed books without access.
 */
export default function CheckoutButton({ bookSlug, priceTiyin }: Props) {
  const [provider, setProvider] = useState<CheckoutProvider>('payme')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function handleCheckout() {
    if (busy) return
    setBusy(true)
    setMessage(null)
    try {
      const { response, data } = await createCheckout(bookSlug, provider)
      if (response.status === 409) {
        setMessage(
          (data as { detail?: string } | null)?.detail ||
            'Sizda bu kitobga allaqachon kirish bor.',
        )
        return
      }
      if (response.status === 400) {
        setMessage(
          (data as { detail?: string } | null)?.detail ||
            'Bu kitob hozircha sotib olinmaydi.',
        )
        return
      }
      if (response.status === 503) {
        setMessage('To‘lov tizimi hozircha o‘chirilgan.')
        return
      }
      if (!response.ok || !data || !('checkout_url' in data) || !data.checkout_url) {
        setMessage(
          (data as { detail?: string } | null)?.detail ||
            `To‘lovni boshlab bo‘lmadi (${response.status})`,
        )
        return
      }
      window.location.assign(data.checkout_url)
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Tarmoq xatosi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="checkout-panel" role="group" aria-label="Kitobni sotib olish">
      {priceTiyin != null && priceTiyin > 0 ? (
        <p className="checkout-panel__price">Narx: {formatUzs(priceTiyin)}</p>
      ) : null}
      <div className="checkout-panel__providers">
        <label>
          <input
            type="radio"
            name="payment-provider"
            value="payme"
            checked={provider === 'payme'}
            onChange={() => setProvider('payme')}
            disabled={busy}
          />{' '}
          Payme
        </label>
        <label>
          <input
            type="radio"
            name="payment-provider"
            value="click"
            checked={provider === 'click'}
            onChange={() => setProvider('click')}
            disabled={busy}
          />{' '}
          Click
        </label>
      </div>
      <button
        type="button"
        className="reader-hero__read"
        disabled={busy}
        onClick={handleCheckout}
      >
        {busy ? 'Yuborilmoqda…' : 'Sotib olish'}
      </button>
      {message ? (
        <p className="reader-hero__status-error" role="status">
          {message}
        </p>
      ) : null}
    </div>
  )
}
