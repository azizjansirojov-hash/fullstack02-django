"""Tests for registration and login flows."""

import logging
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library.spa_urls import (
    spa_library_home_url,
    spa_login_url,
    spa_password_reset_url,
    spa_register_url,
)

User = get_user_model()


class AuthPageTests(TestCase):
    def test_register_page_redirects_to_spa(self):
        response = self.client.get(reverse('users:register'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_register_url())

    def test_login_page_redirects_to_spa(self):
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_login_url())

    def test_password_reset_page_redirects_to_spa(self):
        response = self.client.get(reverse('users:password-reset'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_password_reset_url())

    def test_home_redirects_to_login(self):
        response = self.client.get('/')
        self.assertRedirects(
            response,
            reverse('users:login'),
            fetch_redirect_response=False,
        )


class RegisterAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('users:api-register')
        self.valid_payload = {
            'username': 'alice',
            'email': 'alice@example.com',
            'password': 'Str0ng-Passw0rd!',
            'password_confirm': 'Str0ng-Passw0rd!',
        }

    def test_register_success(self):
        response = self.client.post(
            self.url,
            data=self.valid_payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='alice').exists())
        body = response.json()
        self.assertIn('redirect_url', body)
        self.assertIn('user', body)
        self.assertEqual(body['user']['username'], 'alice')
        self.assertNotIn('access', body)
        self.assertNotIn('refresh', body)
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)
        self.assertTrue(response.cookies['access_token']['httponly'])
        self.assertTrue(response.cookies['refresh_token']['httponly'])

    def test_register_requires_csrf_for_session_client(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            self.url,
            data=self.valid_payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_register_duplicate_username(self):
        User.objects.create_user(username='alice', password='Str0ng-Passw0rd!')
        response = self.client.post(
            self.url,
            data=self.valid_payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json())

    def test_register_password_mismatch(self):
        payload = {**self.valid_payload, 'password_confirm': 'Different-Pass1!'}
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('password_confirm', response.json())

    def test_register_weak_password(self):
        payload = {
            **self.valid_payload,
            'password': 'password',
            'password_confirm': 'password',
        }
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json())

    def test_register_requires_email(self):
        payload = {**self.valid_payload, 'email': ''}
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json())

    def test_register_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            username='existing',
            email='Alice@Example.com',
            password='Str0ng-Passw0rd!',
        )
        payload = {**self.valid_payload, 'username': 'alice2', 'email': 'alice@example.com'}
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json())

    def test_email_ci_unique_constraint_at_db(self):
        from django.db import IntegrityError, transaction

        User.objects.create_user(
            username='one',
            email='unique@example.com',
            password='Str0ng-Passw0rd!',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username='two',
                    email='UNIQUE@example.com',
                    password='Str0ng-Passw0rd!',
                )

    def test_register_rejects_disposable_email(self):
        payload = {**self.valid_payload, 'email': 'user@mailinator.com'}
        response = self.client.post(
            self.url,
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json())


