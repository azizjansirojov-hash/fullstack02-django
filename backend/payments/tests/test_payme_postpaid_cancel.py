"""Payme post-paid CancelTransaction revokes Purchase access."""

import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from library.access import user_can_access_book
from library.models import Book, BookTranslation, Notification, Purchase
from payments.entitlement import fulfill_paid_transaction
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
class PaymePostPaidCancelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='revokee',
            password='testpass123',
            email='revokee@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.NOVEL,
            slug='revoke-book',
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
            status=PaymentTransaction.Status.PENDING,
            provider_transaction_id='payme-revoke-1',
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

    def test_post_paid_cancel_revokes_purchase_and_access(self):
        fulfill_paid_transaction(self.tx, provider_transaction_id='payme-revoke-1')
        self.assertTrue(user_can_access_book(self.user, self.book))

        response = self._rpc(
            'CancelTransaction',
            {'id': 'payme-revoke-1', 'reason': 5},
        )
        body = response.json()
        self.assertIn('result', body, body)
        self.assertEqual(body['result']['state'], -2)

        purchase = Purchase.objects.get(user=self.user, book=self.book)
        self.assertEqual(purchase.status, Purchase.Status.REFUNDED)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CANCELLED)
        self.assertIn('revoked_at', self.tx.raw_payload)
        self.assertFalse(user_can_access_book(self.user, self.book))
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                type=Notification.Type.PURCHASE_REFUNDED,
            ).count(),
            1,
        )

    def test_post_paid_cancel_idempotent(self):
        fulfill_paid_transaction(self.tx, provider_transaction_id='payme-revoke-1')
        first = self._rpc('CancelTransaction', {'id': 'payme-revoke-1', 'reason': 5})
        self.assertIn('result', first.json())
        revoked_at = PaymentTransaction.objects.get(pk=self.tx.pk).raw_payload.get(
            'revoked_at'
        )

        second = self._rpc('CancelTransaction', {'id': 'payme-revoke-1', 'reason': 5})
        self.assertIn('result', second.json())
        self.assertEqual(second.json()['result']['state'], -2)

        purchase = Purchase.objects.get(user=self.user, book=self.book)
        self.assertEqual(purchase.status, Purchase.Status.REFUNDED)
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                type=Notification.Type.PURCHASE_REFUNDED,
            ).count(),
            1,
        )
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.raw_payload.get('revoked_at'), revoked_at)

    def test_cancel_before_paid_does_not_create_refund_notification(self):
        response = self._rpc(
            'CancelTransaction',
            {'id': 'payme-revoke-1', 'reason': 4},
        )
        self.assertIn('result', response.json())
        self.assertEqual(response.json()['result']['state'], -1)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CANCELLED)
        self.assertFalse(
            Purchase.objects.filter(user=self.user, book=self.book).exists()
        )
        self.assertEqual(
            Notification.objects.filter(
                type=Notification.Type.PURCHASE_REFUNDED,
            ).count(),
            0,
        )
