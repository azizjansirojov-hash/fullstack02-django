"""JSON API views for the library (SPA).

Thin re-export shim — implementations live in ``library.api``.
"""

from .api._common import (  # noqa: F401
    ACTIVITY_TIMESTAMPS_LIMIT,
    REVIEW_PAGE_SIZE,
    category_label_uz,
    progress_queryset_for_user,
    serialize_activity_timestamps,
    serialize_book_card,
    serialize_progress_card,
    serialize_progress_payload,
    serialize_review,
    status_counts_for_user,
)
from .api.books import BookDetailAPIView, BookReaderManifestAPIView
from .api.catalog import CatalogAPIView, MyLibraryAPIView
from .api.progress import ReadingProgressAPIView, ReadingStatusAPIView
from .api.reviews import ReviewAPIView

__all__ = [
    'ACTIVITY_TIMESTAMPS_LIMIT',
    'REVIEW_PAGE_SIZE',
    'CatalogAPIView',
    'MyLibraryAPIView',
    'BookDetailAPIView',
    'BookReaderManifestAPIView',
    'ReadingProgressAPIView',
    'ReadingStatusAPIView',
    'ReviewAPIView',
    'serialize_activity_timestamps',
    'serialize_book_card',
    'serialize_progress_card',
    'serialize_progress_payload',
    'serialize_review',
    'category_label_uz',
    'progress_queryset_for_user',
    'status_counts_for_user',
]
