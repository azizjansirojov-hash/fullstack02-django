"""Payme Merchant API (JSON-RPC 2.0) provider.

Auth scheme (Merchant API): HTTP Basic Auth with login ``Paycom`` and
password = merchant key (``PAYME_MERCHANT_KEY``). Verified with
``hmac.compare_digest``. Official protocol:
https://developer.help.paycom.uz/protokol-merchant-api/
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
import uuid
from typing import Any

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from payments.entitlement import fulfill_paid_transaction, revoke_paid_transaction
from payments.logging_utils import redact_payload
from payments.models import PaymentTransaction
from payments.providers.base import PaymentProvider

logger = logging.getLogger('payments')

# Payme transaction states (Merchant API).
STATE_CREATED = 1
STATE_COMPLETED = 2
STATE_CANCELLED = -1
STATE_CANCELLED_AFTER = -2

# Official Merchant API error codes (developer.help.paycom.uz).
ERR_INVALID_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_COULD_NOT_PERFORM = -31008
ERR_CANNOT_CANCEL = -31007
ERR_ORDER_NOT_FOUND = -31050
ERR_AUTH = -32504
ERR_METHOD = -32601
ERR_PARSE = -32700


def verify_payme_basic_auth(authorization_header: str | None, merchant_key: str) -> bool:
    """Return True if Authorization is Basic Paycom:<merchant_key>.

    Spec: Merchant API uses HTTP Basic Authentication; password is the cash
    register key. Login is ``Paycom`` (test/prod cabinet convention documented
    across Payme Merchant integrations).
    """
    if not authorization_header or not merchant_key:
        return False
    parts = authorization_header.split(' ', 1)
    if len(parts) != 2 or parts[0].lower() != 'basic':
        return False
    try:
        decoded = base64.b64decode(parts[1].strip(), validate=True).decode('utf-8')
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    if ':' not in decoded:
        return False
    login, password = decoded.split(':', 1)
    login_ok = hmac.compare_digest(login, 'Paycom')
    password_ok = hmac.compare_digest(password, merchant_key)
    return login_ok and password_ok


def _rpc_error(rpc_id: Any, code: int, message: str, data: Any = None) -> JsonResponse:
    err: dict[str, Any] = {'code': code, 'message': message}
    if data is not None:
        err['data'] = data
    return JsonResponse({'jsonrpc': '2.0', 'id': rpc_id, 'error': err}, status=200)


def _rpc_result(rpc_id: Any, result: dict) -> JsonResponse:
    return JsonResponse({'jsonrpc': '2.0', 'id': rpc_id, 'result': result}, status=200)


def _ms(dt) -> int:
    if dt is None:
        return 0
    return int(dt.timestamp() * 1000)


def _statement_create_time(tx: PaymentTransaction) -> int:
    meta = tx.raw_payload or {}
    raw = meta.get('create_time')
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    return _ms(tx.created_at)


def _payme_state(tx: PaymentTransaction) -> int:
    meta = tx.raw_payload or {}
    if tx.status == PaymentTransaction.Status.PAID:
        return STATE_COMPLETED
    if tx.status == PaymentTransaction.Status.CANCELLED:
        return meta.get('state') or STATE_CANCELLED
    return STATE_CREATED


def _order_id_from_account(account: dict | None) -> str | None:
    if not isinstance(account, dict):
        return None
    raw = account.get('order_id')
    if raw is None:
        return None
    return str(raw)


def _get_tx_by_order_id(order_id: str) -> PaymentTransaction | None:
    try:
        uid = uuid.UUID(str(order_id))
    except (ValueError, TypeError, AttributeError):
        return None
    return (
        PaymentTransaction.objects.select_related('user', 'book')
        .filter(pk=uid, provider=PaymentTransaction.Provider.PAYME)
        .first()
    )


class PaymeProvider(PaymentProvider):
    name = 'payme'

    def create_checkout_url(self, tx: PaymentTransaction, *, return_url: str) -> str:
        merchant_id = getattr(settings, 'PAYME_MERCHANT_ID', '') or ''
        test_mode = bool(getattr(settings, 'PAYME_TEST_MODE', True))
        host = 'https://test.paycom.uz' if test_mode else 'https://checkout.paycom.uz'
        # GET /base64(params) — https://developer.help.paycom.uz/initsializatsiya-platezhey/
        params = (
            f'm={merchant_id};'
            f'ac.order_id={tx.id};'
            f'a={tx.amount};'
            f'c={return_url}'
        )
        encoded = base64.b64encode(params.encode('utf-8')).decode('ascii')
        return f'{host}/{encoded}'

    def verify_and_process_callback(self, request: HttpRequest) -> HttpResponse:
        merchant_key = getattr(settings, 'PAYME_MERCHANT_KEY', '') or ''
        auth = request.META.get('HTTP_AUTHORIZATION')
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning('payme_webhook parse_error payload=%s', redact_payload({}))
            return _rpc_error(None, ERR_PARSE, 'Parse error')

        rpc_id = body.get('id')
        logger.info(
            'payme_webhook method=%s payload=%s',
            body.get('method'),
            redact_payload(body),
        )

        if not verify_payme_basic_auth(auth, merchant_key):
            return _rpc_error(
                rpc_id,
                ERR_AUTH,
                'Insufficient privilege',
                {'ru': 'Недостаточно привилегий', 'uz': 'Yetarli huquq yo‘q', 'en': 'Auth error'},
            )

        method = body.get('method')
        params = body.get('params') or {}
        handlers = {
            'CheckPerformTransaction': self._check_perform,
            'CreateTransaction': self._create,
            'PerformTransaction': self._perform,
            'CancelTransaction': self._cancel,
            'CheckTransaction': self._check,
            'GetStatement': self._statement,
        }
        handler = handlers.get(method)
        if handler is None:
            return _rpc_error(rpc_id, ERR_METHOD, f'Method not found: {method}')
        return handler(rpc_id, params)

    def _check_perform(self, rpc_id, params) -> JsonResponse:
        order_id = _order_id_from_account(params.get('account'))
        amount = params.get('amount')
        tx = _get_tx_by_order_id(order_id) if order_id else None
        if tx is None:
            return _rpc_error(
                rpc_id,
                ERR_ORDER_NOT_FOUND,
                'Order not found',
                {'ru': 'Заказ не найден', 'uz': 'Buyurtma topilmadi', 'en': 'Order not found'},
            )
        if tx.status in (
            PaymentTransaction.Status.PAID,
            PaymentTransaction.Status.CANCELLED,
            PaymentTransaction.Status.FAILED,
        ):
            return _rpc_error(
                rpc_id,
                ERR_COULD_NOT_PERFORM,
                'Order not available for payment',
            )
        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            return _rpc_error(rpc_id, ERR_INVALID_AMOUNT, 'Invalid amount')
        if amount_int != tx.amount:
            return _rpc_error(rpc_id, ERR_INVALID_AMOUNT, 'Invalid amount')
        return _rpc_result(rpc_id, {'allow': True})

    @transaction.atomic
    def _create(self, rpc_id, params) -> JsonResponse:
        # Lookup is by account.order_id (merchant UUID), not by Payme params.id.
        # Empty params.id cannot collide with blank provider_transaction_id here.
        # Do not switch this to filter(provider_transaction_id=payme_id) without an
        # empty-id guard like _perform/_cancel/_check.
        order_id = _order_id_from_account(params.get('account'))
        payme_id = str(params.get('id') or '')
        amount = params.get('amount')
        tx = _get_tx_by_order_id(order_id) if order_id else None
        if tx is None:
            return _rpc_error(
                rpc_id,
                ERR_ORDER_NOT_FOUND,
                'Order not found',
                {'ru': 'Заказ не найден', 'uz': 'Buyurtma topilmadi', 'en': 'Order not found'},
            )
        locked = PaymentTransaction.objects.select_for_update().get(pk=tx.pk)
        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            return _rpc_error(rpc_id, ERR_INVALID_AMOUNT, 'Invalid amount')
        if amount_int != locked.amount:
            return _rpc_error(rpc_id, ERR_INVALID_AMOUNT, 'Invalid amount')

        # Idempotent: same Payme id already linked.
        if locked.provider_transaction_id and locked.provider_transaction_id == payme_id:
            state = STATE_COMPLETED if locked.status == PaymentTransaction.Status.PAID else STATE_CREATED
            if locked.status == PaymentTransaction.Status.CANCELLED:
                state = STATE_CANCELLED
            meta = locked.raw_payload or {}
            return _rpc_result(
                rpc_id,
                {
                    'create_time': meta.get('create_time') or _ms(locked.created_at),
                    'transaction': str(locked.id),
                    'state': state,
                },
            )

        if locked.status == PaymentTransaction.Status.PAID:
            return _rpc_error(rpc_id, ERR_COULD_NOT_PERFORM, 'Already paid')
        if locked.status == PaymentTransaction.Status.CANCELLED:
            return _rpc_error(rpc_id, ERR_COULD_NOT_PERFORM, 'Cancelled')

        # Different Payme id already attached → conflict.
        if locked.provider_transaction_id and locked.provider_transaction_id != payme_id:
            return _rpc_error(rpc_id, ERR_COULD_NOT_PERFORM, 'Transaction already exists')

        create_time = int(params.get('time') or _ms(timezone.now()))
        locked.provider_transaction_id = payme_id
        locked.status = PaymentTransaction.Status.PENDING
        locked.raw_payload = {
            **(locked.raw_payload or {}),
            'create_time': create_time,
            'perform_time': 0,
            'cancel_time': 0,
            'state': STATE_CREATED,
            'reason': None,
            'last_method': 'CreateTransaction',
            'last_params': params,
        }
        locked.save(
            update_fields=[
                'provider_transaction_id',
                'status',
                'raw_payload',
                'updated_at',
            ]
        )
        return _rpc_result(
            rpc_id,
            {
                'create_time': create_time,
                'transaction': str(locked.id),
                'state': STATE_CREATED,
            },
        )

    @transaction.atomic
    def _perform(self, rpc_id, params) -> JsonResponse:
        payme_id = str(params.get('id') or '')
        if not payme_id:
            return _rpc_error(rpc_id, ERR_TRANSACTION_NOT_FOUND, 'Transaction not found')
        locked = (
            PaymentTransaction.objects.select_for_update()
            .filter(
                provider=PaymentTransaction.Provider.PAYME,
                provider_transaction_id=payme_id,
            )
            .first()
        )
        if locked is None:
            return _rpc_error(rpc_id, ERR_TRANSACTION_NOT_FOUND, 'Transaction not found')

        meta = dict(locked.raw_payload or {})
        if locked.status == PaymentTransaction.Status.PAID:
            return _rpc_result(
                rpc_id,
                {
                    'transaction': str(locked.id),
                    'perform_time': meta.get('perform_time') or _ms(locked.paid_at),
                    'state': STATE_COMPLETED,
                },
            )
        if locked.status == PaymentTransaction.Status.CANCELLED:
            return _rpc_error(rpc_id, ERR_COULD_NOT_PERFORM, 'Cannot perform cancelled')

        perform_time = _ms(timezone.now())
        meta.update(
            {
                'perform_time': perform_time,
                'state': STATE_COMPLETED,
                'last_method': 'PerformTransaction',
                'last_params': params,
            }
        )
        fulfill_paid_transaction(
            locked,
            provider_transaction_id=payme_id,
            raw_payload=meta,
        )
        return _rpc_result(
            rpc_id,
            {
                'transaction': str(locked.id),
                'perform_time': perform_time,
                'state': STATE_COMPLETED,
            },
        )

    @transaction.atomic
    def _cancel(self, rpc_id, params) -> JsonResponse:
        payme_id = str(params.get('id') or '')
        if not payme_id:
            return _rpc_error(rpc_id, ERR_TRANSACTION_NOT_FOUND, 'Transaction not found')
        reason = params.get('reason')
        locked = (
            PaymentTransaction.objects.select_for_update()
            .filter(
                provider=PaymentTransaction.Provider.PAYME,
                provider_transaction_id=payme_id,
            )
            .first()
        )
        if locked is None:
            return _rpc_error(rpc_id, ERR_TRANSACTION_NOT_FOUND, 'Transaction not found')

        meta = dict(locked.raw_payload or {})
        if locked.status == PaymentTransaction.Status.PAID:
            # Post-paid cancel/refund from Payme (state -2). Revoke Purchase access.
            cancel_time = meta.get('cancel_time') or _ms(timezone.now())
            meta.update(
                {
                    'cancel_time': cancel_time,
                    'state': STATE_CANCELLED_AFTER,
                    'reason': reason,
                    'last_method': 'CancelTransaction',
                }
            )
            revoke_paid_transaction(
                locked,
                reason=str(reason) if reason is not None else '',
                raw_payload=meta,
            )
            return _rpc_result(
                rpc_id,
                {
                    'transaction': str(locked.id),
                    'cancel_time': cancel_time,
                    'state': STATE_CANCELLED_AFTER,
                },
            )

        # Also handle drift: tx already cancelled but Purchase may still be paid
        # (pre-fix path). Re-entry with CancelTransaction should revoke once.
        if locked.status == PaymentTransaction.Status.CANCELLED:
            cancel_time = meta.get('cancel_time') or _ms(timezone.now())
            meta.update(
                {
                    'cancel_time': cancel_time,
                    'state': meta.get('state') or STATE_CANCELLED_AFTER,
                    'reason': reason,
                    'last_method': 'CancelTransaction',
                }
            )
            revoke_paid_transaction(
                locked,
                reason=str(reason) if reason is not None else '',
                raw_payload=meta,
            )
            return _rpc_result(
                rpc_id,
                {
                    'transaction': str(locked.id),
                    'cancel_time': cancel_time,
                    'state': meta.get('state') or STATE_CANCELLED_AFTER,
                },
            )

        cancel_time = _ms(timezone.now())
        locked.status = PaymentTransaction.Status.CANCELLED
        meta.update(
            {
                'cancel_time': cancel_time,
                'state': STATE_CANCELLED,
                'reason': reason,
                'last_method': 'CancelTransaction',
            }
        )
        locked.raw_payload = meta
        locked.save(update_fields=['status', 'raw_payload', 'updated_at'])
        return _rpc_result(
            rpc_id,
            {
                'transaction': str(locked.id),
                'cancel_time': cancel_time,
                'state': STATE_CANCELLED,
            },
        )

    def _check(self, rpc_id, params) -> JsonResponse:
        payme_id = str(params.get('id') or '')
        if not payme_id:
            return _rpc_error(rpc_id, ERR_TRANSACTION_NOT_FOUND, 'Transaction not found')
        tx = (
            PaymentTransaction.objects.filter(
                provider=PaymentTransaction.Provider.PAYME,
                provider_transaction_id=payme_id,
            )
            .first()
        )
        if tx is None:
            return _rpc_error(rpc_id, ERR_TRANSACTION_NOT_FOUND, 'Transaction not found')
        meta = tx.raw_payload or {}
        return _rpc_result(
            rpc_id,
            {
                'create_time': _statement_create_time(tx),
                'perform_time': meta.get('perform_time') or 0,
                'cancel_time': meta.get('cancel_time') or 0,
                'transaction': str(tx.id),
                'state': _payme_state(tx),
                'reason': meta.get('reason'),
            },
        )

    def _statement(self, rpc_id, params) -> JsonResponse:
        try:
            from_ms = int(params.get('from'))
            to_ms = int(params.get('to'))
        except (TypeError, ValueError):
            return _rpc_result(rpc_id, {'transactions': []})

        rows = (
            PaymentTransaction.objects.filter(
                provider=PaymentTransaction.Provider.PAYME,
            )
            .exclude(provider_transaction_id='')
            .select_related('user', 'book')
        )
        items = []
        for tx in rows:
            create_time = _statement_create_time(tx)
            if create_time < from_ms or create_time > to_ms:
                continue
            meta = tx.raw_payload or {}
            items.append(
                {
                    'id': tx.provider_transaction_id,
                    'time': create_time,
                    'amount': tx.amount,
                    'account': {'order_id': str(tx.id)},
                    'create_time': create_time,
                    'perform_time': meta.get('perform_time') or 0,
                    'cancel_time': meta.get('cancel_time') or 0,
                    'transaction': str(tx.id),
                    'state': _payme_state(tx),
                    'reason': meta.get('reason'),
                }
            )
        items.sort(key=lambda row: (row['time'], row['transaction']))
        return _rpc_result(rpc_id, {'transactions': items})
