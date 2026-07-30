"""Book reader SPA redirects and catalog/detail URL safety nets."""

from django.shortcuts import get_object_or_404, redirect
from django.views import View

from .models import Book
from .spa_urls import spa_book_detail_url, spa_book_read_url, spa_library_home_url


class CatalogToSpaRedirectView(View):
    """Send /library/ traffic to the React SPA dashboard (local dual-stack)."""

    def get(self, request):
        return redirect(spa_library_home_url())


class BookDetailToSpaRedirectView(View):
    """Send /library/<slug>/ to the React SPA detail page (local dual-stack)."""

    def get(self, request, slug):
        get_object_or_404(Book, slug=slug, is_published=True)
        return redirect(spa_book_detail_url(slug))


class BookReadToSpaRedirectView(View):
    """Send /library/<slug>/read/ to the React immersive reader (local dual-stack).

    Auth and entitlement are enforced by the SPA + reader manifest API.
    Preserves query string and hash is client-only (not sent to server).
    """

    def get(self, request, slug):
        get_object_or_404(Book, slug=slug, is_published=True)
        target = spa_book_read_url(slug)
        qs = request.META.get('QUERY_STRING', '')
        if qs:
            target = f'{target}?{qs}' if '?' not in target else f'{target}&{qs}'
        return redirect(target)
