"""Click Shop API (Prepare / Complete) provider.

Signature (docs.click.uz Shop API):
  Prepare:  md5(click_trans_id + service_id + secret_key + merchant_trans_id
                + amount + action + sign_time)
  Complete: md5(click_trans_id + service_id + secret_key + merchant_trans_id
                + merchant_prepare_id + amount + action + sign_time)

Amounts on Click wire format are UZS (major units). Internally we store tiyin.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import logging
import uuid
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse

from payments.entitlement import fulfill_paid_transaction
from payments.logging_utils import redact_payload
from payments.models import PaymentTransaction
from payments.providers.base import PaymentProvider

logger = logging.getLogger('payments')

# Click Shop API error codes (docs.click.uz).
CLICK_SUCCESS = 0
CLICK_SIGN_FAILED = -1
CLICK_INVALID_AMOUNT = -2
CLICK_ACTION_NOT_FOUND = -3
CLICK_ALREADY_PAID = -4
CLICK_USER_NOT_FOUND = -5
CLICK_TRANSACTION_NOT_FOUND = -6
CLICK_FAILED_UPDATE = -7
CLICK_BAD_REQUEST = -8
CLICK_CANCELLED = -9


def click_sign_prepare(
    *,
    click_trans_id: str,
    service_id: str,
    secret_key: str,
    merchant_trans_id: str,
    amount: str,
    action: str,
    sign_time: str,
) -> str:
    """MD5 sign_string for Prepare (action 0) — formula from docs.click.uz."""
    raw = (
        f'{click_trans_id}{service_id}{secret_key}{merchant_trans_id}'
        f'{amount}{action}{sign_time}'
    )
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def click_sign_complete(
    *,
    click_trans_id: str,
    service_id: str,
    secret_key: str,
    merchant_trans_id: str,
    merchant_prepare_id: str,
    amount: str,
    action: str,
    sign_time: str,
) -> str:
    """MD5 sign_string for Complete (action 1) — formula from docs.click.uz."""
    raw = (
        f'{click_trans_id}{service_id}{secret_key}{merchant_trans_id}'
        f'{merchant_prepare_id}{amount}{action}{sign_time}'
    )
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def verify_click_sign(expected: str, provided: str) -> bool:
    return hmac.compare_digest(expected, provided or '')


def _form(request: HttpRequest) -> dict[str, str]:
    """Normalize POST form / JSON body to a flat string dict."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            import json

            data = json.loads(request.body.decode('utf-8') or '{}')
            if isinstance(data, dict):
                return {str(k): '' if v is None else str(v) for k, v in data.items()}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return {k: request.POST.get(k, '') for k in request.POST.keys()}


def _click_response(**kwargs) -> JsonResponse:
    return JsonResponse(kwargs, status=200)


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _amount_matches_uzs(tx: PaymentTransaction, amount_raw: str) -> bool:
    """Compare Click's UZS amount (major units, possibly with decimals)
    against the snapshotted tiyin amount, with exact decimal arithmetic."""
    try:
        amount_uzs = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError, ValueError):
        return False
    expected_tiyin = tx.amount  # already an int, minor units
    # Convert Click's major-unit decimal to tiyin, rejecting any sub-tiyin
    # fractional remainder rather than silently rounding it away.
    amount_tiyin = amount_uzs * 100
    if amount_tiyin != amount_tiyin.to_integral_value():
        return False
    return int(amount_tiyin) == expected_tiyin


