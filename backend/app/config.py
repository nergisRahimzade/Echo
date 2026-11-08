"""All settings and secret keys, loaded from environment variables or a .env file.

The .env file can live in backend/.env or at the repo root (.env); backend/.env wins.
Use `get_settings()` anywhere in the backend. If a required key is missing the app
stops at startup with a message that lists exactly which keys to add.
Optional keys (ElevenLabs, embeddings) only switch on better features; Echo falls back
to the browser voice and to text-similarity search without them.
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
# Later files win, so backend/.env overrides a root .env.
ENV_FILES: tuple[Path, ...] = (REPO_DIR / ".env", ENV_FILE)

# Keys that must be present (and not blank) for Echo to run.
REQUIRED_KEYS = (
    "anthropic_api_key",
    "mongodb_uri",
)
# Nice to have: each one switches on a better feature, with a fallback without it.
OPTIONAL_KEYS = (
    "openai_api_key",
    "groq_api_key",
    "elevenlabs_api_key",
    "embedding_api_key",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore"
    )

    # --- Secret keys (from the project brief) ---
    anthropic_api_key: str
    openai_api_key: str | None = None  # Whisper via OpenAI ...
    groq_api_key: str | None = None  # ... or via Groq (one of the two is required)
    elevenlabs_api_key: str | None = None  # optional: browser voice is the fallback
    mongodb_uri: str
    embedding_api_key: str | None = None  # optional: text-similarity search is the fallback

    # --- Normal settings (safe defaults) ---
    mongodb_db: str = "echo"
    frontend_url: str = "http://localhost:3000"  # comma-separated list allowed
    phrases_dir: Path = REPO_DIR / "phrases"  # enrollment phrase lists (tr.json, en.json)
    uploads_dir: Path = REPO_DIR / "uploads"  # audio files: uploads/{user_id}/{sample_id}.webm
    max_upload_mb: float = 10.0
    whisper_model: str | None = None  # default: whisper-large-v3 on Groq, whisper-1 on OpenAI
    # Sound matching: DTW cost at which similarity reaches 0 (measured: same phrase ~0.04,
    # different phrase ~0.47), extra weight for sentences a helper corrected, and less weight for
    # sentences only approved by silence (nobody pressed thumbs-down; nobody said thumbs-up either).
    sound_match_scale: float = 0.5
    corrected_match_weight: float = 1.15
    silent_match_weight: float = 0.85
    # ElevenLabs voices. multilingual_v2 = the most natural, expressive model that stays exact on
    # short sentences (~0.45 s); every voice can speak Turkish and English. The voice list itself
    # is in app/services/voices.py. Child voices are your own ElevenLabs voices (Voice Design on
    # elevenlabs.io; the free plan cannot use library voices through the API), so they are only
    # offered once their voice ids are set here.
    elevenlabs_model: str = "eleven_multilingual_v2"
    # Speech-to-text: with an ElevenLabs key, Scribe adds one more reading of every recording,
    # next to the Whisper ones (more independent readings = a better agreement score).
    elevenlabs_stt: bool = True
    elevenlabs_stt_model: str = "scribe_v2"
    default_voice: str = "jessica"
    elevenlabs_voice_girl: str | None = None
    elevenlabs_voice_boy: str | None = None
    # Text embeddings (Voyage AI, multilingual) for Atlas Vector Search.
    # Combined score weights (brief: 0.5 / 0.25 / 0.25; tune with real data) and the default
    # speak-aloud threshold for new users.
    score_weight_agent: float = 0.5
    score_weight_agreement: float = 0.25
    score_weight_sound: float = 0.25
    default_threshold: float = 0.80
    # The agent brain (the brief specifies Claude Sonnet). Low effort keeps it fast.
    agent_model: str = "claude-sonnet-5-5"
    agent_effort: str = "low"
    embedding_model: str = "voyage-3.5"
    embedding_dims: int = 1024

    @field_validator(*REQUIRED_KEYS, *OPTIONAL_KEYS, mode="before")
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
        # Browsers send the origin without a trailing slash, so "https://x.com/" would never match.
        return [o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()]


class MissingSettingsError(RuntimeError):
    """Raised with a human-friendly list of the keys that need to be set."""


WHISPER_KEY_MESSAGE = "OPENAI_API_KEY or GROQ_API_KEY (one is needed for Whisper)"


def read_env_values(env_files: tuple[Path, ...] | Path | None = ENV_FILES) -> dict[str, str | None]:
    """Raw key/values from the .env file(s) plus the real environment (environment wins)."""
    if isinstance(env_files, Path):
        env_files = (env_files,)
    values: dict[str, str | None] = {}
    for f in env_files or ():
        if f.exists():
            values.update({k.upper(): v for k, v in dotenv_values(f).items()})
    values.update({k.upper(): v for k, v in os.environ.items()})
    return values


def _whisper_key_missing(env_files) -> bool:
    """Pydantic skips the Whisper check when other keys already failed, so check it directly."""
    values = read_env_values(env_files)
    return not any((values.get(k) or "").strip() for k in ("OPENAI_API_KEY", "GROQ_API_KEY"))


def _friendly_error(exc: ValidationError, env_file) -> MissingSettingsError:
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


def load_settings(env_file: tuple[Path, ...] | Path | None = ENV_FILES) -> Settings:
    """Read settings fresh. Pass env_file=None to use only real environment variables."""
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        raise _friendly_error(exc, env_file) from None


@lru_cache
def get_settings() -> Settings:
    """The app-wide settings, read once."""
    return load_settings()
