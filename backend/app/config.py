"""All settings and secret keys, loaded from environment variables or backend/.env.

Use `get_settings()` anywhere in the backend. If a required key is missing the app
stops at startup with a message that lists exactly which keys to add.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"

# Keys that must be present (and not blank) for Echo to run.
REQUIRED_KEYS = (
    "anthropic_api_key",
    "elevenlabs_api_key",
    "mongodb_uri",
    "embedding_api_key",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # --- Secret keys (from the project brief) ---
    anthropic_api_key: str
    openai_api_key: str | None = None  # Whisper via OpenAI ...
    groq_api_key: str | None = None  # ... or via Groq (one of the two is required)
    elevenlabs_api_key: str
    mongodb_uri: str
    embedding_api_key: str

    # --- Normal settings (safe defaults) ---
    mongodb_db: str = "echo"
    frontend_url: str = "http://localhost:3000"  # comma-separated list allowed
    phrases_dir: Path = REPO_DIR / "phrases"  # enrollment phrase lists (tr.json, en.json)
    uploads_dir: Path = REPO_DIR / "uploads"  # audio files: uploads/{user_id}/{sample_id}.webm
    max_upload_mb: float = 10.0

    @field_validator(*REQUIRED_KEYS, "openai_api_key", "groq_api_key", mode="before")
    @classmethod
    def blank_means_missing(cls, value):
        """Treat `KEY=` (empty, copied from .env.example) the same as not set."""
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def need_one_whisper_key(self):
        if not (self.openai_api_key or self.groq_api_key):
            raise ValueError(WHISPER_KEY_MESSAGE)
        return self

    @property
    def frontend_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_url.split(",") if o.strip()]


class MissingSettingsError(RuntimeError):
    """Raised with a human-friendly list of the keys that need to be set."""


WHISPER_KEY_MESSAGE = "OPENAI_API_KEY or GROQ_API_KEY (one is needed for Whisper)"


def _whisper_key_missing(env_file: Path | None) -> bool:
    """Pydantic skips the Whisper check when other keys already failed, so check it directly."""
    values: dict[str, str | None] = {}
    if env_file and Path(env_file).exists():
        values.update({k.upper(): v for k, v in dotenv_values(env_file).items()})
    values.update({k.upper(): v for k, v in os.environ.items()})
    return not any((values.get(k) or "").strip() for k in ("OPENAI_API_KEY", "GROQ_API_KEY"))


def _friendly_error(exc: ValidationError, env_file: Path | None) -> MissingSettingsError:
    problems = []
    for err in exc.errors():
        if err["loc"]:
            problems.append(str(err["loc"][0]).upper())
        else:  # model-level check, e.g. the Whisper key
            problems.append(str(err["msg"]).removeprefix("Value error, "))
    if WHISPER_KEY_MESSAGE not in problems and _whisper_key_missing(env_file):
        problems.append(WHISPER_KEY_MESSAGE)
    lines = "\n".join(f"  - {p}" for p in problems)
    return MissingSettingsError(
        "Echo cannot start: these settings are missing or empty:\n"
        f"{lines}\n"
        f"Add them to {ENV_FILE} (copy backend/.env.example to start) "
        "or set them as environment variables."
    )


def load_settings(env_file: Path | None = ENV_FILE) -> Settings:
    """Read settings fresh. Pass env_file=None to use only real environment variables."""
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        raise _friendly_error(exc, env_file) from None


@lru_cache
def get_settings() -> Settings:
    """The app-wide settings, read once."""
    return load_settings()
