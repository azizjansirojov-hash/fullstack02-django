"""Book detail and reader manifest API views."""

from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import JWTCookieAuthentication

from ..access import paid_book_ids_for_user, user_can_access_book
from ..catalog_context import DISPLAY_LANG
from ..models import Book, ReadingProgress
from ._common import category_label_uz, serialize_book_card, serialize_progress_payload


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
