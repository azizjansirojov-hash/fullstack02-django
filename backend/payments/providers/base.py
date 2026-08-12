"""Payment provider ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod

from django.http import HttpRequest, HttpResponse

from payments.models import PaymentTransaction


class PaymentProvider(ABC):
    """Create checkout URLs and process gateway callbacks."""

    name: str = 'base'

    @abstractmethod
    def create_checkout_url(self, tx: PaymentTransaction, *, return_url: str) -> str:
        """Return the provider-hosted checkout URL for this transaction."""

    @abstractmethod
    def verify_and_process_callback(self, request: HttpRequest) -> HttpResponse:
        """Verify auth/signature and process the provider callback."""
