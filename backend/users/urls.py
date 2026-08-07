"""URL configuration for the users app."""

from django.urls import path

from . import views

app_name = 'users'

# JSON auth APIs — always mounted.
api_urlpatterns = [
    path('api/register/', views.RegisterAPIView.as_view(), name='api-register'),
    path('api/login/', views.LoginAPIView.as_view(), name='api-login'),
    path('api/csrf/', views.CsrfAPIView.as_view(), name='api-csrf'),
    path('api/me/', views.MeAPIView.as_view(), name='api-me'),
    path(
        'api/preferences/',
        views.PreferencesAPIView.as_view(),
        name='api-preferences',
    ),
    path('api/logout/', views.LogoutAPIView.as_view(), name='api-logout'),
    path(
        'api/token/refresh/',
        views.CookieTokenRefreshAPIView.as_view(),
        name='api-token-refresh',
    ),
    path(
        'api/password-reset/',
        views.PasswordResetRequestAPIView.as_view(),
        name='api-password-reset',
    ),
    path(
        'api/password-reset/confirm/',
        views.PasswordResetConfirmAPIView.as_view(),
        name='api-password-reset-confirm',
    ),
]

# Legacy Django auth paths redirect to their SPA equivalents.
page_urlpatterns = [
    path('register/', views.RegisterPageView.as_view(), name='register'),
    path('login/', views.LoginPageView.as_view(), name='login'),
    path(
        'password-reset/',
        views.PasswordResetPageView.as_view(),
        name='password-reset',
    ),
]

# Email link landing — redirects to SPA confirm route (local dual-stack).
# When FRONTEND_DIST is set, backend/urls.py mounts the SPA index instead.
confirm_urlpatterns = [
    path(
        'password-reset/<uidb64>/<token>/',
        views.PasswordResetConfirmPageView.as_view(),
        name='password-reset-confirm',
    ),
]

urlpatterns = page_urlpatterns + confirm_urlpatterns + api_urlpatterns
