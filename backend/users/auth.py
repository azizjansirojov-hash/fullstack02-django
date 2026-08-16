"""JWT cookie helpers shared by authentication views."""

from datetime import timedelta

from django.conf import settings
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

REMEMBER_ME_CLAIM = 'rm'
REMEMBER_ME_REFRESH_LIFETIME = timedelta(days=7)


def refresh_lifetime(*, remember_me: bool) -> timedelta:
    if remember_me:
        return REMEMBER_ME_REFRESH_LIFETIME
    return settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']


def get_tokens_for_user(user, *, remember_me=False):
    """Return access and refresh token strings for the given user."""
    refresh = RefreshToken.for_user(user)
    remember_me = bool(remember_me)
    refresh.set_exp(lifetime=refresh_lifetime(remember_me=remember_me))
    refresh[REMEMBER_ME_CLAIM] = remember_me
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'remember_me': remember_me,
    }


def remember_me_from_refresh(raw_refresh) -> bool:
    try:
        token = RefreshToken(raw_refresh)
        return bool(token.get(REMEMBER_ME_CLAIM))
    except TokenError:
        return False


def set_jwt_cookies(response, tokens, *, remember_me=None):
    """Attach access and refresh JWTs as secure HttpOnly cookies."""
    access_max_age = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
    if remember_me is None:
        remember_me = remember_me_from_refresh(tokens.get('refresh', ''))
    refresh_max_age = int(refresh_lifetime(remember_me=bool(remember_me)).total_seconds())

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
