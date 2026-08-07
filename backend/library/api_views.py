"""JSON API views for the library (SPA). Template views stay unchanged."""

from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from users.authentication import CSRFEnforcedAuthentication, JWTCookieAuthentication

from .access import paid_book_ids_for_user, user_can_access_book, user_has_access_to_book
from .catalog_context import DISPLAY_LANG, build_catalog_context
from .models import Book, ReadingProgress, Review
from .serializers import ProgressUpsertSerializer, ReviewSerializer, ReviewWriteSerializer

REVIEW_PAGE_SIZE = 20


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
        similar_books = _serialize_similar_books(
            book, request.user, authenticated=True, limit=4
        )
        agg = book.reviews.aggregate(avg=Avg('rating'), total=Count('id'))
        payload.update(
            {
                'can_read': can_read_body and has_access,
                'has_access': has_access,
                'audio_chapters': audio_chapters,
                'summary': (translation.summary or '') if translation else '',
                'reading_status': progress.status if progress else None,
                'similar_books': similar_books,
                'average_rating': round(agg['avg'], 2) if agg['avg'] else None,
                'review_count': agg['total'],
            }
        )
        return Response(payload)


class ReviewAPIView(APIView):
    """List, create, update, or delete the review for a published book.

    GET  — public, returns all reviews + aggregate stats.
    POST — authenticated; creates a review (one per user per book).
    PUT  — authenticated; updates the caller's existing review.
    DELETE — authenticated; deletes the caller's existing review.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'review_write'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_authenticators(self):
        if self.request.method == 'GET':
            return [JWTCookieAuthentication()]
        return [
            CSRFEnforcedAuthentication(),
            JWTCookieAuthentication(),
        ]

    def _get_published_book(self, slug):
        return get_object_or_404(Book, slug=slug, is_published=True)

    def get_throttles(self):
        # Keep review browsing public/unthrottled; throttle only writes.
        if self.request.method == 'GET':
            return []
        return super().get_throttles()

    def get(self, request, slug):
        book = self._get_published_book(slug)
        reviews_qs = book.reviews.select_related('user').order_by('-created_at')
        agg = book.reviews.aggregate(avg=Avg('rating'), total=Count('id'))
        paginator = Paginator(reviews_qs, REVIEW_PAGE_SIZE)
        page = paginator.get_page(request.GET.get('page') or 1)
        payload = {
            'count': agg['total'],
            'average_rating': round(agg['avg'], 2) if agg['avg'] else None,
            'results': ReviewSerializer(page.object_list, many=True).data,
            'pagination': {
                'page': page.number,
                'num_pages': page.paginator.num_pages,
                'has_previous': page.has_previous(),
                'has_next': page.has_next(),
                'previous_page': (
                    page.previous_page_number() if page.has_previous() else None
                ),
                'next_page': page.next_page_number() if page.has_next() else None,
            },
        }
        if request.user and request.user.is_authenticated:
            mine = book.reviews.filter(user=request.user).select_related('user').first()
            payload['my_review'] = (
                ReviewSerializer(mine).data if mine else None
            )
        return Response(payload)

    def post(self, request, slug):
        book = self._get_published_book(slug)
        if Review.objects.filter(user=request.user, book=book).exists():
            return Response(
                {'detail': 'You already have a review for this book. Use PUT to update it.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReviewWriteSerializer(data=request.data)
        if not serializer.is_valid():
            detail = next(iter(serializer.errors.values()))[0]
            if 'rating' in serializer.errors:
                detail = 'rating must be an integer between 1 and 5.'
            elif 'text' in serializer.errors:
                detail = 'text must not exceed 2000 characters.'
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        rating = serializer.validated_data['rating']
        text = serializer.validated_data.get('text', '')
        try:
            review = Review.objects.create(
                user=request.user, book=book, rating=rating, text=text
            )
        except IntegrityError:
            return Response(
                {'detail': 'You already have a review for this book. Use PUT to update it.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    def put(self, request, slug):
        book = self._get_published_book(slug)
        review = Review.objects.filter(user=request.user, book=book).first()
        if not review:
            return Response(
                {'detail': 'No review found. Use POST to create one.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ReviewWriteSerializer(data=request.data)
        if not serializer.is_valid():
            detail = next(iter(serializer.errors.values()))[0]
            if 'rating' in serializer.errors:
                detail = 'rating must be an integer between 1 and 5.'
            elif 'text' in serializer.errors:
                detail = 'text must not exceed 2000 characters.'
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        review.rating = serializer.validated_data['rating']
        review.text = serializer.validated_data.get('text', '')
        review.save(update_fields=['rating', 'text', 'updated_at'])
        return Response(ReviewSerializer(review).data)

    def delete(self, request, slug):
        book = self._get_published_book(slug)
        review = Review.objects.filter(user=request.user, book=book).first()
        if not review:
            return Response(
                {'detail': 'No review found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingProgressAPIView(APIView):
    """Get or upsert the current user's reading progress for a book."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [
        CSRFEnforcedAuthentication,
        JWTCookieAuthentication,
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
        serializer = ProgressUpsertSerializer(data=request.data)
        if not serializer.is_valid():
            if 'status' in serializer.errors:
                return Response(
                    {'detail': 'Invalid status.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        mode = data['mode']
        page = data['page']
        total_pages = data['total_pages']
        chapter_id = data['chapter_id']
        position = data['position']
        reopen = data['reopen']
        clear_audio = data['clear_audio']
        requested_status = data['status']

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
            'status': next_status,
        }

        # Listen owns audio bookmark but must not clobber flip/pdf page from a stale client.
        # Flip/pdf own page but must not clobber React listen position/chapter_id.
        if mode == ReadingProgress.Mode.LISTEN:
            defaults['chapter_id'] = chapter_id
            defaults['position'] = position
            if existing:
                defaults['page'] = existing.page
                if existing.total_pages is not None:
                    defaults['total_pages'] = existing.total_pages
            else:
                defaults['page'] = page
                if total_pages is not None:
                    defaults['total_pages'] = total_pages
        elif clear_audio:
            defaults['page'] = page
            defaults['chapter_id'] = chapter_id
            defaults['position'] = position
            if total_pages is not None:
                defaults['total_pages'] = total_pages
        else:
            defaults['page'] = page
            if total_pages is not None:
                defaults['total_pages'] = total_pages
            if existing:
                defaults['chapter_id'] = existing.chapter_id
                defaults['position'] = existing.position
            else:
                defaults['chapter_id'] = chapter_id
                defaults['position'] = position

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


class BookReaderManifestAPIView(APIView):
    """Entitlement-gated payload for the React immersive reader."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTCookieAuthentication]

    def get(self, request, slug):
        book = get_object_or_404(
            Book.objects.prefetch_related('translations', 'audio_chapters'),
            slug=slug,
            is_published=True,
        )
        translation = book.get_translation(DISPLAY_LANG)
        if not translation or not translation.body.strip():
            return Response(
                {'detail': 'Translation not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_can_access_book(request.user, book):
            return Response(
                {'detail': 'Purchase required to access this book.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        audio_chapters = book.get_audio_chapters_payload(include_urls=True)
        audio_url = audio_chapters[0]['url'] if audio_chapters else ''
        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
        progress_payload = (
            serialize_progress_payload(progress)
            if progress
            else {'exists': False, 'status': None}
        )

        return Response(
            {
                'slug': book.slug,
                'title': translation.title,
                'author_name': book.author_name,
                'category': book.category,
                'category_label': category_label_uz(book.category),
                'published_year': book.published_year,
                'body': translation.body,
                'audio_sync': translation.audio_sync or [],
                'audio_chapters': audio_chapters,
                'pdf_url': book.gated_pdf_url() if book.has_pdf() else '',
                'audio_url': audio_url,
                'has_access': True,
                'has_pdf': book.has_pdf(),
                'has_audio': book.has_audio(),
                'sentence_wrap': bool(audio_url),
                'read_url': f'/library/{book.slug}/read/',
                'detail_url': f'/library/{book.slug}/',
                'reading_progress': progress_payload,
            }
        )
