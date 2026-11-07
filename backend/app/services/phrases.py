"""Enrollment phrase lists, one JSON file per language in the phrases/ folder.

Adding a language = dropping a new `<code>.json` file there; nothing else to change here.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, TypeAdapter

from app.config import get_settings

Category = Literal["greetings", "needs", "feelings", "questions", "yes_no"]


class Phrase(BaseModel):
    id: str
    text: str
    category: Category
    icon: str  # an emoji, shown as the picture for people who don't read


_phrase_list = TypeAdapter(list[Phrase])


def phrases_dir() -> Path:
    return get_settings().phrases_dir


def supported_languages() -> list[str]:
    """Language codes that have a phrase file, e.g. ["en", "tr"]."""
    return sorted(p.stem for p in phrases_dir().glob("*.json"))


@lru_cache
def load_phrases(lang: str) -> list[Phrase]:
    """Read and validate one language's phrases. Raises KeyError for unknown languages."""
    if lang not in supported_languages():
        raise KeyError(lang)
    raw = json.loads((phrases_dir() / f"{lang}.json").read_text(encoding="utf-8"))
    return _phrase_list.validate_python(raw)


def phrase_text(lang: str, phrase_id: str) -> str | None:
    """The sentence for a phrase id, or None if there is no such phrase."""
    try:
        phrases = load_phrases(lang)
    except KeyError:
        return None
    return next((p.text for p in phrases if p.id == phrase_id), None)
