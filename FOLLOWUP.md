# FOLLOWUP.md — technical debt & roadmap

Living list of deferred work. Seeded from `PROJECT_OVERVIEW.md` Appendix B and Known Issues. Audit trail: [`AUDITS.md`](AUDITS.md) (`PROJECT_ANALYSIS.md` superseded `PROJECT_AUDIT.md` on 2026-08-16).

Payme and Click checkout are **implemented** (see `payments/`, `PAYMENTS.md`): `POST /api/payments/checkout/`, provider webhooks, and `Purchase` fulfillment/revoke. Admin can still mark purchases as paid as a manual override.

## Still open

- Second TTS provider behind `TTS_PROVIDER` before treating edge-tts as a production SLA (see `ARCHITECTURE.md`).
- Keep Django legal-page static assets in sync with SPA branding, or intentionally slim further after confirming no template references remain.
- Act on dependency audit findings (PR CI blocks high/critical; weekly workflow remains advisory) — see README / DEPLOY policy once landed.
- Notification preferences + push/email.
- Continue converting residual `.jsx` under `frontend/src` to TypeScript.
- Real multi-locale catalog copy (if ever needed beyond Uzbek); keep `LANGUAGE_CODE = 'uz'` until then.
- Roles: Django staff/superuser only — no custom reader/publisher roles (product decision pending).
- Licensed-content protection is attribution-only; full reader `body` JSON remains an entitled-user exfil path. See [`CONTENT_PROTECTION.md`](CONTENT_PROTECTION.md).

## Recently completed (prior remediation)

- JWT-only auth (SPA + gated media); Django HTML auth templates removed
- Real `Notification` model + `/api/notifications/` + sidebar wiring
- `Review` registered in Django admin for moderation
- Bridge parity scripts and unused `book-detail-enhancements.js` deleted
- Compose/docs Postgres defaults renamed `luma` → `libro` (see DEPLOY.md rename script)
- Reader HTML-fallback flags/comments removed
- Payme/Click payment gateway checkout and webhooks

## i18n

Locale infrastructure is ready (`frontend/src/lib/locale.ts`); UI strings remain Uzbek-hardcoded.
