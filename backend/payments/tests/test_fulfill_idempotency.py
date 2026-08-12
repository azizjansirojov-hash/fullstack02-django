"""Double-fulfill idempotency for PaymentTransaction → Purchase."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from library.models import Book, BookTranslation, Notification, Purchase
from payments.entitlement import fulfill_paid_transaction
from payments.models import PaymentTransaction

User = get_user_model()


class FulfillPaidTransactionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='fulfill',
            password='testpass123',
            email='fulfill@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.NOVEL,
            slug='fulfill-book',
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
            amount=50_000,
            status=PaymentTransaction.Status.PENDING,
            provider_transaction_id='pt-1',
        )

    def test_double_fulfill_one_purchase_one_notification(self):
        fulfill_paid_transaction(self.tx, provider_transaction_id='pt-1')
        fulfill_paid_transaction(self.tx, provider_transaction_id='pt-1')

        self.assertEqual(
            Purchase.objects.filter(user=self.user, book=self.book).count(),
            1,
        )
        purchase = Purchase.objects.get(user=self.user, book=self.book)
        self.assertEqual(purchase.status, Purchase.Status.PAID)
        self.assertIsNotNone(purchase.paid_at)

        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.PAID)
        self.assertIsNotNone(self.tx.paid_at)

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                type=Notification.Type.PURCHASE_PAID,
            ).count(),
            1,
        )
