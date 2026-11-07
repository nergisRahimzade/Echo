from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.services import tts, voices

router = APIRouter(tags=["voice"])


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    language: Literal["tr", "en"]
    voice: str | None = None  # an id from GET /voices; default voice when missing

    @field_validator("text")
    @classmethod
    def tidy(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be blank")
        return v

    @field_validator("voice")
    @classmethod
    def known_voice(cls, v: str | None) -> str | None:
        if v is not None and not voices.is_available(v):
            raise ValueError(f"unknown voice: {v}")
        return v


class VoiceOut(BaseModel):
    id: str
    name: str
    kind: voices.Kind
    style: str


class VoicesOut(BaseModel):
    enabled: bool  # false = no ElevenLabs key: the browser's own voice is used
    default: str
    voices: list[VoiceOut]
    missing: list[voices.Kind]  # kinds Echo supports but this server has not set up (child voices)


@router.get("/voices", response_model=VoicesOut)
async def list_voices() -> VoicesOut:
    """The voices a user can choose for Echo to speak with."""
    ready = voices.available()
    return VoicesOut(
        enabled=tts.enabled(),
        default=voices.get(get_settings().default_voice).id,
        voices=[VoiceOut(id=v.id, name=v.name, kind=v.kind, style=v.style) for v in ready],
        missing=[v.kind for v in voices.all_voices() if not v.elevenlabs_id],
    )


@router.post("/tts", response_class=Response, responses={200: {"content": {"audio/mpeg": {}}}, 503: {}})
async def text_to_speech(body: TTSIn) -> Response:
    """Turn a sentence into clear speech (mp3). 503 = use the browser's own voice instead."""
    try:
        audio, cached = await tts.synthesize(body.text, body.language, body.voice)
    except tts.TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return Response(content=audio, media_type="audio/mpeg", headers={"X-TTS-Cache": "hit" if cached else "miss", "Cache-Control": "private, max-age=86400"})
