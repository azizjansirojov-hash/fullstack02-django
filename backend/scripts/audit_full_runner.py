"""Full auth + authz audit via Django test Client (works with Secure cookies)."""
from __future__ import annotations

import json
import os
import traceback

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client
from django.utils import timezone

from library.models import Book, BookTranslation, Purchase, ReadingProgress

User = get_user_model()

# Audit run must not be blocked by production auth throttles (5/min).
from django.conf import settings
from django.core.cache import cache

settings.REST_FRAMEWORK = {
    **settings.REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {
        'auth': '10000/min',
        'password_reset': '10000/min',
        'rights_report': '10000/hour',
        'review_write': '10000/min',
        'reading_progress': '10000/min',
    },
}
cache.clear()


def trunc(s, n=220):
    s = (s or '').replace('\n', ' ')
    return s if len(s) <= n else s[: n - 3] + '...'


def tiny_png():
    import base64

    return base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    )


def ensure_fixtures():
    staff, _ = User.objects.get_or_create(
        username='audit_staff',
        defaults={'email': 'audit_staff@example.com', 'is_staff': True},
    )
    staff.set_password('StaffPassw0rd!Strong')
    staff.is_staff = True
    staff.save()

    superu, _ = User.objects.get_or_create(
        username='audit_super',
        defaults={'email': 'audit_super@example.com', 'is_superuser': True, 'is_staff': True},
    )
    superu.set_password('SuperPassw0rd!Strong')
    superu.is_superuser = True
    superu.is_staff = True
    superu.save()

    owner, _ = User.objects.get_or_create(
        username='audit_owner',
        defaults={'email': 'audit_owner@example.com'},
    )
    owner.set_password('OwnerPassw0rd!Strong')
    owner.save()

    other, _ = User.objects.get_or_create(
        username='audit_other',
        defaults={'email': 'audit_other@example.com'},
    )
    other.set_password('OtherPassw0rd!Strong')
    other.save()

    def make_book(slug, rights, published=True):
        book, _ = Book.objects.get_or_create(
            slug=slug,
            defaults={
                'author_name': 'Audit Author',
                'category': Book.Category.OTHER,
                'rights_status': rights,
                'is_published': False,
                'pdf_generation_status': 'ready',
                'audio_generation_status': 'ready',
            },
        )
        book.rights_status = rights
        book.pdf_generation_status = 'ready'
        book.audio_generation_status = 'ready'
        if not book.pdf_file:
            book.pdf_file.save(f'{slug}.pdf', ContentFile(b'%PDF-1.4 audit\n'), save=False)
        if not book.cover_image:
            book.cover_image.save(f'{slug}.png', ContentFile(tiny_png()), save=False)
        book.save()
        BookTranslation.objects.update_or_create(
            book=book,
            language=BookTranslation.Language.UZ,
            defaults={
                'title': f'Title {slug}',
                'summary': f'Summary {slug}',
                'body': 'Paragraph one.\n\nParagraph two.',
            },
        )
        book.is_published = published
        book.save()
        return book

    pd = make_book('audit-public-domain', Book.RightsStatus.PUBLIC_DOMAIN)
    licensed = make_book('audit-licensed', Book.RightsStatus.LICENSED)
    unset = make_book('audit-unset', Book.RightsStatus.UNSET, published=False)

    Purchase.objects.update_or_create(
        user=owner,
        book=licensed,
        defaults={'status': Purchase.Status.PAID, 'paid_at': timezone.now()},
    )
    ReadingProgress.objects.update_or_create(
        user=owner,
        book=pd,
        defaults={
            'status': ReadingProgress.Status.READING,
            'mode': ReadingProgress.Mode.PDF,
            'page': 1,
        },
    )
    return {
        'staff': staff,
        'super': superu,
        'owner': owner,
        'other': other,
        'pd': pd,
        'licensed': licensed,
        'unset': unset,
    }


def csrf_client():
    c = Client(HTTP_HOST='localhost')
    c.get('/api/csrf/')
    return c


