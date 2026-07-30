"""URL routes for the Libro.UZ library."""

from django.urls import path

from . import media_views, views

app_name = 'library'

# Always mounted — gated media streams + immersive reader.
media_urlpatterns = [
    path(
        'media/<slug:slug>/pdf/',
        media_views.BookPdfMediaView.as_view(),
        name='book-media-pdf',
    ),
    path(
        'media/<slug:slug>/audio/',
        media_views.BookAudioMediaView.as_view(),
        name='book-media-audio',
    ),
    path(
        'media/<slug:slug>/audio/<int:chapter_id>/',
        media_views.BookChapterAudioMediaView.as_view(),
        name='book-media-chapter-audio',
    ),
]

book_read_urlpattern = path(
    '<slug:slug>/read/',
    views.BookReadToSpaRedirectView.as_view(),
    name='book-read',
)

media_and_read_urlpatterns = media_urlpatterns + [book_read_urlpattern]

# Local dual-stack: redirect catalog/detail URL names to the React SPA.
# (With FRONTEND_DIST, backend/urls.py remaps these names to _spa_index.)
template_catalog_urlpatterns = [
    path('', views.CatalogToSpaRedirectView.as_view(), name='catalog'),
    path('<slug:slug>/', views.BookDetailToSpaRedirectView.as_view(), name='book-detail'),
]

# Default include: full template stack (local dev without FRONTEND_DIST).
urlpatterns = media_and_read_urlpatterns + template_catalog_urlpatterns
