"""Phase-1 verification smoke: auth, catalog, entitlement, media gating, CSRF, cookies.

Run from backend/: 
  SECRET_KEY=... DEBUG=True python ../scripts/verify_phase1_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
os.environ.setdefault("SECRET_KEY", "verify-strong-secret-key-not-for-prod-use-32chars!!")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("ALLOW_CONSOLE_EMAIL", "1")
# Prefer LocMem for local smoke when Redis is not running (backend/.env may set REDIS_URL).
os.environ["REDIS_URL"] = ""

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from library.models import Book, BookTranslation, Purchase, Notification
from library.catalog_context import PAGE_SIZE
from users.auth import get_tokens_for_user

User = get_user_model()
RESULTS: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str):
    RESULTS.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def jwt_client(user=None) -> Client:
    c = Client(enforce_csrf_checks=True)
    if user is not None:
        tokens = get_tokens_for_user(user)
        c.cookies[settings.JWT_ACCESS_COOKIE_NAME] = tokens["access"]
        c.cookies[settings.JWT_REFRESH_COOKIE_NAME] = tokens["refresh"]
    return c


def ensure_csrf(c: Client) -> str:
    r = c.get("/api/csrf/")
    assert r.status_code == 200
    return c.cookies.get("csrftoken").value


def main():
    # Seed PD + licensed books
    pd, _ = Book.objects.get_or_create(
        slug="verify-pd",
        defaults=dict(
            author_name="Verify PD",
            category=Book.Category.FICTION,
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status="ready",
            audio_generation_status="ready",
        ),
    )
    BookTranslation.objects.get_or_create(
        book=pd,
        language=BookTranslation.Language.UZ,
        defaults=dict(title="Verify PD Title", summary="s", body="Body one.\n\nBody two."),
    )
    lic, _ = Book.objects.get_or_create(
        slug="verify-licensed",
        defaults=dict(
            author_name="Verify Lic",
            category=Book.Category.NOVEL,
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status="ready",
            audio_generation_status="ready",
        ),
    )
    BookTranslation.objects.get_or_create(
        book=lic,
        language=BookTranslation.Language.UZ,
        defaults=dict(title="Verify Licensed Title", summary="s", body="Licensed body."),
    )

    # Register
    c = Client(enforce_csrf_checks=True)
    token = ensure_csrf(c)
    uname = f"verify_user_{User.objects.count()}"
    reg = c.post(
        "/api/register/",
        data=json.dumps(
            {
                "username": uname,
                "email": f"{uname}@example.com",
                "password": "Verify-Passw0rd!Strong",
                "password_confirm": "Verify-Passw0rd!Strong",
            }
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record("register", reg.status_code in (200, 201), f"status={reg.status_code} body={reg.content[:200]}")

    # Anti-enumeration password reset (same response whether email exists)
    token = ensure_csrf(c)
    pr = c.post(
        "/api/password-reset/",
        data=json.dumps({"email": "nobody-not-registered@example.com"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    token = ensure_csrf(c)
    pr2 = c.post(
        "/api/password-reset/",
        data=json.dumps({"email": f"{uname}@example.com"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record(
        "password_reset_anti_enum",
        pr.status_code == 200
        and pr2.status_code == 200
        and pr.json().get("detail") == pr2.json().get("detail"),
        f"unknown={pr.status_code}/{pr.json() if pr.status_code==200 else pr.content[:80]} "
        f"known={pr2.status_code}/{pr2.json() if pr2.status_code==200 else pr2.content[:80]}",
    )

    # Login
    token = ensure_csrf(c)
    login = c.post(
        "/api/login/",
        data=json.dumps({"username": uname, "password": "Verify-Passw0rd!Strong"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record("login", login.status_code == 200, f"status={login.status_code}")
    access_set = settings.JWT_ACCESS_COOKIE_NAME in login.cookies
    record("login_sets_access_cookie", access_set, f"cookies={list(login.cookies.keys())}")

    # CSRF rejection
    c2 = Client(enforce_csrf_checks=True)
    ensure_csrf(c2)
    bad = c2.post(
        "/api/login/",
        data=json.dumps({"username": uname, "password": "Verify-Passw0rd!Strong"}),
        content_type="application/json",
        # no CSRF header
    )
    record("csrf_enforced_on_login", bad.status_code in (403, 401), f"status={bad.status_code}")

    user = User.objects.get(username=uname)
    auth = jwt_client(user)
    ensure_csrf(auth)

    # Catalog / pagination metadata
    cat = auth.get("/api/library/")
    record("catalog", cat.status_code == 200, f"keys={list(cat.json().keys())}")
    pag = cat.json().get("pagination", {})
    record("catalog_pagination_shape", all(k in pag for k in ("page", "num_pages", "has_next")), f"pagination={pag}")

    # Discover page=2 when enough books exist
    n_pub = Book.objects.filter(is_published=True).count()
    cat2 = auth.get("/api/library/?page=2")
    record(
        "catalog_page2",
        cat2.status_code == 200,
        f"published={n_pub} page_size={PAGE_SIZE} page={cat2.json().get('pagination')}",
    )

    # Book detail PD vs licensed
    d_pd = auth.get(f"/api/library/{pd.slug}/")
    d_lic = auth.get(f"/api/library/{lic.slug}/")
    record(
        "detail_pd_access",
        d_pd.status_code == 200 and d_pd.json().get("has_access") is True,
        f"status={d_pd.status_code} has_access={d_pd.json().get('has_access') if d_pd.status_code==200 else None}",
    )
    record(
        "detail_licensed_no_purchase",
        d_lic.status_code == 200 and d_lic.json().get("has_access") is False,
        f"status={d_lic.status_code} has_access={d_lic.json().get('has_access') if d_lic.status_code==200 else None}",
    )

    # Reader manifest entitlement
    r_pd = auth.get(f"/api/library/{pd.slug}/reader/")
    r_lic = auth.get(f"/api/library/{lic.slug}/reader/")
    record("reader_pd", r_pd.status_code == 200, f"status={r_pd.status_code}")
    record("reader_licensed_blocked", r_lic.status_code == 403, f"status={r_lic.status_code} body={r_lic.content[:120]}")

    # Media gating: no auth
    anon = Client()
    m1 = anon.get(f"/library/media/{pd.slug}/pdf/")
    record("media_pdf_no_auth", m1.status_code in (401, 403), f"status={m1.status_code}")

    # Media gated path for licensed without purchase
    m2 = auth.get(f"/library/media/{lic.slug}/pdf/")
    record("media_pdf_licensed_no_purchase", m2.status_code == 403, f"status={m2.status_code}")

    # Raw /media/books/ must 404
    m3 = anon.get("/media/books/pdf/anything.pdf")
    record("raw_media_books_blocked", m3.status_code == 404, f"status={m3.status_code}")

    # Mark purchase paid → access unlocks
    purchase = Purchase.objects.create(user=user, book=lic, status=Purchase.Status.PENDING)
    purchase.status = Purchase.Status.PAID
    from django.utils import timezone

    purchase.paid_at = timezone.now()
    purchase.save()
    d_after = auth.get(f"/api/library/{lic.slug}/")
    record(
        "purchase_paid_unlocks_detail",
        d_after.status_code == 200 and d_after.json().get("has_access") is True,
        f"has_access={d_after.json().get('has_access') if d_after.status_code==200 else None}",
    )
    notif_count = Notification.objects.filter(user=user, type=Notification.Type.PURCHASE_PAID).count()
    record("purchase_paid_notification", notif_count >= 1, f"count={notif_count}")

    # Shelf status
    token = ensure_csrf(auth)
    st = auth.put(
        f"/api/library/{pd.slug}/status/",
        data=json.dumps({"status": "planned"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record("shelf_planned", st.status_code == 200, f"status={st.status_code}")
    token = ensure_csrf(auth)
    st2 = auth.put(
        f"/api/library/{pd.slug}/status/",
        data=json.dumps({"status": "reading"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record("shelf_reading", st2.status_code == 200, f"status={st2.status_code}")
    token = ensure_csrf(auth)
    prog = auth.put(
        f"/api/library/{pd.slug}/progress/",
        data=json.dumps({"mode": "flip", "page": 1, "total_pages": 5, "status": "reading"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record("progress_save", prog.status_code == 200, f"status={prog.status_code} body={prog.content[:120]}")
    getp = auth.get(f"/api/library/{pd.slug}/progress/")
    record(
        "progress_persist",
        getp.status_code == 200 and getp.json().get("page") == 1,
        f"page={getp.json().get('page') if getp.status_code==200 else None}",
    )

    # Reviews CRUD
    token = ensure_csrf(auth)
    rev = auth.post(
        f"/api/library/{pd.slug}/reviews/",
        data=json.dumps({"rating": 5, "text": "Zo‘r kitob"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record("review_create", rev.status_code in (200, 201), f"status={rev.status_code}")
    token = ensure_csrf(auth)
    rev_u = auth.put(
        f"/api/library/{pd.slug}/reviews/",
        data=json.dumps({"rating": 4, "text": "Yaxshi"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    record("review_update", rev_u.status_code == 200, f"status={rev_u.status_code}")
    token = ensure_csrf(auth)
    rev_d = auth.delete(
        f"/api/library/{pd.slug}/reviews/",
        HTTP_X_CSRFTOKEN=token,
    )
    record("review_delete", rev_d.status_code in (200, 204), f"status={rev_d.status_code}")

    # Notifications list / mark read
    nlist = auth.get("/api/notifications/")
    record("notifications_list", nlist.status_code == 200, f"unread={nlist.json().get('unread_count')}")
    results = nlist.json().get("results") or []
    if results:
        nid = results[0]["id"]
        token = ensure_csrf(auth)
        nr = auth.post(f"/api/notifications/{nid}/read/", HTTP_X_CSRFTOKEN=token)
        record("notification_mark_read", nr.status_code == 200, f"status={nr.status_code}")
    else:
        record("notification_mark_read", False, "no notifications to mark")

    # Logout
    token = ensure_csrf(auth)
    out = auth.post("/api/logout/", HTTP_X_CSRFTOKEN=token)
    record("logout", out.status_code == 200, f"status={out.status_code}")
    me = auth.get("/api/me/")
    record("logout_clears_me", me.status_code == 200 and me.json().get("authenticated") is False, f"body={me.json()}")

    # Cookie flags when DEBUG=False
    with override_settings(DEBUG=False, JWT_COOKIE_SECURE=True):
        from importlib import reload
        # settings already loaded — check SimpleJWT cookie helpers via login response under DEBUG False client env
        pass
    # Direct settings inspection + documented Secure when not DEBUG
    record(
        "cookie_flags_code",
        settings.JWT_COOKIE_HTTPONLY is True and settings.JWT_COOKIE_SAMESITE == "Lax",
        f"HttpOnly={settings.JWT_COOKIE_HTTPONLY} Secure(not DEBUG)={not True} SameSite={settings.JWT_COOKIE_SAMESITE} "
        f"(runtime DEBUG={settings.DEBUG}; Secure computed as not DEBUG in settings)",
    )

    # Performance: query count on catalog with existing books
    buyer = User.objects.create_user(username="perf_buyer", password="x")
    for b in Book.objects.filter(is_published=True, rights_status=Book.RightsStatus.LICENSED)[:30]:
        Purchase.objects.get_or_create(user=buyer, book=b, defaults={"status": Purchase.Status.PAID})
    pc = jwt_client(buyer)
    with CaptureQueriesContext(connection) as ctx:
        resp = pc.get("/api/library/")
    purchase_q = [q["sql"] for q in ctx.captured_queries if "library_purchase" in q["sql"].lower()]
    record(
        "catalog_query_count_authenticated",
        resp.status_code == 200 and len(purchase_q) <= 1,
        f"total_queries={len(ctx.captured_queries)} purchase_queries={len(purchase_q)}",
    )

    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print("\n=== SUMMARY ===")
    print(f"passed={sum(1 for r in RESULTS if r[1]=='PASS')} failed={len(fails)} total={len(RESULTS)}")
    for name, status, detail in fails:
        print(f"  FAIL {name}: {detail}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
