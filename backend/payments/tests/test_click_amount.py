"""Exact Decimal comparison for Click UZS amounts vs tiyin snapshot."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from library.models import Book
from payments.models import PaymentTransaction
from payments.providers.click import _amount_matches_uzs

User = get_user_model()


class ClickAmountMatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='amt',
            password='testpass123',
            email='amt@example.com',
        )
        self.book = Book.objects.create(
            author_name='Author',
            category=Book.Category.OTHER,
            slug='amt-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
        )
        self.tx = PaymentTransaction(
            user=self.user,
            book=self.book,
            provider=PaymentTransaction.Provider.CLICK,
            amount=500_000,  # 5000 UZS
            status=PaymentTransaction.Status.CREATED,
        )

    def test_exact_integer_uzs(self):
        self.assertTrue(_amount_matches_uzs(self.tx, '5000'))

    def test_decimal_zeros_match(self):
        self.assertTrue(_amount_matches_uzs(self.tx, '5000.00'))

    def test_mismatch(self):
        self.assertFalse(_amount_matches_uzs(self.tx, '5001'))
        self.assertFalse(_amount_matches_uzs(self.tx, '4999.99'))

    def test_garbage_rejected(self):
        self.assertFalse(_amount_matches_uzs(self.tx, 'not-a-number'))
        self.assertFalse(_amount_matches_uzs(self.tx, ''))

    def test_sub_tiyin_fraction_rejected(self):
        # Would round under float epsilon paths; must reject exactly.
        self.assertFalse(_amount_matches_uzs(self.tx, '5000.005'))
