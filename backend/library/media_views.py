"""Authenticated serving of book PDF and audio files."""

from io import BytesIO

from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from .access import user_can_access_book
from .auth_access import AuthRequiredMixin
from .media_streaming import serve_ranged_file
from .models import AudioChapter, Book, Purchase
from .pdf_watermark import license_identifier, stamp_pdf_bytes


def _published_book(slug):
    return get_object_or_404(Book, slug=slug, is_published=True)


def _deny_access(request):
    """403 for API clients; redirect HTML clients to the book detail SPA."""
    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse(
            {'detail': 'Purchase required to access this book.'},
            status=403,
        )
    # Prefer referring book slug path when available; fall back to library home.
    return redirect(reverse('library:catalog'))


class BookPdfMediaView(AuthRequiredMixin, View):
    """Stream a published book's PDF to entitled authenticated users."""

    def get(self, request, slug):
        book = _published_book(slug)
        if not user_can_access_book(request.user, book):
            return _deny_access(request)
        if not book.pdf_file:
            raise Http404('PDF not available.')
        filename = book.pdf_file.name.split('/')[-1]
        if book.rights_status != Book.RightsStatus.LICENSED:
            return FileResponse(
                book.pdf_file.open('rb'),
                as_attachment=False,
                filename=filename,
                content_type='application/pdf',
            )
        purchase = Purchase.objects.filter(
            user=request.user,
            book=book,
            status=Purchase.Status.PAID,
        ).first()
        identifier = license_identifier(user=request.user, purchase=purchase)
        with book.pdf_file.open('rb') as handle:
            stamped = stamp_pdf_bytes(handle.read(), identifier)
        return FileResponse(
            BytesIO(stamped),
            as_attachment=False,
            filename=filename,
            content_type='application/pdf',
        )


class BookAudioMediaView(AuthRequiredMixin, View):
    """Stream legacy book-level audio to entitled authenticated users."""

    def get(self, request, slug):
        book = _published_book(slug)
        if not user_can_access_book(request.user, book):
            return _deny_access(request)
        if not book.audio_file:
            raise Http404('Audio not available.')
        filename = book.audio_file.name.split('/')[-1]
        return serve_ranged_file(
            request,
            book.audio_file.open('rb'),
            filename=filename,
            as_attachment=False,
        )


class BookChapterAudioMediaView(AuthRequiredMixin, View):
    """Stream a chapter audio track to entitled authenticated users."""

    def get(self, request, slug, chapter_id):
        book = _published_book(slug)
        if not user_can_access_book(request.user, book):
            return _deny_access(request)
        chapter = get_object_or_404(AudioChapter, pk=chapter_id, book=book)
        if not chapter.audio_file:
            raise Http404('Audio not available.')
        filename = chapter.audio_file.name.split('/')[-1]
        return serve_ranged_file(
            request,
            chapter.audio_file.open('rb'),
            filename=filename,
            as_attachment=False,
        )
