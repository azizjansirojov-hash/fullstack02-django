"""JSON API views for the library (SPA). Template views stay unchanged."""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import CSRFEnforcedAuthentication, JWTCookieAuthentication

from .access import user_can_access_book
from .catalog_context import DISPLAY_LANG, build_catalog_context
from .models import Book, ReadingProgress


def serialize_activity_timestamps(user):
    """ISO timestamps of reading activity (excludes planned-only wishlist rows)."""
    return [
        ts.isoformat()
        for ts in ReadingProgress.objects.filter(user=user)
        .exclude(status=ReadingProgress.Status.PLANNED)
        .values_list('updated_at', flat=True)
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


def serialize_book_card(book, translation, *, authenticated=False, user=None):
    """Shelf/card payload shared by catalog and detail APIs.

    PDF/audio URLs are only included when the user may access full content
    (public_domain or paid purchase). Authenticated users without access still
    see has_pdf/has_audio flags so the UI can show a purchase-required state.
    """
    has_access = False
    if authenticated and user is not None:
        has_access = user_can_access_book(user, book)
    include_urls = has_access
    audio_chapters = book.get_audio_chapters_payload(include_urls=include_urls)
    audio_url = audio_chapters[0]['url'] if audio_chapters and include_urls else ''
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
        'pdf_generation_status': book.pdf_generation_status or 'pending',
        'audio_generation_status': book.audio_generation_status or 'pending',
        'pdf_url': book.gated_pdf_url() if include_urls else '',
        'read_url': f'/library/{book.slug}/read/',
        'audio_url': audio_url,
        'audio_duration_seconds': book.total_audio_duration_seconds(),
        'title': translation.title if translation else book.slug,
        'summary': (translation.summary or '') if translation else '',
    }


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


