"""Echo backend: the FastAPI app that runs speech recognition, the agent and memory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.config import get_settings
from app.services.asr import close_shared_client
from app.routes import enroll, feedback, phrases, translate, tts, turns, users, utterances, words

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Fails right here, with a clear list of missing keys, if backend/.env is incomplete.
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger = logging.getLogger("echo")
    if not settings.elevenlabs_api_key:
        logger.warning("ELEVENLABS_API_KEY not set: the app will use the browser's built-in voice.")
    if not settings.embedding_api_key:
        logger.warning("EMBEDDING_API_KEY not set: similar sentences are matched by spelling, not meaning.")
    await db.connect(settings.mongodb_uri, settings.mongodb_db)
    yield
    await close_shared_client()
    await db.close()


app = FastAPI(title="Echo API", version="0.1.0", lifespan=lifespan)

# The frontend runs on a different port/domain, so the browser needs CORS permission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(db.DatabaseUnavailable)
async def database_unavailable(_: Request, exc: db.DatabaseUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(phrases.router)
app.include_router(users.router)
app.include_router(enroll.router)
app.include_router(words.router)
app.include_router(translate.router)
app.include_router(turns.router)
app.include_router(feedback.router)
app.include_router(tts.router)
app.include_router(utterances.router)


@app.get("/health")
async def health() -> dict:
    """Simple "I'm alive" check used by the frontend and the hosting platform."""
    return {
        "status": "ok",
        "db": await db.ping(),
        # Which optional features are switched on (the app adapts to them).
        "features": {
            "tts": "elevenlabs" if settings.elevenlabs_api_key else "browser",
            "embeddings": "voyage" if settings.embedding_api_key else "spelling",
        },
    }
