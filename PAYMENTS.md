# PAYMENTS.md — Payme and Click checkout

Operator guide for the `payments` Django app. Entitlement itself is unchanged: a paid `library.Purchase` is what [`user_can_access_book`](backend/library/access.py) checks. This document matches the current code (`payments/providers/payme.py`, `payments/providers/click.py`, `payments/payment_service.py`, `payments/entitlement.py`, `payments/views.py`).

Payments stay **off** until merchant accounts exist (`PAYMENTS_ENABLED=0` in [`backend/.env.example`](backend/.env.example)).

## Enablement and env vars

| Variable | Role |
|----------|------|
| `PAYMENTS_ENABLED` | Master switch. Default false. |
| `BOOK_PRICE_TIYIN` | Global catalog price in **tiyin** (1 UZS = 100 tiyin). Required when payments are enabled. |
| `PAYME_MERCHANT_ID` | Payme cash-register / merchant id (`m=` in checkout URL). |
| `PAYME_MERCHANT_KEY` | Payme Merchant API password (HTTP Basic). |
| `PAYME_TEST_MODE` | Default `True`. `True` → `https://test.paycom.uz`; `False` → `https://checkout.paycom.uz`. |
| `CLICK_MERCHANT_ID` | Click merchant id. |
| `CLICK_SERVICE_ID` | Click service id. |
| `CLICK_SECRET_KEY` | Click MD5 signature secret. |

When `PAYMENTS_ENABLED=True` and `BOOK_PRICE_TIYIN` is missing or not a positive integer, Django raises `ImproperlyConfigured` (see `backend/.env.example` and this file).

When `PAYMENTS_ENABLED=True` and `DEBUG=False`, all five merchant fields must be non-empty: `PAYME_MERCHANT_ID`, `PAYME_MERCHANT_KEY`, `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`, `CLICK_SECRET_KEY`. `PAYME_TEST_MODE` is **not** in that production required list. See also [`DEPLOY.md`](DEPLOY.md).

## Pricing (`price_tiyin`)

Resolver: `book_price_tiyin(book=None)` / `require_book_price_tiyin(book=None)` in `payment_service.py`.

1. If payments are disabled → `None` (checkout returns `503` `payments_disabled` before price is required).
2. If `book.price_tiyin` is a positive integer → that value.
3. Else `settings.BOOK_PRICE_TIYIN` if it is a positive integer.
4. `0` or an invalid per-book override **falls back** to the global setting.

Catalog/detail JSON exposes the same resolved amount as `book_price_tiyin`. Staff can edit `Book.price_tiyin` in Django admin.

Checkout **snapshots** the resolved amount onto `PaymentTransaction.amount` at create time. Reused `created`/`pending` rows keep the original amount even if the catalog price changes later. Payme `CheckPerformTransaction` compares the provider amount to that snapshot, not the current book price.

## Checkout flow (SPA)

Authenticated `POST /api/payments/checkout/` (`CheckoutAPIView`):

- Auth: JWT cookies + CSRF (`CSRFEnforcedAuthentication`).
- Throttle scope `payment_checkout` at **10/min**.
- Body: `{ "book_slug": "...", "provider": "payme" | "click" }`.
- Book must be published. Public-domain or already entitled → `409` `already_entitled`. Non-licensed → `400` `not_purchasable`. Missing slug → `400` `invalid_request`. Bad provider → `400` `invalid_provider`. Unset price → `503` `price_unset`.

Success JSON: `transaction_id`, `provider`, `checkout_url`, `amount_tiyin`, `status`. The SPA (`CheckoutButton`) assigns `window.location` to `checkout_url`. Return URL is the SPA status page `/payment/status/<transaction_uuid>/`.

`GET /api/payments/transactions/<uuid>/` is owner-scoped status for polling (`PaymentStatusPage` polls every 2.5s until `paid` / `failed` / `cancelled`).

