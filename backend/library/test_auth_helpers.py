"""Shared JWT cookie helpers for Django tests (JWT-only auth)."""

from django.conf import settings

from users.auth import get_tokens_for_user


def authenticate_jwt(client, user):
    """Attach JWT cookies for user; clear session so tests prove JWT-only access."""
    tokens = get_tokens_for_user(user)
    client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']
    client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = tokens['refresh']
    client.cookies.pop('sessionid', None)
    return tokens
