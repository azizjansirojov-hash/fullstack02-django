"""Catalog and my-library API views."""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import JWTCookieAuthentication

from ..access import paid_book_ids_for_user
from ..activity import serialize_activity_stats
from ..catalog_context import build_catalog_context
from ..models import ReadingProgress
from ._common import (
    category_label_uz,
    progress_queryset_for_user,
    serialize_activity_timestamps,
    serialize_book_card,
    serialize_progress_card,
    status_counts_for_user,
)

class CatalogAPIView(APIView):
    """Public catalog JSON — mirrors CatalogView / build_catalog_context."""

    permission_classes = [AllowAny]
    authentication_classes = [JWTCookieAuthentication]

    def get(self, request):
        authenticated = bool(request.user and request.user.is_authenticated)
        ctx = build_catalog_context(request)
        page = ctx['page']
        continue_reading = []
        activity_timestamps = []
        activity_stats = None
        status_by_book_id = {}
        progress_rows = []
        paid_book_ids: set[int] | None = None
        if authenticated:
            status_by_book_id = dict(
                ReadingProgress.objects.filter(user=request.user).values_list(
                    'book_id', 'status'
                )
            )
            progress_rows = list(
                progress_queryset_for_user(
                    request.user, ReadingProgress.Status.READING
                )[:12]
            )
            activity_timestamps = serialize_activity_timestamps(request.user)
            activity_stats = serialize_activity_stats(request.user)
            book_ids = [item['book'].pk for item in ctx['shelf']]
            for group in ctx['category_lists']:
                book_ids.extend(item['book'].pk for item in group['items'][:5])
            book_ids.extend(row.book_id for row in progress_rows)
            paid_book_ids = paid_book_ids_for_user(request.user, book_ids)
            for row in progress_rows:
                continue_reading.append(
                    serialize_progress_card(
                        row, user=request.user, paid_book_ids=paid_book_ids
                    )
                )
        category_lists = []
        for group in ctx['category_lists']:
            category_lists.append(
                {
                    'code': group['code'],
                    'label': category_label_uz(group['code']),
                    'count': group['count'],
                    'items': [
                        _card_with_status(
                            item['book'],
                            item['translation'],
                            authenticated=authenticated,
                            user=request.user if authenticated else None,
                            status_by_book_id=status_by_book_id,
                            paid_book_ids=paid_book_ids,
                        )
                        for item in group['items'][:5]
                    ],
                }
            )
        shelf = [
            _card_with_status(
                item['book'],
                item['translation'],
                authenticated=authenticated,
                user=request.user if authenticated else None,
                status_by_book_id=status_by_book_id,
                paid_book_ids=paid_book_ids,
            )
            for item in ctx['shelf']
        ]
        return Response(
            {
                'query': ctx['query'],
                'category': ctx['category'],
                'is_empty': ctx['is_empty'],
                'can_read': ctx['can_read'],
                'shelf': shelf,
                'category_lists': category_lists,
                'continue_reading': continue_reading,
                'activity_timestamps': activity_timestamps,
                'activity_stats': activity_stats,
                'pagination': {
                    'page': page.number,
                    'num_pages': page.paginator.num_pages,
                    'has_previous': page.has_previous(),
                    'has_next': page.has_next(),
                    'previous_page': page.previous_page_number() if page.has_previous() else None,
                    'next_page': page.next_page_number() if page.has_next() else None,
                },
                'user': (
                    {
                        'id': request.user.pk,
                        'username': request.user.username,
                        'is_staff': request.user.is_staff,
                    }
                    if authenticated
                    else None
                ),
            }
        )


def _card_with_status(
    book,
    translation,
    *,
    authenticated,
    status_by_book_id,
    user=None,
    paid_book_ids: set[int] | None = None,
):
    card = serialize_book_card(
        book,
        translation,
        authenticated=authenticated,
        user=user,
        paid_book_ids=paid_book_ids,
    )
    if authenticated:
        card['reading_status'] = status_by_book_id.get(book.pk)
    return card


class MyLibraryAPIView(APIView):
    """Authenticated shelf lists grouped by reading status."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTCookieAuthentication]

    def get(self, request):
        filter_status = (request.query_params.get('status') or '').strip()
        valid = set(ReadingProgress.Status.values)
        if filter_status and filter_status not in valid:
            return Response(
                {'detail': 'Invalid status filter.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        counts = status_counts_for_user(request.user)
        payload = {
            'counts': {
                'reading': counts[ReadingProgress.Status.READING],
                'planned': counts[ReadingProgress.Status.PLANNED],
                'finished': counts[ReadingProgress.Status.FINISHED],
            },
            'can_read': True,
            'reading': [],
            'planned': [],
            'finished': [],
        }

        statuses_to_load = (
            [filter_status] if filter_status else list(ReadingProgress.Status.values)
        )
        rows_by_status = {
            status_value: list(progress_queryset_for_user(request.user, status_value))
            for status_value in statuses_to_load
        }
        all_book_ids = [
            row.book_id
            for rows in rows_by_status.values()
            for row in rows
        ]
        paid_ids = paid_book_ids_for_user(request.user, all_book_ids)
        for status_value, rows in rows_by_status.items():
            payload[status_value] = [
                serialize_progress_card(
                    row, user=request.user, paid_book_ids=paid_ids
                )
                for row in rows
            ]

        return Response(payload)


def _serialize_similar_books(book, user, *, authenticated=False, limit=4):
    """Return up to `limit` published books in the same category, excluding `book`."""
    similar_qs = list(
        Book.objects.filter(
            category=book.category,
            is_published=True,
        )
        .exclude(pk=book.pk)
        .prefetch_related('translations', 'audio_chapters')
        .order_by('author_name', 'slug')[:limit]
    )
    paid_ids = None
    if authenticated and user is not None:
        paid_ids = paid_book_ids_for_user(user, [s.pk for s in similar_qs])
    result = []
    for similar in similar_qs:
        translation = similar.get_translation(DISPLAY_LANG)
        result.append(
            serialize_book_card(
                similar,
                translation,
                authenticated=authenticated,
                user=user if authenticated else None,
                paid_book_ids=paid_ids,
            )
        )
    return result


