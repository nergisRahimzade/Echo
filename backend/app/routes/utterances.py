"""A user's translated sentences and what happened to them (for helpers and the progress view)."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db import get_db
from app.ids import require_user

router = APIRouter(tags=["learning"])

Status = Literal["pending", "spoken", "approved", "rejected"]


class UtteranceOut(BaseModel):
    utterance_id: str
    session_id: str
    sentence: str
    final_text: str | None = None
    status: str
    verdict: str | None = None
    was_corrected: bool | None = None
    auto_approved: bool | None = None
    action: str | None = None
    score: float | None = None
    attempt: int | None = None
    language: str | None = None
    audio_path: str | None = None
    created_at: datetime


@router.get("/utterances", response_model=list[UtteranceOut])
async def list_utterances(
    user_id: str = Query(...),
    status: Status | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[UtteranceOut]:
    """Newest first. Only the user's own speech (not the other person's typed turns)."""
    db = get_db()
    await require_user(db, user_id)
    query: dict = {"user_id": user_id, "speaker": "user"}
    if status:
        query["status"] = status
    cursor = db.utterances.find(query).sort("created_at", -1).limit(limit)
    return [
        UtteranceOut(
            utterance_id=str(d["_id"]),
            session_id=d.get("session_id", ""),
            sentence=d.get("sentence", ""),
            final_text=d.get("final_text"),
            status=d["status"],
            verdict=d.get("verdict"),
            was_corrected=d.get("was_corrected"),
            auto_approved=d.get("auto_approved"),
            action=d.get("action"),
            score=(d.get("score") or {}).get("score"),
            attempt=d.get("attempt"),
            language=d.get("language"),
            audio_path=d.get("audio_path"),
            created_at=d["created_at"],
        )
        async for d in cursor
    ]
