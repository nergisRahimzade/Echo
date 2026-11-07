"""The voices a user can pick for Echo to speak with (all American English accents).

Adults are ElevenLabs default voices, which every plan can use through the API.
The girl and boy voices are the account's own voices (ElevenLabs Voice Design), configured with
ELEVENLABS_VOICE_GIRL / ELEVENLABS_VOICE_BOY; until then they are simply not offered.
"""

from dataclasses import dataclass
from typing import Literal

from app.config import get_settings

Kind = Literal["woman", "man", "girl", "boy"]


@dataclass(frozen=True)
class Voice:
    id: str  # Echo's own name for the voice (stored on the user)
    name: str
    kind: Kind
    style: str  # short description key, translated by the frontend (settings.voiceStyles.*)
    elevenlabs_id: str | None


ADULT_VOICES = [
    Voice("jessica", "Jessica", "woman", "bright", "cgSgspJ2msm6clMCkdW9"),
    Voice("sarah", "Sarah", "woman", "calm", "EXAVITQu4vr4xnSDxMaL"),
    Voice("will", "Will", "man", "friendly", "bIHbv24MWmeRgasZH58o"),
    Voice("chris", "Chris", "man", "relaxed", "iP95p4xoKVk53GoZ742B"),
]


def all_voices() -> list[Voice]:
    """Every voice Echo knows, including child voices that are not set up yet."""
    s = get_settings()
    return [
        *ADULT_VOICES,
        Voice("girl", "Lily", "girl", "cheerful", s.elevenlabs_voice_girl or None),
        Voice("boy", "Max", "boy", "cheerful", s.elevenlabs_voice_boy or None),
    ]


def available() -> list[Voice]:
    return [v for v in all_voices() if v.elevenlabs_id]


def get(voice_id: str | None) -> Voice:
    """The chosen voice, or the default when none was chosen / it is no longer available."""
    voices = {v.id: v for v in available()}
    return voices.get(voice_id or "") or voices.get(get_settings().default_voice) or ADULT_VOICES[0]


def is_available(voice_id: str) -> bool:
    return any(v.id == voice_id for v in available())
