"""ElevenLabs account state, used by text-to-speech (services/tts.py).

When the account runs out of credits ElevenLabs answers every request with "quota_exceeded".
That is remembered for a while, so requests skip ElevenLabs straight away (the app falls back to
the browser's voice) instead of waiting for an answer that is sure to be "no".
"""

import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger("echo.elevenlabs")

# How long to skip ElevenLabs after it says the account has no credits left.
EMPTY_PAUSE_SECONDS = 15 * 60

_empty_until = 0.0


def enabled() -> bool:
    return bool(get_settings().elevenlabs_api_key)


def out_of_credits() -> bool:
    return time.monotonic() < _empty_until


def note_response(res: httpx.Response) -> None:
    """Call with every failed ElevenLabs response: notices an empty account."""
    global _empty_until
    if res.status_code in (401, 402, 429) and "quota_exceeded" in res.text:
        if not out_of_credits():
            logger.warning("ElevenLabs has no credits left: skipping it for %d minutes.", EMPTY_PAUSE_SECONDS // 60)
        _empty_until = time.monotonic() + EMPTY_PAUSE_SECONDS


def reset() -> None:
    """Forget the "out of credits" state (tests)."""
    global _empty_until
    _empty_until = 0.0


def status() -> str:
    """For /health: "off" (no key), "out of credits", or "on"."""
    if not enabled():
        return "off"
    return "out of credits" if out_of_credits() else "on"
