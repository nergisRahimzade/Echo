"""Load the ready-trained demo account for the judges (task 6.5).

Run from backend/ (uses MONGODB_URI from .env, or the environment):

    python -m scripts.seed_demo                       # recordings made with an ElevenLabs voice
    python -m scripts.seed_demo --audio-dir my_recs   # real recordings: {lang}-{phrase_id}.wav/.webm/.mp3/.m4a
    python -m scripts.seed_demo --no-style            # skip the Claude style summary

Creates "Deniz", who mixes Turkish and English, with:
- enrollment recordings for every phrase in both languages (with sound fingerprints),
- personal names and places (daughter Zeynep, brother Ahmet, cat Boncuk, Dr. Aydın, Kadıköy),
- 31 approved sentences over the past three weeks, 5 of them corrected by a helper, plus the
  other person's replies, so the progress ring, sound matching and the style profile all have data,
- a style profile written by Claude and one automatic threshold adjustment.

Safe to run again: the previous demo account and everything in it are deleted first.
Open <FRONTEND_URL>/demo to use it.
"""

import argparse
import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bson import ObjectId

from app import db as database
from app.config import get_settings
from app.services import privacy, storage, style, tts
from app.services.audio import AudioError
from app.services.phrases import load_phrases
from app.services.voiceprint import fingerprint_upload

NAME = "Deniz"
WORDS = [("Zeynep", "person"), ("Ahmet", "person"), ("Dr. Aydın", "person"), ("Boncuk", "pet"), ("Kadıköy", "place")]

# (what Echo understood, what the user meant if a helper corrected it, language)
SESSIONS: list[list[tuple[str, str | None, str] | str]] = [
    # Strings are the other person's replies; tuples are the user's approved sentences.
    ["Günaydın Deniz, nasıl uyudun?", ("Bugün kendimi daha iyi hissediyorum.", None, "tr"),
     ("Çayımı şekersiz içiyorum.", None, "tr"), ("Su istiyorum lütfen.", None, "tr"),
     ("Pencereyi açar mısın?", None, "tr"), ("Teşekkür ederim, çok naziksin.", None, "tr")],
    ["Zeynep birazdan arayacak.", ("Zeynep bugün okuldan ne zaman gelecek?", None, "tr"),
     ("Zeynep'e sevgilerimi söyle.", None, "tr"), ("Bonjuk'a mama verdin mi?", "Boncuk'a mama verdin mi?", "tr"),
     ("Ahmet akşam yemeğe geliyor mu?", None, "tr"), ("Zeynep'i arayalım, I miss her.", None, "tr")],
    ["Good afternoon! How are you feeling?", ("I am feeling much better today.", None, "en"),
     ("I would like a cup of tea, please.", None, "en"), ("Where did I put my glasses?", None, "en"),
     ("Could you speak a little slower?", None, "en"), ("Thank you for helping me.", None, "en")],
    ["Dışarısı çok güzel bugün.", ("Kadıköy'e otobüsle gidelim.", "Kadıköy'e vapurla gidelim.", "tr"),
     ("Biraz dinlenmek istiyorum.", None, "tr"), ("Başım biraz ağrıyor.", None, "tr"),
     ("İlaçlarımı aldım mı?", None, "tr"), ("Dr. Aydın'ı arayabilir misin?", None, "tr")],
    ["Do you need anything?", ("Can you call Zehra for me?", "Can you call Zeynep for me?", "en"),
     ("Please turn the light off.", None, "en"), ("I need my jacket, I am cold.", "I need my blanket, I am cold.", "en"),
     ("Boncuk is hungry, can you feed her?", None, "en"), ("I want to watch the news.", None, "en")],
    ["Akşam ne yapalım?", ("What time is my appointment with the doctor?", "What time is my appointment with Dr. Aydın?", "en"),
     ("Televizyonun sesini kısar mısın?", None, "tr"), ("Let's have dinner with Ahmet on Sunday.", None, "en"),
     ("Can we go for a walk in the park?", None, "en"), ("Yarın hava nasıl olacak?", None, "tr"), ("I love you.", None, "en")],
]


def find_recording(audio_dir: Path | None, lang: str, phrase_id: str) -> Path | None:
    if not audio_dir:
        return None
    for ext in ("wav", "webm", "mp3", "m4a", "ogg"):
        path = audio_dir / f"{lang}-{phrase_id}.{ext}"
        if path.exists():
            return path
    return None


