"""Pre-record Echo's spoken prompts ("say it again", ...) with ElevenLabs, once per language.

Run from backend/ (needs ELEVENLABS_API_KEY):  python -m scripts.make_prompts
Writes frontend/public/prompts/{lang}/{id}.mp3. The app plays these files when they exist
and falls back to the browser voice when they don't.
Keep the texts in sync with frontend/lib/prompts.ts.
"""

import asyncio
import os
import sys

from app.config import REPO_DIR, read_env_values

for k, v in read_env_values().items():
    if v and (k.endswith("_API_KEY") or k.startswith("MONGODB")):
        os.environ.setdefault(k, v)

from app.services.tts import TTSUnavailable, synthesize  # noqa: E402

PROMPTS = {
    "tr": {"sayAgain": "Lütfen tekrar söyle.", "helper": "Bir yardımcı yazabilir."},
    "en": {"sayAgain": "Please say it again.", "helper": "A helper can type it."},
}


async def main() -> int:
    out = REPO_DIR / "frontend" / "public" / "prompts"
    try:
        for lang, prompts in PROMPTS.items():
            for pid, text in prompts.items():
                audio, _ = await synthesize(text, lang)
                path = out / lang / f"{pid}.mp3"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(audio)
                print(f"wrote {path.relative_to(REPO_DIR)}")
    except TTSUnavailable as exc:
        print(f"Cannot record prompts: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
