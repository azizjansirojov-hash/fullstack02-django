"""Shared catalog browse context for library templates."""

import logging

from django.core.cache import cache
from django.core.cache.backends.base import InvalidCacheBackendError
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch, Q

from .models import Book, BookTranslation

logger = logging.getLogger(__name__)

# redis is optional at import time (LocMem cache). When REDIS_URL is set, Django's
# RedisCache still requires the redis package installed.
_CACHE_INVALIDATE_ERRORS = (InvalidCacheBackendError,)
try:
    from redis.exceptions import RedisError

    _CACHE_INVALIDATE_ERRORS = (RedisError, InvalidCacheBackendError)
except ImportError:  # pragma: no cover
    pass

VALID_CATEGORIES = {code for code, _label in Book.Category.choices}
PAGE_SIZE = 24
DISPLAY_LANG = BookTranslation.Language.UZ
MAX_SEARCH_QUERY_LENGTH = 200
# v3 stores JSON-safe {code, label, count, book_ids} — not live ORM instances.
CATEGORY_SHELVES_CACHE_KEY = 'catalog:category_shelves:v3'
CATEGORY_SHELVES_CACHE_TTL = 60


def invalidate_category_shelves_cache():
    try:
        cache.delete(CATEGORY_SHELVES_CACHE_KEY)
    except _CACHE_INVALIDATE_ERRORS as exc:
        logger.warning('Category shelf cache invalidation failed: %s', exc)


def published_books_queryset():
    """Published books with a usable Uzbek translation for shelf display."""
    return (
        Book.objects.filter(is_published=True)
        .filter(translations__language=DISPLAY_LANG)
        .exclude(translations__title='')
        .exclude(translations__body='')
        .annotate(
            avg_rating=Avg('reviews__rating'),
            review_total=Count('reviews', distinct=True),
        )
        .distinct()
    )


def _uzbek_translation_prefetch():
    return Prefetch(
        'translations',
        queryset=BookTranslation.objects.filter(language=DISPLAY_LANG),
    )


def _serialize_category_shelf_payload(category_lists):
    """Convert ORM shelf groups to JSON-safe cache payloads."""
    return [
        {
            'code': group['code'],
            'label': group['label'],
            'count': group['count'],
            'book_ids': [item['book'].pk for item in group['items']],
        }
        for group in category_lists
    ]


def _hydrate_category_lists(cached_payload):
    """Rebuild [{book, translation}, …] groups from cached book_ids."""
    all_ids = []
    for group in cached_payload:
        all_ids.extend(group['book_ids'])
    if not all_ids:
        return [
            {
                'code': group['code'],
                'label': group['label'],
                'items': [],
                'count': group['count'],
            }
            for group in cached_payload
        ]

    books = (
        published_books_queryset()
        .filter(pk__in=all_ids)
        .prefetch_related(_uzbek_translation_prefetch(), 'audio_chapters')
    )
    by_id = {book.pk: book for book in books}
    category_lists = []
    for group in cached_payload:
        items = []
        for book_id in group['book_ids']:
            book = by_id.get(book_id)
            if book is None:
                continue
            translation = book.get_translation(DISPLAY_LANG)
            items.append({'book': book, 'translation': translation})
        category_lists.append(
            {
                'code': group['code'],
                'label': group['label'],
                'items': items,
                'count': group['count'],
            }
        )
    return category_lists


def build_category_lists(*, use_cache=True):
    """Category shelf structure (all published books), optionally cached."""
    if use_cache:
        cached = cache.get(CATEGORY_SHELVES_CACHE_KEY)
        if cached is not None:
            return _hydrate_category_lists(cached)

    published = (
        published_books_queryset()
        .prefetch_related(_uzbek_translation_prefetch(), 'audio_chapters')
        .order_by('author_name', 'slug')
    )
    by_category = {code: [] for code, _label in Book.Category.choices}
    for book in published:
        translation = book.get_translation(DISPLAY_LANG)
        by_category.setdefault(book.category, []).append(
            {'book': book, 'translation': translation}
        )
    category_lists = []
    for code, label in Book.Category.choices:
        items = by_category.get(code, [])
        category_lists.append(
            {
                'code': code,
                'label': label,
                'items': items,
                'count': len(items),
            }
        )
    if use_cache:
        cache.set(
            CATEGORY_SHELVES_CACHE_KEY,
            _serialize_category_shelf_payload(category_lists),
            CATEGORY_SHELVES_CACHE_TTL,
        )
    return category_lists


def build_catalog_context(request):
    """Build search, shelves, and shelf grid context shared by catalog and book pages."""
    query = (request.GET.get('q') or '').strip()
    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        query = query[:MAX_SEARCH_QUERY_LENGTH]
    category = request.GET.get('category', '')
    if category not in VALID_CATEGORIES:
        category = ''

    books = (
        published_books_queryset()
        .prefetch_related(
            _uzbek_translation_prefetch(),
            'audio_chapters',
        )
        .order_by('-created_at', 'author_name', 'slug')
        .distinct()
    )

    if query:
        books = books.filter(
            Q(author_name__icontains=query)
            | Q(translations__title__icontains=query)
            | Q(translations__summary__icontains=query)
        ).distinct()

    if category:
        books = books.filter(category=category)

    paginator = Paginator(books, PAGE_SIZE)
    page_number = request.GET.get('page') or 1
    page = paginator.get_page(page_number)

    shelf = []
    for book in page.object_list:
        translation = book.get_translation(DISPLAY_LANG)
        shelf.append({'book': book, 'translation': translation})

    category_lists = build_category_lists(use_cache=True)
    total_published = published_books_queryset().count()
    filtering = bool(query or category)

    return {
        'page': page,
        'shelf': shelf,
        'query': query,
        'category': category,
        'category_lists': category_lists,
        'categories': Book.Category.choices,
        'is_empty': total_published == 0 and not filtering,
        'can_read': request.user.is_authenticated,
    }
