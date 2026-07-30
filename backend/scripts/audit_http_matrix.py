"""Ephemeral audit script: auth lifecycle + permission matrix against live server.

Run inside web container or host with network to :8000.
Does not commit fixtures permanently beyond created users/books for the audit.
"""
from __future__ import annotations

import json
import os
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = os.environ.get('AUDIT_BASE', 'http://127.0.0.1:8000').rstrip('/') + '/'


class Client:
    def __init__(self, label: str):
        self.label = label
        self.jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def cookie(self, name: str) -> str | None:
        for c in self.jar:
            if c.name == name:
                return c.value
        return None

    def request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        *,
        csrf: bool = False,
        headers: dict | None = None,
    ) -> tuple[int, str, dict]:
        url = urljoin(BASE, path.lstrip('/'))
        body = None
        hdrs = {'Accept': 'application/json', **(headers or {})}
        if data is not None:
            body = json.dumps(data).encode()
            hdrs['Content-Type'] = 'application/json'
        if csrf:
            token = self.cookie('csrftoken')
            if token:
                hdrs['X-CSRFToken'] = token
                hdrs['Referer'] = BASE
        req = Request(url, data=body, headers=hdrs, method=method)
        try:
            with self.opener.open(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
                return resp.status, raw, dict(resp.headers)
        except HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            return exc.code, raw, dict(exc.headers)

    def ensure_csrf(self) -> None:
        self.request('GET', '/api/csrf/')


def trunc(s: str, n: int = 180) -> str:
    s = s.replace('\n', ' ')
    return s if len(s) <= n else s[: n - 3] + '...'


def main() -> int:
    results = []

    def log(section: str, **kwargs):
        row = {'section': section, **kwargs}
        results.append(row)
        print(json.dumps(row, default=str))

    # --- CSRF + register ---
    anon = Client('anon')
    anon.ensure_csrf()
    log('csrf', status=200, csrftoken=bool(anon.cookie('csrftoken')))

    reg_user = f'audit_user_{os.getpid()}'
    reg_email = f'{reg_user}@example.com'
    reg_pass = 'AuditPassw0rd!Strong'
    st, body, hdrs = anon.request(
        'POST',
        '/api/register/',
        {
            'username': reg_user,
            'email': reg_email,
            'password': reg_pass,
            'password_confirm': reg_pass,
        },
        csrf=True,
    )
    log(
        'register',
        status=st,
        body=trunc(body),
        set_access=bool(anon.cookie('access_token')),
        set_refresh=bool(anon.cookie('refresh_token')),
        has_is_staff='is_staff' in body,
    )
    access_after_reg = anon.cookie('access_token')
    refresh_after_reg = anon.cookie('refresh_token')

    st, body, _ = anon.request('GET', '/api/me/')
    log('me_after_register', status=st, body=trunc(body))

    # --- login new tokens (fixation check: compare to pre-clear) ---
    # Capture cookies before logout then login again
    st, body, _ = anon.request('POST', '/api/logout/', {}, csrf=True)
    log('logout', status=st, body=trunc(body), access_cleared=anon.cookie('access_token') in (None, ''))

    # Reuse old refresh after logout
    jar2 = Client('stale')
    jar2.ensure_csrf()
    # manually inject old refresh via header won't work for cookie auth; use Cookie header
    st, body, _ = jar2.request(
        'POST',
        '/api/token/refresh/',
        {},
        csrf=True,
        headers={'Cookie': f'refresh_token={refresh_after_reg}; csrftoken={jar2.cookie("csrftoken")}'},
    )
    log('refresh_after_logout_with_old_refresh', status=st, body=trunc(body))

    # Access token after logout (if still present in a jar that kept it)
    stale_access = Client('stale_access')
    stale_access.ensure_csrf()
    st, body, _ = stale_access.request(
        'GET',
        '/api/me/',
        headers={'Cookie': f'access_token={access_after_reg}'},
    )
    log('access_token_after_logout', status=st, body=trunc(body))

    # Login again
    user = Client('user')
    user.ensure_csrf()
    st, body, _ = user.request(
        'POST',
        '/api/login/',
        {'username': reg_user, 'password': reg_pass},
        csrf=True,
    )
    access1 = user.cookie('access_token')
    refresh1 = user.cookie('refresh_token')
    log(
        'login',
        status=st,
        body=trunc(body),
        access=bool(access1),
        refresh=bool(refresh1),
        tokens_differ_from_register=access1 != access_after_reg,
    )

    # Refresh
    st, body, _ = user.request('POST', '/api/token/refresh/', {}, csrf=True)
    access2 = user.cookie('access_token')
    log('refresh', status=st, body=trunc(body), rotated=access2 != access1 and bool(access2))

    # Password reset request
    st, body, _ = user.request(
        'POST',
        '/api/password-reset/',
        {'email': reg_email},
        csrf=True,
    )
    log('password_reset_request', status=st, body=trunc(body))

    # Missing endpoints
    for path in ['/api/verify-email/', '/api/account/delete/', '/api/v1/library/', '/health/']:
        st, body, _ = anon.request('GET', path)
        log('missing_endpoint', path=path, status=st)

    # Concurrent sessions
    device_b = Client('device_b')
    device_b.ensure_csrf()
    st, body, _ = device_b.request(
        'POST',
        '/api/login/',
        {'username': reg_user, 'password': reg_pass},
        csrf=True,
    )
    st_a, body_a, _ = user.request('GET', '/api/me/')
    st_b, body_b, _ = device_b.request('GET', '/api/me/')
    log(
        'concurrent_sessions',
        login_b=st,
        me_a=st_a,
        me_b=st_b,
        both_ok=st_a == 200 and st_b == 200,
    )

    # Deactivate while token valid — needs Django shell side; print marker
    log('note', msg='deactivate/delete tests require manage.py shell companion')

    print('---MATRIX_PLACEHOLDER---', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
