"""Authenticated serving of book PDF and audio files."""

import hashlib
from pathlib import Path

from django.conf import settings
from django.http import Http404, JsonResponse
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


def _source_file_token(file_field) -> str:
    name = getattr(file_field, 'name', '') or ''
    size = getattr(file_field, 'size', 0) or 0
    mtime = 0
    storage = getattr(file_field, 'storage', None)
    if storage is not None and name:
        try:
            mtime = storage.get_modified_time(name).timestamp()
        except OSError:
            mtime = 0
    return f'{name}:{size}:{mtime}'


def _stamp_cache_path(purchase, file_field) -> Path:
    digest = hashlib.sha256(_source_file_token(file_field).encode('utf-8')).hexdigest()[:16]
    cache_dir = Path(settings.MEDIA_ROOT) / 'pdf_stamps'
    return cache_dir / f'{purchase.pk}_{digest}.pdf'


def _stamped_at_iso(purchase) -> str:
    paid_at = getattr(purchase, 'paid_at', None)
    if paid_at is None:
        return 'unknown'
    return paid_at.strftime('%Y-%m-%dT%H:%MZ')


def _cached_or_stamp_licensed_pdf(book, user, purchase):
    """Stamp once per purchase+source file, then stream from disk (Range-capable).

    First miss still loads the whole PDF into memory (pypdf cannot stream a merge).
    Subsequent requests serve the cached bytes with HTTP Range. This is not object
    storage / pre-stamp-at-purchase; it only avoids repeating the merge on every GET.
    """
    cache_path = _stamp_cache_path(purchase, book.pdf_file)
    if not cache_path.is_file():
        identifier = license_identifier(user=user, purchase=purchase)
        with book.pdf_file.open('rb') as handle:
            stamped = stamp_pdf_bytes(
                handle.read(),
                identifier,
                stamped_at_iso=_stamped_at_iso(purchase),
            )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(stamped)
    return cache_path.open('rb')


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
            return serve_ranged_file(
                request,
                book.pdf_file.open('rb'),
                filename=filename,
                content_type='application/pdf',
                as_attachment=False,
            )
        purchase = Purchase.objects.filter(
            user=request.user,
            book=book,
            status=Purchase.Status.PAID,
        ).first()
        if purchase is None:
            return _deny_access(request)
        handle = _cached_or_stamp_licensed_pdf(book, request.user, purchase)
        return serve_ranged_file(
            request,
            handle,
            filename=filename,
            content_type='application/pdf',
            as_attachment=False,
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
