import { apiFetch } from './client'

export type CheckoutProvider = 'payme' | 'click'

export type CheckoutResponse = {
  transaction_id: string
  provider: CheckoutProvider
  checkout_url: string
  amount_tiyin: number
  status: string
}

export type CheckoutError = {
  detail?: string
  code?: string
}

export type TransactionStatusResponse = {
  id: string
  status: 'created' | 'pending' | 'paid' | 'cancelled' | 'failed' | string
  provider: CheckoutProvider | string
  amount_tiyin: number
  book_slug: string
  paid_at: string | null
}

export async function createCheckout(bookSlug: string, provider: CheckoutProvider) {
  return apiFetch<CheckoutResponse | CheckoutError>('/api/payments/checkout/', {
    method: 'POST',
    body: JSON.stringify({ book_slug: bookSlug, provider }),
  })
}

export async function fetchPaymentTransaction(transactionId: string) {
  return apiFetch<TransactionStatusResponse>(
    `/api/payments/transactions/${encodeURIComponent(transactionId)}/`,
  )
}
