"""Bridge PaymentTransaction → library.Purchase entitlement."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from library.models import Purchase
from library.notifications import notify_purchase_refunded

from .models import PaymentTransaction

logger = logging.getLogger('payments')


@transaction.atomic
def fulfill_paid_transaction(
    tx: PaymentTransaction,
    *,
    provider_transaction_id: str | None = None,
    raw_payload: dict | None = None,
) -> Purchase:
    """Mark transaction paid and create/update Purchase (idempotent).

    Nested under a webhook ``@transaction.atomic`` this joins that outer
    transaction (savepoint) and does not commit independently.

    Uses instance Purchase.save() so notify_purchase_paid fires only when
    Purchase transitions into paid (gated by Purchase previous status, not
    merely PaymentTransaction.already_paid — the two rows can drift).
    """
    locked = (
        PaymentTransaction.objects.select_for_update()
        .select_related('user', 'book')
        .get(pk=tx.pk)
    )
    now = timezone.now()
    if provider_transaction_id and not locked.provider_transaction_id:
        locked.provider_transaction_id = str(provider_transaction_id)
    if raw_payload is not None:
        locked.raw_payload = raw_payload

    already_paid = locked.status == PaymentTransaction.Status.PAID
    if not already_paid:
        locked.status = PaymentTransaction.Status.PAID
        locked.paid_at = now
    locked.save(
        update_fields=[
            'provider_transaction_id',
            'raw_payload',
            'status',
            'paid_at',
            'updated_at',
        ]
    )

    purchase, _created = Purchase.objects.select_for_update().get_or_create(
        user=locked.user,
        book=locked.book,
        defaults={
            'status': Purchase.Status.PAID,
            'paid_at': now,
        },
    )
    # Notify only on Purchase → paid transition (Purchase.save), never on
    # re-fulfill when Purchase is already paid.
    if purchase.status != Purchase.Status.PAID:
        purchase.status = Purchase.Status.PAID
        purchase.paid_at = now
        purchase.save(update_fields=['status', 'paid_at', 'updated_at'])

    logger.info(
        'fulfill_paid_transaction tx=%s purchase_id=%s already_paid=%s',
        locked.id,
        purchase.pk,
        already_paid,
    )
    return purchase


@transaction.atomic
def revoke_paid_transaction(
    tx: PaymentTransaction,
    *,
    reason: str = '',
    raw_payload: dict | None = None,
) -> Purchase | None:
    """Revoke Purchase after a gateway reports post-paid cancel/refund.

    Idempotent: if Purchase is already ``refunded``, no second notification
    or duplicate revoke log is emitted. Idempotency is gated on Purchase
    status (not only PaymentTransaction.status) because the two rows can
    drift after a post-paid cancel that previously left Purchase paid.
    """
    locked = (
        PaymentTransaction.objects.select_for_update()
        .select_related('user', 'book')
        .get(pk=tx.pk)
    )
    now = timezone.now()

    purchase = (
        Purchase.objects.select_for_update()
        .filter(user=locked.user, book=locked.book)
        .first()
    )

    # Merge audit into existing payload — never wipe paid-era history.
    merged = dict(locked.raw_payload or {})
    if raw_payload is not None:
        merged['post_paid_cancel'] = raw_payload
    if reason != '':
        merged['revoke_reason'] = str(reason)
    merged.setdefault('revoked_at', now.isoformat())

    locked.status = PaymentTransaction.Status.CANCELLED
    locked.raw_payload = merged
    locked.save(update_fields=['status', 'raw_payload', 'updated_at'])

    if purchase is None:
        logger.warning(
            'revoke_paid_transaction tx=%s purchase_id=None reason=%s '
            '(no Purchase row)',
            locked.id,
            reason,
        )
        return None

    if purchase.status == Purchase.Status.REFUNDED:
        # Already revoked — idempotent no-op for notify/log spam.
        return purchase

    if purchase.status != Purchase.Status.PAID:
        logger.warning(
            'revoke_paid_transaction tx=%s purchase_id=%s reason=%s '
            'skipped_non_paid_status=%s',
            locked.id,
            purchase.pk,
            reason,
            purchase.status,
        )
        return purchase

    purchase.status = Purchase.Status.REFUNDED
    purchase.save(update_fields=['status', 'updated_at'])
    notify_purchase_refunded(purchase)

    logger.warning(
        'revoke_paid_transaction tx=%s purchase_id=%s reason=%s',
        locked.id,
        purchase.pk,
        reason,
    )
    return purchase
