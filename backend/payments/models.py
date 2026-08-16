"""Gateway payment attempts; entitlement still lives on library.Purchase."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class PaymentTransaction(models.Model):
    """One checkout attempt with a payment provider (Payme or Click)."""

    class Provider(models.TextChoices):
        PAYME = 'payme', 'Payme'
        CLICK = 'click', 'Click'

    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payment_transactions',
    )
    book = models.ForeignKey(
        'library.Book',
        on_delete=models.PROTECT,
        related_name='payment_transactions',
    )
    provider = models.CharField(
        max_length=16,
        choices=Provider.choices,
        db_index=True,
    )
    provider_transaction_id = models.CharField(
        max_length=128,
        blank=True,
        default='',
        db_index=True,
        help_text='Gateway-side transaction id once the provider creates it.',
    )
    amount = models.PositiveIntegerField(
        help_text=(
            'Amount in tiyin (UZS minor units), snapshotted at checkout. '
            'Intentional: reused created/pending rows keep this amount even if '
            'Book.price_tiyin or BOOK_PRICE_TIYIN changes later (not live-priced).'
        ),
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['provider', 'provider_transaction_id'],
                name='pay_tx_provider_ptid_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                condition=models.Q(
                    status__in=['created', 'pending'],
                ),
                name='uniq_active_payment_per_user_book',
            ),
            models.UniqueConstraint(
                fields=['provider', 'provider_transaction_id'],
                condition=~models.Q(provider_transaction_id=''),
                name='uniq_provider_transaction_id',
            ),
        ]

    def __str__(self):
        return f'{self.provider}:{self.id} ({self.status})'

    @property
    def click_prepare_id(self) -> int:
        """Stable positive int for Click merchant_prepare_id (UUID-derived)."""
        return self.id.int & ((1 << 63) - 1)

    @property
    def amount_uzs(self) -> int:
        """Major units for Click redirect/callbacks (tiyin // 100)."""
        return self.amount // 100