Active unique constraint: one `created`/`pending` transaction per `(user, book)`. A second checkout reuses that row and may switch provider; it does **not** re-price.

Django also serves the SPA return path `payment/status/<uuid>/` when `FRONTEND_DIST` is set.

## Payme Merchant API

Protocol: [Payme Merchant API](https://developer.help.paycom.uz/protokol-merchant-api/). Checkout init: [payment initialization](https://developer.help.paycom.uz/initsializatsiya-platezhey/).

**Webhook:** `POST /api/payments/payme/webhook/` (CSRF-exempt, no DRF session auth).

**Auth:** HTTP Basic, login `Paycom`, password `PAYME_MERCHANT_KEY` (`hmac.compare_digest`). This is **not** `X-Auth`. Failed auth → JSON-RPC error `-32504`. HTTP status is **always 200**; errors live in `error.code`.

**Checkout URL** (`create_checkout_url`):

- Test: `https://test.paycom.uz/{base64}`
- Prod: `https://checkout.paycom.uz/{base64}`
- Params: `m={PAYME_MERCHANT_ID};ac.order_id={tx.id};a={tx.amount};c={return_url}`
- Amount `a` is **tiyin**. Account field `order_id` is the `PaymentTransaction` UUID.

**JSON-RPC methods implemented**

| Method | Behavior |
|--------|----------|
| `CheckPerformTransaction` | Amount must equal snapshotted `tx.amount`; else `-31001`. |
| `CreateTransaction` | Lookup by `account.order_id`; sets pending; stores Payme `id`. |
| `PerformTransaction` | Lookup by `provider_transaction_id`; `fulfill_paid_transaction`. |
| `CancelTransaction` | Pre-paid → cancelled state `-1`. Already paid → state `-2` and `revoke_paid_transaction`. |
| `CheckTransaction` | Current state / times. |
| `GetStatement` | Payme rows with a non-empty `provider_transaction_id`, filtered by `create_time` in `[from, to]` milliseconds (inclusive). Uses `raw_payload.create_time` when present, else `created_at`. |

Unknown method → `-32601`. Parse error → `-32700`. Other codes used: `-31003` transaction not found, `-31008` cannot perform, `-31050` order not found. `-31007` is defined but unused.

Register the HTTPS webhook URL in the Payme merchant cabinet (see [`DEPLOY.md`](DEPLOY.md)).

## Click Shop API

**Endpoints:**

- `POST /api/payments/click/prepare/` — action `0`
- `POST /api/payments/click/complete/` — action `1`

CSRF-exempt. Form POST or JSON. Auth: MD5 `sign_string` compared with `hmac.compare_digest`. Optional `service_id` must match `CLICK_SERVICE_ID` when sent.

Prepare sign: `md5(click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time)`

Complete sign: same, with `merchant_prepare_id` after `merchant_trans_id`.

**Checkout URL:** `https://my.click.uz/services/pay?service_id&merchant_id&amount&transaction_param&return_url`

- `amount` is **UZS** (`tiyin // 100`).
- `transaction_param` / `merchant_trans_id` = transaction UUID.

Prepare success returns `merchant_prepare_id` = `tx.click_prepare_id`. Complete must match that id. Success → `fulfill_paid_transaction`. Negative Click `error` on complete → local `CANCELLED` and **does not** revoke a paid purchase.

Error codes used: `0` success, `-1` sign, `-2` amount, `-3` action, `-4` already paid, `-5` order not found (prepare), `-6` tx/prepare mismatch (complete), `-9` cancelled. Defined unused: `-7`, `-8`.

Click Shop API has **no post-paid refund webhook**. After a paid Click payment, refunds must be reconciled **manually**: set the `Purchase` to `refunded` (admin override). That is the path referenced from `click.py`.

## Entitlement

`fulfill_paid_transaction` (Payme Perform, Click Complete):

- Locks the `PaymentTransaction`, sets `paid` + `paid_at`.
- `Purchase.get_or_create(user, book)` with `status=paid`.
- `Purchase.save()` on transition to paid triggers `notify_purchase_paid`.

`revoke_paid_transaction` (Payme post-paid cancel only):

- Sets the transaction `cancelled`.
- If purchase is `paid` → `refunded` + `notify_purchase_refunded`.

Admin can still mark a `Purchase` paid as a manual override ([`FOLLOWUP.md`](FOLLOWUP.md)).

## Sandbox, certification, and tests

- Leave `PAYME_TEST_MODE=1` until Payme production checkout is certified.
- Click checkout is always `https://my.click.uz/services/pay`. There is no Django `CLICK_TEST_MODE` flag (removed: Click’s Shop API does not expose a separate test host; use a Click test merchant).
- Playwright `e2e/payment-checkout.spec.ts` covers the status-page UI shell (mocked) **and** an application-level checkout → Payme JSON-RPC → entitlement path against Django with **dummy** merchant keys. That is not Payme/Click sandbox certification.
- Backend coverage lives under `backend/payments/tests/` (checkout, webhooks, statement, Click sign/amount, post-paid cancel, entitlement).

### Operator runbook — real Payme / Click sandbox certification

This environment has **no** live merchant credentials. Certification is **Blocked** until a human supplies them. Do not treat unit tests or the dummy-key Playwright spec as certification.

**Prerequisites**

1. Payme merchant cabinet access (test cash register) and Click test merchant.
2. Public HTTPS origin (Payme/Click will not call `localhost`). Use a tunnel or staging host.
3. Production-like env with `DEBUG=False` **or** a dedicated staging `.env` that still has real test keys.

**Env vars (from this file)**

```
PAYMENTS_ENABLED=1
BOOK_PRICE_TIYIN=<positive integer tiyin>
PAYME_MERCHANT_ID=<cash-register id>
PAYME_MERCHANT_KEY=<Merchant API password>
PAYME_TEST_MODE=1
CLICK_MERCHANT_ID=<id>
CLICK_SERVICE_ID=<id>
CLICK_SECRET_KEY=<secret>
```

With `DEBUG=False`, all five merchant fields are required at boot.

**Register webhooks** (HTTPS):

| Provider | Method | URL |
|----------|--------|-----|
| Payme Merchant API | POST JSON-RPC | `https://<host>/api/payments/payme/webhook/` |
| Click Prepare | POST form/JSON | `https://<host>/api/payments/click/prepare/` |
| Click Complete | POST form/JSON | `https://<host>/api/payments/click/complete/` |

Payme auth is HTTP Basic login `Paycom`, password `PAYME_MERCHANT_KEY` (not `X-Auth`). Click auth is MD5 `sign_string` as documented above.

**Payme checkout host:** `https://test.paycom.uz/{base64}` when `PAYME_TEST_MODE=1`; `https://checkout.paycom.uz/{base64}` when `0`.

**Pass criteria (human)**

1. SPA checkout for a licensed unpaid book returns `checkout_url`; browser lands on Payme test checkout.
2. Complete a test payment; webhook `CheckPerformTransaction` → `CreateTransaction` → `PerformTransaction` results in `PaymentTransaction.status=paid` and `Purchase.status=paid`.
3. Reader manifest and `/library/media/<slug>/pdf/` succeed for that user.
4. `GetStatement` for the payment window returns the Payme `id` stored on `provider_transaction_id`.
5. Repeat for Click: redirect to `my.click.uz`, Prepare then Complete, same entitlement.
6. Cancel/refund paths: Payme post-paid cancel revokes; Click refund remains a manual admin `Purchase` → `refunded`.

Record merchant ticket / certification IDs in your ops notes — they are not stored in this repo.

## Logging

Webhook payloads are logged through `payments.logging_utils.redact_payload` (masks `sign_string`, keys, secrets). Do not log raw merchant keys.

Licensed PDF/audio/text protection (what it is not): [`CONTENT_PROTECTION.md`](CONTENT_PROTECTION.md).
