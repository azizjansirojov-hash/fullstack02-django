"""Checkout → webhook → Purchase → entitlement happy paths."""

import base64
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from library.access import user_can_access_book
from library.models import Book, BookTranslation
from library.test_auth_helpers import authenticate_jwt
from payments.models import PaymentTransaction
from payments.providers.click import click_sign_complete, click_sign_prepare

User = get_user_model()

PAYMENTS_ON = dict(
    PAYMENTS_ENABLED=True,
    BOOK_PRICE_TIYIN=50_000,
    PAYME_MERCHANT_ID='payme-m',
    PAYME_MERCHANT_KEY='payme-secret-key',
    PAYME_TEST_MODE=True,
    CLICK_MERCHANT_ID='11',
    CLICK_SERVICE_ID='22',
    CLICK_SECRET_KEY='click-secret',
)


@override_settings(**PAYMENTS_ON)
class EntitlementFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='flow',
            password='testpass123',
            email='flow@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.NOVEL,
            slug='flow-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Flow',
            summary='s',
            body='body',
        )
        authenticate_jwt(self.client, self.user)

    def test_payme_end_to_end(self):
        checkout = self.client.post(
            reverse('payments:checkout'),
            data={'book_slug': 'flow-book', 'provider': 'payme'},
            content_type='application/json',
        )
        self.assertEqual(checkout.status_code, 200)
        tx_id = checkout.json()['transaction_id']
        self.assertFalse(user_can_access_book(self.user, self.book))

        auth = 'Basic ' + base64.b64encode(b'Paycom:payme-secret-key').decode()
        for method, params in (
            (
                'CheckPerformTransaction',
                {'amount': 50_000, 'account': {'order_id': tx_id}},
            ),
            (
                'CreateTransaction',
                {
                    'id': 'p1',
                    'time': 1,
                    'amount': 50_000,
                    'account': {'order_id': tx_id},
                },
            ),
            ('PerformTransaction', {'id': 'p1'}),
        ):
            response = self.client.post(
                reverse('payments:payme-webhook'),
                data=json.dumps({'id': 1, 'method': method, 'params': params}),
                content_type='application/json',
                HTTP_AUTHORIZATION=auth,
            )
            self.assertIn('result', response.json(), response.json())

        self.assertTrue(user_can_access_book(self.user, self.book))
        status = self.client.get(reverse('payments:transaction-status', args=[tx_id]))
        self.assertEqual(status.json()['status'], PaymentTransaction.Status.PAID)

    def test_click_end_to_end(self):
        checkout = self.client.post(
            reverse('payments:checkout'),
            data={'book_slug': 'flow-book', 'provider': 'click'},
            content_type='application/json',
        )
        tx_id = checkout.json()['transaction_id']
        tx = PaymentTransaction.objects.get(pk=tx_id)
        amount = str(tx.amount_uzs)
        sign_time = '2026-01-02 10:00:00'
        prep = click_sign_prepare(
            click_trans_id='55',
            service_id='22',
            secret_key='click-secret',
            merchant_trans_id=tx_id,
            amount=amount,
            action='0',
            sign_time=sign_time,
        )
        self.client.post(
            reverse('payments:click-prepare'),
            data={
                'click_trans_id': '55',
                'service_id': '22',
                'merchant_trans_id': tx_id,
                'amount': amount,
                'action': '0',
                'sign_time': sign_time,
                'sign_string': prep,
                'error': '0',
            },
        )
        comp = click_sign_complete(
            click_trans_id='55',
            service_id='22',
            secret_key='click-secret',
            merchant_trans_id=tx_id,
            merchant_prepare_id=str(tx.click_prepare_id),
            amount=amount,
            action='1',
            sign_time=sign_time,
        )
        self.client.post(
            reverse('payments:click-complete'),
            data={
                'click_trans_id': '55',
                'service_id': '22',
                'merchant_trans_id': tx_id,
                'merchant_prepare_id': str(tx.click_prepare_id),
                'amount': amount,
                'action': '1',
                'sign_time': sign_time,
                'sign_string': comp,
                'error': '0',
            },
        )
        self.assertTrue(user_can_access_book(self.user, self.book))
