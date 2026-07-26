"""Catalog query count and search length tests."""

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from .catalog_context import (
    CATEGORY_SHELVES_CACHE_KEY,
    MAX_SEARCH_QUERY_LENGTH,
    build_catalog_context,
)
from .models import Book, BookTranslation


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
            build_catalog_context(request)
        warm_count = len(warm)

        self.assertGreater(cold_count, 0)
        self.assertLess(
            warm_count,
            cold_count,
            msg=f'Expected warm cache fewer queries (cold={cold_count}, warm={warm_count})',
        )
        self.assertIsNotNone(cache.get(CATEGORY_SHELVES_CACHE_KEY))

    def test_search_query_truncated_to_max(self):
        long_q = 'a' * (MAX_SEARCH_QUERY_LENGTH + 50)
        request = self.factory.get('/api/library/', {'q': long_q})
        request.user = AnonymousUser()
        ctx = build_catalog_context(request)
        self.assertEqual(len(ctx['query']), MAX_SEARCH_QUERY_LENGTH)
