"""Views for registration, login, password reset, and JWT cookie APIs."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import logout as django_logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import clear_jwt_cookies, get_tokens_for_user, set_jwt_cookies
from .authentication import CSRFEnforcedAuthentication, JWTCookieAuthentication
from .models import (
    DEFAULT_DAILY_GOAL_MINUTES,
    MAX_DAILY_GOAL_MINUTES,
    MIN_DAILY_GOAL_MINUTES,
    UserPreferences,
)
from .serializers import LoginSerializer, RegisterSerializer
from library.spa_urls import (
    spa_library_home_url,
    spa_login_url,
    spa_password_reset_confirm_url,
    spa_password_reset_url,
    spa_register_url,
)

User = get_user_model()


def _safe_redirect_url(request, candidate, fallback=None):
    """Return candidate if it is a safe same-host path; otherwise the SPA library home."""
    if fallback is None:
        fallback = spa_library_home_url()
    if not candidate:
        return fallback
    if url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    # Allow relative paths like /library/slug/
    if candidate.startswith('/') and not candidate.startswith('//'):
        return candidate
    return fallback


@method_decorator(ensure_csrf_cookie, name='dispatch')
class RegisterPageView(APIView):
    """Redirect the registration route to the SPA."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.shortcuts import redirect

        return redirect(spa_register_url())


@method_decorator(ensure_csrf_cookie, name='dispatch')
class LoginPageView(APIView):
    """Redirect the login route to the SPA."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.shortcuts import redirect

        return redirect(spa_login_url())


@method_decorator(ensure_csrf_cookie, name='dispatch')
class PasswordResetPageView(APIView):
    """Redirect the password-reset request route to the SPA."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.shortcuts import redirect

        return redirect(spa_password_reset_url())


@method_decorator(ensure_csrf_cookie, name='dispatch')
class PasswordResetConfirmPageView(APIView):
    """Redirect email confirm links to the React SPA confirm route."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, uidb64, token):
        from django.shortcuts import redirect

        return redirect(spa_password_reset_confirm_url(uidb64, token))


class RegisterAPIView(APIView):
    """Create a new user account and issue JWT cookies only (no session)."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = get_tokens_for_user(user)
        redirect_url = _safe_redirect_url(
            request,
            request.data.get('next') or request.query_params.get('next'),
        )
        response = Response(
            {
                'detail': 'Account created successfully.',
                'redirect_url': redirect_url,
                'user': {
                    'id': user.pk,
                    'username': user.username,
                    'email': user.email,
                    'is_staff': user.is_staff,
                },
            },
            status=status.HTTP_201_CREATED,
        )
        return set_jwt_cookies(response, tokens)


