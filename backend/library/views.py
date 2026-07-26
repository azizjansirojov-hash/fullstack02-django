"""Book reader views and SPA redirect safety nets for catalog/detail URL names."""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .access import user_can_access_book
from .auth_access import AuthRequiredMixin
from .catalog_context import DISPLAY_LANG
from .models import Book, ReadingProgress
from .spa_urls import spa_book_detail_url, spa_library_home_url


class CatalogToSpaRedirectView(View):
    """Send /library/ traffic to the React SPA dashboard (local dual-stack)."""

    def get(self, request):
        return redirect(spa_library_home_url())


class BookDetailToSpaRedirectView(View):
    """Send /library/<slug>/ to the React SPA detail page (local dual-stack)."""

    def get(self, request, slug):
        get_object_or_404(Book, slug=slug, is_published=True)
        return redirect(spa_book_detail_url(slug))


class BookReadView(AuthRequiredMixin, View):
    """Immersive reader with page-turn animation. Session or JWT cookie auth."""

    template_name = 'library/book_read.html'

    def get(self, request, slug):
        book = get_object_or_404(
            Book.objects.prefetch_related('translations', 'audio_chapters'),
            slug=slug,
            is_published=True,
        )

        if not user_can_access_book(request.user, book):
            if 'application/json' in request.headers.get('Accept', ''):
                return JsonResponse(
                    {'detail': 'Purchase required to access this book.'},
                    status=403,
                )
            return redirect(spa_book_detail_url(slug))

        translation = book.get_translation(DISPLAY_LANG)
        if not translation or not translation.body.strip():
            return redirect(spa_book_detail_url(slug))

        audio_chapters = book.get_audio_chapters_payload(include_urls=True)
        audio_url = audio_chapters[0]['url'] if audio_chapters else ''

        progress = ReadingProgress.objects.filter(
            user=request.user, book=book
        ).first()
        reading_progress = None
        if progress:
            reading_progress = {
                'exists': True,
                'mode': progress.mode,
                'page': progress.page,
                'total_pages': progress.total_pages,
                'chapter_id': progress.chapter_id,
                'position': progress.position,
            }

        return render(
            request,
            self.template_name,
            {
                'book': book,
                'translation': translation,
                'audio_url': audio_url,
                'audio_chapters': audio_chapters,
                'pdf_url': book.gated_pdf_url(),
                'audio_sync': translation.audio_sync or [],
                'reading_progress': reading_progress,
                'spa_library_url': spa_library_home_url(),
                'spa_detail_url': spa_book_detail_url(book.slug),
            },
        )
