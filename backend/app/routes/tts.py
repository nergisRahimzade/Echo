from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from app.services import tts

router = APIRouter(tags=["voice"])


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    language: Literal["tr", "en"]

    @field_validator("text")
    @classmethod
    def tidy(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be blank")
        return v


@router.post("/tts", response_class=Response, responses={200: {"content": {"audio/mpeg": {}}}, 503: {}})
async def text_to_speech(body: TTSIn) -> Response:
    """Turn a sentence into clear speech (mp3). 503 = use the browser's own voice instead."""
    try:
        audio, cached = await tts.synthesize(body.text, body.language)
    except tts.TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return Response(content=audio, media_type="audio/mpeg", headers={"X-TTS-Cache": "hit" if cached else "miss", "Cache-Control": "private, max-age=86400"})
