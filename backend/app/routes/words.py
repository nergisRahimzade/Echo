"""Personal words: names of family, friends, places and pets.

They are fed to Whisper as hints (so "Zeynep" isn't heard as "seen up") and given to the agent.
"""

import re
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.db import get_db
from app.ids import require_user

router = APIRouter(tags=["personal words"])

WordKind = Literal["person", "place", "pet", "other"]


def word_key(word: str) -> str:
    """Case-insensitive key so "Zeynep" and "zeynep" are the same word."""
    return word.casefold()


class WordIn(BaseModel):
    word: str = Field(min_length=1, max_length=60)
    kind: WordKind = "other"

    @field_validator("word")
    @classmethod
    def tidy(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if not v:
            raise ValueError("word must not be blank")
        return v


class AddWords(BaseModel):
    user_id: str
    words: list[WordIn] = Field(min_length=1, max_length=100)


class WordOut(BaseModel):
    word: str
    kind: WordKind


@router.post("/words")
async def add_words(body: AddWords) -> dict:
    """Save names/places for a user. Adding an existing word updates its kind."""
    db = get_db()
    await require_user(db, body.user_id)
    now = datetime.now(UTC)
    for w in body.words:  # at most 100, so one update per word is fine
        await db.personal_words.update_one(
            {"user_id": body.user_id, "key": word_key(w.word)},
            {
                "$set": {"word": w.word, "kind": w.kind, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
    return {"ok": True, "count": len(body.words)}


@router.get("/words", response_model=list[WordOut])
async def list_words(user_id: str = Query(...)) -> list[WordOut]:
    db = get_db()
    await require_user(db, user_id)
    cursor = db.personal_words.find({"user_id": user_id}).sort("created_at", 1)
    return [WordOut(word=d["word"], kind=d["kind"]) async for d in cursor]


@router.delete("/words")
async def delete_word(user_id: str = Query(...), word: str = Query(..., min_length=1)) -> dict:
    db = get_db()
    await require_user(db, user_id)
    result = await db.personal_words.delete_one({"user_id": user_id, "key": word_key(word.strip())})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Word not found")
    return {"ok": True}