def serialize_progress_card(row, *, authenticated=True, user=None):
    """Book card with nested progress for My Library / continue_reading."""
    translation = row.book.get_translation(DISPLAY_LANG)
    card = serialize_book_card(
        row.book,
        translation,
        authenticated=authenticated,
        user=user or row.user,
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
        status_by_book_id = {}
        if authenticated:
            status_by_book_id = dict(
                ReadingProgress.objects.filter(user=request.user).values_list(
                    'book_id', 'status'
                )
            )
            progress_rows = progress_queryset_for_user(
                request.user, ReadingProgress.Status.READING
            )[:12]
            for row in progress_rows:
                continue_reading.append(
                    serialize_progress_card(row, user=request.user)
                )
            activity_timestamps = serialize_activity_timestamps(request.user)
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


def _card_with_status(book, translation, *, authenticated, status_by_book_id, user=None):
    card = serialize_book_card(
        book, translation, authenticated=authenticated, user=user
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
        for status_value in statuses_to_load:
            cards = [
                serialize_progress_card(row, user=request.user)
                for row in progress_queryset_for_user(request.user, status_value)
            ]
            payload[status_value] = cards

        return Response(payload)


class BookDetailAPIView(APIView):
    """Protected book detail JSON — mirrors BookDetailView (login required)."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTCookieAuthentication]

    def get(self, request, slug):
        book = get_object_or_404(
            Book.objects.prefetch_related('translations', 'audio_chapters'),
            slug=slug,
            is_published=True,
        )
        translation = book.get_translation(DISPLAY_LANG)
        can_read_body = bool(translation and translation.body.strip())
        has_access = user_can_access_book(request.user, book)
        audio_chapters = book.get_audio_chapters_payload(include_urls=has_access)

        payload = serialize_book_card(
            book, translation, authenticated=True, user=request.user
        )
        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
        payload.update(
            {
                'can_read': can_read_body and has_access,
                'has_access': has_access,
                'audio_chapters': audio_chapters,
                'summary': (translation.summary or '') if translation else '',
                'reading_status': progress.status if progress else None,
            }
        )
        return Response(payload)


class ReadingProgressAPIView(APIView):
    """Get or upsert the current user's reading progress for a book."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [
        CSRFEnforcedAuthentication,
        JWTCookieAuthentication,
        SessionAuthentication,
    ]

    def get(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
        if not progress:
            return Response({'exists': False, 'status': None})
        return Response(serialize_progress_payload(progress))

    def put(self, request, slug):
        return self._upsert(request, slug)

    def post(self, request, slug):
        return self._upsert(request, slug)

    def _upsert(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        mode = request.data.get('mode') or ReadingProgress.Mode.FLIP
        if mode not in ReadingProgress.Mode.values:
            mode = ReadingProgress.Mode.FLIP
        try:
            page = int(request.data.get('page', 0) or 0)
        except (TypeError, ValueError):
            page = 0
        page = max(0, page)
        total_pages = request.data.get('total_pages', None)
        if total_pages in ('', None):
            total_pages = None
        else:
            try:
                total_pages = max(1, int(total_pages))
            except (TypeError, ValueError):
                total_pages = None
        chapter_id = request.data.get('chapter_id', None)
        if chapter_id in ('', None):
            chapter_id = None
        else:
            try:
                chapter_id = int(chapter_id)
            except (TypeError, ValueError):
                chapter_id = None
        try:
            position = float(request.data.get('position', 0) or 0)
        except (TypeError, ValueError):
            position = 0.0

        reopen = bool(request.data.get('reopen'))
        requested_status = request.data.get('status')
        if requested_status not in (None, '') and requested_status not in ReadingProgress.Status.values:
            return Response(
                {'detail': 'Invalid status.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = ReadingProgress.objects.filter(user=request.user, book=book).first()
        next_status = ReadingProgress.Status.READING
        if existing:
            if existing.status == ReadingProgress.Status.PLANNED:
                next_status = ReadingProgress.Status.READING
            elif existing.status == ReadingProgress.Status.FINISHED:
                if reopen or requested_status == ReadingProgress.Status.READING:
                    next_status = ReadingProgress.Status.READING
                else:
                    next_status = ReadingProgress.Status.FINISHED
            else:
                next_status = ReadingProgress.Status.READING
                if requested_status == ReadingProgress.Status.READING:
                    next_status = ReadingProgress.Status.READING
        elif requested_status == ReadingProgress.Status.READING or reopen:
            next_status = ReadingProgress.Status.READING

        defaults = {
            'mode': mode,
            'page': page,
            'chapter_id': chapter_id,
            'position': position,
            'status': next_status,
        }
        if total_pages is not None:
            defaults['total_pages'] = total_pages

        progress, _created = ReadingProgress.objects.update_or_create(
            user=request.user,
            book=book,
            defaults=defaults,
        )
        return Response(serialize_progress_payload(progress), status=status.HTTP_200_OK)


class ReadingStatusAPIView(APIView):
    """Set or remove the user's shelf status for a book (planned / reading / finished)."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [
        CSRFEnforcedAuthentication,
        JWTCookieAuthentication,
        SessionAuthentication,
    ]

    def put(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        new_status = request.data.get('status')
        if new_status not in ReadingProgress.Status.values:
            return Response(
                {'detail': 'Invalid status. Use planned, reading, or finished.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()

        if new_status == ReadingProgress.Status.PLANNED:
            if progress and progress.status in (
                ReadingProgress.Status.READING,
                ReadingProgress.Status.FINISHED,
            ):
                # Do not downgrade — return current status unchanged.
                return Response(serialize_progress_payload(progress))
            progress, _ = ReadingProgress.objects.update_or_create(
                user=request.user,
                book=book,
                defaults={
                    'status': ReadingProgress.Status.PLANNED,
                    'mode': ReadingProgress.Mode.FLIP,
                    'page': 0,
                    'position': 0,
                    'chapter_id': None,
                },
            )
            return Response(serialize_progress_payload(progress))

        if progress:
            progress.status = new_status
            progress.save(update_fields=['status', 'updated_at'])
        else:
            progress = ReadingProgress.objects.create(
                user=request.user,
                book=book,
                status=new_status,
            )
        return Response(serialize_progress_payload(progress))

    def delete(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
        if not progress:
            return Response({'exists': False, 'status': None})
        if progress.status != ReadingProgress.Status.PLANNED:
            return Response(
                {
                    'detail': (
                        'DELETE only removes planned books. '
                        'Use PUT status=reading to undo finished.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        progress.delete()
        return Response({'exists': False, 'status': None}, status=status.HTTP_200_OK)
