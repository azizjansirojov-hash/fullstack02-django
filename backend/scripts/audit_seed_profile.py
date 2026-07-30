"""Ephemeral large-dataset seeder for audit (500 books, 1000 users, 5000 progress)."""
from __future__ import annotations

import os
import random

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import connection, reset_queries
from django.test.utils import override_settings
from django.utils import timezone

from library.models import Book, BookTranslation, Purchase, ReadingProgress

User = get_user_model()

PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)


def seed():
    print('SEED_START', flush=True)
    # Users
    existing = User.objects.filter(username__startswith='seeduser_').count()
    to_create = max(0, 1000 - existing)
    batch = []
    for i in range(existing, existing + to_create):
        u = User(username=f'seeduser_{i:04d}', email=f'seeduser_{i:04d}@example.com')
        u.set_password('SeedPassw0rd!')
        batch.append(u)
        if len(batch) >= 200:
            User.objects.bulk_create(batch, ignore_conflicts=True)
            batch = []
            print(f'users={User.objects.filter(username__startswith="seeduser_").count()}', flush=True)
    if batch:
        User.objects.bulk_create(batch, ignore_conflicts=True)
    print(f'USERS {User.objects.filter(username__startswith="seeduser_").count()}', flush=True)

    existing_books = Book.objects.filter(slug__startswith='seed-book-').count()
    for i in range(existing_books, 500):
        slug = f'seed-book-{i:04d}'
        rights = Book.RightsStatus.PUBLIC_DOMAIN if i % 3 == 0 else Book.RightsStatus.LICENSED
        book = Book(
            slug=slug,
            author_name=f'Author {i % 50}',
            category=random.choice(list(Book.Category.values)),
            rights_status=rights,
            is_published=False,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        book.pdf_file.save(f'{slug}.pdf', ContentFile(b'%PDF-1.4 seed\n'), save=False)
        book.save()
        BookTranslation.objects.create(
            book=book,
            language=BookTranslation.Language.UZ,
            title=f'Seed Book {i}',
            summary=f'Summary for seed book {i}',
            body='Body paragraph.\n\nMore text.',
        )
        Book.objects.filter(pk=book.pk).update(is_published=True)
        if i % 50 == 0:
            print(f'books={i+1}', flush=True)
    print(f'BOOKS {Book.objects.filter(slug__startswith="seed-book-").count()}', flush=True)

    users = list(User.objects.filter(username__startswith='seeduser_').values_list('id', flat=True)[:1000])
    books = list(Book.objects.filter(slug__startswith='seed-book-').values_list('id', flat=True)[:500])
    existing_p = ReadingProgress.objects.filter(user_id__in=users).count()
    need = max(0, 5000 - existing_p)
    batch = []
    seen = set(
        ReadingProgress.objects.filter(user_id__in=users).values_list('user_id', 'book_id')
    )
    attempts = 0
    while len(batch) + existing_p < 5000 and attempts < 20000:
        attempts += 1
        uid = random.choice(users)
        bid = random.choice(books)
        if (uid, bid) in seen:
            continue
        seen.add((uid, bid))
        batch.append(
            ReadingProgress(
                user_id=uid,
                book_id=bid,
                status=random.choice(list(ReadingProgress.Status.values)),
                mode=ReadingProgress.Mode.PDF,
                page=random.randint(0, 20),
            )
        )
        if len(batch) >= 500:
            ReadingProgress.objects.bulk_create(batch, ignore_conflicts=True)
            existing_p = ReadingProgress.objects.filter(user_id__in=users).count()
            batch = []
            print(f'progress={existing_p}', flush=True)
    if batch:
        ReadingProgress.objects.bulk_create(batch, ignore_conflicts=True)
    print(f'PROGRESS {ReadingProgress.objects.count()}', flush=True)

    # Some purchases
    owner_ids = users[:100]
    licensed = list(
        Book.objects.filter(slug__startswith='seed-book-', rights_status=Book.RightsStatus.LICENSED).values_list(
            'id', flat=True
        )[:50]
    )
    pb = []
    for uid in owner_ids[:50]:
        for bid in licensed[:5]:
            pb.append(
                Purchase(
                    user_id=uid,
                    book_id=bid,
                    status=Purchase.Status.PAID,
                    paid_at=timezone.now(),
                )
            )
    Purchase.objects.bulk_create(pb, ignore_conflicts=True)
    print(f'PURCHASES {Purchase.objects.count()}', flush=True)
    print('SEED_DONE', flush=True)


def profile():
    from django.test import Client
    from users.auth import get_tokens_for_user

    user = User.objects.filter(username__startswith='seeduser_').first()
    tokens = get_tokens_for_user(user)
    c = Client(HTTP_HOST='localhost')
    c.get('/api/csrf/')
    c.cookies['access_token'] = tokens['access']

    book = Book.objects.filter(slug__startswith='seed-book-', is_published=True).first()

    def measure(label, path):
        reset_queries()
        with override_settings(DEBUG=True):
            reset_queries()
            # Force connection queries capture
            from django.conf import settings

            settings.DEBUG = True
            reset_queries()
            resp = c.get(path, HTTP_HOST='localhost')
            q = len(connection.queries)
            settings.DEBUG = False
        print(
            json_dumps(
                {
                    'section': 's8_profile',
                    'label': label,
                    'path': path,
                    'status': resp.status_code,
                    'queries': q,
                }
            ),
            flush=True,
        )

    import json as _json

    def json_dumps(o):
        return _json.dumps(o)

    measure('catalog', '/api/library/')
    measure('catalog_page2', '/api/library/?page=2')
    measure('my', '/api/library/my/')
    measure('detail', f'/api/library/{book.slug}/')
    measure('progress', f'/api/library/{book.slug}/progress/')
    print('PROFILE_DONE', flush=True)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'profile':
        profile()
    else:
        seed()
