"""API URL routes for the library (mounted under /api/library/)."""

from django.urls import path

from . import api_views

app_name = 'library_api'

urlpatterns = [
    path('', api_views.CatalogAPIView.as_view(), name='catalog'),
    path('my/', api_views.MyLibraryAPIView.as_view(), name='my-library'),
    path(
        '<slug:slug>/progress/',
        api_views.ReadingProgressAPIView.as_view(),
        name='reading-progress',
    ),
    path(
        '<slug:slug>/status/',
        api_views.ReadingStatusAPIView.as_view(),
        name='reading-status',
    ),
    path(
        '<slug:slug>/reader/',
        api_views.BookReaderManifestAPIView.as_view(),
        name='reader-manifest',
    ),
    path(
        '<slug:slug>/reviews/',
        api_views.ReviewAPIView.as_view(),
        name='book-reviews',
    ),
    path('<slug:slug>/', api_views.BookDetailAPIView.as_view(), name='book-detail'),
]
