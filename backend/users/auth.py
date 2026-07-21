"""JWT cookie helpers shared by authentication views."""

from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken


def get_tokens_for_user(user):
    """Return access and refresh token strings for the given user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def set_jwt_cookies(response, tokens):
    """Attach access and refresh JWTs as secure HttpOnly cookies."""
    access_max_age = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
    refresh_max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

    cookie_kwargs = {
        'httponly': settings.JWT_COOKIE_HTTPONLY,
        'secure': settings.JWT_COOKIE_SECURE,
        'samesite': settings.JWT_COOKIE_SAMESITE,
        'path': settings.JWT_COOKIE_PATH,
    }

    response.set_cookie(
        settings.JWT_ACCESS_COOKIE_NAME,
        tokens['access'],
        max_age=access_max_age,
        **cookie_kwargs,
    )
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        tokens['refresh'],
        max_age=refresh_max_age,
        **cookie_kwargs,
    )
    return response


def clear_jwt_cookies(response):
    """Remove JWT cookies from the response."""
    response.delete_cookie(
        settings.JWT_ACCESS_COOKIE_NAME,
        path=settings.JWT_COOKIE_PATH,
        samesite=settings.JWT_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_COOKIE_PATH,
        samesite=settings.JWT_COOKIE_SAMESITE,
    )
    return response
