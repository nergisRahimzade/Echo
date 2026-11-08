"""The learning loop: what happens when a sentence is approved, or a guess is rejected."""

import logging
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.services import embeddings, style
from app.services.audio import AudioError
from app.services.voiceprint import fingerprint_upload
from app.text import normalize

logger = logging.getLogger("echo.learning")

# A sentence Echo spoke on its own counts as right if nobody pressed thumbs-down in time.
# The app confirms after 5 s; this catches the cases where the app closed before it could.
UNANSWERED_SPOKEN_AFTER = timedelta(seconds=10)


async def on_approved(db, utterance: dict) -> None:
    """Called after an utterance is approved (thumbs up, auto-approved, or helper fix).

    The approved sentence becomes a new example:
    - its sound fingerprint (saved at translate time) is used by sound matching right away;
    - a text embedding (when configured) lets similar-sentence search find it by meaning.
    """
    text = utterance.get("final_text") or utterance.get("sentence") or ""
    update: dict = {}
    if text and embeddings.enabled():
        vectors = await embeddings.embed([text], input_type="document")
        if vectors:
            update["text_vector"] = vectors[0]
    if not utterance.get("audio_vector") and utterance.get("audio_path"):
        try:  # older utterance without a fingerprint
            update |= await fingerprint_upload(utterance["audio_path"])
        except (AudioError, FileNotFoundError) as exc:
            logger.warning("Could not fingerprint %s: %s", utterance.get("_id"), exc)
    if update:
        await db.utterances.update_one({"_id": utterance["_id"]}, {"$set": update})
    logger.info("learned utterance %s (%r)", utterance.get("_id"), text[:60])
    if utterance.get("user_id"):
        # Every 10 approvals the style profile is rebuilt in the background.
        await style.maybe_update_in_background(db, utterance["user_id"])


async def relabel_failed_attempts(db, utterance: dict, text: str) -> int:
    """Give the recordings of this message's earlier, rejected attempts the sentence the user
    finally confirmed (thumbs up or a helper fix). Returns how many were relabelled.

    Attempt 1 rejected, attempt 2 confirmed as "Su istiyorum": attempt 1's recording was the user
    trying to say "Su istiyorum" too, so it becomes a second example of how they say it (sound
    matching). It stays "rejected" with its wrong guess, so the progress counts, the threshold
    tuning and "not this" are unchanged. Silent approvals don't relabel: nobody checked them.
    """
    earlier = int(utterance.get("attempt", 1)) - 1
    if earlier < 1 or not text or not utterance.get("session_id"):
        return 0
    cursor = db.utterances.find({
        "user_id": utterance["user_id"],
        "session_id": utterance["session_id"],
        "speaker": {"$ne": "other"},
        "created_at": {"$lt": utterance["created_at"]},
    }).sort("created_at", -1).limit(earlier)
    ids = []
    async for d in cursor:
        if d.get("status") != "rejected" or d.get("final_text"):
            break  # the attempts of this message are the rejected ones right before it
        ids.append(d["_id"])
    if ids:
        await db.utterances.update_many(
            {"_id": {"$in": ids}},
            {"$set": {"final_text": text, "relabelled_from": str(utterance["_id"]), "relabelled_at": datetime.now(UTC)}},
        )
        logger.info("relabelled %d earlier attempt(s) of %s as %r", len(ids), utterance["_id"], text[:60])
    return len(ids)


async def dispute_silent_matches(db, utterance: dict) -> int:
    """A guess was rejected. If it came from sound-matching a sentence that was only approved by
    silence, that example may be a missed mistake: stop learning from it. Returns how many.

    Examples a person confirmed (thumbs up, helper fix) are kept: the new recording may just be a
    different sentence that sounds alike.
    """
    wrong = normalize(utterance.get("sentence") or "")
    if not wrong:
        return 0
    ids = []
    for m in utterance.get("sound_matches") or []:
        if m.get("source") == "utterance" and normalize(m.get("text") or "") == wrong and ObjectId.is_valid(m.get("ref_id") or ""):
            ids.append(ObjectId(m["ref_id"]))
    if not ids:
        return 0
    result = await db.utterances.update_many(
        {"_id": {"$in": ids}, "user_id": utterance["user_id"], "auto_approved": True, "was_corrected": {"$ne": True}},
        {"$set": {"disputed": True, "disputed_by": str(utterance["_id"])}},
    )
    if result.modified_count:
        logger.info("disputed %d silently approved example(s) of %r", result.modified_count, wrong[:60])
    return result.modified_count


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
    if count:
        from app.services import threshold  # local import: threshold <-> learning are siblings

        await threshold.maybe_tune(db, user_id)
    return count
