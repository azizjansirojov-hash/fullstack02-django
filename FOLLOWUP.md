# FOLLOWUP.md — technical debt & roadmap

## Recently completed (remediation pass)

- JWT-only auth (SPA + gated media); Django HTML auth templates removed
- Real `Notification` model + `/api/notifications/` + sidebar wiring
- `Review` registered in Django admin for moderation
- Bridge parity scripts and unused `book-detail-enhancements.js` deleted
- Compose/docs Postgres defaults renamed `luma` → `libro` (see DEPLOY.md rename script)
- Reader HTML-fallback flags/comments removed

## Payments & roles

- Purchases are admin-marked (`Purchase.status = paid`). No payment gateway yet.
- Roles: Django staff/superuser only — no custom reader/publisher roles.

## i18n

- Locale infrastructure is ready (`frontend/src/lib/locale.ts`); UI strings remain Uzbek-hardcoded. Keep `LANGUAGE_CODE = 'uz'`.

## Remaining JSX → TSX

- Continue converting residual `.jsx` under `frontend/src` (tracked in remediation).

## Product / ops

- Payment gateway integration
- Notification preferences + push/email
- Real multi-locale catalog copy (if ever needed beyond Uzbek)
