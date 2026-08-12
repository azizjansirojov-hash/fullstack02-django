"""Catalog query count and search length tests."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import connection
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from .catalog_context import (
    CATEGORY_SHELVES_CACHE_KEY,
    MAX_SEARCH_QUERY_LENGTH,
    build_catalog_context,
)
from .models import Book, BookTranslation, Purchase
from .test_auth_helpers import authenticate_jwt

User = get_user_model()


class CatalogPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for i in range(8):
            book = Book.objects.create(
                author_name=f'Author {i}',
                slug=f'perf-book-{i}',
                is_published=True,
                rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
                category=Book.Category.SCIENCE if i % 2 == 0 else Book.Category.FICTION,
                pdf_generation_status='ready',
                audio_generation_status='ready',
            )
            BookTranslation.objects.create(
                book=book,
                language=BookTranslation.Language.UZ,
                title=f'Kitob {i}',
                summary='Qisqa.',
                body='Matn.' * 20,
            )

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def test_category_shelf_cache_reduces_queries(self):
        request = self.factory.get('/api/library/')
        request.user = AnonymousUser()

        with CaptureQueriesContext(connection) as cold:
            build_catalog_context(request)
        cold_count = len(cold)

        with CaptureQueriesContext(connection) as warm:
            warm_ctx = build_catalog_context(request)
        warm_count = len(warm)

        self.assertGreater(cold_count, 0)
        # Warm path still hydrates Books by id (needed for serialization), so on
        # small fixtures query counts may tie; it must not regress above cold.
        self.assertLessEqual(
            warm_count,
            cold_count,
            msg=f'Expected warm cache ≤ cold queries (cold={cold_count}, warm={warm_count})',
        )
        self.assertIsNotNone(cache.get(CATEGORY_SHELVES_CACHE_KEY))
        cached = cache.get(CATEGORY_SHELVES_CACHE_KEY)
        self.assertIsInstance(cached, list)
        self.assertTrue(cached)
        self.assertIn('book_ids', cached[0])
        self.assertNotIn('items', cached[0])
        # Hydrated structure still usable by API consumers.
        self.assertTrue(any(g['count'] > 0 for g in warm_ctx['category_lists']))

    def test_category_cache_reflects_book_save_after_invalidate(self):
        request = self.factory.get('/api/library/')
        request.user = AnonymousUser()
        build_catalog_context(request)
        self.assertIsNotNone(cache.get(CATEGORY_SHELVES_CACHE_KEY))

        book = Book.objects.get(slug='perf-book-0')
        book.category = Book.Category.HISTORY
        book.save()  # invalidates category shelves cache

        self.assertIsNone(cache.get(CATEGORY_SHELVES_CACHE_KEY))
        ctx = build_catalog_context(request)
        history = next(g for g in ctx['category_lists'] if g['code'] == 'history')
        self.assertTrue(any(item['book'].slug == 'perf-book-0' for item in history['items']))

    def test_book_save_survives_cache_delete_connection_error(self):
        """Redis/cache connection failure on invalidate must not break Book.save()."""
        from redis.exceptions import ConnectionError as RedisConnectionError
        from unittest.mock import patch

        book = Book.objects.get(slug='perf-book-0')
        book.author_name = 'Author Survives Cache Outage'

        with patch.object(cache, 'delete', side_effect=RedisConnectionError('redis down')):
            with self.assertLogs('library.catalog_context', level='WARNING') as cm:
                book.save()

        book.refresh_from_db()
        self.assertEqual(book.author_name, 'Author Survives Cache Outage')
        self.assertTrue(
            any('Category shelf cache invalidation failed' in msg for msg in cm.output),
            msg=cm.output,
        )

    def test_search_query_truncated_to_max(self):
        long_q = 'a' * (MAX_SEARCH_QUERY_LENGTH + 50)
        request = self.factory.get('/api/library/', {'q': long_q})
        request.user = AnonymousUser()
        ctx = build_catalog_context(request)
        self.assertEqual(len(ctx['query']), MAX_SEARCH_QUERY_LENGTH)

    def test_has_audio_uses_prefetched_chapters_without_extra_exists(self):
        """Prefetched audio_chapters must not trigger per-book EXISTS queries."""
        from django.core.files.base import ContentFile

        from .models import AudioChapter

        books = list(
            Book.objects.filter(slug__startswith='perf-book-')
            .prefetch_related('audio_chapters')
            .order_by('slug')
        )
        # Attach a chapter file to the first book only.
        chapter = AudioChapter(book=books[0], title='1-qism', order=0)
        chapter.audio_file.save('perf-ch.mp3', ContentFile(b'ID3'), save=True)
        books = list(
            Book.objects.filter(slug__startswith='perf-book-')
            .prefetch_related('audio_chapters')
            .order_by('slug')
        )

        with CaptureQueriesContext(connection) as ctx:
            results = [book.has_audio() for book in books]

        self.assertTrue(results[0])
        self.assertFalse(any(results[1:]))
        audio_exists_queries = [
            q['sql']
            for q in ctx.captured_queries
            if 'library_audiochapter' in q['sql'].lower()
            and 'exists' in q['sql'].lower()
        ]
        self.assertEqual(
            audio_exists_queries,
            [],
            msg=f'Unexpected EXISTS queries: {audio_exists_queries}',
        )
        # No additional chapter SELECTs when already prefetched.
        chapter_selects = [
            q['sql']
            for q in ctx.captured_queries
            if 'library_audiochapter' in q['sql'].lower()
        ]
        self.assertEqual(chapter_selects, [])


class CatalogEntitlementBatchTests(TestCase):
    """A2: authenticated catalog should batch Purchase lookups."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='batch-buyer', password='testpass123'
        )
        cls.books = []
        for i in range(6):
            book = Book.objects.create(
                author_name=f'Licensed {i}',
                slug=f'licensed-batch-{i}',
                is_published=True,
                rights_status=Book.RightsStatus.LICENSED,
                category=Book.Category.NOVEL,
                pdf_generation_status='ready',
                audio_generation_status='ready',
            )
            BookTranslation.objects.create(
                book=book,
                language=BookTranslation.Language.UZ,
                title=f'Licensed {i}',
                summary='x',
                body='Body text.',
            )
            cls.books.append(book)
            if i % 2 == 0:
                Purchase.objects.create(
                    user=cls.user,
                    book=book,
                    status=Purchase.Status.PAID,
                )

    def test_catalog_issues_at_most_one_purchase_query(self):
        cache.clear()
        client = Client()
        authenticate_jwt(client, self.user)
        with CaptureQueriesContext(connection) as ctx:
            response = client.get('/api/library/')
        self.assertEqual(response.status_code, 200)
        purchase_queries = [
            q['sql']
            for q in ctx.captured_queries
            if 'library_purchase' in q['sql'].lower()
        ]
        self.assertLessEqual(
            len(purchase_queries),
            1,
            msg=(
                f'Expected ≤1 purchase query, got {len(purchase_queries)}: '
                f'{purchase_queries}'
            ),
        )
        shelf = response.json()['shelf']
        by_slug = {row['slug']: row for row in shelf}
        self.assertTrue(by_slug['licensed-batch-0']['has_access'])
        self.assertFalse(by_slug['licensed-batch-1']['has_access'])
