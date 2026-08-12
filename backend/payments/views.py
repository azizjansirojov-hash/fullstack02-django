"""Checkout, status polling, and provider webhook endpoints."""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from library.access import user_can_access_book
from library.models import Book
from library.spa_urls import _spa_url
from users.authentication import CSRFEnforcedAuthentication, JWTCookieAuthentication

from .models import PaymentTransaction
from .payment_service import (
    get_payment_provider,
    payments_enabled,
    require_book_price_tiyin,
)
from .providers.click import ClickProvider
from .providers.payme import PaymeProvider

logger = logging.getLogger('payments')


def _is_purchasable(book: Book, user) -> tuple[bool, str]:
    """Return (ok, error_code) for checkout eligibility."""
    if book.rights_status == Book.RightsStatus.PUBLIC_DOMAIN:
        return False, 'already_entitled'
    if book.rights_status != Book.RightsStatus.LICENSED:
        return False, 'not_purchasable'
    if user_can_access_book(user, book):
        return False, 'already_entitled'
    return True, ''


class CheckoutAPIView(APIView):
    """POST /api/payments/checkout/ — start Payme or Click checkout."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [CSRFEnforcedAuthentication, JWTCookieAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'payment_checkout'

    def post(self, request):
        if not payments_enabled():
            return Response(
                {'detail': 'Payments are disabled.', 'code': 'payments_disabled'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        book_slug = (request.data.get('book_slug') or '').strip()
        provider_name = (request.data.get('provider') or '').strip().lower()
        if not book_slug:
            return Response(
                {'detail': 'book_slug is required.', 'code': 'invalid_request'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if provider_name not in (
            PaymentTransaction.Provider.PAYME,
            PaymentTransaction.Provider.CLICK,
        ):
            return Response(
                {'detail': 'provider must be "payme" or "click".', 'code': 'invalid_provider'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        book = get_object_or_404(Book, slug=book_slug, is_published=True)
        ok, err = _is_purchasable(book, request.user)
        if not ok:
            if err == 'already_entitled':
                return Response(
                    {
                        'detail': 'You already have access to this book.',
                        'code': 'already_entitled',
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                {
                    'detail': (
                        'This book is not available for purchase '
                        f'(rights_status={book.rights_status}).'
                    ),
                    'code': 'not_purchasable',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = require_book_price_tiyin()
        except Exception:
            return Response(
                {'detail': 'Payment price is not configured.', 'code': 'price_unset'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        with transaction.atomic():
            active = (
                PaymentTransaction.objects.select_for_update()
                .filter(
                    user=request.user,
                    book=book,
                    status__in=[
                        PaymentTransaction.Status.CREATED,
                        PaymentTransaction.Status.PENDING,
                    ],
                )
                .first()
            )
            if active is not None:
                # Reuse pending/created checkout; refresh provider if requested.
                if active.provider != provider_name:
                    active.provider = provider_name
                    active.save(update_fields=['provider', 'updated_at'])
                tx = active
            else:
                try:
                    tx = PaymentTransaction.objects.create(
                        user=request.user,
                        book=book,
                        provider=provider_name,
                        amount=amount,
                        status=PaymentTransaction.Status.CREATED,
                    )
                except IntegrityError:
                    tx = (
                        PaymentTransaction.objects.select_for_update()
                        .filter(
                            user=request.user,
                            book=book,
                            status__in=[
                                PaymentTransaction.Status.CREATED,
                                PaymentTransaction.Status.PENDING,
                            ],
                        )
                        .first()
                    )
                    if tx is None:
                        raise

        provider = get_payment_provider(tx.provider)
        return_url = _spa_url(f'/payment/status/{tx.id}')
        checkout_url = provider.create_checkout_url(tx, return_url=return_url)
        logger.info(
            'checkout_created tx=%s user=%s book=%s provider=%s amount=%s',
            tx.id,
            request.user.pk,
            book.slug,
            tx.provider,
            tx.amount,
        )
        return Response(
            {
                'transaction_id': str(tx.id),
                'provider': tx.provider,
                'checkout_url': checkout_url,
                'amount_tiyin': tx.amount,
                'status': tx.status,
            }
        )


class TransactionStatusAPIView(APIView):
    """GET /api/payments/transactions/<id>/ — owner-scoped status."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTCookieAuthentication]

    def get(self, request, transaction_id):
        tx = get_object_or_404(
            PaymentTransaction.objects.select_related('book'),
            pk=transaction_id,
            user=request.user,
        )
        return Response(
            {
                'id': str(tx.id),
                'status': tx.status,
                'provider': tx.provider,
                'amount_tiyin': tx.amount,
                'book_slug': tx.book.slug,
                'paid_at': tx.paid_at.isoformat() if tx.paid_at else None,
            }
        )


@method_decorator(
    csrf_exempt,
    name='dispatch',
)
class PaymeWebhookAPIView(APIView):
    """POST /api/payments/payme/webhook/

    CSRF-exempt: Payme Merchant API servers POST JSON-RPC without a Django
    CSRF token. Authentication is HTTP Basic Auth (Paycom + merchant key),
    verified with constant-time comparison before any state change.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        return PaymeProvider().verify_and_process_callback(request)


@method_decorator(
    csrf_exempt,
    name='dispatch',
)
class ClickPrepareAPIView(APIView):
    """POST /api/payments/click/prepare/

    CSRF-exempt: Click Shop API Prepare callbacks are server-to-server form
    posts without CSRF tokens. Authenticity is MD5 sign_string verification.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        return ClickProvider().handle_prepare(request)


@method_decorator(
    csrf_exempt,
    name='dispatch',
)
class ClickCompleteAPIView(APIView):
    """POST /api/payments/click/complete/

    CSRF-exempt: Click Shop API Complete callbacks are server-to-server form
    posts without CSRF tokens. Authenticity is MD5 sign_string verification.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        return ClickProvider().handle_complete(request)
