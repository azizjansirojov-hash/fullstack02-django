"""Shared serializers/helpers for library API views."""

from django.db.models import Avg, Count

from ..access import user_has_access_to_book
from ..catalog_context import DISPLAY_LANG
from ..models import ReadingProgress
from ..serializers import ReviewSerializer

REVIEW_PAGE_SIZE = 20
ACTIVITY_TIMESTAMPS_LIMIT = 50


def serialize_activity_timestamps(user):
    """ISO timestamps of reading activity (excludes planned-only wishlist rows).

    Capped to the 50 most recent progress updates for catalog payload size.
    """
    return [
        ts.isoformat()
        for ts in ReadingProgress.objects.filter(user=user)
        .exclude(status=ReadingProgress.Status.PLANNED)
        .order_by('-updated_at')
        .values_list('updated_at', flat=True)[:ACTIVITY_TIMESTAMPS_LIMIT]
    ]


CATEGORY_LABELS_UZ = {
    'science': 'Fan',
    'fiction': 'Badiiy',
    'novel': 'Romanlar',
    'fantasy': 'Fantastika',
    'history': 'Tarix',
    'biography': 'Tarjimai hol',
    'poetry': 'She’riyat',
    'technology': 'Texnologiya',
    'philosophy': 'Falsafa',
    'other': 'Boshqa',
}


def category_label_uz(code):
    return CATEGORY_LABELS_UZ.get(code, 'Boshqa')


def serialize_book_card(
    book,
    translation,
    *,
    authenticated=False,
    user=None,
    paid_book_ids: set[int] | None = None,
):
    """Shelf/card payload shared by catalog and detail APIs.

    PDF/audio URLs are only included when the user may access full content
    (public_domain or paid purchase). Authenticated users without access still
    see has_pdf/has_audio flags so the UI can show a purchase-required state.

    Pass ``paid_book_ids`` from a single batched Purchase query when serializing
    many cards to avoid per-book EXISTS lookups.
    """
    from payments.payment_service import book_price_tiyin, payments_enabled

    has_access = False
    if authenticated and user is not None:
        has_access = user_has_access_to_book(
            user, book, paid_book_ids=paid_book_ids
        )
    include_urls = has_access
    audio_chapters = book.get_audio_chapters_payload(include_urls=include_urls)
    audio_url = audio_chapters[0]['url'] if audio_chapters and include_urls else ''
    avg = getattr(book, 'avg_rating', None)
    review_total = getattr(book, 'review_total', None)
    price = book_price_tiyin(book)
    is_purchasable = (
        payments_enabled()
        and price is not None
        and authenticated
        and user is not None
        and book.rights_status == book.RightsStatus.LICENSED
        and not has_access
    )
    return {
        'slug': book.slug,
        'author_name': book.author_name,
        'category': book.category,
        'category_label': category_label_uz(book.category),
        'published_year': book.published_year,
        'cover_url': book.cover_image.url if book.cover_image else '',
        'has_pdf': book.has_pdf(),
        'has_audio': book.has_audio(),
        'has_access': has_access,
        'rights_status': book.rights_status,
        'book_price_tiyin': price,
        'is_purchasable': is_purchasable,
        'pdf_generation_status': book.pdf_generation_status or 'pending',
        'audio_generation_status': book.audio_generation_status or 'pending',
        'pdf_url': book.gated_pdf_url() if include_urls else '',
        'read_url': f'/library/{book.slug}/read/',
        'audio_url': audio_url,
        'audio_duration_seconds': book.total_audio_duration_seconds(),
        'title': translation.title if translation else book.slug,
        'summary': (translation.summary or '') if translation else '',
        # Present when queryset was annotated (catalog / continue_reading).
        'average_rating': round(float(avg), 2) if avg is not None else None,
        'review_count': int(review_total) if review_total is not None else 0,
    }


def serialize_review(review):
    """Minimal public review payload."""
    return ReviewSerializer(review).data


def serialize_progress_payload(progress):
    """Shared progress + status dict for progress/status endpoints."""
    return {
        'exists': True,
        'status': progress.status,
        'mode': progress.mode,
        'page': progress.page,
        'total_pages': progress.total_pages,
        'chapter_id': progress.chapter_id,
        'position': progress.position,
        'updated_at': progress.updated_at,
    }


def serialize_progress_card(
    row, *, authenticated=True, user=None, paid_book_ids: set[int] | None = None
):
    """Book card with nested progress for My Library / continue_reading."""
    translation = row.book.get_translation(DISPLAY_LANG)
    # Propagate review aggregates annotated on the progress queryset onto the book
    # so serialize_book_card can include average_rating / review_count.
    if getattr(row, 'avg_rating', None) is not None or getattr(row, 'review_total', None) is not None:
        row.book.avg_rating = getattr(row, 'avg_rating', None)
        row.book.review_total = getattr(row, 'review_total', 0) or 0
    card = serialize_book_card(
        row.book,
        translation,
        authenticated=authenticated,
        user=user or row.user,
        paid_book_ids=paid_book_ids,
    )
    card['reading_status'] = row.status
    card['progress'] = {
        'mode': row.mode,
        'page': row.page,
        'total_pages': row.total_pages,
        'chapter_id': row.chapter_id,
        'position': row.position,
        'updated_at': row.updated_at,
        'audio_duration_seconds': row.book.total_audio_duration_seconds(),
        'status': row.status,
    }
    return card


def progress_queryset_for_user(user, status_value=None):
    qs = (
        ReadingProgress.objects.filter(user=user, book__is_published=True)
        .select_related('book')
        .prefetch_related('book__translations', 'book__audio_chapters')
        .annotate(
            avg_rating=Avg('book__reviews__rating'),
            review_total=Count('book__reviews', distinct=True),
        )
        .order_by('-updated_at')
    )
    if status_value is not None:
        qs = qs.filter(status=status_value)
    return qs


def status_counts_for_user(user):
    rows = (
        ReadingProgress.objects.filter(user=user, book__is_published=True)
        .values('status')
        .annotate(n=Count('id'))
    )
    counts = {
        ReadingProgress.Status.READING: 0,
        ReadingProgress.Status.PLANNED: 0,
        ReadingProgress.Status.FINISHED: 0,
    }
    for row in rows:
        if row['status'] in counts:
            counts[row['status']] = row['n']
    return counts


