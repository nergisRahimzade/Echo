"""The learning loop: what happens when a sentence is approved."""

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger("echo.learning")

# A sentence Echo spoke on its own counts as right if nobody pressed thumbs-down in time.
# The app confirms after 5 s; this catches the cases where the app closed before it could.
UNANSWERED_SPOKEN_AFTER = timedelta(seconds=10)


async def on_approved(db, utterance: dict) -> None:
    """Called after an utterance is approved (thumbs up, auto-approved, or helper fix)."""
    logger.info("approved utterance %s", utterance.get("_id"))


async def approve_unanswered_spoken(db, user_id: str) -> int:
    """Approve this user's spoken sentences that never got a thumbs-down. Returns how many."""
    cutoff = datetime.now(UTC) - UNANSWERED_SPOKEN_AFTER
    query = {"user_id": user_id, "status": "spoken", "verdict": {"$exists": False}, "created_at": {"$lt": cutoff}}
    count = 0
    async for utt in db.utterances.find(query):
        update = {"status": "approved", "verdict": "up", "auto_approved": True, "was_corrected": False, "feedback_at": datetime.now(UTC)}
        result = await db.utterances.update_one({"_id": utt["_id"], "status": "spoken"}, {"$set": update})
        if result.modified_count:
            count += 1
            await on_approved(db, {**utt, **update})
    return count