class LoginAPIView(APIView):
    """Authenticate a user and issue JWT cookies."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        remember_me = bool(serializer.validated_data.get('remember_me'))

        tokens = get_tokens_for_user(user, remember_me=remember_me)
        redirect_url = _safe_redirect_url(
            request,
            request.data.get('next') or request.query_params.get('next'),
        )
        response = Response(
            {
                'detail': 'Signed in successfully.',
                'redirect_url': redirect_url,
                'user': {
                    'id': user.pk,
                    'username': user.username,
                    'email': user.email,
                    'is_staff': user.is_staff,
                },
            },
            status=status.HTTP_200_OK,
        )
        return set_jwt_cookies(response, tokens, remember_me=remember_me)


class CookieTokenRefreshAPIView(APIView):
    """Issue a new access JWT from the HttpOnly refresh cookie (with rotation)."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token_refresh'

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not raw_refresh:
            return Response(
                {'detail': 'Refresh token missing.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            old = RefreshToken(raw_refresh)
        except TokenError:
            response = Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return clear_jwt_cookies(response)

        remember_me = bool(old.get('rm'))
        user_id = old.get(settings.SIMPLE_JWT.get('USER_ID_CLAIM', 'user_id'))
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            response = Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return clear_jwt_cookies(response)

        try:
            old.blacklist()
        except TokenError:
            pass

        tokens = get_tokens_for_user(user, remember_me=remember_me)
        response = Response({'detail': 'Token refreshed.'})
        return set_jwt_cookies(response, tokens, remember_me=remember_me)

@method_decorator(ensure_csrf_cookie, name='dispatch')
class CsrfAPIView(APIView):
    """Ensure a CSRF cookie is set for SPA clients."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'detail': 'ok'})


class MeAPIView(APIView):
    """Return the current authenticated user, or anonymous state."""

    permission_classes = [AllowAny]
    authentication_classes = [JWTCookieAuthentication]

    def get(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {
                    'authenticated': False,
                    'user': None,
                }
            )
        return Response(
            {
                'authenticated': True,
                'user': {
                    'id': user.pk,
                    'username': user.username,
                    'email': user.email,
                    'is_staff': user.is_staff,
                },
            }
        )


class LogoutAPIView(APIView):
    """JWT cookies are primary auth; clear residual Django session if present."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication, JWTCookieAuthentication]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass
        if request.user and request.user.is_authenticated:
            django_logout(request)
        response = Response({'detail': 'Signed out successfully.'})
        return clear_jwt_cookies(response)


class PasswordResetRequestAPIView(APIView):
    """Email a password-reset link. Always returns 200 to avoid account enumeration."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        detail = (
            'If an account exists for that email, a reset link has been sent.'
        )
        if not email:
            return Response({'detail': detail})

        users = list(User.objects.filter(email__iexact=email, is_active=True))
        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            # Prefer SPA confirm URL; Django path still redirects for old emails.
            reset_url = spa_password_reset_confirm_url(uid, token)
            if reset_url.startswith('/'):
                reset_url = request.build_absolute_uri(reset_url)
            try:
                send_mail(
                    subject='Libro.UZ — parolni tiklash',
                    message=(
                        f'Salom {user.username},\n\n'
                        f'Parolingizni tiklash uchun havola:\n{reset_url}\n\n'
                        'Agar so‘rovni siz yubormagan bo‘lsangiz,'
                        ' e’tiborsiz qoldiring.\n'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                # Keep HTTP 200 (anti-enumeration) but log so SMTP
                # misconfigurations are visible in server logs.
                logger.exception(
                    'Password-reset email failed for user pk=%s', user.pk
                )
        return Response({'detail': detail})


class PasswordResetConfirmAPIView(APIView):
    """Set a new password using uid + token from the email link."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        uidb64 = request.data.get('uid') or request.data.get('uidb64') or ''
        token = request.data.get('token') or ''
        password = request.data.get('password') or ''
        password_confirm = request.data.get('password_confirm') or ''

        if password != password_confirm:
            return Response(
                {'password_confirm': ['Passwords do not match.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'detail': 'Invalid reset link.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {'detail': 'Invalid or expired reset link.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            return Response(
                {'password': list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=['password'])
        return Response(
            {
                'detail': 'Password updated. You can now sign in.',
                'redirect_url': reverse('users:login'),
            }
        )


class PreferencesAPIView(APIView):
    """GET/PUT the current user's reading preferences (daily goal)."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [CSRFEnforcedAuthentication, JWTCookieAuthentication]

    def get(self, request):
        prefs, _ = UserPreferences.objects.get_or_create(
            user=request.user,
            defaults={'daily_goal_minutes': DEFAULT_DAILY_GOAL_MINUTES},
        )
        return Response({'daily_goal_minutes': prefs.daily_goal_minutes})

    def put(self, request):
        raw = request.data.get('daily_goal_minutes', None)
        try:
            goal = int(raw)
        except (TypeError, ValueError):
            return Response(
                {'daily_goal_minutes': 'Enter an integer between 5 and 300.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if goal < MIN_DAILY_GOAL_MINUTES or goal > MAX_DAILY_GOAL_MINUTES:
            return Response(
                {
                    'daily_goal_minutes': (
                        f'Must be between {MIN_DAILY_GOAL_MINUTES} '
                        f'and {MAX_DAILY_GOAL_MINUTES}.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        prefs, _ = UserPreferences.objects.update_or_create(
            user=request.user,
            defaults={'daily_goal_minutes': goal},
        )
        return Response({'daily_goal_minutes': prefs.daily_goal_minutes})

