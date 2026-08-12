"""Checkout API and purchasability rules."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, BookTranslation, Purchase
from library.test_auth_helpers import authenticate_jwt
from payments.models import PaymentTransaction

User = get_user_model()

PAYMENTS_ON = dict(
    PAYMENTS_ENABLED=True,
    BOOK_PRICE_TIYIN=1_000_00,  # 1000 UZS
    PAYME_MERCHANT_ID='payme-m',
    PAYME_MERCHANT_KEY='payme-key',
    PAYME_TEST_MODE=True,
    CLICK_MERCHANT_ID='click-m',
    CLICK_SERVICE_ID='click-s',
    CLICK_SECRET_KEY='click-secret',
)


@override_settings(**PAYMENTS_ON)
class CheckoutAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='payer',
            password='testpass123',
            email='payer@example.com',
        )
        self.licensed = Book.objects.create(
            author_name='Licensed',
            category=Book.Category.NOVEL,
            slug='licensed-for-sale',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
        )
        BookTranslation.objects.create(
            book=self.licensed,
            language=BookTranslation.Language.UZ,
            title='Pullik',
            summary='s',
            body='body',
        )
        self.unset = Book.objects.create(
            author_name='Unset',
            category=Book.Category.OTHER,
            slug='unset-rights',
            is_published=True,
            rights_status=Book.RightsStatus.UNSET,
        )
        BookTranslation.objects.create(
            book=self.unset,
            language=BookTranslation.Language.UZ,
            title='Unset',
            summary='s',
            body='body',
        )
        self.public = Book.objects.create(
            author_name='Public',
            category=Book.Category.HISTORY,
            slug='public-free',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
        )
        BookTranslation.objects.create(
            book=self.public,
            language=BookTranslation.Language.UZ,
            title='Free',
            summary='s',
            body='body',
        )
        authenticate_jwt(self.client, self.user)

    def _checkout(self, slug, provider='payme'):
        return self.client.post(
            reverse('payments:checkout'),
            data={'book_slug': slug, 'provider': provider},
            content_type='application/json',
        )

    def test_licensed_checkout_creates_transaction(self):
        response = self._checkout('licensed-for-sale', 'payme')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['amount_tiyin'], 100_000)
        self.assertIn('checkout_url', body)
        self.assertTrue(
            PaymentTransaction.objects.filter(
                user=self.user,
                book=self.licensed,
                status=PaymentTransaction.Status.CREATED,
            ).exists()
        )

    def test_reuse_pending_transaction(self):
        first = self._checkout('licensed-for-sale', 'payme')
        second = self._checkout('licensed-for-sale', 'click')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['transaction_id'], second.json()['transaction_id'])
        self.assertEqual(
            PaymentTransaction.objects.filter(user=self.user, book=self.licensed).count(),
            1,
        )
        tx = PaymentTransaction.objects.get(pk=first.json()['transaction_id'])
        self.assertEqual(tx.provider, 'click')

    def test_unset_rejected(self):
        response = self._checkout('unset-rights')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'not_purchasable')

    def test_public_domain_conflict(self):
        response = self._checkout('public-free')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'already_entitled')

    def test_already_paid_conflict(self):
        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
        )
        response = self._checkout('licensed-for-sale')
        self.assertEqual(response.status_code, 409)

    @override_settings(PAYMENTS_ENABLED=False)
    def test_disabled_returns_503(self):
        response = self._checkout('licensed-for-sale')
        self.assertEqual(response.status_code, 503)
