"""Spot-check JWT-only login/logout cookies + notification API (HTTP only)."""
from __future__ import annotations

import json
import http.cookiejar
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8000'


def jar_opener():
    cj = http.cookiejar.CookieJar()
    return cj, urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def req(opener, method, url, data=None, headers=None):
    body = None if data is None else json.dumps(data).encode()
    h = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with opener.open(r, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, raw, {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), {k.lower(): v for k, v in e.headers.items()}


def cookie_names(cj):
    return sorted({c.name for c in cj})


def main():
    print('=== A) JWT cookie spot-check ===')
    cj, opener = jar_opener()
    st, body, _ = req(opener, 'GET', f'{BASE}/api/csrf/')
    print('csrf', st, body)
    csrf = next((c.value for c in cj if c.name == 'csrftoken'), '')

    st, body, hdrs = req(
        opener,
        'POST',
        f'{BASE}/api/login/',
        {'username': 'e2e_owner', 'password': 'E2e-Passw0rd!Strong'},
        {'X-CSRFToken': csrf},
    )
    print('login_status', st)
    set_cookie = hdrs.get('set-cookie', '')
    # urllib may join multiple Set-Cookie; also inspect jar
    print('set_cookie_mentions_sessionid', 'sessionid=' in set_cookie.lower())
    print('cookies_after_login', cookie_names(cj))
    print('has_sessionid', 'sessionid' in cookie_names(cj))
    print('has_access_token', 'access_token' in cookie_names(cj))
    print('has_refresh_token', 'refresh_token' in cookie_names(cj))

    csrf = next((c.value for c in cj if c.name == 'csrftoken'), csrf)
    st, body, hdrs = req(opener, 'POST', f'{BASE}/api/logout/', {}, {'X-CSRFToken': csrf})
    print('logout_status', st, body)
    # Deleted cookies often arrive as empty / Max-Age=0
    print('logout_set_cookie_snippet', (hdrs.get('set-cookie') or '')[:240])
    st, body, _ = req(opener, 'GET', f'{BASE}/api/me/')
    print('me_after_logout', st, body)

    print('=== B) Notifications API (after ensuring paid purchase via manage.py) ===')
    # Expect seed/admin path already created a notification; list as e2e_owner
    cj2, opener2 = jar_opener()
    req(opener2, 'GET', f'{BASE}/api/csrf/')
    csrf2 = next((c.value for c in cj2 if c.name == 'csrftoken'), '')
    req(
        opener2,
        'POST',
        f'{BASE}/api/login/',
        {'username': 'e2e_owner', 'password': 'E2e-Passw0rd!Strong'},
        {'X-CSRFToken': csrf2},
    )
    st, body, _ = req(opener2, 'GET', f'{BASE}/api/notifications/?page=1')
    print('notifications_status', st)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print('notifications_body', body[:200])
        return
    print('unread_count', data.get('unread_count'))
    print('result_count', len(data.get('results') or []))
    if data.get('results'):
        first = data['results'][0]
        print('first_type', first.get('type'))
        print('first_message', (first.get('message') or '')[:100])
        print('first_is_read', first.get('is_read'))


if __name__ == '__main__':
    main()
