from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.db import get_db
from app.ids import require_user
from app.services import storage
from app.services.audio import AudioError
from app.services.translate import translate as run_translate

router = APIRouter(tags=["conversation"])


@router.post("/translate")
async def translate(
    user_id: str = Form(...),
    session_id: str = Form(..., min_length=1, max_length=64),
    audio: UploadFile = File(...),
) -> dict:
    """One recording -> one clear sentence, a confidence score and what to do with it.

    action "speak": score >= the user's threshold, say it aloud to the listener.
    action "check": play it back to the user privately and wait for thumbs up / down.
    """
    db = get_db()
    user = await require_user(db, user_id)
    audio_path, _ = await storage.save_upload(audio, user_id, f"utt-{ObjectId()}")
    try:
        return await run_translate(db, user, session_id, audio_path)
    except AudioError:
        await storage.delete_file(audio_path)
        raise HTTPException(status_code=422, detail="Could not read the recording. Please record again.") from None
