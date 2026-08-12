"""Payment orchestration — mirrors library.tts_service / get_tts_provider."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from payments.models import PaymentTransaction
from payments.providers.base import PaymentProvider
from payments.providers.click import ClickProvider
from payments.providers.payme import PaymeProvider


def get_payment_provider(provider_id: str) -> PaymentProvider:
    """Return the configured payment provider instance."""
    name = (provider_id or '').lower().strip()
    if name == PaymentTransaction.Provider.PAYME:
        return PaymeProvider()
    if name == PaymentTransaction.Provider.CLICK:
        return ClickProvider()
    raise NotImplementedError(
        f'Payment provider {provider_id!r} is not implemented. '
        'Supported: "payme", "click".'
    )


def payments_enabled() -> bool:
    return bool(getattr(settings, 'PAYMENTS_ENABLED', False))


def book_price_tiyin() -> int | None:
    """Global catalog price in tiyin, or None if unset/disabled."""
    if not payments_enabled():
        return None
    value = getattr(settings, 'BOOK_PRICE_TIYIN', None)
    if value is None:
        return None
    try:
        price = int(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def require_book_price_tiyin() -> int:
    price = book_price_tiyin()
    if price is None:
        raise ImproperlyConfigured(
            'BOOK_PRICE_TIYIN must be a positive integer when PAYMENTS_ENABLED=True.'
        )
    return price
