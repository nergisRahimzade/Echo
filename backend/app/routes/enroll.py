from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.db import get_db
from app.ids import require_user
from app.services import storage
from app.services.phrases import supported_languages

router = APIRouter(tags=["enrollment"])


class SampleOut(BaseModel):
    sample_id: str
    phrase_id: str | None
    text: str
    language: str
    created_at: datetime


def resolve_language(requested: str | None, user: dict) -> str:
    """The sample's language: as sent, else the user's main language."""
    lang = (requested or "").strip().lower() or user["main_language"]
    if lang not in supported_languages():
        raise HTTPException(
            status_code=422,
            detail=f"language must be one of: {', '.join(supported_languages())}",
        )
    return lang


@router.post("/enroll", status_code=201)
async def enroll(
    user_id: str = Form(...),
    phrase_text: str = Form(..., min_length=1, max_length=300),
    audio: UploadFile = File(...),
    phrase_id: str | None = Form(None, max_length=64),
    language: str | None = Form(None),
) -> dict:
    """Save one enrollment recording together with the sentence it was meant to be."""
    db = get_db()
    user = await require_user(db, user_id)
    lang = resolve_language(language, user)
    text = phrase_text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="phrase_text must not be blank")

    sample_id = ObjectId()
    audio_path, size = await storage.save_upload(audio, user_id, str(sample_id))
    doc = {
        "_id": sample_id,
        "user_id": user_id,
        "phrase_id": phrase_id,
        "text": text,
        "language": lang,
        "audio_path": audio_path,
        "mime_type": audio.content_type,
        "size_bytes": size,
        "created_at": datetime.now(UTC),
    }
    try:
        await db.enrollment_samples.insert_one(doc)
    except Exception:
        await storage.delete_file(audio_path)  # don't leave orphan audio behind
        raise
    return {"sample_id": str(sample_id)}


@router.get("/enroll", response_model=list[SampleOut])
async def list_samples(user_id: str = Query(...)) -> list[SampleOut]:
    """A user's enrollment samples, oldest first (used to show progress and resume)."""
    db = get_db()
    await require_user(db, user_id)
    cursor = db.enrollment_samples.find({"user_id": user_id}).sort("created_at", 1)
    return [
        SampleOut(
            sample_id=str(d["_id"]),
            phrase_id=d.get("phrase_id"),
            text=d["text"],
            language=d["language"],
            created_at=d["created_at"],
        )
        async for d in cursor
    ]
