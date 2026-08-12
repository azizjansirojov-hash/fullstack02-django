"""Webhook idempotency and rejection paths for Payme + Click."""

import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, BookTranslation, Notification, Purchase
from payments.models import PaymentTransaction
from payments.providers.click import click_sign_complete, click_sign_prepare

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
class WebhookIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            password='testpass123',
            email='buyer@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.NOVEL,
            slug='paid-book',
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

    def _payme_auth(self):
        token = base64.b64encode(b'Paycom:payme-secret-key').decode('ascii')
        return f'Basic {token}'

    def _payme(self, method, params, rpc_id=1):
        return self.client.post(
            reverse('payments:payme-webhook'),
            data=json.dumps({'id': rpc_id, 'method': method, 'params': params}),
            content_type='application/json',
            HTTP_AUTHORIZATION=self._payme_auth(),
        )

    def test_payme_happy_path_and_idempotent_perform(self):
        tx = PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            amount=100_000,
            status=PaymentTransaction.Status.CREATED,
        )
        check = self._payme(
            'CheckPerformTransaction',
            {'amount': 100_000, 'account': {'order_id': str(tx.id)}},
        )
        self.assertEqual(check.status_code, 200)
        self.assertIn('result', check.json())

        create = self._payme(
            'CreateTransaction',
            {
                'id': 'payme-tx-1',
                'time': 1_700_000_000_000,
                'amount': 100_000,
                'account': {'order_id': str(tx.id)},
            },
        )
        self.assertIn('result', create.json(), create.json())

        perform = self._payme('PerformTransaction', {'id': 'payme-tx-1'})
        self.assertIn('result', perform.json(), perform.json())
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.PAID)
        self.assertEqual(Purchase.objects.filter(user=self.user, book=self.book).count(), 1)
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                type=Notification.Type.PURCHASE_PAID,
            ).count(),
            1,
        )

        # Replay Perform — still one purchase / one notification.
        replay = self._payme('PerformTransaction', {'id': 'payme-tx-1'})
        self.assertIn('result', replay.json())
        self.assertEqual(Purchase.objects.filter(user=self.user, book=self.book).count(), 1)
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                type=Notification.Type.PURCHASE_PAID,
            ).count(),
            1,
        )
        from library.access import user_can_access_book

        self.assertTrue(user_can_access_book(self.user, self.book))

    def test_payme_rejects_bad_auth(self):
        response = self.client.post(
            reverse('payments:payme-webhook'),
            data=json.dumps(
                {
                    'id': 1,
                    'method': 'CheckPerformTransaction',
                    'params': {'amount': 1, 'account': {'order_id': 'x'}},
                }
            ),
            content_type='application/json',
            HTTP_AUTHORIZATION='Basic ' + base64.b64encode(b'Paycom:wrong').decode(),
        )
        self.assertEqual(response.json()['error']['code'], -32504)

    def test_payme_amount_mismatch(self):
        tx = PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            amount=100_000,
        )
        response = self._payme(
            'CheckPerformTransaction',
            {'amount': 50_000, 'account': {'order_id': str(tx.id)}},
        )
        self.assertEqual(response.json()['error']['code'], -31001)

    def test_click_happy_path_and_idempotent_complete(self):
        tx = PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.CLICK,
            amount=100_000,
            status=PaymentTransaction.Status.CREATED,
        )
        amount = str(tx.amount_uzs)
        sign_time = '2026-05-05 14:30:00'
        prepare_sign = click_sign_prepare(
            click_trans_id='999',
            service_id='22',
            secret_key='click-secret',
            merchant_trans_id=str(tx.id),
            amount=amount,
            action='0',
            sign_time=sign_time,
        )
        prepare = self.client.post(
            reverse('payments:click-prepare'),
            data={
                'click_trans_id': '999',
                'service_id': '22',
                'merchant_trans_id': str(tx.id),
                'amount': amount,
                'action': '0',
                'sign_time': sign_time,
                'sign_string': prepare_sign,
                'error': '0',
            },
        )
        self.assertEqual(prepare.json()['error'], 0, prepare.json())

        complete_sign = click_sign_complete(
            click_trans_id='999',
            service_id='22',
            secret_key='click-secret',
            merchant_trans_id=str(tx.id),
            merchant_prepare_id=str(tx.click_prepare_id),
            amount=amount,
            action='1',
            sign_time=sign_time,
        )
        complete_data = {
            'click_trans_id': '999',
            'service_id': '22',
            'merchant_trans_id': str(tx.id),
            'merchant_prepare_id': str(tx.click_prepare_id),
            'amount': amount,
            'action': '1',
            'sign_time': sign_time,
            'sign_string': complete_sign,
            'error': '0',
        }
        complete = self.client.post(reverse('payments:click-complete'), data=complete_data)
        self.assertEqual(complete.json()['error'], 0, complete.json())
        self.assertEqual(Purchase.objects.filter(user=self.user, book=self.book).count(), 1)
        notes = Notification.objects.filter(
            user=self.user,
            type=Notification.Type.PURCHASE_PAID,
        ).count()
        self.assertEqual(notes, 1)

        replay = self.client.post(reverse('payments:click-complete'), data=complete_data)
        self.assertEqual(replay.json()['error'], 0)
        self.assertEqual(Purchase.objects.filter(user=self.user, book=self.book).count(), 1)
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                type=Notification.Type.PURCHASE_PAID,
            ).count(),
            1,
        )

    def test_click_rejects_bad_sign(self):
        tx = PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.CLICK,
            amount=100_000,
        )
        response = self.client.post(
            reverse('payments:click-prepare'),
            data={
                'click_trans_id': '1',
                'service_id': '22',
                'merchant_trans_id': str(tx.id),
                'amount': '1000',
                'action': '0',
                'sign_time': '2026-01-01 00:00:00',
                'sign_string': 'not-a-valid-md5',
                'error': '0',
            },
        )
        self.assertEqual(response.json()['error'], -1)