def login(username, password, *, via_api=True):
    """Login via API, or mint JWT cookies directly (avoids auth throttle in bulk tests)."""
    if via_api:
        c = csrf_client()
        resp = c.post(
            '/api/login/',
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value,
            HTTP_REFERER='http://localhost/',
        )
        if resp.status_code == 429:
            via_api = False
        else:
            assert resp.status_code == 200, f'login {username}: {resp.status_code} {resp.content[:200]}'
            return c
    from users.auth import get_tokens_for_user

    user = User.objects.get(username=username)
    assert user.check_password(password)
    tokens = get_tokens_for_user(user)
    c = csrf_client()
    c.cookies['access_token'] = tokens['access']
    c.cookies['refresh_token'] = tokens['refresh']
    return c


def req(c, method, path, data=None):
    kwargs = {'HTTP_HOST': 'localhost'}
    if 'csrftoken' in c.cookies and method in ('post', 'put', 'patch', 'delete'):
        kwargs['HTTP_X_CSRFTOKEN'] = c.cookies['csrftoken'].value
        kwargs['HTTP_REFERER'] = 'http://localhost/'
    if data is not None:
        kwargs['data'] = json.dumps(data)
        kwargs['content_type'] = 'application/json'
    return getattr(c, method)(path, **kwargs)


