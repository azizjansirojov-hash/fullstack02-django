# REMEDIATION_LOG.md — Risk remediation pass (2026-08-08)

Scoped pass on Libro.UZ (Django + React). **Payment / checkout / Purchase creation flows were not modified.**

Branch commits (newest last among this pass):

| Item | Commit |
|------|--------|
| 1 TTS | `1cbef65` |
| 2 TLS certs | `8b39422` |
| 3 Docs | `2f4051a` |
| 4 Dependency audits | `2bf4711` |
| 5 Django static CSS | `a35e71b` |
| 6 Migration gap | `bd8fced` |
| 7 Console email Compose | `f59968b` |

---

## 1. TTS provider — reduce edge-tts SPOF risk

**Changed:** `backend/library/tts_providers/edge.py` (retry/backoff 1s/2s/4s, 3 attempts, 120s timeout), `tts_service.py` (keep `generating` on synth failure during retries), `jobs.py` (set `audio_generation_status=failed` only on terminal job failure), `tts_providers/__init__.py` (`NotImplementedError` for non-edge providers), `ARCHITECTURE.md` (TTS Provider Risk), `test_generation.py`, `PROJECT_OVERVIEW.md`.

**Tests:** `python manage.py test library.test_generation` → **OK** (17 tests, 1 skipped).

**Skipped:** Full second TTS provider (explicitly out of scope).

---

## 2. Remove TLS private key material from the repository

**History scan:** `git ls-files deploy/certs/`, `git log --all --full-history -- deploy/certs/`, and `git rev-list --objects --all | selfsigned.(key|crt)` → **empty**. Certs were **untracked working-tree only**; **no history rewrite**.

**Changed:** deleted `deploy/certs/selfsigned.crt` / `.key`; `.gitignore` (`deploy/certs/*.crt|*.key`); `deploy/generate_selfsigned_cert.sh` warnings; `deploy/certs/README.md`; README TLS note; overview.

**Tests:** N/A (ops/docs). Verified `git check-ignore` matches `*.crt` / `*.key`.

**Needs human confirmation:** none for history rewrite (not required). If certs ever appear under other paths in remotes, re-scan before filter-repo.

---

## 3. Restore missing production documentation

**Changed:** `DEPLOY.md` (env checklist, TLS generate workflow, migrations, Redis, SMTP, backups via `scripts/backup_postgres_media.sh`, rollback), `FOLLOWUP.md` (Appendix B–style deferred list **excluding payment implementation**; payment marked deferred/out of pass), README links, overview Appendix A.

**Tests:** N/A (docs). Files present; README links resolve.

**Skipped:** Any payment/checkout implementation content beyond a single “still open / out of scope” note.

---

## 4. Make dependency vulnerability scanning enforceable

**Changed:** `.github/workflows/ci.yml` blocking `dependency-audit` job; `scripts/ci_pip_audit_high.py` (pip-audit has no `--severity` — OSV HIGH/CRITICAL filter); `.github/workflows/dependency-audit.yml` kept weekly advisory; README + DEPLOY policy sections; trivial `nanoid` 3.3.16 → 3.3.18 via `npm audit fix` (`frontend/package-lock.json`).

**Local findings (at time of pass):**

| Tool | Result |
|------|--------|
| `pip-audit -r requirements.lock.txt --disable-pip` | **No known vulnerabilities** |
| `python scripts/ci_pip_audit_high.py` | **exit 0** — no HIGH/CRITICAL |
| `npm audit --prefix frontend --audit-level=high` (before fix) | **1 high** — `nanoid <3.3.17` (via postcss/vite) |
| After `npm audit fix --prefix frontend` | **0 vulnerabilities** |
| `npm audit` (repo root) | **0 vulnerabilities** |

**Skipped:** Non-trivial dependency major upgrades (none needed after nanoid patch).

---

## 5. Resolve duplicated CSS/JS between Django static and React

**Changed:** deleted unused `backend/static/library/css/library.css` (+ empty `backend/static/library` tree); kept `users/css|js` for legal `base.html`; updated `frontend/MIGRATION_NOTES.md` final state.

**Tests:** grep — no remaining template refs to deleted asset; legal templates still load users static.

**Skipped:** Rewriting legal pages into the SPA (would remove users static entirely — not required).

---

## 6. Investigate migration numbering gap

**Commands:** `python manage.py makemigrations --check --dry-run` → **No changes detected**; `python manage.py migrate --plan` → **No planned migration operations**.

**Changed:** module docstring on `backend/library/migrations/0021_readingsession.py` (gap intentional; do not invent `0020`).

**Inconsistency found:** none — no auto-fix needed.

---

## 7. Harden `ALLOW_CONSOLE_EMAIL` default in Docker Compose

**Changed:** `docker-compose.yml` `${ALLOW_CONSOLE_EMAIL:-0}` + warnings; `backend/.env.example`; README / DEPLOY smoke instructions; overview.

**Tests:** `python manage.py test backend.test_settings_guards` → **OK** (13 tests). Settings guard (`DEBUG=False` + console email requires `ALLOW_CONSOLE_EMAIL` + `ENVIRONMENT=staging`) unchanged and still correct.

---

## Closing notes

- **`PROJECT_OVERVIEW.md`** restored from prior audit transcript, then updated with **Resolved in this pass** and payment marked **STILL OPEN**.
- **Payment/checkout:** deliberately untouched throughout.
- **Human follow-ups:** make CI `dependency-audit` a required status check in GitHub branch protection if not already; ensure local `backend/.env` sets `ALLOW_CONSOLE_EMAIL=1` for Compose smoke after this change.
