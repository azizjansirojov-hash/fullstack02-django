"""Click prepare/complete validation hardening."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, BookTranslation
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
class ClickValidationHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='clickval',
            password='testpass123',
            email='clickval@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.NOVEL,
            slug='click-val-book',
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
            provider=PaymentTransaction.Provider.CLICK,
            amount=100_000,
            status=PaymentTransaction.Status.CREATED,
        )

    def test_prepare_rejects_action_0_0(self):
        amount = str(self.tx.amount_uzs)
        sign_time = '2026-05-05 14:30:00'
        action = '0.0'
        sign = click_sign_prepare(
            click_trans_id='1',
            service_id='22',
            secret_key='click-secret',
            merchant_trans_id=str(self.tx.id),
            amount=amount,
            action=action,
            sign_time=sign_time,
        )
        response = self.client.post(
            reverse('payments:click-prepare'),
            data={
                'click_trans_id': '1',
                'service_id': '22',
                'merchant_trans_id': str(self.tx.id),
                'amount': amount,
                'action': action,
                'sign_time': sign_time,
                'sign_string': sign,
                'error': '0',
            },
        )
        self.assertEqual(response.json()['error'], -3)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CREATED)

    def test_complete_rejects_empty_merchant_prepare_id(self):
        # Move to pending as if Prepare succeeded.
        self.tx.status = PaymentTransaction.Status.PENDING
        self.tx.provider_transaction_id = '999'
        self.tx.save(update_fields=['status', 'provider_transaction_id', 'updated_at'])

        amount = str(self.tx.amount_uzs)
        sign_time = '2026-05-05 14:31:00'
        sign = click_sign_complete(
            click_trans_id='999',
            service_id='22',
            secret_key='click-secret',
            merchant_trans_id=str(self.tx.id),
            merchant_prepare_id='',
            amount=amount,
            action='1',
            sign_time=sign_time,
        )
        response = self.client.post(
            reverse('payments:click-complete'),
            data={
                'click_trans_id': '999',
                'service_id': '22',
                'merchant_trans_id': str(self.tx.id),
                'merchant_prepare_id': '',
                'amount': amount,
                'action': '1',
                'sign_time': sign_time,
                'sign_string': sign,
                'error': '0',
            },
        )
        self.assertEqual(response.json()['error'], -6)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.PENDING)
