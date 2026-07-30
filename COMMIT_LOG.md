# COMMIT_LOG.md — safe commit & push report

**Date:** 2026-07-30  
**Branch pushed:** `remediation/full-pass-2026-07-30`  
**Remote:** `origin/remediation/full-pass-2026-07-30`

---

## Step 1 — Backup

| Item | Value |
|------|--------|
| Pre-commit status dump | `git_status_before_commit.txt` (repo root; gitignored) |
| Backup archive | `C:\Users\User\Documents\salom\libro_backup_20260730_184608.tar.gz` |
| Backup size | **396,082,471 bytes** (~377.73 MB) |
| Exclusions | `node_modules`, `.git`, `venv`, `backend/media`, `__pycache__`, Playwright artifacts, `frontend/dist`, `backend/staticfiles` |

---

## Step 2 — Ahead / behind vs `origin/main`

| Direction | Count |
|-----------|------:|
| Local HEAD **behind** `origin/main` | **0** |
| Local HEAD **ahead** of `origin/main` (before remediation commits) | **16** |

- `git fetch origin` completed; no new commits on `origin/main` since this work started.
- No overlapping/conflicting remote history: nobody else pushed to `main` while this branch was prepared.
- The 16 pre-existing local commits (Purchase gating through book-detail actions) remain on this branch and were included in the push (they were never on `origin/main`).

---

## Step 3 — Branch

Created and used: **`remediation/full-pass-2026-07-30`** (not `main`).

---

## Step 4 — Staging review (not committed)

Explicitly excluded / ignored:

- `backend/.env` (real secrets — already gitignored)
- `backend/db.sqlite3` (untracked from index; gitignored)
- `__pycache__` / `*.pyc` (removed from index; gitignored)
- `backend/media/**` (gitignored)
- `backups/**` including large `media.tar.gz` / `postgres.dump` (gitignored)
- Playwright `test-results/` / `playwright-report/` (gitignored)
- `git_status_before_commit.txt` / `git_status_review.txt` (gitignored)
- Locked local `scripts/parity_*.py` (ignored after delete failed with access denied)

Secret pattern scan: only placeholders in `.env.example` / docs, build-only `SECRET_KEY` in Dockerfile, and known E2E seed passwords in test helpers — no production secrets staged.

---

## Step 5 — Commits made (newest first among remediation; full list vs origin/main below)

### Remediation / cleanup commits (this session)

| Hash | Message |
|------|---------|
| `7e49d84` | chore: ignore leftover local parity scripts |
| `81dc88e` | docs: add REMEDIATION_REPORT.md and REMEDIATION_REPORT_2.md |
| `fd5139c` | frontend: migrate legacy luma-* storage keys with safe bootstrap migration |
| `f8c5f46` | frontend: migrate remaining JSX/JS to TSX/TS |
| `a5d9d55` | deps: add locked requirements, bump Pillow, upgrade react-router-dom to 7.18.2 |
| `2fd46f9` | chore: pin Node/Python versions (.nvmrc, .python-version, engines) |
| `d4722fe` | test: fix test discovery (rename test_*.py), update CI |
| `0cedcce` | security: add Redis auth, bind web port to localhost, email guard warnings |
| `fc98aeb` | chore: rename luma references to libro (env, docs, rename script) |
| `618c071` | chore: remove dead code (parity scripts, unused JS, empty dirs) |
| `36d796f` | admin: register Review model with moderation support |
| `c196a59` | feature: add real Notification model, API, and UI |
| `e980cc7` | frontend: remove stale reader-fallback flags and dead branches |
| `9f34880` | auth: migrate to JWT-only, remove Django session dual-auth |
| `1514e81` | chore: stop tracking local DB and bytecode |

### Exceptions / cross-cutting notes

- `docker-compose.yml` (libro DB naming + Redis password + `127.0.0.1:8000`) landed in the **security** commit; luma→libro docs/script landed in the rename commit.
- `frontend/package.json` **engines** landed with the **deps** commit (with the router bump) rather than the pin-only commit.
- Layout shell components shipped with the **notifications** commit because the sidebar hosts the notification UI.
- Large SPA/API/generation/E2E surface shipped under **frontend: migrate remaining JSX/JS to TSX/TS**; `storageKeys` + `main.tsx` bootstrap are the following commit.
- Extra commit `7e49d84` was required because a local lock prevented deleting `scripts/parity_b5_form_live.py`.

### Also on branch (already committed on local `main` before this pass; now on the feature branch tip)

`7e30222` … `9c85f65` (16 commits ahead of `origin/main` prior to remediation).

---

## Step 6 — Final test suite (after commit-splitting)

| Check | Result |
|-------|--------|
| `python manage.py test library users backend` | **169 OK** (1 skipped) |
| `cd frontend && npm run lint` | **exit 0** (warnings only) |
| `cd frontend && npm run typecheck` | **exit 0** |
| `cd frontend && npm run test` | **93 passed** |
| `CI=true npm run test:e2e` | **12 passed** |
| `git status` | **clean** |

---

## Step 7 — Push confirmation

- Pushed: `git push -u origin remediation/full-pass-2026-07-30`
- Remote tip verified: `git log --oneline origin/remediation/full-pass-2026-07-30 -5` starts at `7e49d84`
- Tracking: local branch tracks `origin/remediation/full-pass-2026-07-30`
- Suggested PR URL (not opened): https://github.com/azizjansirojov-hash/fullstack02-django/pull/new/remediation/full-pass-2026-07-30

---

## Explicit note

**main was NOT modified; a pull request / merge into main is a separate, deliberate decision left to the repository owner.**
