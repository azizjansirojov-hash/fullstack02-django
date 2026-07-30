"""
URL configuration for backend project.

When FRONTEND_DIST is set, the React SPA is the product UI at `/`.
Django keeps admin, APIs, gated media, and SPA shells when FRONTEND_DIST is set.
"""

from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

from library.urls import (
    media_and_read_urlpatterns,
    media_urlpatterns,
    template_catalog_urlpatterns,
)
from library.health_views import GenerationHealthView
from library.legal_views import (
    PrivacyPageView,
    RightsReportAPIView,
    RightsReportPageView,
    TermsPageView,
)
from users.urls import api_urlpatterns as users_api_urlpatterns
from users.urls import confirm_urlpatterns as users_confirm_urlpatterns
from users.urls import page_urlpatterns as users_page_urlpatterns

admin.site.site_header = 'Libro.UZ'
admin.site.site_title = 'Libro.UZ'
admin.site.index_title = 'Libro.UZ'

_frontend_dist = getattr(settings, 'FRONTEND_DIST', None) or None
_spa_enabled = bool(_frontend_dist and Path(_frontend_dist).is_dir())


def _spa_index(_request):
    """Serve the built React index.html for same-origin production."""
    dist = Path(settings.FRONTEND_DIST)
    index = dist / 'index.html'
    if not index.is_file():
        raise Http404('SPA build not found.')
    return FileResponse(index.open('rb'), content_type='text/html')


# Public covers only — never serve books/pdf or books/audio openly.
_covers_root = Path(settings.MEDIA_ROOT) / 'covers'
_cover_patterns = [
    re_path(
        r'^media/covers/(?P<path>.*)$',
        serve,
        {'document_root': str(_covers_root)},
    ),
]

if _spa_enabled:
    dist = Path(_frontend_dist)
    # SPA owns password-reset confirm HTML; keep Django name for reverse()/emails.
    users_urlpatterns = (
        users_api_urlpatterns
        + [
            path('login/', _spa_index, name='login'),
            path('register/', _spa_index, name='register'),
            path('password-reset/', _spa_index, name='password-reset'),
            path(
                'password-reset/<uidb64>/<token>/',
                _spa_index,
                name='password-reset-confirm',
            ),
        ]
    )
    library_urlpatterns = media_urlpatterns + [
        path('', _spa_index, name='catalog'),
        path('<slug:slug>/', _spa_index, name='book-detail'),
        path('<slug:slug>/read/', _spa_index, name='book-read'),
    ]
    urlpatterns = [
        path('admin/', admin.site.urls),
        path('health/generation/', GenerationHealthView.as_view(), name='generation-health'),
        path('terms/', TermsPageView.as_view(), name='terms'),
        path('privacy/', PrivacyPageView.as_view(), name='privacy'),
        path('rights-report/', RightsReportPageView.as_view(), name='rights-report'),
        path('api/rights-report/', RightsReportAPIView.as_view(), name='rights-report-api'),
        path('', _spa_index, name='home'),
        path('', include((users_urlpatterns, 'users'))),
        path('api/library/', include('library.api_urls')),
        path('api/notifications/', include('library.notification_urls')),
        path('library/', include((library_urlpatterns, 'library'))),
        *_cover_patterns,
        re_path(
            r'^assets/(?P<path>.*)$',
            serve,
            {'document_root': str(dist / 'assets')},
        ),
    ]
else:
    users_urlpatterns = (
        users_page_urlpatterns + users_confirm_urlpatterns + users_api_urlpatterns
    )
    library_urlpatterns = media_and_read_urlpatterns + template_catalog_urlpatterns
    urlpatterns = [
        path('admin/', admin.site.urls),
        path('health/generation/', GenerationHealthView.as_view(), name='generation-health'),
        path('terms/', TermsPageView.as_view(), name='terms'),
        path('privacy/', PrivacyPageView.as_view(), name='privacy'),
        path('rights-report/', RightsReportPageView.as_view(), name='rights-report'),
        path('api/rights-report/', RightsReportAPIView.as_view(), name='rights-report-api'),
        path(
            '',
            RedirectView.as_view(pattern_name='users:login', permanent=False),
            name='home',
        ),
        path('', include((users_urlpatterns, 'users'))),
        path('api/library/', include('library.api_urls')),
        path('api/notifications/', include('library.notification_urls')),
        path('library/', include((library_urlpatterns, 'library'))),
        *_cover_patterns,
    ]
