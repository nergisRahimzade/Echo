"""Conversation turns: what the other person said (typed by a helper), so the agent knows the topic."""

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from app.agent.tools import ToolContext, get_recent_turns
from app.db import get_db
from app.ids import require_user

router = APIRouter(tags=["conversation"])


class TurnIn(BaseModel):
    user_id: str
    session_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def tidy(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be blank")
        return v


@router.post("/turns", status_code=201)
async def add_turn(body: TurnIn) -> dict:
    """Save something the other person said in this conversation."""
    db = get_db()
    await require_user(db, body.user_id)
    result = await db.utterances.insert_one(
        {
            "user_id": body.user_id,
            "session_id": body.session_id,
            "speaker": "other",
            "sentence": body.text,
            "status": "turn",
            "created_at": datetime.now(UTC),
        }
    )
    return {"turn_id": str(result.inserted_id)}


@router.get("/turns")
async def list_turns(user_id: str = Query(...), session_id: str = Query(...), n: int = Query(10, ge=1, le=50)) -> list[dict]:
    """The last confirmed turns of a conversation (both speakers), oldest first."""
    db = get_db()
    await require_user(db, user_id)
    return await get_recent_turns(ToolContext(db=db, user_id=user_id, session_id=session_id), n=n)
