"""Views for registration and login pages and APIs."""

from django.contrib.auth import login as django_login
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import get_tokens_for_user, set_jwt_cookies
from .authentication import CSRFEnforcedAuthentication
from .serializers import LoginSerializer, RegisterSerializer


def _safe_redirect_url(request, candidate, fallback_name='library:catalog'):
    """Return candidate if it is a safe same-host path; otherwise the fallback."""
    fallback = reverse(fallback_name)
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
    """Render the registration page and ensure a CSRF cookie is set."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return render(request, 'users/register.html')


@method_decorator(ensure_csrf_cookie, name='dispatch')
class LoginPageView(APIView):
    """Render the login page and ensure a CSRF cookie is set."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return render(request, 'users/login.html')


class RegisterAPIView(APIView):
    """Create a new user account."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        login_url = f"{reverse('users:login')}?registered=1"
        return Response(
            {
                'detail': 'Account created successfully. You can now sign in.',
                'redirect_url': login_url,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    """Authenticate a user and issue JWT cookies."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Keep Django's request.user available for templates/messages.
        django_login(request, user)

        tokens = get_tokens_for_user(user)
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
                },
            },
            status=status.HTTP_200_OK,
        )
        return set_jwt_cookies(response, tokens)
