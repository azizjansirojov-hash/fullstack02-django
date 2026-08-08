"""edge-tts provider (unofficial Microsoft Edge online TTS)."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path

from . import TTSProvider

logger = logging.getLogger(__name__)

# Per-attempt hard timeout for communicate.save (seconds).
_SYNTH_TIMEOUT_SECONDS = 120
# Transient network / endpoint failures: retry with exponential backoff.
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1.0, 2.0, 4.0)


class EdgeTTSProvider(TTSProvider):
    name = 'edge-tts'

    def synthesize(self, text: str, *, voice: str) -> bytes:
        last_exc: BaseException | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return _run_async(self._synthesize_async(text, voice))
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_ATTEMPTS:
                    delay = _BACKOFF_SECONDS[attempt - 1]
                    logger.warning(
                        'TTS provider transient failure provider=%s voice=%s '
                        'attempt=%s/%s retry_in=%.1fs error=%s',
                        self.name,
                        voice,
                        attempt,
                        _MAX_ATTEMPTS,
                        delay,
                        exc,
                        extra={'tts_provider': self.name},
                    )
                    time.sleep(delay)
                    continue
                # Do not swallow — re-raise after structured log so GenerationJob
                # marks failed and /health/generation/ failed_recent_24h increments.
                logger.error(
                    'TTS provider failure provider=%s voice=%s attempts=%s error=%s',
                    self.name,
                    voice,
                    _MAX_ATTEMPTS,
                    exc,
                    extra={'tts_provider': self.name},
                )
                raise
        assert last_exc is not None
        raise last_exc

    async def _synthesize_async(self, text: str, voice: str) -> bytes:
        import edge_tts

        if not (text or '').strip():
            return b''
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate='-14%',
            pitch='+0Hz',
            volume='+0%',
            boundary='SentenceBoundary',
        )
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            # Hard timeout prevents indefinite hangs when the unofficial
            # edge-tts network service stalls. Provider-level retries (above)
            # and job-level retries in jobs.py cover transient outages.
            try:
                await asyncio.wait_for(
                    communicate.save(tmp_path),
                    timeout=_SYNTH_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f'edge-tts timed out after {_SYNTH_TIMEOUT_SECONDS} s '
                    f'for voice={voice!r}'
                ) from None
            return Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