def main():
    def log(**kwargs):
        print(json.dumps(kwargs, default=str), flush=True)

    fx = ensure_fixtures()
    log(section='fixtures', ok=True, pd=fx['pd'].slug, licensed=fx['licensed'].slug)

    anon = csrf_client()
    endpoints = [
        ('get', '/api/library/', None),
        ('post', '/api/library/', {}),
        ('delete', '/api/library/', None),
        ('get', '/api/library/my/', None),
        ('get', '/api/library/audit-public-domain/', None),
        ('get', '/api/library/audit-public-domain/progress/', None),
        ('put', '/api/library/audit-public-domain/progress/', {'mode': 'pdf', 'page': 2}),
        ('get', '/library/media/audit-public-domain/pdf/', None),
        ('get', '/library/audit-public-domain/read/', None),
        ('get', '/health/generation/', None),
        ('get', '/health/', None),
        ('get', '/api/v1/library/', None),
        ('get', '/admin/', None),
        ('post', '/api/rights-report/', {'book_slug': 'audit-licensed', 'message': 'audit rights report test message xx'}),
        ('get', '/api/me/', None),
        ('get', '/api/csrf/', None),
        ('get', '/terms/', None),
        ('get', '/privacy/', None),
    ]
    for method, path, data in endpoints:
        resp = req(anon, method, path, data)
        log(section='s4_anon_probe', method=method.upper(), path=path, status=resp.status_code, body=trunc(resp.content.decode('utf-8', 'replace')))

    resp = req(anon, 'get', '/api/library/')
    payload = resp.json()
    shelf0 = (payload.get('shelf') or [None])[0]
    log(
        section='s4_catalog_shape',
        status=resp.status_code,
        has_pagination='pagination' in payload,
        pagination=payload.get('pagination'),
        shelf0_keys=list(shelf0.keys()) if isinstance(shelf0, dict) else None,
        shelf0_has_access=shelf0.get('has_access') if isinstance(shelf0, dict) else None,
        shelf0_pdf_url=shelf0.get('pdf_url') if isinstance(shelf0, dict) else None,
        top_keys=list(payload.keys()),
    )

    # Versioning absence
    log(section='s4_versioning', strategy='none', evidence='no /api/v1/; paths are /api/library/ etc.')

    # ----- S5 lifecycle -----
    User.objects.filter(username='audit_lifecycle_user').delete()
    reg = csrf_client()
    resp = req(
        reg,
        'post',
        '/api/register/',
        {
            'username': 'audit_lifecycle_user',
            'email': 'audit_lifecycle_user@example.com',
            'password': 'LifeCyclePassw0rd!',
            'password_confirm': 'LifeCyclePassw0rd!',
        },
    )
    access0 = reg.cookies.get('access_token')
    refresh0 = reg.cookies.get('refresh_token')
    access0_v = access0.value if access0 else None
    refresh0_v = refresh0.value if refresh0 else None
    log(
        section='s5_register',
        status=resp.status_code,
        body=trunc(resp.content.decode()),
        access=bool(access0_v),
        refresh=bool(refresh0_v),
        is_staff_leaked='is_staff' in resp.content.decode(),
    )

    resp = req(reg, 'get', '/api/me/')
    log(section='s5_me', status=resp.status_code, body=trunc(resp.content.decode()))

    resp = req(reg, 'post', '/api/logout/', {})
    log(
        section='s5_logout',
        status=resp.status_code,
        body=trunc(resp.content.decode()),
        access_cleared=not reg.cookies.get('access_token') or reg.cookies.get('access_token').value == '',
    )

    # Replay old refresh
    stale = csrf_client()
    stale.cookies['refresh_token'] = refresh0_v or ''
    resp = req(stale, 'post', '/api/token/refresh/', {})
    log(section='s5_refresh_after_logout', status=resp.status_code, body=trunc(resp.content.decode()))

    # Replay old access
    stale_a = csrf_client()
    if access0_v:
        stale_a.cookies['access_token'] = access0_v
    resp = req(stale_a, 'get', '/api/me/')
    log(section='s5_access_after_logout', status=resp.status_code, body=trunc(resp.content.decode()))

    user = login('audit_lifecycle_user', 'LifeCyclePassw0rd!')
    access1 = user.cookies.get('access_token').value
    refresh1 = user.cookies.get('refresh_token').value
    log(
        section='s5_login',
        status=200,
        new_access_differs=access1 != access0_v,
        new_refresh_differs=refresh1 != refresh0_v,
        me=trunc(req(user, 'get', '/api/me/').content.decode()),
    )

    resp = req(user, 'post', '/api/token/refresh/', {})
    log(
        section='s5_refresh_ok',
        status=resp.status_code,
        access_rotated=user.cookies.get('access_token').value != access1,
        body=trunc(resp.content.decode()),
    )

    resp = req(user, 'post', '/api/password-reset/', {'email': 'audit_lifecycle_user@example.com'})
    log(section='s5_password_reset', status=resp.status_code, body=trunc(resp.content.decode()))

    # Password reset confirm with bad token
    resp = req(
        csrf_client(),
        'post',
        '/api/password-reset/confirm/',
        {
            'uid': 'MQ',
            'token': 'invalid-token',
            'password': 'NewPassw0rd!Strong',
            'password_confirm': 'NewPassw0rd!Strong',
        },
    )
    log(section='s5_password_reset_confirm_bad', status=resp.status_code, body=trunc(resp.content.decode()))

    other_sess = login('audit_lifecycle_user', 'LifeCyclePassw0rd!')
    log(
        section='s5_concurrent',
        me_a=req(user, 'get', '/api/me/').status_code,
        me_b=req(other_sess, 'get', '/api/me/').status_code,
    )

    # Deactivate
    u = User.objects.get(username='audit_lifecycle_user')
    access_live = user.cookies.get('access_token').value
    u.is_active = False
    u.save(update_fields=['is_active'])
    # fresh client with same JWT
    deactivated = csrf_client()
    deactivated.cookies['access_token'] = access_live
    r1 = req(deactivated, 'get', '/api/me/')
    r2 = req(deactivated, 'get', '/api/library/my/')
    log(
        section='s5_deactivated',
        me=r1.status_code,
        me_body=trunc(r1.content.decode()),
        my=r2.status_code,
        my_body=trunc(r2.content.decode()),
    )

    u.is_active = True
    u.save(update_fields=['is_active'])
    user2 = login('audit_lifecycle_user', 'LifeCyclePassw0rd!')
    access_del = user2.cookies.get('access_token').value
    uid = u.pk
    u.delete()
    deleted = csrf_client()
    deleted.cookies['access_token'] = access_del
    r = req(deleted, 'get', '/api/me/')
    log(section='s5_deleted_user', status=r.status_code, body=trunc(r.content.decode()), pk=uid)

    for path in ['/api/verify-email/', '/api/account/delete/', '/api/v1/library/']:
        r = req(anon, 'get', path)
        log(section='s5_missing', path=path, status=r.status_code)

    # ----- S6 matrix -----
    roles = {
        'anon': csrf_client(),
        'owner': login('audit_owner', 'OwnerPassw0rd!Strong'),
        'other': login('audit_other', 'OtherPassw0rd!Strong'),
        'staff': login('audit_staff', 'StaffPassw0rd!Strong'),
        'super': login('audit_super', 'SuperPassw0rd!Strong'),
    }
    actions = [
        ('get', '/api/library/', None),
        ('get', '/api/library/my/', None),
        ('get', '/api/library/audit-public-domain/', None),
        ('get', '/api/library/audit-licensed/', None),
        ('get', '/api/library/audit-public-domain/progress/', None),
        ('put', '/api/library/audit-public-domain/progress/', {'mode': 'pdf', 'page': 2, 'total_pages': 10}),
        ('put', '/api/library/audit-public-domain/status/', {'status': 'reading'}),
        ('get', '/library/media/audit-public-domain/pdf/', None),
        ('get', '/library/media/audit-licensed/pdf/', None),
        ('get', '/library/audit-public-domain/read/', None),
        ('get', '/library/audit-licensed/read/', None),
        ('get', '/health/generation/', None),
        ('get', '/admin/', None),
        ('get', '/api/me/', None),
    ]
    for role, client in roles.items():
        for method, path, data in actions:
            r = req(client, method, path, data)
            has_access = None
            if path in ('/api/library/audit-licensed/', '/api/library/audit-public-domain/') and r.status_code == 200:
                try:
                    has_access = r.json().get('has_access')
                except Exception:
                    pass
            try:
                body_txt = r.content.decode('utf-8', 'replace')
            except Exception:
                body_txt = f'<streaming {r.get("Content-Type", "")}>'
            log(
                section='s6_matrix',
                role=role,
                method=method.upper(),
                path=path,
                status=r.status_code,
                has_access=has_access,
                body=trunc(body_txt, 100),
            )

    # Progress isolation: other should not see owner's progress as own - progress is per-user so empty/exists false
    other = roles['other']
    r = req(other, 'get', '/api/library/audit-public-domain/progress/')
    log(section='s6_progress_isolation', status=r.status_code, body=trunc(r.content.decode()))

    # S7 refund + rights
    owner = roles['owner']
    r = req(owner, 'get', '/library/media/audit-licensed/pdf/')
    log(section='s7_before_refund', status=r.status_code)
    Purchase.objects.filter(user=fx['owner'], book=fx['licensed']).update(status=Purchase.Status.REFUNDED)
    r = req(owner, 'get', '/library/media/audit-licensed/pdf/')
    log(section='s7_after_refund', status=r.status_code, body=trunc(r.content.decode()))
    Purchase.objects.filter(user=fx['owner'], book=fx['licensed']).update(
        status=Purchase.Status.PAID, paid_at=timezone.now()
    )

    r = req(owner, 'get', '/library/media/audit-public-domain/pdf/')
    log(section='s7_pd_before_flip', status=r.status_code)
    fx['pd'].rights_status = Book.RightsStatus.LICENSED
    fx['pd'].save(update_fields=['rights_status'])
    r = req(owner, 'get', '/library/media/audit-public-domain/pdf/')
    log(section='s7_pd_after_flip', status=r.status_code, body=trunc(r.content.decode()))
    fx['pd'].rights_status = Book.RightsStatus.PUBLIC_DOMAIN
    fx['pd'].save(update_fields=['rights_status'])

    # Generation fail halfway
    from library.models import GenerationJob

    job = GenerationJob.objects.create(
        book=fx['licensed'],
        job_type=GenerationJob.JobType.PDF,
        status=GenerationJob.Status.FAILED,
        attempts=3,
        max_attempts=3,
        error_message='audit forced failure',
    )
    Book.objects.filter(pk=fx['licensed'].pk).update(pdf_generation_status='failed')
    fx['licensed'].refresh_from_db()
    log(
        section='s7_generation_failed',
        job_id=job.pk,
        book_pdf_status=fx['licensed'].pdf_generation_status,
        media_status=req(owner, 'get', '/library/media/audit-licensed/pdf/').status_code,
    )
    Book.objects.filter(pk=fx['licensed'].pk).update(pdf_generation_status='ready')
    fx['licensed'].refresh_from_db()

    # Regenerate while progress exists
    prog_before = ReadingProgress.objects.get(user=fx['owner'], book=fx['pd'])
    page_before = prog_before.page
    old_pdf_name = fx['pd'].pdf_file.name
    fx['pd'].pdf_file.save('audit-public-domain-regen.pdf', ContentFile(b'%PDF-1.4 regen\n'), save=True)
    prog_after = ReadingProgress.objects.get(user=fx['owner'], book=fx['pd'])
    log(
        section='s7_regen_progress',
        page_before=page_before,
        page_after=prog_after.page,
        progress_survived=prog_after.page == page_before,
        pdf_name_before=old_pdf_name,
        pdf_name_after=fx['pd'].pdf_file.name,
        pdf_url_changed=old_pdf_name != fx['pd'].pdf_file.name,
    )

    print('AUDIT_DONE', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
