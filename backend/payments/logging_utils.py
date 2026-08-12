"""Redact secrets from payment webhook payloads before logging."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_SENSITIVE_KEYS = frozenset(
    {
        'password',
        'secret',
        'secret_key',
        'merchant_key',
        'sign_string',
        'authorization',
        'payme_merchant_key',
        'click_secret_key',
        'card',
        'cvv',
        'pan',
    }
)


def redact_payload(payload: Any) -> Any:
    """Return a deep-copied payload with sensitive fields masked."""
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            key_l = str(key).lower()
            if key_l in _SENSITIVE_KEYS or 'secret' in key_l or 'password' in key_l:
                out[key] = '***'
            elif key_l.endswith('_key') and key_l not in ('merchant_id',):
                out[key] = '***'
            else:
                out[key] = redact_payload(value)
        return out
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    return deepcopy(payload) if isinstance(payload, (dict, list)) else payload
