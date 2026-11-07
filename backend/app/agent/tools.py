"""Memory tools the agent can call to look things up about the user.

Each tool returns short JSON text. The user and session are fixed by the server (ToolContext),
never chosen by the model, so the agent can only ever read this one person's memory.
"""

import json
import logging
from dataclasses import dataclass

from app.db import aggregate
from app.services import embeddings
from app.text import similarity

logger = logging.getLogger("echo.tools")
VECTOR_INDEX = "utterance_text_vector"


@dataclass
class ToolContext:
    db: object
    user_id: str
    session_id: str | None = None


# ---------- the tools ----------


async def search_similar_sentences(ctx: ToolContext, text: str, limit: int = 5) -> list[dict]:
    """Sentences this person said before (approved) that are closest to `text`."""
    if embeddings.enabled():
        try:
            hits = await _vector_search(ctx, text, limit)
            if hits:
                return hits
        except Exception as exc:  # no Atlas index yet, or not on Atlas
            logger.info("Vector search unavailable (%s); using spelling similarity.", exc)
    return await _lexical_search(ctx, text, limit)


async def get_personal_words(ctx: ToolContext) -> list[dict]:
    cursor = ctx.db.personal_words.find({"user_id": ctx.user_id}, {"word": 1, "kind": 1}).sort("created_at", 1)
    return [{"word": d["word"], "kind": d.get("kind", "other")} async for d in cursor]


async def get_style_profile(ctx: ToolContext) -> dict:
    doc = await ctx.db.style_profiles.find_one({"user_id": ctx.user_id})
    if not doc:
        return {"status": "no style profile yet"}
    return {k: v for k, v in doc.items() if k not in ("_id", "user_id", "updated_at", "based_on")}


async def get_recent_turns(ctx: ToolContext, n: int = 5) -> list[dict]:
    """The last n confirmed turns of this conversation, oldest first."""
    if not ctx.session_id:
        return []
    query = {
        "user_id": ctx.user_id,
        "session_id": ctx.session_id,
        # pending/rejected guesses are not things the user actually said
        "status": {"$in": ["approved", "spoken", "turn"]},
    }
    cursor = ctx.db.utterances.find(query).sort("created_at", -1).limit(n)
    turns = [
        {"speaker": "other person" if d.get("speaker") == "other" else "user", "text": d.get("final_text") or d.get("sentence", "")}
        async for d in cursor
    ]
    return list(reversed(turns))


# ---------- search helpers ----------


async def _known_sentences(ctx: ToolContext) -> dict[str, int]:
    """Every sentence this person is known to say -> how many times."""
    counts: dict[str, int] = {}
    pipeline = [
        {"$match": {"user_id": ctx.user_id, "status": "approved"}},
        {"$group": {"_id": {"$ifNull": ["$final_text", "$sentence"]}, "n": {"$sum": 1}}},
    ]
    for d in await aggregate(ctx.db.utterances, pipeline):
        if d["_id"]:
            counts[d["_id"]] = counts.get(d["_id"], 0) + d["n"]
    async for d in ctx.db.enrollment_samples.find({"user_id": ctx.user_id}, {"text": 1}):
        counts.setdefault(d["text"], 1)
    return counts


async def _lexical_search(ctx: ToolContext, text: str, limit: int) -> list[dict]:
    counts = await _known_sentences(ctx)
    scored = [{"text": t, "score": round(similarity(text, t), 3), "times_said": n} for t, n in counts.items()]
    scored.sort(key=lambda h: (h["score"], h["times_said"]), reverse=True)
    return scored[:limit]


async def _vector_search(ctx: ToolContext, text: str, limit: int) -> list[dict]:
    vectors = await embeddings.embed([text], input_type="query")
    if not vectors:
        return []
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX,
                "path": "text_vector",
                "queryVector": vectors[0],
                "numCandidates": 100,
                "limit": limit * 3,
                "filter": {"user_id": ctx.user_id, "status": "approved"},
            }
        },
        {"$project": {"sentence": 1, "final_text": 1, "score": {"$meta": "vectorSearchScore"}}},
    ]
    best: dict[str, dict] = {}
    for d in await aggregate(ctx.db.utterances, pipeline):
        t = d.get("final_text") or d.get("sentence")
        if not t:
            continue
        if t in best:
            best[t]["times_said"] += 1
        else:
            best[t] = {"text": t, "score": round(float(d["score"]), 3), "times_said": 1}
    return sorted(best.values(), key=lambda h: h["score"], reverse=True)[:limit]


# ---------- definitions for Claude + dispatcher ----------

TOOL_DEFINITIONS = [
    {
        "name": "search_similar_sentences",
        "description": (
            "Find sentences this person said before (confirmed correct) that are closest to a text, "
            "with how often they said each. Use it when the transcripts are garbled and you want to know "
            "whether they match something this person often says."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "A transcript or your best guess."}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_personal_words",
        "description": "Names of this person's family, friends, places and pets.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_style_profile",
        "description": "How this person likes to talk: favourite words, typical length, formality, humour, common phrases.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_recent_turns",
        "description": "The last few things said in this conversation (by the person and the other person), oldest first.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


async def run_tool(ctx: ToolContext, name: str, args: dict) -> str:
    """Run one tool and return its result as compact JSON text."""
    if name == "search_similar_sentences":
        result = await search_similar_sentences(ctx, str(args.get("text", ""))[:300])
    elif name == "get_personal_words":
        result = await get_personal_words(ctx)
    elif name == "get_style_profile":
        result = await get_style_profile(ctx)
    elif name == "get_recent_turns":
        result = await get_recent_turns(ctx)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return json.dumps(result, ensure_ascii=False)
