"""Style profile: how this person likes to talk, summarised by Claude every 10 approvals.

The agent reads it through get_style_profile(), so its sentences sound like the user.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime

import anthropic

from app.agent.run import FALLBACK_BETA, get_client
from app.config import get_settings

logger = logging.getLogger("echo.style")

EVERY_N_APPROVALS = 10
RECENT_SENTENCES = 60

STYLE_SYSTEM = """\
You describe how one person talks, from sentences they actually said (they have cerebral palsy \
or dysarthria; these are the clear versions they approved). Another assistant will use your \
profile to translate their speech in THEIR style, so be concrete and only describe what the \
sentences show. Do not invent traits. Keep each field short.\
"""

STYLE_SCHEMA = {
    "type": "object",
    "properties": {
        "favourite_words": {"type": "array", "items": {"type": "string"}, "description": "Words they use often or distinctively."},
        "common_phrases": {"type": "array", "items": {"type": "string"}, "description": "Phrases they repeat."},
        "typical_length": {"type": "string", "description": "e.g. 'short, 2-5 words'."},
        "formality": {"type": "string", "description": "e.g. 'casual, uses sen not siz'."},
        "humour": {"type": "string", "description": "Any humour or 'none seen'."},
        "languages": {"type": "string", "description": "Languages used and any mixing."},
        "notes": {"type": "string", "description": "Anything else that helps keep their voice."},
    },
    "required": ["favourite_words", "common_phrases", "typical_length", "formality", "humour", "languages", "notes"],
    "additionalProperties": False,
}

_running: set[str] = set()  # users whose profile is being rebuilt right now
_tasks: set[asyncio.Task] = set()  # keep references so background tasks aren't garbage-collected


async def approved_sentences(db, user_id: str, limit: int = RECENT_SENTENCES) -> list[str]:
    cursor = db.utterances.find({"user_id": user_id, "status": "approved"}, {"sentence": 1, "final_text": 1}).sort("created_at", -1).limit(limit)
    return [d.get("final_text") or d.get("sentence") async for d in cursor if d.get("final_text") or d.get("sentence")]


async def summarize_style(sentences: list[str], client: anthropic.AsyncAnthropic | None = None) -> dict:
    """Ask Claude for a style profile of these sentences."""
    s = get_settings()
    client = client or get_client()
    listing = "\n".join(f"- {t}" for t in sentences)
    response = await client.beta.messages.create(
        model=s.agent_model,
        max_tokens=4000,
        system=STYLE_SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": STYLE_SCHEMA}},
        betas=[FALLBACK_BETA],
        fallbacks="default",
        messages=[{"role": "user", "content": f"Sentences this person said (newest first):\n{listing}"}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("style summary declined")
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


async def update_style_profile(db, user_id: str, client: anthropic.AsyncAnthropic | None = None) -> dict | None:
    """Rebuild and save the profile from the latest approved sentences."""
    sentences = await approved_sentences(db, user_id)
    if not sentences:
        return None
    profile = await summarize_style(sentences, client)
    total = await db.utterances.count_documents({"user_id": user_id, "status": "approved"})
    if total == 0:  # the user deleted their data while Claude was summarizing: save nothing
        return None
    doc = {**profile, "user_id": user_id, "based_on": total, "updated_at": datetime.now(UTC)}
    await db.style_profiles.update_one({"user_id": user_id}, {"$set": doc}, upsert=True)
    logger.info("style profile for %s updated from %d approvals", user_id, total)
    return doc


async def due(db, user_id: str) -> bool:
    """True when 10+ approvals have arrived since the profile was last built."""
    total = await db.utterances.count_documents({"user_id": user_id, "status": "approved"})
    profile = await db.style_profiles.find_one({"user_id": user_id}, {"based_on": 1})
    built_on = (profile or {}).get("based_on", 0)
    return total >= EVERY_N_APPROVALS and total - built_on >= EVERY_N_APPROVALS


async def _run(db, user_id: str) -> None:
    try:
        await update_style_profile(db, user_id)
    except Exception as exc:  # never let a background job break the app
        logger.warning("style profile update failed for %s: %s", user_id, exc)
    finally:
        _running.discard(user_id)


async def maybe_update_in_background(db, user_id: str) -> bool:
    """Start a background rebuild when due. Returns True if one was started."""
    if user_id in _running or not await due(db, user_id):
        return False
    _running.add(user_id)
    task = asyncio.create_task(_run(db, user_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True
