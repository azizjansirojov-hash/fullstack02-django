"""TTS provider abstraction — swap backends via TTS_PROVIDER setting."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Synthesize spoken audio bytes from plain text."""

    name: str = 'base'

    @abstractmethod
    def synthesize(self, text: str, *, voice: str) -> bytes:
        """Return MP3 (or provider-native) audio bytes for text."""


def get_tts_provider():
    """Return the configured TTS provider instance."""
    from django.conf import settings

    provider_id = getattr(settings, 'TTS_PROVIDER', 'edge').lower().strip()
    if provider_id in ('edge', 'edge-tts'):
        from .edge import EdgeTTSProvider

        return EdgeTTSProvider()
    raise NotImplementedError(
        f'TTS_PROVIDER={provider_id!r} is not implemented. '
        'Only "edge" (edge-tts) is supported today. '
        'Add a provider module under library/tts_providers/ and wire it here.'
    )
