"""edge-tts provider (unofficial Microsoft Edge online TTS)."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from . import TTSProvider


class EdgeTTSProvider(TTSProvider):
    name = 'edge-tts'

    def synthesize(self, text: str, *, voice: str) -> bytes:
        return _run_async(self._synthesize_async(text, voice))

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
            # 120-second hard timeout prevents indefinite hangs when the
            # unofficial edge-tts network service stalls.  The job-level
            # retry in jobs.py (up to max_attempts=3) handles transient
            # failures, so re-raising here is intentional.
            try:
                await asyncio.wait_for(communicate.save(tmp_path), timeout=120)
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f'edge-tts timed out after 120 s for voice={voice!r}'
                )
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
