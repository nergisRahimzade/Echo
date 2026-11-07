"""Echo backend: the FastAPI app that runs speech recognition, the agent and memory."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Echo API", version="0.1.0")

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
    return {"status": "ok"}
