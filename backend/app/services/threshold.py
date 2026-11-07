"""Per-user threshold tuning: how sure Echo must be before speaking without asking.

After 30 answered sentences, and then every 20, look at the sentences since the last review:
- more than 5% of the sentences Echo spoke on its own got a thumbs-down -> raise by 0.05
  (it is putting words in their mouth too often);
- more than 90% of the checks got a thumbs-up -> lower by 0.05
  (it is asking too often, which costs the user effort and breath).
Always kept between 0.70 and 0.90. If both happen, raising wins: safety first.
"""

import logging
from datetime import UTC, datetime

from bson import ObjectId

from app.config import get_settings

logger = logging.getLogger("echo.threshold")

FIRST_REVIEW_AFTER = 30
REVIEW_EVERY = 20
STEP = 0.05
MIN_T, MAX_T = 0.70, 0.90
MAX_SPOKEN_DOWN_RATE = 0.05
MAX_CHECK_UP_RATE = 0.90


def _answered_query(user_id: str) -> dict:
    return {"user_id": user_id, "speaker": "user", "verdict": {"$exists": True}, "action": {"$in": ["speak", "check"]}}


def decide(current: float, window: list[dict]) -> tuple[float, str | None, dict]:
    """Pure rule: new threshold, reason (None = unchanged) and the stats behind it."""
    spoken = [u for u in window if u["action"] == "speak"]
    checks = [u for u in window if u["action"] == "check"]
    spoken_down = sum(u["verdict"] == "down" for u in spoken)
    checks_up = sum(u["verdict"] == "up" for u in checks)
    stats = {
        "window": len(window),
        "spoken": len(spoken),
        "spoken_down": spoken_down,
        "checks": len(checks),
        "checks_up": checks_up,
    }
    if spoken and spoken_down / len(spoken) > MAX_SPOKEN_DOWN_RATE:
        new, reason = current + STEP, f"{spoken_down}/{len(spoken)} auto-spoken sentences got a thumbs-down"
    elif checks and checks_up / len(checks) > MAX_CHECK_UP_RATE:
        new, reason = current - STEP, f"{checks_up}/{len(checks)} checks got a thumbs-up"
    else:
        return current, None, stats
    new = round(min(MAX_T, max(MIN_T, new)), 2)
    if new == round(current, 2):
        return current, None, stats  # already at the limit
    return new, reason, stats


async def maybe_tune(db, user_id: str) -> float | None:
    """Review the threshold if a review is due. Returns the new threshold if it changed."""
    total = await db.utterances.count_documents(_answered_query(user_id))
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"threshold": 1, "threshold_reviewed_at": 1})
    if not user:
        return None
    reviewed_at = user.get("threshold_reviewed_at", 0)
    due_at = FIRST_REVIEW_AFTER if reviewed_at == 0 else reviewed_at + REVIEW_EVERY
    if total < due_at:
        return None

    window_size = total - reviewed_at  # everything answered since the last review
    cursor = db.utterances.find(_answered_query(user_id), {"action": 1, "verdict": 1}).sort("created_at", -1).limit(window_size)
    window = [d async for d in cursor]
    current = float(user.get("threshold", get_settings().default_threshold))
    new, reason, stats = decide(current, window)

    update: dict = {"threshold_reviewed_at": total}
    if reason:
        update["threshold"] = new
        change = {"at": datetime.now(UTC), "from": current, "to": new, "reason": reason, **stats}
        await db.users.update_one({"_id": user["_id"]}, {"$set": update, "$push": {"threshold_history": change}})
        logger.info("threshold for %s: %.2f -> %.2f (%s)", user_id, current, new, reason)
        return new
    await db.users.update_one({"_id": user["_id"]}, {"$set": update})
    logger.info("threshold for %s stays %.2f after reviewing %d sentences %s", user_id, current, len(window), stats)
    return None
