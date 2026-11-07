from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.db import get_db
from app.ids import require_user
from app.services.phrases import supported_languages

router = APIRouter(tags=["users"])

# "both" = the user switches between languages; the recognizer auto-detects each utterance.
MIXED_LANGUAGE = "both"


class CreateUser(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    main_language: str
    consent: bool

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("main_language")
    @classmethod
    def known_language(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = [*supported_languages(), MIXED_LANGUAGE]
        if v not in allowed:
            raise ValueError(f"main_language must be one of: {', '.join(allowed)}")
        return v


class ThresholdChange(BaseModel):
    at: datetime
    to: float
    reason: str


class UserOut(BaseModel):
    user_id: str
    name: str
    main_language: str
    threshold: float
    created_at: datetime
    threshold_history: list[ThresholdChange] = []


@router.post("/users", status_code=201)
async def create_user(body: CreateUser) -> dict:
    """Sign up: save the user's name, main language and consent. Returns the new user_id."""
    if not body.consent:
        raise HTTPException(
            status_code=400,
            detail="Consent is required: Echo stores voice recordings to learn how the user speaks.",
        )
    doc = {
        "name": body.name,
        "main_language": body.main_language,
        "threshold": get_settings().default_threshold,
        "consent": True,
        "consent_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    result = await get_db().users.insert_one(doc)
    return {"user_id": str(result.inserted_id)}


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: str) -> UserOut:
    """Used by the app on start-up to check the saved user still exists."""
    user = await require_user(get_db(), user_id)
    return UserOut(
        user_id=str(user["_id"]),
        name=user["name"],
        main_language=user["main_language"],
        threshold=user["threshold"],
        created_at=user["created_at"],
        threshold_history=[
            ThresholdChange(at=c["at"], to=c["to"], reason=c["reason"]) for c in user.get("threshold_history", [])[-5:]
        ],
    )


# The progress ring fills toward the next milestone, then starts on the next one.
MILESTONES = [10, 25, 50, 100, 200, 500, 1000]


@router.get("/users/{user_id}/progress")
async def progress(user_id: str) -> dict:
    """How much Echo has learned about this user (for the progress ring and helpers)."""
    db = get_db()
    user = await require_user(db, user_id)
    learned = await db.utterances.count_documents({"user_id": user_id, "speaker": "user", "status": "approved"})
    corrected = await db.utterances.count_documents({"user_id": user_id, "status": "approved", "was_corrected": True})
    samples = await db.enrollment_samples.count_documents({"user_id": user_id})
    words = await db.personal_words.count_documents({"user_id": user_id})
    target = next((m for m in MILESTONES if m > learned), learned + 500)
    previous = max([0, *[m for m in MILESTONES if m <= learned]])
    return {
        "learned": learned,
        "corrected": corrected,
        "enrollment_samples": samples,
        "personal_words": words,
        "threshold": user.get("threshold", get_settings().default_threshold),
        "milestone": target,
        "fraction": round((learned - previous) / (target - previous), 3),
    }
