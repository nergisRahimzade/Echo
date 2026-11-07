"""Echo backend: the FastAPI app that runs speech recognition, the agent and memory."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    yield
    await db.close()


app = FastAPI(title="Echo API", version="0.1.0", lifespan=lifespan)

# The frontend runs on a different port/domain, so the browser needs CORS permission.
# Comma-separated list, e.g. "http://localhost:3000,https://echo.vercel.app".
frontend_origins = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in frontend_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Simple "I'm alive" check used by the frontend and the hosting platform."""
    return {"status": "ok", "db": await db.ping()}