class PasswordResetEmailTests(TestCase):
    """Password-reset email: SMTP failure is logged but HTTP 200 is still returned."""

    def setUp(self):
        cache.clear()
        self.url = reverse('users:api-password-reset')
        self.user = User.objects.create_user(
            username='resetme',
            email='resetme@example.com',
            password='Str0ng-Passw0rd!',
        )

    def test_reset_returns_200_even_when_smtp_fails(self):
        from smtplib import SMTPException

        with patch('users.views.send_mail', side_effect=SMTPException('conn refused')):
            with self.assertLogs('users.views', level=logging.ERROR) as log_ctx:
                response = self.client.post(
                    self.url,
                    data={'email': 'resetme@example.com'},
                    content_type='application/json',
                )
        self.assertEqual(response.status_code, 200)
        self.assertIn('reset link has been sent', response.json()['detail'])
        # At least one ERROR/EXCEPTION entry mentioning the user pk
        combined = ' '.join(log_ctx.output)
        self.assertIn(str(self.user.pk), combined)

    def test_reset_returns_200_for_unknown_email(self):
        response = self.client.post(
            self.url,
            data={'email': 'nobody@example.com'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)


class PasswordResetConfirmThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_confirm_view_has_password_reset_throttle(self):
        from rest_framework.throttling import ScopedRateThrottle

        from users.views import PasswordResetConfirmAPIView

        self.assertEqual(
            PasswordResetConfirmAPIView.throttle_scope,
            'password_reset',
        )
        self.assertIn(ScopedRateThrottle, PasswordResetConfirmAPIView.throttle_classes)


class CookieTokenRefreshThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='refresh_throttle',
            email='refresh_throttle@example.com',
            password='Str0ng-Passw0rd!',
        )

    def test_refresh_view_has_token_refresh_throttle(self):
        from rest_framework.throttling import ScopedRateThrottle

        from users.views import CookieTokenRefreshAPIView

        self.assertEqual(
            CookieTokenRefreshAPIView.throttle_scope,
            'token_refresh',
        )
        self.assertIn(ScopedRateThrottle, CookieTokenRefreshAPIView.throttle_classes)

    def test_21st_refresh_returns_429(self):
        login = self.client.post(
            reverse('users:api-login'),
            data={
                'username': 'refresh_throttle',
                'password': 'Str0ng-Passw0rd!',
            },
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        url = reverse('users:api-token-refresh')
        statuses = []
        for _ in range(21):
            statuses.append(
                self.client.post(url, data={}, content_type='application/json').status_code
            )
        self.assertEqual(statuses[:20], [200] * 20, statuses)
        self.assertEqual(statuses[20], 429, statuses)


class LoginAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('users:api-login')
        self.user = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='Str0ng-Passw0rd!',
        )

    def test_login_success_sets_jwt_cookies(self):
        response = self.client.post(
            self.url,
            data={'username': 'bob', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['user']['username'], 'bob')
        self.assertNotIn('access', body)
        self.assertNotIn('refresh', body)

        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)

        access_cookie = response.cookies['access_token']
        refresh_cookie = response.cookies['refresh_token']
        self.assertTrue(access_cookie['httponly'])
        self.assertTrue(refresh_cookie['httponly'])
        self.assertEqual(access_cookie['samesite'], 'Lax')
        self.assertEqual(refresh_cookie['samesite'], 'Lax')
        # DEBUG=True in settings => Secure cookies are off in development.
        self.assertFalse(access_cookie['secure'])
        self.assertFalse(refresh_cookie['secure'])

    def test_login_invalid_credentials(self):
        response = self.client.post(
            self.url,
            data={'username': 'bob', 'password': 'wrong-password'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json())
        self.assertNotIn('access_token', response.cookies)

    def test_login_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        response = self.client.post(
            self.url,
            data={'username': 'bob', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        # Inactive users fail authenticate() and get a generic message,
        # which avoids account-existence leaks.
        self.assertIn('detail', body)

    def test_login_requires_csrf_for_session_client(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            self.url,
            data={'username': 'bob', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(JWT_COOKIE_SECURE=True)
    def test_secure_cookie_flag_when_configured(self):
        response = self.client.post(
            self.url,
            data={'username': 'bob', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies['access_token']['secure'])
        self.assertTrue(response.cookies['refresh_token']['secure'])

    def test_default_refresh_cookie_is_one_day(self):
        response = self.client.post(
            self.url,
            data={'username': 'bob', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.cookies['refresh_token']['max-age']), 86400)

    def test_remember_me_refresh_cookie_is_seven_days(self):
        response = self.client.post(
            self.url,
            data={
                'username': 'bob',
                'password': 'Str0ng-Passw0rd!',
                'remember_me': True,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.cookies['refresh_token']['max-age']), 604800)
        refresh = self.client.post(
            reverse('users:api-token-refresh'),
            data={},
            content_type='application/json',
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertEqual(int(refresh.cookies['refresh_token']['max-age']), 604800)


class Argon2HasherTests(TestCase):
    def test_new_user_uses_argon2(self):
        user = User.objects.create_user(
            username='argonuser',
            email='argon@example.com',
            password='Str0ng-Passw0rd!',
        )
        self.assertTrue(user.password.startswith('argon2'))

    def test_pbkdf2_user_can_login_and_hash_upgrades(self):
        from django.contrib.auth.hashers import make_password

        user = User.objects.create_user(
            username='legacyhash',
            email='legacyhash@example.com',
            password='Str0ng-Passw0rd!',
        )
        user.password = make_password('Str0ng-Passw0rd!', hasher='pbkdf2_sha256')
        user.save(update_fields=['password'])
        self.assertTrue(user.password.startswith('pbkdf2_'))
        response = self.client.post(
            reverse('users:api-login'),
            data={'username': 'legacyhash', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith('argon2'))
