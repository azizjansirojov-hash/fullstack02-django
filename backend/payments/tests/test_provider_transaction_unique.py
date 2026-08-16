"""provider_transaction_id uniqueness for non-empty gateway ids."""

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.contrib.auth import get_user_model

from library.models import Book, BookTranslation
from payments.models import PaymentTransaction

User = get_user_model()


class ProviderTransactionIdUniqueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ptid',
            password='Str0ng-Passw0rd!',
            email='ptid@example.com',
        )
        self.book = Book.objects.create(
            author_name='A',
            slug='ptid-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='T',
            body='b',
        )

    def test_duplicate_nonempty_provider_id_rejected(self):
        PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            provider_transaction_id='payme-dup-1',
            amount=1000,
            status=PaymentTransaction.Status.PAID,
        )
        other = User.objects.create_user(
            username='ptid2',
            password='Str0ng-Passw0rd!',
            email='ptid2@example.com',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentTransaction.objects.create(
                    user=other,
                    book=self.book,
                    provider=PaymentTransaction.Provider.PAYME,
                    provider_transaction_id='payme-dup-1',
                    amount=1000,
                    status=PaymentTransaction.Status.PAID,
                )

    def test_empty_provider_ids_may_repeat(self):
        PaymentTransaction.objects.create(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            provider_transaction_id='',
            amount=1000,
            status=PaymentTransaction.Status.CANCELLED,
        )
        other = User.objects.create_user(
            username='ptid3',
            password='Str0ng-Passw0rd!',
            email='ptid3@example.com',
        )
        PaymentTransaction.objects.create(
            user=other,
            book=self.book,
            provider=PaymentTransaction.Provider.PAYME,
            provider_transaction_id='',
            amount=1000,
            status=PaymentTransaction.Status.CANCELLED,
        )