async def add_enrollment(db, uid: str, start: datetime, audio_dir: Path | None, voice: str) -> int:
    """One recording per phrase per language, fingerprinted exactly like POST /enroll does."""
    use_tts = audio_dir is None and tts.enabled()
    if audio_dir is None and not use_tts:
        print("  no --audio-dir and no ELEVENLABS_API_KEY: skipping enrollment recordings")
        return 0
    saved = 0
    for lang in ("tr", "en"):
        for i, phrase in enumerate(load_phrases(lang)):
            recording = find_recording(audio_dir, lang, phrase.id)
            if recording:
                data, ext = recording.read_bytes(), recording.suffix.lstrip(".")
            elif use_tts:
                data, _ = await tts.synthesize(phrase.text, lang, voice)
                ext = "mp3"
            else:
                continue
            sample_id = ObjectId()
            relative = f"{uid}/{sample_id}.{ext}"
            target = storage.absolute_path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            try:
                fingerprint = await fingerprint_upload(relative)
            except AudioError as exc:
                print(f"  skipped {lang}-{phrase.id}: {exc}")
                continue
            await db.enrollment_samples.insert_one({
                "_id": sample_id, "user_id": uid, "phrase_id": phrase.id, "text": phrase.text, "language": lang,
                "audio_path": relative, "mime_type": f"audio/{'mpeg' if ext == 'mp3' else ext}", "size_bytes": len(data),
                **fingerprint, "created_at": start + timedelta(minutes=i + (30 if lang == "en" else 0)),
            })
            saved += 1
    return saved


async def add_sentences(db, uid: str, start: datetime) -> tuple[int, int]:
    rng = random.Random(7)  # same numbers every run
    approved = corrected = 0
    for day, session in enumerate(SESSIONS):
        session_id = f"demo-{day + 1}"
        at = start + timedelta(days=2 + day * 3, hours=10 + day % 4)
        for item in session:
            at += timedelta(minutes=rng.randint(1, 4))
            if isinstance(item, str):
                await db.utterances.insert_one({"user_id": uid, "session_id": session_id, "speaker": "other",
                                                "sentence": item, "status": "turn", "created_at": at})
                continue
            heard, meant, lang = item
            agent = round(rng.uniform(0.55, 0.7) if meant else rng.uniform(0.8, 0.97), 2)
            agreement = round(rng.uniform(0.4, 0.6) if meant else rng.uniform(0.7, 1.0), 2)
            sound = round(rng.uniform(0.3, 0.5) if meant else rng.uniform(0.6, 0.9), 2)
            score = round(0.5 * agent + 0.25 * agreement + 0.25 * sound, 3)
            action = "speak" if score >= 0.8 and not meant else "check"
            doc = {
                "user_id": uid, "session_id": session_id, "speaker": "user", "sentence": heard, "language": lang,
                "score": {"score": score, "agent_confidence": agent, "candidate_agreement": agreement, "sound_match": sound},
                "threshold": 0.8, "action": action, "attempt": 1 if not meant else 2,
                "status": "approved", "verdict": "helper" if meant else "up", "was_corrected": bool(meant),
                "created_at": at, "feedback_at": at + timedelta(seconds=8),
            }
            if meant:
                doc["final_text"] = meant
                corrected += 1
            await db.utterances.insert_one(doc)
            approved += 1
    return approved, corrected


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audio-dir", type=Path, help="real recordings named {lang}-{phrase_id}.wav (or .webm/.mp3/.m4a)")
    parser.add_argument("--voice", default="chris", help="ElevenLabs voice for generated recordings (default: chris)")
    parser.add_argument("--no-style", action="store_true", help="don't ask Claude for a style profile")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Turkish letters on the Windows console
    if args.audio_dir and not args.audio_dir.is_dir():
        print(f"--audio-dir {args.audio_dir} is not a folder")
        return 1

    s = get_settings()
    await database.connect(s.mongodb_uri, s.mongodb_db)
    try:
        db = database.get_db()
        await db.command("ping")
    except Exception as exc:
        print(f"Cannot reach the database: {exc}")
        return 1

    async for old in db.users.find({"demo": True}):
        removed = await privacy.delete_everything(db, old)
        print(f"removed the previous demo account ({removed['deleted']})")

    now = datetime.now(UTC)
    start = now - timedelta(days=21)
    uid = ObjectId()
    await db.users.insert_one({
        "_id": uid, "name": NAME, "main_language": "both", "threshold": 0.78, "consent": True,
        "consent_at": start, "created_at": start, "demo": True,
        "threshold_history": [{"at": start + timedelta(days=12), "from": 0.80, "to": 0.78,
                               "reason": "9/10 checks got a thumbs-up"}],
    })
    uid = str(uid)
    print(f"created demo user {NAME} ({uid})")

    for word, kind in WORDS:
        await db.personal_words.insert_one({"user_id": uid, "key": word.casefold(), "word": word, "kind": kind,
                                            "created_at": start, "updated_at": start})
    print(f"  {len(WORDS)} names and places")
    samples = await add_enrollment(db, uid, start, args.audio_dir, args.voice)
    print(f"  {samples} enrollment recordings with sound fingerprints")
    approved, corrected = await add_sentences(db, uid, start)
    print(f"  {approved} approved sentences ({corrected} corrected by a helper) in {len(SESSIONS)} conversations")

    if not args.no_style:
        try:
            profile = await style.update_style_profile(db, uid)
            if profile:
                print(f"  style profile: {profile.get('languages')} | {profile.get('typical_length')} | {profile.get('formality')}")
        except Exception as exc:
            print(f"  style profile skipped: {exc}")

    print(f"\nDone. Open {s.frontend_origins[0]}/demo to use the demo account.")
    await database.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
