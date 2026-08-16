"""Catalog and my-library API views."""

from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import JWTCookieAuthentication

from ..access import paid_book_ids_for_user
from ..activity import serialize_activity_stats
from ..catalog_context import PAGE_SIZE, build_catalog_context
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


def _pagination_payload(page):
    paginator = page.paginator
    return {
        'page': page.number,
        'num_pages': paginator.num_pages,
        'count': paginator.count,
        'has_previous': page.has_previous(),
        'has_next': page.has_next(),
        'previous_page': page.previous_page_number() if page.has_previous() else None,
        'next_page': page.next_page_number() if page.has_next() else None,
    }


def _empty_progress_page(page_number=1):
    paginator = Paginator([], PAGE_SIZE)
    page = paginator.get_page(page_number)
    return {'results': [], 'pagination': _pagination_payload(page)}


class MyLibraryAPIView(APIView):
    """Authenticated shelf lists grouped by reading status (paginated per bucket)."""

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
        page_number = request.query_params.get('page') or 1
        payload = {
            'counts': {
                'reading': counts[ReadingProgress.Status.READING],
                'planned': counts[ReadingProgress.Status.PLANNED],
                'finished': counts[ReadingProgress.Status.FINISHED],
            },
            'can_read': True,
            'reading': _empty_progress_page(page_number),
            'planned': _empty_progress_page(page_number),
            'finished': _empty_progress_page(page_number),
        }

        statuses_to_load = (
            [filter_status] if filter_status else list(ReadingProgress.Status.values)
        )
        querysets = {
            status_value: progress_queryset_for_user(request.user, status_value)
            for status_value in statuses_to_load
        }
        pages = {}
        all_book_ids = []
        for status_value, queryset in querysets.items():
            paginator = Paginator(queryset, PAGE_SIZE)
            page = paginator.get_page(page_number)
            pages[status_value] = page
            all_book_ids.extend(row.book_id for row in page.object_list)
        paid_ids = paid_book_ids_for_user(request.user, all_book_ids)
        for status_value, page in pages.items():
            payload[status_value] = {
                'results': [
                    serialize_progress_card(
                        row, user=request.user, paid_book_ids=paid_ids
                    )
                    for row in page.object_list
                ],
                'pagination': _pagination_payload(page),
            }

        return Response(payload)


