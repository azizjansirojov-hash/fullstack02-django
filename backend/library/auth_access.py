"""JWT-cookie gate for media streams and staff HTML views."""

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.views import View
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from users.authentication import JWTCookieAuthentication


def ensure_request_user(request):
    """Populate request.user from the JWT access cookie only (no session fallback)."""
    try:
        result = JWTCookieAuthentication().authenticate(request)
    except (InvalidToken, TokenError):
        request.user = AnonymousUser()
        return request.user
    if result is not None:
        user, _token = result
        request.user = user
        return user
    request.user = AnonymousUser()
    return request.user


class AuthRequiredMixin:
    """Require a valid JWT access cookie."""

    def dispatch(self, request, *args, **kwargs):
        ensure_request_user(request)
        if not request.user.is_authenticated:
            if request.headers.get('Accept', '').find('application/json') != -1:
                return JsonResponse({'detail': 'Authentication required.'}, status=401)
            return redirect_to_login(request.get_full_path())
        return super().dispatch(request, *args, **kwargs)


class AuthRequiredView(AuthRequiredMixin, View):
    """Convenience base for class-based views that need JWT cookie auth."""
