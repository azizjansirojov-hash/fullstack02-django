"""Payme GetStatement returns transactions in the requested time window."""

import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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

T0 = 1_700_000_000_000
T1 = 1_700_000_100_000
T2 = 1_700_000_200_000
T3 = 1_700_000_300_000


@override_settings(**PAYMENTS_ON)
class PaymeGetStatementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='stmt',
            password='testpass123',
            email='stmt@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.NOVEL,
            slug='statement-book',
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

    def _tx(self, payme_id, create_time, *, amount=100_000, status=None):
        return PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            amount=amount,
            status=status or PaymentTransaction.Status.PAID,
            provider_transaction_id=payme_id,
            raw_payload={'create_time': create_time, 'perform_time': 0, 'cancel_time': 0},
        )

    def test_empty_window(self):
        self._tx('payme-a', T1)
        response = self._rpc('GetStatement', {'from': T0, 'to': T0 + 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['transactions'], [])

    def test_single_transaction(self):
        tx = self._tx('payme-one', T1)
        response = self._rpc('GetStatement', {'from': T1, 'to': T1})
        rows = response.json()['result']['transactions']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['id'], 'payme-one')
        self.assertEqual(row['time'], T1)
        self.assertEqual(row['amount'], 100_000)
        self.assertEqual(row['account'], {'order_id': str(tx.id)})
        self.assertEqual(row['create_time'], T1)
        self.assertEqual(row['transaction'], str(tx.id))
        self.assertEqual(row['state'], 2)

    def test_multiple_transactions_ordered(self):
        later = self._tx('payme-later', T2)
        earlier = self._tx('payme-earlier', T1)
        outside = self._tx('payme-outside', T3)
        response = self._rpc('GetStatement', {'from': T1, 'to': T2})
        rows = response.json()['result']['transactions']
        ids = [row['id'] for row in rows]
        self.assertEqual(ids, ['payme-earlier', 'payme-later'])
        self.assertEqual(rows[0]['transaction'], str(earlier.id))
        self.assertEqual(rows[1]['transaction'], str(later.id))
        self.assertNotIn(str(outside.id), [row['transaction'] for row in rows])

    def test_boundary_timestamps_inclusive(self):
        at_from = self._tx('payme-from', T1)
        at_to = self._tx('payme-to', T2)
        before = self._tx('payme-before', T1 - 1)
        after = self._tx('payme-after', T2 + 1)
        response = self._rpc('GetStatement', {'from': T1, 'to': T2})
        ids = {row['id'] for row in response.json()['result']['transactions']}
        self.assertEqual(ids, {'payme-from', 'payme-to'})
        self.assertNotIn('payme-before', ids)
        self.assertNotIn('payme-after', ids)
        self.assertEqual(
            {row['transaction'] for row in response.json()['result']['transactions']},
            {str(at_from.id), str(at_to.id)},
        )
        self.assertNotIn(str(before.id), {row['transaction'] for row in response.json()['result']['transactions']})
        self.assertNotIn(str(after.id), {row['transaction'] for row in response.json()['result']['transactions']})

    def test_skips_rows_without_payme_id(self):
        PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            amount=100_000,
            status=PaymentTransaction.Status.CREATED,
            provider_transaction_id='',
            raw_payload={'create_time': T1},
        )
        response = self._rpc('GetStatement', {'from': T0, 'to': T3})
        self.assertEqual(response.json()['result']['transactions'], [])

    def test_missing_create_time_falls_back_to_created_at(self):
        now = timezone.now()
        tx = PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            amount=123_456,
            status=PaymentTransaction.Status.PAID,
            provider_transaction_id='payme-fallback',
            raw_payload={'perform_time': 0, 'cancel_time': 0},
        )
        PaymentTransaction.objects.filter(pk=tx.pk).update(created_at=now)
        tx.refresh_from_db()
        create_ms = int(tx.created_at.timestamp() * 1000)
        response = self._rpc(
            'GetStatement',
            {'from': create_ms - 5_000, 'to': create_ms + 5_000},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get('jsonrpc'), '2.0')
        rows = body['result']['transactions']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['id'], 'payme-fallback')
        self.assertEqual(row['amount'], 123_456)
        self.assertEqual(row['account'], {'order_id': str(tx.id)})
        self.assertEqual(row['transaction'], str(tx.id))
        self.assertEqual(row['time'], create_ms)
        self.assertEqual(row['create_time'], create_ms)