class ClickProvider(PaymentProvider):
    name = 'click'

    def create_checkout_url(self, tx: PaymentTransaction, *, return_url: str) -> str:
        merchant_id = getattr(settings, 'CLICK_MERCHANT_ID', '') or ''
        service_id = getattr(settings, 'CLICK_SERVICE_ID', '') or ''
        query = urlencode(
            {
                'service_id': service_id,
                'merchant_id': merchant_id,
                'amount': str(tx.amount_uzs),
                'transaction_param': str(tx.id),
                'return_url': return_url,
            }
        )
        return f'https://my.click.uz/services/pay?{query}'

    def verify_and_process_callback(self, request: HttpRequest) -> HttpResponse:
        # Shared entry; views dispatch prepare vs complete by path.
        raise NotImplementedError('Use handle_prepare / handle_complete')

    def handle_prepare(self, request: HttpRequest) -> HttpResponse:
        data = _form(request)
        logger.info('click_prepare payload=%s', redact_payload(data))
        return self._prepare(data)

    def handle_complete(self, request: HttpRequest) -> HttpResponse:
        data = _form(request)
        logger.info('click_complete payload=%s', redact_payload(data))
        return self._complete(data)

    def _auth_ok(self, data: dict[str, str], *, complete: bool) -> bool:
        secret = getattr(settings, 'CLICK_SECRET_KEY', '') or ''
        service_id = getattr(settings, 'CLICK_SERVICE_ID', '') or ''
        if not secret:
            return False
        # Optional service_id match
        if service_id and data.get('service_id') and data.get('service_id') != str(service_id):
            return False
        if complete:
            expected = click_sign_complete(
                click_trans_id=data.get('click_trans_id', ''),
                service_id=data.get('service_id', ''),
                secret_key=secret,
                merchant_trans_id=data.get('merchant_trans_id', ''),
                merchant_prepare_id=data.get('merchant_prepare_id', ''),
                amount=data.get('amount', ''),
                action=data.get('action', ''),
                sign_time=data.get('sign_time', ''),
            )
        else:
            expected = click_sign_prepare(
                click_trans_id=data.get('click_trans_id', ''),
                service_id=data.get('service_id', ''),
                secret_key=secret,
                merchant_trans_id=data.get('merchant_trans_id', ''),
                amount=data.get('amount', ''),
                action=data.get('action', ''),
                sign_time=data.get('sign_time', ''),
            )
        return verify_click_sign(expected, data.get('sign_string', ''))

    @transaction.atomic
    def _prepare(self, data: dict[str, str]) -> JsonResponse:
        click_trans_id = data.get('click_trans_id', '')
        merchant_trans_id = data.get('merchant_trans_id', '')
        base: dict[str, Any] = {
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
        }
        if not self._auth_ok(data, complete=False):
            return _click_response(
                **base,
                error=CLICK_SIGN_FAILED,
                error_note='Invalid sign_string',
            )
        if str(data.get('action', '')) != '0':
            return _click_response(
                **base,
                error=CLICK_ACTION_NOT_FOUND,
                error_note='Action not found',
            )

        uid = _parse_uuid(merchant_trans_id)
        if uid is None:
            return _click_response(
                **base,
                error=CLICK_USER_NOT_FOUND,
                error_note='Order not found',
            )
        locked = (
            PaymentTransaction.objects.select_for_update()
            .filter(pk=uid, provider=PaymentTransaction.Provider.CLICK)
            .first()
        )
        if locked is None:
            return _click_response(
                **base,
                error=CLICK_USER_NOT_FOUND,
                error_note='Order not found',
            )
        if locked.status == PaymentTransaction.Status.PAID:
            return _click_response(
                **base,
                merchant_prepare_id=locked.click_prepare_id,
                error=CLICK_ALREADY_PAID,
                error_note='Already paid',
            )
        if locked.status == PaymentTransaction.Status.CANCELLED:
            return _click_response(
                **base,
                merchant_prepare_id=locked.click_prepare_id,
                error=CLICK_CANCELLED,
                error_note='Cancelled',
            )
        if not _amount_matches_uzs(locked, data.get('amount', '')):
            return _click_response(
                **base,
                merchant_prepare_id=locked.click_prepare_id,
                error=CLICK_INVALID_AMOUNT,
                error_note='Incorrect amount',
            )

        locked.provider_transaction_id = str(click_trans_id)
        locked.status = PaymentTransaction.Status.PENDING
        locked.raw_payload = {
            **(locked.raw_payload or {}),
            'prepare': data,
            'last_action': 'prepare',
        }
        locked.save(
            update_fields=[
                'provider_transaction_id',
                'status',
                'raw_payload',
                'updated_at',
            ]
        )
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=locked.click_prepare_id,
            error=CLICK_SUCCESS,
            error_note='Success',
        )

    @transaction.atomic
    def _complete(self, data: dict[str, str]) -> JsonResponse:
        click_trans_id = data.get('click_trans_id', '')
        merchant_trans_id = data.get('merchant_trans_id', '')
        base: dict[str, Any] = {
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
        }
        if not self._auth_ok(data, complete=True):
            return _click_response(
                **base,
                error=CLICK_SIGN_FAILED,
                error_note='Invalid sign_string',
            )
        if str(data.get('action', '')) != '1':
            return _click_response(
                **base,
                error=CLICK_ACTION_NOT_FOUND,
                error_note='Action not found',
            )

        uid = _parse_uuid(merchant_trans_id)
        if uid is None:
            return _click_response(
                **base,
                error=CLICK_USER_NOT_FOUND,
                error_note='Order not found',
            )
        locked = (
            PaymentTransaction.objects.select_for_update()
            .filter(pk=uid, provider=PaymentTransaction.Provider.CLICK)
            .first()
        )
        if locked is None:
            return _click_response(
                **base,
                error=CLICK_TRANSACTION_NOT_FOUND,
                error_note='Transaction not found',
            )

        prepare_id = str(data.get('merchant_prepare_id', ''))
        if prepare_id != str(locked.click_prepare_id):
            return _click_response(
                **base,
                merchant_confirm_id=locked.click_prepare_id,
                error=CLICK_TRANSACTION_NOT_FOUND,
                error_note='Prepare id mismatch',
            )

        # Click-side error (negative) → cancel
        try:
            click_error = int(float(data.get('error', '0') or '0'))
        except (TypeError, ValueError):
            click_error = 0
        if click_error < 0:
            locked.status = PaymentTransaction.Status.CANCELLED
            locked.raw_payload = {
                **(locked.raw_payload or {}),
                'complete': data,
                'last_action': 'complete_cancelled',
            }
            locked.save(update_fields=['status', 'raw_payload', 'updated_at'])
            return _click_response(
                **base,
                merchant_confirm_id=locked.click_prepare_id,
                error=CLICK_CANCELLED,
                error_note='Cancelled',
            )

        if locked.status == PaymentTransaction.Status.PAID:
            # Idempotent success — already paid.
            # Click Shop API (docs.click.uz) only defines Prepare/Complete merchant
            # callbacks. Post-paid refunds/cancellations are Merchant API /cancel
            # (merchant-initiated) or dashboard actions — there is no Shop API
            # webhook that notifies us after a successful Complete. Refunds must
            # be reconciled manually per PAYMENTS.md (revoke Purchase → refunded).
            return _click_response(
                click_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                merchant_confirm_id=locked.click_prepare_id,
                error=CLICK_SUCCESS,
                error_note='Success',
            )

        if locked.status == PaymentTransaction.Status.CANCELLED:
            return _click_response(
                **base,
                merchant_confirm_id=locked.click_prepare_id,
                error=CLICK_CANCELLED,
                error_note='Cancelled',
            )

        if not _amount_matches_uzs(locked, data.get('amount', '')):
            return _click_response(
                **base,
                merchant_confirm_id=locked.click_prepare_id,
                error=CLICK_INVALID_AMOUNT,
                error_note='Incorrect amount',
            )

        payload = {
            **(locked.raw_payload or {}),
            'complete': data,
            'last_action': 'complete',
        }
        fulfill_paid_transaction(
            locked,
            provider_transaction_id=str(click_trans_id),
            raw_payload=payload,
        )
        return _click_response(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            merchant_confirm_id=locked.click_prepare_id,
            error=CLICK_SUCCESS,
            error_note='Success',
        )
