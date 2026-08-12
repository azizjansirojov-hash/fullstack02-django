"""Reject empty/missing Payme transaction id before DB lookup."""

import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, BookTranslation
from payments.models import PaymentTransaction

User = get_user_model()

PAYMENTS_ON = dict(
    PAYMENTS_ENABLED=True,
    BOOK_PRICE_TIYIN=100_000,
    PAYME_MERCHANT_ID='payme-m',
    PAYME_MERCHANT_KEY='payme-secret-key',
    PAYME_TEST_MODE=True,
    CLICK_MERCHANT_ID='11',
    CLICK_SERVICE_ID='22',
    CLICK_SECRET_KEY='click-secret',
)


@override_settings(**PAYMENTS_ON)
class PaymeEmptyIdTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='emptyid',
            password='testpass123',
            email='emptyid@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.NOVEL,
            slug='empty-id-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Kitob',
            summary='s',
            body='body',
        )
        self.tx = PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            amount=100_000,
            status=PaymentTransaction.Status.CREATED,
            provider_transaction_id='',
        )

    def _auth(self):
        token = base64.b64encode(b'Paycom:payme-secret-key').decode('ascii')
        return f'Basic {token}'

    def _rpc(self, method, params):
        return self.client.post(
            reverse('payments:payme-webhook'),
            data=json.dumps({'id': 1, 'method': method, 'params': params}),
            content_type='application/json',
            HTTP_AUTHORIZATION=self._auth(),
        )

    def test_perform_empty_id_rejected(self):
        before_updated = self.tx.updated_at
        response = self._rpc('PerformTransaction', {'id': ''})
        self.assertEqual(response.json()['error']['code'], -31003)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CREATED)
        self.assertEqual(self.tx.updated_at, before_updated)

    def test_perform_missing_id_rejected(self):
        before_updated = self.tx.updated_at
        response = self._rpc('PerformTransaction', {})
        self.assertEqual(response.json()['error']['code'], -31003)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CREATED)
        self.assertEqual(self.tx.updated_at, before_updated)

    def test_cancel_empty_id_rejected(self):
        before_updated = self.tx.updated_at
        response = self._rpc('CancelTransaction', {'id': '', 'reason': 1})
        self.assertEqual(response.json()['error']['code'], -31003)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CREATED)
        self.assertEqual(self.tx.updated_at, before_updated)

    def test_check_empty_id_rejected(self):
        before_updated = self.tx.updated_at
        response = self._rpc('CheckTransaction', {'id': ''})
        self.assertEqual(response.json()['error']['code'], -31003)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CREATED)
        self.assertEqual(self.tx.updated_at, before_updated)
