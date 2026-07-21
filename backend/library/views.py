"""Catalog and book reader views."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .catalog_context import DISPLAY_LANG, build_catalog_context
from .models import Book


class CatalogView(View):
    """Browse published books by search and category. Reading requires an account."""

    template_name = 'library/catalog.html'

    def get(self, request):
        context = build_catalog_context(request)
        return render(request, self.template_name, context)


class BookDetailView(LoginRequiredMixin, View):
    """Book preview with metadata. Full text opens in the immersive reader."""

    template_name = 'library/book_detail.html'
    raise_exception = False

    def get(self, request, slug):
        book = get_object_or_404(
            Book.objects.prefetch_related('translations'),
            slug=slug,
            is_published=True,
        )

        translation = book.get_translation(DISPLAY_LANG)

        can_read = bool(translation and translation.body.strip())

        return render(
            request,
            self.template_name,
            {
                'book': book,
                'translation': translation,
                'can_read': can_read,
                'read_url': request.build_absolute_uri(
                    f"/library/{book.slug}/read/"
                ),
                'audio_url': book.audio_file.url if book.audio_file else '',
                'pdf_url': book.pdf_file.url if book.pdf_file else '',
            },
        )


class BookReadView(LoginRequiredMixin, View):
    """Immersive reader with page-turn animation. Requires a signed-in account."""

    template_name = 'library/book_read.html'
    raise_exception = False

    def get(self, request, slug):
        book = get_object_or_404(
            Book.objects.prefetch_related('translations'),
            slug=slug,
            is_published=True,
        )

        translation = book.get_translation(DISPLAY_LANG)
        if not translation or not translation.body.strip():
            return redirect('library:book-detail', slug=slug)

        return render(
            request,
            self.template_name,
            {
                'book': book,
                'translation': translation,
                'audio_url': book.audio_file.url if book.audio_file else '',
                'pdf_url': book.pdf_file.url if book.pdf_file else '',
                'audio_sync': translation.audio_sync or [],
            },
        )